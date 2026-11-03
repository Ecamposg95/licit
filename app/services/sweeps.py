"""Barrido diario automático en SIDOF (trabajo `daily_sweep`, T17) y «Volver a barrer».

El worker encola un barrido por organización a partir de `DAILY_SWEEP_HOUR` (hora de Ciudad de México) si no existe el
del día. Un barrido busca los términos del diccionario más los de las búsquedas guardadas (tope `MAX_SWEEP_TERMS`) en
los últimos `WINDOW_DAYS` días de publicación, en lotes de `search_runs.MAX_TERMS`: cada lote es un `SearchRun` con
`sweep_id`. Reglas:

- El barrido diario corre sin actor («Sistema»); el manual lleva a quien lo pidió.
- Estado: `done` si todos los lotes quedan `done`, `failed` si todos fallan, `partial` en cualquier otra mezcla.
- Un barrido diario `failed` se reintenta cada `RETRY_AFTER` hasta `MAX_DAILY_ATTEMPTS` intentos en el día. Uno que el
  reinicio dejó a medias (su trabajo quedó `failed`) se marca `failed` con `interrupted` y entra al mismo reintento.
- Nunca se rellena nada: un lote caído queda registrado en `errors` con su número de lote.
"""
import copy
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.models import (
    Job, JobStatus, Organization, SavedSearch, SearchRun, SearchRunStatus, Sweep, SweepStatus, User,
)
from app.models.base import utcnow
from app.schemas.sweep import SweepOut
from app.schemas.v1 import UserRef
from app.services import audit, jobs, search_runs
from app.sources.dates_es import MX
from app.sources.sidof import SOURCE_KEY, SidofClient

logger = logging.getLogger(__name__)

JOB_KIND = "daily_sweep"
MAX_SWEEP_TERMS = 30
WINDOW_DAYS = 7
RETRY_AFTER = timedelta(hours=1)
MAX_DAILY_ATTEMPTS = 3
TICK_EVERY = timedelta(seconds=60)

_COUNT_KEYS = ("notes", "procedures", "new", "updated", "unchanged")
_OPEN = (SweepStatus.QUEUED.value, SweepStatus.RUNNING.value)
_last_tick: datetime | None = None          # marca en memoria del último `tick` que llamó a `schedule_due`


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ── Términos y estado ────────────────────────────────────────────────────────

def compose_terms(db: Session, org_id: str) -> tuple[list[str], list[str]]:
    """`(términos, descartados)`: el diccionario primero y luego los de las búsquedas guardadas por uso (desempate
    alfabético), sin repetir (sin acentos ni mayúsculas), con tope `MAX_SWEEP_TERMS`."""
    terms = list(search_runs.DEFAULT_TERMS)
    seen = {search_runs.term_key(t) for t in terms}
    uses: Counter[str] = Counter()
    label: dict[str, str] = {}
    saved = db.scalars(select(SavedSearch).where(SavedSearch.organization_id == org_id)
                       .order_by(SavedSearch.created_at, SavedSearch.id))
    for ss in saved:
        for term in search_runs.normalize_terms(ss.terms, default=False):
            key = search_runs.term_key(term)
            if key in seen:
                continue
            uses[key] += 1
            label.setdefault(key, term)
    for key in sorted(uses, key=lambda k: (-uses[k], k)):
        terms.append(label[key])
    return terms[:MAX_SWEEP_TERMS], terms[MAX_SWEEP_TERMS:]


def aggregate_status(statuses: list[str]) -> str:
    if statuses and all(s == SearchRunStatus.DONE.value for s in statuses):
        return SweepStatus.DONE.value
    if not statuses or all(s == SearchRunStatus.FAILED.value for s in statuses):
        return SweepStatus.FAILED.value
    return SweepStatus.PARTIAL.value


def latest(db: Session, org_id: str) -> Sweep | None:
    return db.scalars(select(Sweep).where(Sweep.organization_id == org_id)
                      .order_by(Sweep.created_at.desc(), Sweep.id.desc()).limit(1)).first()


def _daily_today(db: Session, org_id: str, day) -> list[Sweep]:
    return list(db.scalars(select(Sweep).where(Sweep.organization_id == org_id, Sweep.trigger == "daily",
                                               Sweep.day == day).order_by(Sweep.attempt)))


def _due_now(now: datetime) -> bool:
    return bool(config.DAILY_SWEEP) and now.astimezone(MX).hour >= config.DAILY_SWEEP_HOUR


def today_state(db: Session, org_id: str, now: datetime) -> dict:
    """`last`: el barrido más reciente (diario o manual). `scheduled_pending`: ya pasó la hora, el barrido diario está
    activo y el de hoy todavía no existe (ni en curso ni terminado)."""
    pending = _due_now(now) and not _daily_today(db, org_id, now.astimezone(MX).date())
    return {"last": latest(db, org_id), "scheduled_pending": pending}


# ── Programación ─────────────────────────────────────────────────────────────

def _sync_interrupted(db: Session, org_id: str, now: datetime) -> None:
    """Un barrido en cola o en curso cuyo trabajo ya quedó `failed` (reinicio del proceso) pasa a `failed`."""
    stale = db.execute(select(Sweep).join(Job, Job.id == Sweep.job_id)
                       .where(Sweep.organization_id == org_id, Sweep.status.in_(_OPEN),
                              Job.status == JobStatus.FAILED.value)).scalars().all()
    for sweep in stale:
        before = sweep.status
        sweep.status = SweepStatus.FAILED.value
        sweep.errors = [{"batch": None, "code": "interrupted", "message": jobs.STALE_ERROR}]
        sweep.finished_at = now
        audit.record(db, organization_id=org_id, actor_id=None, action="sweep.finish", resource_type="sweep",
                     resource_id=sweep.id, before={"status": before},
                     after={"status": sweep.status, "errors": ["interrupted"]})


def _enqueue_sweep(db: Session, org_id: str, *, day, attempt: int, trigger: str, user_id: str | None,
                   key: str | None) -> Sweep:
    job = jobs.enqueue(db, organization_id=org_id, kind=JOB_KIND, payload={"trigger": trigger, "day": day.isoformat(),
                                                                         "attempt": attempt},
                       created_by_id=user_id, idempotency_key=key)
    existing = db.scalars(select(Sweep).where(Sweep.job_id == job.id)).first()
    if existing is not None:
        return existing
    sweep = Sweep(organization_id=org_id, day=day, attempt=attempt, trigger=trigger,
                  status=SweepStatus.QUEUED.value, terms=[], dropped_terms=[], counts={}, errors=[],
                  job_id=job.id, created_by_id=user_id)
    db.add(sweep)
    db.flush()
    audit.record(db, organization_id=org_id, actor_id=user_id, action="sweep.start", resource_type="sweep",
                 resource_id=sweep.id, after={"day": day.isoformat(), "attempt": attempt, "trigger": trigger,
                                              "job_id": job.id})
    return sweep


def schedule_due(db: Session, now: datetime) -> list[Sweep]:
    """Encola el barrido diario que toque en cada organización (primer intento o reintento) y hace commit.

    Los barridos interrumpidos (diarios o manuales) se sincronizan siempre, aunque el barrido diario esté apagado o
    no sea la hora todavía.
    """
    due = _due_now(now)
    now = now.astimezone(timezone.utc)
    day = now.astimezone(MX).date()
    created: list[Sweep] = []
    for org_id in db.scalars(select(Organization.id).order_by(Organization.id)).all():
        _sync_interrupted(db, org_id, now)
        db.flush()
        if not due:
            continue
        today = _daily_today(db, org_id, day)
        last = today[-1] if today else None
        if last is None:
            attempt = 1
        elif (last.status == SweepStatus.FAILED.value and last.attempt < MAX_DAILY_ATTEMPTS
              and last.finished_at is not None and now - _aware(last.finished_at) >= RETRY_AFTER):
            attempt = last.attempt + 1
        else:
            continue
        created.append(_enqueue_sweep(db, org_id, day=day, attempt=attempt, trigger="daily", user_id=None,
                                      key=f"{JOB_KIND}:{org_id}:{day.isoformat()}:{attempt}"))
    db.commit()
    return created


def tick(db: Session, now: datetime) -> None:
    """Gancho del worker: llama a `schedule_due` como mucho cada `TICK_EVERY`."""
    global _last_tick
    if _last_tick is not None and now - _last_tick < TICK_EVERY:
        return
    _last_tick = now
    schedule_due(db, now)


def start_manual(db: Session, user: User, idempotency_key: str | None) -> Sweep:
    """«Volver a barrer»: encola un barrido con el actor y audita `sweep.start` (el commit lo hace quien llama)."""
    key = f"{JOB_KIND}:{user.organization_id}:manual:{idempotency_key}" if idempotency_key else None
    return _enqueue_sweep(db, user.organization_id, day=datetime.now(MX).date(), attempt=0, trigger="manual",
                          user_id=user.id, key=key)


# ── Trabajo ──────────────────────────────────────────────────────────────────

def _batch(db: Session, job: Job, sweep: Sweep, number: int, terms: list[str], date_from, date_to,
           client_factory: Callable[[], object]) -> tuple[str, dict, list[dict]]:
    query = {"terms": terms, "date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
    run = SearchRun(organization_id=sweep.organization_id, created_by_id=sweep.created_by_id, query=query,
                    status=SearchRunStatus.QUEUED.value, counts=search_runs._empty_counts(terms), errors=[],
                    job_id=job.id, sweep_id=sweep.id)
    db.add(run)
    db.flush()
    run_id = run.id
    audit.record(db, organization_id=sweep.organization_id, actor_id=sweep.created_by_id, action="search.start",
                 resource_type="search_run", resource_id=run_id,
                 after={**query, "job_id": job.id, "sweep_id": sweep.id, "batch": number})
    db.commit()
    try:
        result = search_runs.execute_run(db, job, run, client_factory)
    except Exception as exc:
        db.rollback()
        logger.exception("El lote %d del barrido %s falló", number, sweep.id)
        message = f"El lote se detuvo por un error interno ({type(exc).__name__})."
        run = db.get(SearchRun, run_id)
        if run.status not in (SearchRunStatus.DONE.value, SearchRunStatus.PARTIAL.value,
                              SearchRunStatus.FAILED.value):
            # Falló antes del manejo de errores de la corrida: no se deja en cola ni en curso para siempre.
            run.status = SearchRunStatus.FAILED.value
            run.finished_at = utcnow()
            run.errors = list(run.errors or []) + [
                {"source": SOURCE_KEY, "term": None, "code": "internal_error", "message": message}]
            db.commit()
        return run.status, search_runs.summary_counts(run.counts), [
            {"batch": number, "term": None, "code": "internal_error", "message": message}]
    errors = [{"batch": number, "term": e.get("term"), "code": e["code"], "message": e["message"]}
              for e in result["errors"]]
    return result["status"], result["counts"], errors


def run_sweep_job(db: Session, job: Job, client_factory: Callable[[], object] = SidofClient) -> dict:
    """Handler del trabajo `daily_sweep`: corre los lotes uno tras otro y agrega su resultado."""
    sweep = db.scalars(select(Sweep).where(Sweep.job_id == job.id,
                                           Sweep.organization_id == job.organization_id)).first()
    if sweep is None:
        raise LookupError(f"El trabajo {job.id} no tiene barrido")
    sweep_id = sweep.id
    try:
        terms, dropped = compose_terms(db, sweep.organization_id)
        sweep.terms, sweep.dropped_terms = terms, dropped
        sweep.status = SweepStatus.RUNNING.value
        sweep.started_at = utcnow()
        db.commit()

        date_to = sweep.day
        date_from = date_to - timedelta(days=WINDOW_DAYS - 1)
        statuses: list[str] = []
        counts = {k: 0 for k in _COUNT_KEYS}
        errors: list[dict] = []
        size = search_runs.MAX_TERMS
        for number, start in enumerate(range(0, len(terms), size), start=1):
            status, batch_counts, batch_errors = _batch(db, job, sweep, number, terms[start:start + size],
                                                        date_from, date_to, client_factory)
            statuses.append(status)
            for k in _COUNT_KEYS:
                counts[k] += int(batch_counts.get(k) or 0)
            errors.extend(batch_errors)
            sweep = db.get(Sweep, sweep_id)

        status = aggregate_status(statuses)
        sweep.status = status
        sweep.counts = counts
        sweep.errors = copy.deepcopy(errors)
        sweep.finished_at = utcnow()
        audit.record(db, organization_id=sweep.organization_id, actor_id=sweep.created_by_id, action="sweep.finish",
                     resource_type="sweep", resource_id=sweep_id,
                     after={"status": status, "counts": counts, "batches": len(statuses),
                            "dropped_terms": len(dropped), "errors": [e["code"] for e in errors]})
        db.commit()
        return {"sweep_id": sweep_id, "status": status, "counts": counts, "errors": copy.deepcopy(errors)}
    except Exception as exc:
        db.rollback()
        logger.exception("El barrido %s falló", sweep_id)
        sweep = db.get(Sweep, sweep_id)
        sweep.status = SweepStatus.FAILED.value
        sweep.errors = list(sweep.errors or []) + [
            {"batch": None, "code": "internal_error",
             "message": f"El barrido se detuvo por un error interno ({type(exc).__name__})."}]
        sweep.finished_at = utcnow()
        audit.record(db, organization_id=sweep.organization_id, actor_id=sweep.created_by_id, action="sweep.finish",
                     resource_type="sweep", resource_id=sweep_id,
                     after={"status": sweep.status, "errors": [e["code"] for e in sweep.errors]})
        db.commit()
        raise


def serialize(db: Session, sweep: Sweep) -> SweepOut:
    author = db.get(User, sweep.created_by_id) if sweep.created_by_id else None
    return SweepOut(
        id=sweep.id, day=sweep.day, attempt=sweep.attempt, trigger=sweep.trigger, status=sweep.status,
        terms=list(sweep.terms or []), dropped_terms=list(sweep.dropped_terms or []),
        counts=search_runs.summary_counts(sweep.counts), errors=list(sweep.errors or []),
        created_by=UserRef.model_validate(author) if author else None,
        started_at=sweep.started_at, finished_at=sweep.finished_at,
    )


def _handler(db: Session, job: Job) -> dict:
    # Se resuelve en cada llamada para poder sustituir el cliente en pruebas.
    return run_sweep_job(db, job, client_factory=SidofClient)


jobs.register(JOB_KIND, _handler)
jobs.register_tick(tick)
