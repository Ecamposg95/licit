"""Corridas de búsqueda en vivo en SIDOF (trabajo asíncrono `search_run`).

Una corrida busca cada término, conserva solo las notas de la sección de convocatorias, lee cada nota una vez
(aunque la encuentren varios términos), extrae sus procedimientos y deduplica por número normalizado. Cada lectura
queda como evidencia (URL, hora, SHA-256 y un extracto corto). Reglas:

- Nunca se rellena con fixtures: si SIDOF falla, la corrida lo registra (`errors`) y no crea nada para ese término.
- Una respuesta sin `messageCode` es «cero sin confirmar» (`zero_unconfirmed`), nunca «no hay licitaciones».
- Solo se crean procedimientos cuyo objeto coincide con algún término; un aviso de fallo no crea una oportunidad,
  pero sí cierra la que ya existe.
- La bitácora toma un candado por organización hasta el commit: se hace commit después de cada auditoría y antes
  de la siguiente petición a SIDOF.
"""
import copy
import logging
import re
from datetime import date, datetime, timezone
from typing import Callable, Literal, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import DataKind, Job, Opportunity, OpportunityEvidence, SearchRun, SearchRunStatus, Source, User
from app.models.base import utcnow
from app.models.opportunity import SourceStatus
from app.schemas.search import SearchCounts, SearchErrorOut, SearchQueryOut, SearchRunOut, SearchTermOut
from app.schemas.v1 import UserRef
from app.services import audit, jobs
from app.services.demo_seed import normalize_external_id
from app.sources.base import NoteDetail, NoteHit, ProcedureParsed, SourceUnavailable
from app.sources.dates_es import MX, normalize_text
from app.sources.sidof import CV_PREFIX, SOURCE_KEY, SidofClient, parse_procedures

logger = logging.getLogger(__name__)

JOB_KIND = "search_run"
DEFAULT_TERMS = ["osteosintesis", "endoprotesis", "implantes ortopedicos", "material de osteosintesis"]
# Familia que se asigna a un procedimiento real según el término (y los términos que su objeto menciona).
FAMILY_BY_TERM = {
    "osteosintesis": "Osteosíntesis",
    "material de osteosintesis": "Osteosíntesis",
    "endoprotesis": "Endoprótesis",
    "implantes ortopedicos": "Implantes ortopédicos",
}
PAGE_LENGTH = 100
MAX_PAGES_PER_TERM = 10
MAX_NOTES_PER_RUN = 300
ABORT_AFTER_FAILURES = 3
EXCERPT_MAX = 500
MAX_TERMS = 10

Outcome = Literal["new", "updated", "unchanged"]
_COUNT_KEYS = ("notes", "procedures", "new", "updated", "unchanged")
_AUDIT_FIELDS = ["external_id", "title", "buyer", "state", "data_kind", "source_url", "families",
                 "verification_status", "reported_status", "result", "questions_at", "submission_at", "ruling_at"]
_REPORTED = {
    "convocatoria": "Resumen de convocatoria publicado en el DOF",
    "fallo": "Fallo publicado en el DOF",
    "aviso": "Aviso publicado en el DOF",
}
VERIFICATION_SCOPE = "Resumen publicado en el DOF (SIDOF); las bases y la vigencia se confirman en Compras MX."


# ── Términos y familias ──────────────────────────────────────────────────────

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_text(text or ""))


def matches_term(text: str | None, term: str) -> bool:
    """Todas las palabras del término aparecen como palabras completas (sin acentos), como hace SIDOF."""
    words = set(_words(text or ""))
    return bool(words) and all(w in words for w in _words(term))


def families_for(text: str | None, terms: Sequence[str] = ()) -> list[str]:
    found: list[str] = []
    for term in terms:
        fam = FAMILY_BY_TERM.get(" ".join(_words(term)))
        if fam and fam not in found:
            found.append(fam)
    for key, fam in FAMILY_BY_TERM.items():
        if fam not in found and matches_term(text, key):
            found.append(fam)
    return found


def normalize_terms(terms: Sequence[str] | None) -> list[str]:
    """Términos limpios y sin repetir (sin distinguir acentos ni mayúsculas); vacío → DEFAULT_TERMS."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in terms or []:
        term = re.sub(r"\s+", " ", raw or "").strip()
        key = " ".join(_words(term))
        if key and key not in seen:
            seen.add(key)
            out.append(term)
    return out or list(DEFAULT_TERMS)


# ── Inicio ───────────────────────────────────────────────────────────────────

def start_search(db: Session, user: User, terms: list[str], date_from: date, date_to: date,
                 idempotency_key: str | None) -> SearchRun:
    """Crea la corrida en `queued`, encola el trabajo y audita `search.start` (el commit lo hace quien llama).

    Con la misma `Idempotency-Key` devuelve la corrida ya creada: no hay una segunda corrida ni otro evento.
    """
    terms = normalize_terms(terms)
    if len(terms) > MAX_TERMS:
        raise AppError(422, "validation_error", f"Usa como máximo {MAX_TERMS} términos por búsqueda")
    if date_from > date_to:
        raise AppError(422, "validation_error", "La fecha inicial es posterior a la final")
    query = {"terms": terms, "date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
    key = f"{JOB_KIND}:{user.organization_id}:{idempotency_key}" if idempotency_key else None
    job = jobs.enqueue(db, organization_id=user.organization_id, kind=JOB_KIND, payload=dict(query),
                       created_by_id=user.id, idempotency_key=key)
    existing = db.scalars(select(SearchRun).where(SearchRun.job_id == job.id)).first()
    if existing is not None:
        return existing
    run = SearchRun(organization_id=user.organization_id, created_by_id=user.id, query=query,
                    status=SearchRunStatus.QUEUED.value, counts=_empty_counts(terms), errors=[], job_id=job.id)
    db.add(run)
    db.flush()
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="search.start",
                 resource_type="search_run", resource_id=run.id, after={**query, "job_id": job.id})
    return run


def _empty_term(term: str) -> dict:
    return {"term": term, "status": "pendiente", "checked_at": None, "total": None, "notes": 0, "read": 0,
            "skipped_non_cv": 0, "seen_other_term": 0, "procedures": 0, "new": 0, "updated": 0, "unchanged": 0,
            "discarded": 0, "errors": 0}


def _empty_counts(terms: Sequence[str]) -> dict:
    return {**{k: 0 for k in _COUNT_KEYS}, "by_term": [_empty_term(t) for t in terms]}


def summary_counts(counts: dict | None) -> dict:
    """Los cinco conteos del contrato, sin el detalle por término."""
    counts = counts or {}
    return {k: int(counts.get(k) or 0) for k in _COUNT_KEYS}


def serialize_run(db: Session, run: SearchRun) -> SearchRunOut:
    """Contrato público de una corrida (lo usa la API y puede reutilizarlo el panel de dirección)."""
    author = db.get(User, run.created_by_id) if run.created_by_id else None
    return SearchRunOut(
        id=run.id, status=run.status, query=SearchQueryOut(**run.query),
        counts=SearchCounts(**summary_counts(run.counts)),
        terms=[SearchTermOut(**t) for t in (run.counts or {}).get("by_term", [])],
        errors=[SearchErrorOut(**e) for e in (run.errors or [])],
        job_id=run.job_id, created_by=UserRef.model_validate(author) if author else None,
        created_at=run.created_at, started_at=run.started_at, finished_at=run.finished_at,
    )


# ── Alta o actualización de un procedimiento ────────────────────────────────

def _sidof_source(db: Session, org_id: str) -> Source:
    source = db.scalars(select(Source).where(Source.organization_id == org_id, Source.key == SOURCE_KEY)).first()
    if source is None:
        raise AppError(500, "source_missing", "No existe la fuente dof_sidof; ejecuta el bootstrap")
    return source


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _fmt_day(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        dt = _aware(dt).astimezone(MX).date()
    return dt.strftime("%d-%m-%Y")


def _buyer_fallback(note: NoteDetail) -> str:
    if note.title:
        return note.title.split(" - REF")[0].strip()[:255] or "Por verificar"
    return "Por verificar"


def _notes_text(proc: ProcedureParsed, note: NoteDetail) -> str:
    lines = [f"Datos extraídos por reglas de la nota DOF {note.cod_nota}"
             + (f" del {_fmt_day(note.published_on)}" if note.published_on else "")
             + "; los campos que la nota no trae quedan vacíos."]
    if proc.volume:
        lines.append(f"Volumen según la nota: {proc.volume}.")
    if proc.published_at:
        lines.append(f"Publicación en Compras MX según la nota: {_fmt_day(proc.published_at)}.")
    if proc.expediente:
        lines.append(f"Código de expediente en Compras MX: {proc.expediente}.")
    if proc.timezone_assumed:
        lines.append("La nota no indica zona horaria; se supone America/Mexico_City.")
    lines.append("El DOF puede publicar después que Compras MX: reconfirma la vigencia ahí antes de decidir.")
    return " ".join(lines)


def _add_evidence(db: Session, org_id: str, opp: Opportunity, source: Source, note: NoteDetail,
                  proc: ProcedureParsed, run: SearchRun | None) -> None:
    db.add(OpportunityEvidence(
        organization_id=org_id, opportunity_id=opp.id, source_id=source.id, search_run_id=run.id if run else None,
        url=note.url, fetched_at=note.fetched_at, sha256=note.sha256, http_status=note.http_status,
        excerpt=(proc.excerpt or "")[:EXCERPT_MAX] or None,
    ))


def _new_opportunity(org_id: str, nid: str, proc: ProcedureParsed, note: NoteDetail, source: Source,
                     families: list[str]) -> Opportunity:
    has_dates = any((proc.questions_at, proc.submission_at, proc.ruling_at, proc.published_at))
    return Opportunity(
        organization_id=org_id, external_id=proc.external_id[:120], normalized_id=nid,
        title=(proc.title or f"Procedimiento {proc.external_id} (objeto no identificado en la nota)")[:500],
        buyer=(proc.buyer or _buyer_fallback(note))[:255],
        buying_unit=(proc.buying_unit or None) and proc.buying_unit[:255],
        state=proc.state, procedure_type=proc.procedure_type, character=proc.character, families=families,
        data_kind=DataKind.REAL.value, source_id=source.id, source_url=note.url, last_checked_at=note.fetched_at,
        reported_status=_REPORTED.get(proc.notice, _REPORTED["aviso"]),
        verification_status="verificada" if proc.submission_at else "por_verificar",
        verification_scope=VERIFICATION_SCOPE,
        result="fallo publicado" if proc.notice == "fallo" else "desconocido",
        questions_at=proc.questions_at, submission_at=proc.submission_at, ruling_at=proc.ruling_at,
        submission_precision=proc.submission_precision if proc.submission_at else "datetime",
        source_timezone="America/Mexico_City" if has_dates else None, timezone_assumed=proc.timezone_assumed,
        requires_human_review=True, notes=_notes_text(proc, note),
    )


def _apply_update(opp: Opportunity, proc: ProcedureParsed, families: list[str]) -> None:
    """Completa la oportunidad REAL con lo que trae la nota nueva; nunca borra un dato con un vacío."""
    if proc.notice == "fallo":
        opp.result = "fallo publicado"
        opp.reported_status = _REPORTED["fallo"]
        if proc.ruling_at and opp.ruling_at is None:
            opp.ruling_at = proc.ruling_at
    else:
        limits = {"title": 500, "buyer": 255, "buying_unit": 255, "state": 100, "procedure_type": 40, "character": 40}
        for field, limit in limits.items():
            value = getattr(proc, field)
            if value:
                setattr(opp, field, value[:limit])
        for field in ("questions_at", "ruling_at"):
            value = getattr(proc, field)
            if value and _aware(getattr(opp, field)) != value:
                setattr(opp, field, value)
        if proc.submission_at and _aware(opp.submission_at) != proc.submission_at:
            opp.submission_at = proc.submission_at
            opp.submission_precision = proc.submission_precision
            opp.timezone_assumed = proc.timezone_assumed
            opp.source_timezone = "America/Mexico_City"
        if opp.submission_at is not None and opp.verification_status == "por_verificar":
            opp.verification_status = "verificada"
    merged = list(opp.families or []) + [f for f in families if f not in (opp.families or [])]
    if merged != list(opp.families or []):
        opp.families = merged


def upsert_procedure(db: Session, org_id: str, proc: ProcedureParsed, note: NoteDetail, run: SearchRun | None,
                     *, terms: Sequence[str] = (), actor_id: str | None = None) -> Outcome:
    """Crea o actualiza el procedimiento (deduplicado por número normalizado) y agrega su evidencia.

    - Nuevo → oportunidad REAL de `dof_sidof`, auditada como `opportunity.create`.
    - Existente → siempre se agrega la evidencia. Si el SHA-256 de la nota cambió respecto de la última evidencia de
      esa misma nota (o es la primera vez que esa nota respalda la oportunidad) es `updated`; si no, `unchanged`.
      Los registros HISTORICAL o SYNTHETIC solo reciben la evidencia: nunca se convierten en REAL.
    Hace flush, no commit: quien llama hace commit enseguida (candado de la bitácora).
    """
    source = _sidof_source(db, org_id)
    nid = normalize_external_id(proc.external_id)
    if not nid:
        raise ValueError("Procedimiento sin número")
    actor = actor_id or (run.created_by_id if run else None)
    families = families_for(proc.title or proc.excerpt, terms)
    opp = db.scalars(select(Opportunity).where(Opportunity.organization_id == org_id,
                                               Opportunity.normalized_id == nid)
                     .order_by(Opportunity.created_at)).first()
    if opp is None:
        opp = _new_opportunity(org_id, nid, proc, note, source, families)
        db.add(opp)
        db.flush()
        _add_evidence(db, org_id, opp, source, note, proc, run)
        audit.record(db, organization_id=org_id, actor_id=actor, action="opportunity.create",
                     resource_type="opportunity", resource_id=opp.id,
                     after={**audit.snapshot(opp, _AUDIT_FIELDS), "evidence_sha256": note.sha256,
                            "search_run_id": run.id if run else None})
        return "new"

    last = db.scalars(select(OpportunityEvidence)
                      .where(OpportunityEvidence.opportunity_id == opp.id, OpportunityEvidence.url == note.url)
                      .order_by(OpportunityEvidence.fetched_at.desc(), OpportunityEvidence.created_at.desc())
                      ).first()
    changed = last is None or last.sha256 != note.sha256
    _add_evidence(db, org_id, opp, source, note, proc, run)
    if opp.data_kind != DataKind.REAL.value:
        db.flush()
        return "updated" if changed else "unchanged"
    opp.last_checked_at = note.fetched_at
    if not changed:
        db.flush()
        return "unchanged"
    before = audit.snapshot(opp, _AUDIT_FIELDS)
    _apply_update(opp, proc, families)
    after = audit.snapshot(opp, _AUDIT_FIELDS)
    diff = [f for f in _AUDIT_FIELDS if before[f] != after[f]]
    if diff:
        opp.version += 1
        audit.record(db, organization_id=org_id, actor_id=actor, action="opportunity.update",
                     resource_type="opportunity", resource_id=opp.id,
                     before={f: before[f] for f in diff},
                     after={**{f: after[f] for f in diff}, "evidence_sha256": note.sha256})
    db.flush()
    return "updated"


# ── Trabajo ──────────────────────────────────────────────────────────────────

class _State:
    def __init__(self, terms: list[str]):
        self.counts = _empty_counts(terms)
        self.errors: list[dict] = []
        self.responded = 0                  # términos cuya búsqueda obtuvo respuesta de SIDOF

    def term(self, term: str) -> dict:
        return next(t for t in self.counts["by_term"] if t["term"] == term)

    def error(self, term: str | None, code: str, message: str) -> None:
        self.errors.append({"source": SOURCE_KEY, "term": term, "code": code, "message": message})

    def save(self, run: SearchRun) -> None:
        run.counts = copy.deepcopy(self.counts)            # JSON: se reasigna para que se guarde
        run.errors = copy.deepcopy(self.errors)


def _is_convocatoria_section(hit: NoteHit) -> bool:
    return hit.organism is None or normalize_text(hit.organism).startswith(normalize_text(CV_PREFIX))


def _search_term(client, term: str, date_from: date, date_to: date, state: _State) -> tuple[list[NoteHit], int | None, bool]:
    hits: list[NoteHit] = []
    start = 0
    for page_no in range(MAX_PAGES_PER_TERM):
        try:
            page = client.search(term, date_from, date_to, start=start, length=PAGE_LENGTH)
        except SourceUnavailable as exc:
            if page_no == 0:
                raise
            state.error(term, "source_unavailable",
                        f"SIDOF dejó de responder en la página {page_no + 1} de «{term}»: {exc.reason}. "
                        "Los resultados de este término pueden estar incompletos.")
            return hits, None, True
        if not page.confirmed:
            if page_no == 0:
                return [], None, False
            state.error(term, "zero_unconfirmed", f"SIDOF no confirmó la página {page_no + 1} de «{term}»; "
                                                  "los resultados de este término pueden estar incompletos.")
            return hits, None, True
        hits.extend(page.hits)
        total = page.total
        start += PAGE_LENGTH
        if len(page.hits) < PAGE_LENGTH or (total is not None and start >= total):
            return hits, total, True
    state.error(term, "truncated", f"«{term}» tiene más de {MAX_PAGES_PER_TERM * PAGE_LENGTH} notas; "
                                   "solo se leyeron las primeras. Acota el rango de fechas.")
    return hits, total, True


def _opportunity_exists(db: Session, org_id: str, external_id: str) -> bool:
    return db.scalar(select(Opportunity.id).where(Opportunity.organization_id == org_id,
                                                  Opportunity.normalized_id == normalize_external_id(external_id))
                     .limit(1)) is not None


def _execute(db: Session, job: Job, run: SearchRun, client, state: _State) -> None:
    terms = run.query["terms"]
    date_from = date.fromisoformat(run.query["date_from"])
    date_to = date.fromisoformat(run.query["date_to"])

    # 1) Búsqueda de cada término: solo metadatos de las notas.
    hit_terms: dict[str, list[str]] = {}
    hits: dict[str, NoteHit] = {}
    owner: dict[str, str] = {}
    for i, term in enumerate(terms):
        t = state.term(term)
        t["status"] = "buscando"
        try:
            found, total, confirmed = _search_term(client, term, date_from, date_to, state)
        except SourceUnavailable as exc:
            t["status"] = "error"
            t["checked_at"] = utcnow().isoformat()
            t["errors"] += 1
            state.error(term, "source_unavailable", f"SIDOF no respondió al buscar «{term}»: {exc.reason}")
        else:
            state.responded += 1
            t["checked_at"] = utcnow().isoformat()
            t["total"] = total
            if not confirmed:
                t["status"] = "unconfirmed"
                state.error(term, "zero_unconfirmed",
                            f"Sin resultados confirmados para «{term}»: la respuesta de SIDOF no traía messageCode.")
            else:
                t["status"] = "buscado"
            for hit in found:
                if not _is_convocatoria_section(hit):
                    t["skipped_non_cv"] += 1
                elif hit.cod_nota in hit_terms:
                    if term not in hit_terms[hit.cod_nota]:
                        hit_terms[hit.cod_nota].append(term)
                        t["seen_other_term"] += 1
                else:
                    hit_terms[hit.cod_nota] = [term]
                    hits[hit.cod_nota] = hit
                    owner[hit.cod_nota] = term
                    t["notes"] += 1
        state.save(run)
        jobs.set_progress(db, job, 2 + int(8 * (i + 1) / len(terms)), f"Búsqueda de «{term}» terminada")

    # 2) Lectura de cada nota (la más antigua primero, para que una convocatoria preceda a su fallo).
    queue = sorted(hits, key=lambda c: (hits[c].published_on or date.max, int(c)))
    if len(queue) > MAX_NOTES_PER_RUN:
        state.error(None, "truncated", f"Se encontraron {len(queue)} notas; solo se leen las primeras "
                                       f"{MAX_NOTES_PER_RUN}. Acota el rango de fechas o los términos.")
        queue = queue[:MAX_NOTES_PER_RUN]
    failures = 0
    for i, cod in enumerate(queue):
        term = owner[cod]
        t = state.term(term)
        t["status"] = "leyendo"
        try:
            note = client.get_note(cod)
        except SourceUnavailable as exc:
            t["errors"] += 1
            state.error(term, "source_unavailable", f"No se pudo leer la nota {cod}: {exc.reason}")
            failures = failures + 1 if exc.retryable else 0
            if failures >= ABORT_AFTER_FAILURES:
                left = len(queue) - i - 1
                state.error(None, "aborted", f"Se detuvo la lectura tras {ABORT_AFTER_FAILURES} fallos seguidos de "
                                             f"SIDOF; {left} notas quedaron sin leer.")
                state.save(run)
                db.commit()
                break
        else:
            failures = 0
            t["read"] += 1
            state.counts["notes"] += 1
            for proc in parse_procedures(note.html):
                relevant = any(matches_term(proc.title or proc.excerpt, x) for x in hit_terms[cod])
                if not relevant or (proc.notice == "fallo"
                                    and not _opportunity_exists(db, run.organization_id, proc.external_id)):
                    t["discarded"] += 1
                    continue
                outcome = upsert_procedure(db, run.organization_id, proc, note, run, terms=hit_terms[cod])
                state.counts["procedures"] += 1
                state.counts[outcome] += 1
                t["procedures"] += 1
                t[outcome] += 1
                state.save(run)
                db.commit()                 # libera el candado de la bitácora antes de la siguiente petición
        if all(owner[c] != term for c in queue[i + 1:]):
            t["status"] = "terminado" if t["status"] != "unconfirmed" else t["status"]
        state.save(run)
        jobs.set_progress(db, job, 10 + int(88 * (i + 1) / len(queue)), f"Nota {i + 1} de {len(queue)} · «{term}»")
    for t in state.counts["by_term"]:
        if t["status"] in ("buscado", "leyendo"):
            t["status"] = "terminado"


def _finish(db: Session, run: SearchRun, state: _State) -> dict:
    if state.responded == 0:
        status = SearchRunStatus.FAILED.value
    elif state.errors:
        status = SearchRunStatus.PARTIAL.value
    else:
        status = SearchRunStatus.DONE.value
    now = utcnow()
    state.save(run)
    run.status = status
    run.finished_at = now
    source = _sidof_source(db, run.organization_id)
    source.status = SourceStatus.INACCESIBLE.value if status == SearchRunStatus.FAILED.value \
        else SourceStatus.ACTIVA.value
    source.last_checked_at = now
    source.last_error = state.errors[0]["message"][:2000] if state.errors else None
    audit.record(db, organization_id=run.organization_id, actor_id=run.created_by_id, action="search.finish",
                 resource_type="search_run", resource_id=run.id,
                 after={"status": status, "counts": summary_counts(state.counts),
                        "errors": [e["code"] for e in state.errors]})
    db.commit()
    return {"search_run_id": run.id, "status": status, "counts": summary_counts(state.counts),
            "errors": copy.deepcopy(state.errors)}


def run_search_job(db: Session, job: Job, client_factory: Callable[[], object] = SidofClient) -> dict:
    """Handler del trabajo `search_run`. Recibe la sesión del worker y hace commit de cada avance."""
    run = db.scalars(select(SearchRun).where(SearchRun.job_id == job.id,
                                             SearchRun.organization_id == job.organization_id)).first()
    if run is None:
        raise LookupError(f"El trabajo {job.id} no tiene corrida de búsqueda")
    run_id = run.id
    state = _State(run.query["terms"])
    run.status = SearchRunStatus.RUNNING.value
    run.started_at = utcnow()
    state.save(run)
    jobs.set_progress(db, job, 1, "Consultando SIDOF…")
    try:
        client = client_factory()
        try:
            _execute(db, job, run, client, state)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
        return _finish(db, run, state)
    except Exception as exc:
        db.rollback()
        logger.exception("La corrida de búsqueda %s falló", run_id)
        run = db.get(SearchRun, run_id)
        state.error(None, "internal_error", f"La corrida se detuvo por un error interno ({type(exc).__name__}).")
        state.save(run)
        run.status = SearchRunStatus.FAILED.value
        run.finished_at = utcnow()
        db.commit()
        raise


def _handler(db: Session, job: Job) -> dict:
    # Se resuelve en cada llamada para poder sustituir el cliente en pruebas.
    return run_search_job(db, job, client_factory=SidofClient)


jobs.register(JOB_KIND, _handler)
