"""Cola de trabajos asíncronos en la base de datos (tabla `jobs`).

Un hilo del servicio web toma los trabajos con `FOR UPDATE SKIP LOCKED` y ejecuta el handler
registrado para su `kind`. Los módulos que definen handlers los registran al importarse con
`register(kind, handler)`; el handler recibe la sesión y el trabajo y devuelve el resultado (dict) o None.
"""
import logging
import threading
from datetime import timedelta
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import Job, JobStatus
from app.models.base import utcnow

logger = logging.getLogger(__name__)

Handler = Callable[[Session, Job], dict | None]
_HANDLERS: dict[str, Handler] = {}

_STOP_TIMEOUT_SECONDS = 10.0
STALE_ERROR = "Interrumpido: el proceso se reinició antes de terminar"
_stop = threading.Event()          # señal de paro del hilo vigente; cada hilo nuevo recibe la suya
_thread: threading.Thread | None = None


def register(kind: str, handler: Handler) -> None:
    _HANDLERS[kind] = handler


def _by_key(db: Session, key: str) -> Job | None:
    return db.scalars(select(Job).where(Job.idempotency_key == key)).first()


def enqueue(db: Session, *, organization_id: str, kind: str, payload: dict, created_by_id: str | None,
            idempotency_key: str | None = None) -> Job:
    """Crea el trabajo en `queued` dentro de la transacción del llamador (que hace el commit).

    Con la misma `idempotency_key` devuelve el trabajo existente, también ante dos solicitudes
    simultáneas (doble clic): el INSERT ... ON CONFLICT DO NOTHING no duplica ni rompe la transacción.
    """
    if idempotency_key is None:
        job = Job(organization_id=organization_id, kind=kind, payload=payload, created_by_id=created_by_id)
        db.add(job)
        db.flush()
        return job

    job = _by_key(db, idempotency_key)
    if job is None:
        insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
        db.execute(insert(Job).values(
            organization_id=organization_id, kind=kind, payload=payload, created_by_id=created_by_id,
            idempotency_key=idempotency_key,
        ).on_conflict_do_nothing(index_elements=["idempotency_key"]))
        job = _by_key(db, idempotency_key)
    if job.organization_id != organization_id or job.kind != kind:
        raise AppError(409, "idempotency_conflict", "La clave de idempotencia ya se usó para otro trabajo")
    return job


def set_progress(db: Session, job: Job, progress: int, message: str) -> None:
    """Actualiza el avance y hace commit de inmediato para que el polling lo vea."""
    job.progress = max(0, min(100, int(progress)))
    job.message = message
    db.commit()


def run_pending_once(db: Session) -> Job | None:
    """Toma el trabajo en cola más antiguo, lo ejecuta y lo deja en `done` o `failed`."""
    job = db.scalars(
        select(Job).where(Job.status == JobStatus.QUEUED.value)
        .order_by(Job.created_at, Job.id).limit(1).with_for_update(skip_locked=True)
    ).first()
    if job is None:
        db.rollback()
        return None
    job.status = JobStatus.RUNNING.value
    job.started_at = utcnow()
    job.attempts += 1
    db.commit()

    try:
        handler = _HANDLERS.get(job.kind)
        if handler is None:
            raise LookupError(f"No hay handler registrado para el tipo de trabajo «{job.kind}»")
        result = handler(db, job)
        job.status = JobStatus.DONE.value
        job.result = result
        job.progress = 100
        job.finished_at = utcnow()
        db.commit()
    except Exception as exc:
        # Lo que el handler dejó sin commit se descarta; el trabajo queda fallido con el motivo.
        db.rollback()
        logger.exception("El trabajo %s (%s) falló", job.id, job.kind)
        job.status = JobStatus.FAILED.value
        job.error = f"{type(exc).__name__}: {exc}"
        job.finished_at = utcnow()
        db.commit()
    return job


def recover_stale_jobs(db: Session, older_than: timedelta = timedelta(minutes=10)) -> int:
    """Marca como `failed` los trabajos `running` iniciados hace más de `older_than` y devuelve cuántos.

    Un trabajo que sigue en `running` cuando arranca el worker quedó huérfano: el proceso que lo
    ejecutaba se reinició (deploy, caída). Hace commit.
    """
    now = utcnow()
    result = db.execute(
        update(Job)
        .where(Job.status == JobStatus.RUNNING.value, Job.started_at < now - older_than)
        .values(status=JobStatus.FAILED.value, error=STALE_ERROR, finished_at=now)
        .execution_options(synchronize_session=False)      # el commit expira lo que la sesión tenga cargado
    )
    db.commit()
    return result.rowcount


def _loop(poll_seconds: float, stop: threading.Event) -> None:
    while not stop.is_set():
        db = SessionLocal()
        try:
            job = run_pending_once(db)
        except Exception:
            logger.exception("Error del worker de trabajos")
            job = None
        finally:
            db.close()
        if job is None:
            stop.wait(poll_seconds)


def start_worker(poll_seconds: float = 1.0) -> threading.Thread:
    global _thread, _stop
    if _thread is not None and _thread.is_alive():
        if not _stop.is_set():
            return _thread
        # `stop_worker` agotó su espera y el hilo sigue en un handler: se le da un margen para
        # terminar y, si no termina, se reemplaza. Conserva su propia señal de paro, así que sale
        # en cuanto el handler vuelva y no compite con el hilo nuevo.
        _thread.join(timeout=_STOP_TIMEOUT_SECONDS)
    if _thread is None or not _thread.is_alive():
        # Con un hilo anterior aún dentro de un handler, su trabajo `running` no está huérfano.
        _recover_at_startup()
    _stop = threading.Event()
    _thread = threading.Thread(target=_loop, args=(poll_seconds, _stop), name="jobs-worker", daemon=True)
    _thread.start()
    return _thread


def _recover_at_startup() -> None:
    db = SessionLocal()
    try:
        recovered = recover_stale_jobs(db)
        if recovered:
            logger.warning("%d trabajo(s) interrumpido(s) por un reinicio quedaron como fallidos", recovered)
    except Exception:
        logger.exception("No se pudieron recuperar los trabajos interrumpidos")
    finally:
        db.close()


def stop_worker() -> None:
    """Pide al worker que termine y espera al trabajo en curso (hasta 10 s)."""
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=_STOP_TIMEOUT_SECONDS)
        if not _thread.is_alive():
            _thread = None


def worker_alive() -> bool:
    return _thread is not None and _thread.is_alive()
