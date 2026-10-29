"""API de la búsqueda en vivo (corridas en SIDOF) y de la importación manual de oportunidades."""
import json
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import netguard
from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import Perm, require_permission
from app.core.tenant import get_owned
from app.models import DataKind, Opportunity, SearchRun, Source, User
from app.routers.opportunities import _open_counts, _row
from app.schemas.search import (
    MAX_RANGE_DAYS, MIN_DATE, ManualMetadata, OpportunityImport, SearchRunAccepted, SearchRunCreate, SearchRunOut,
)
from app.schemas.v1 import OpportunityRow
from app.services import audit, search_runs
from app.services.demo_seed import normalize_external_id
from app.sources.base import SourceUnavailable
from app.sources.dates_es import MX
from app.sources.sidof import BASE_URL, cod_nota_from_url, parse_note_response, parse_procedures

router = APIRouter(tags=["búsqueda"])

_SIDOF_DOWN = ("SIDOF no respondió: {reason}. Esto no significa que no exista el procedimiento; "
               "puedes capturarlo manualmente.")


def _source(db: Session, org_id: str, key: str) -> Source:
    source = db.scalars(select(Source).where(Source.organization_id == org_id, Source.key == key)).first()
    if source is None:
        raise AppError(500, "source_missing", f"No existe la fuente {key}; ejecuta el bootstrap")
    return source


# ── Corridas ─────────────────────────────────────────────────────────────────

@router.post("/api/v1/search-runs", status_code=202, response_model=SearchRunAccepted)
def create_search_run(payload: SearchRunCreate,
                      idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=64),
                      db: Session = Depends(get_db),
                      user: User = Depends(require_permission(Perm.SEARCH_RUN))):
    today = datetime.now(MX).date()
    date_to = payload.date_to or today
    date_from = payload.date_from or date(date_to.year, 1, 1)
    if date_from > date_to:
        raise AppError(422, "validation_error", "La fecha inicial es posterior a la final")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise AppError(422, "validation_error", f"El rango no puede pasar de {MAX_RANGE_DAYS} días")
    if date_from < MIN_DATE:
        raise AppError(422, "date_out_of_range",
                       f"La búsqueda empieza el {MIN_DATE:%d-%m-%Y} como mínimo: el robots.txt de SIDOF prohíbe "
                       "consultar notas de 2011 a 2020.")
    run = search_runs.start_search(db, user, payload.terms or [], date_from, date_to, idempotency_key)
    db.commit()
    return SearchRunAccepted(search_run_id=run.id, job_id=run.job_id)


@router.get("/api/v1/search-runs", response_model=list[SearchRunOut])
def list_search_runs(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    runs = db.scalars(select(SearchRun).where(SearchRun.organization_id == user.organization_id)
                      .order_by(SearchRun.created_at.desc(), SearchRun.id.desc()).limit(20))
    return [search_runs.serialize_run(db, r) for r in runs]


@router.get("/api/v1/search-runs/{search_run_id}", response_model=SearchRunOut)
def get_search_run(search_run_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    return search_runs.serialize_run(db, get_owned(db, SearchRun, search_run_id, user, "Búsqueda"))


# ── Importación ──────────────────────────────────────────────────────────────

def _host(url: str) -> str:
    try:
        return (httpx.URL(url.strip()).host or "").lower().rstrip(".")
    except Exception:
        return ""


def _in_domains(host: str, domains: list[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _choose(procs, external_id: str | None):
    if external_id:
        wanted = normalize_external_id(external_id)
        for p in procs:
            if normalize_external_id(p.external_id) == wanted:
                return p
        raise AppError(422, "procedure_not_in_note", f"La nota no trae el procedimiento {external_id}",
                       [{"external_id": p.external_id, "title": p.title} for p in procs])
    if len(procs) == 1:
        return procs[0]
    relevant = [p for p in procs
                if any(search_runs.matches_term(p.title or p.excerpt, t) for t in search_runs.DEFAULT_TERMS)]
    if len(relevant) == 1:
        return relevant[0]
    raise AppError(422, "procedure_choice_required",
                   f"La nota trae {len(procs)} procedimientos; elige cuál importar",
                   [{"external_id": p.external_id, "title": p.title} for p in procs])


def _import_sidof(db: Session, user: User, url: str, external_id: str | None) -> tuple[Opportunity, str]:
    compras = _source(db, user.organization_id, "comprasmx").allowed_domains or ["comprasmx.buengobierno.gob.mx"]
    if _in_domains(_host(url), compras):
        raise AppError(422, "use_manual_capture", "Compras MX bloquea la consulta automatizada; "
                                                  "usa la pestaña «Procedimiento de Compras MX (captura)».")
    sidof = _source(db, user.organization_id, "dof_sidof")
    allowed = sidof.allowed_domains or ["sidof.segob.gob.mx"]
    public = netguard.validate_public_url(url, allowed)
    cod = cod_nota_from_url(public)
    if cod is None:
        raise AppError(422, "url_not_a_note", "La URL no es de una nota de SIDOF "
                                              "(https://sidof.segob.gob.mx/notas/docFuente/{número})")
    # La red va antes de cualquier escritura: la bitácora no queda con un candado abierto durante la descarga.
    try:
        response = netguard.safe_get(f"{BASE_URL}/dof/sidof/notas/nota/{cod}", allowed)
    except AppError as exc:
        if exc.code == "source_unavailable":
            raise AppError(502, "source_unavailable", _SIDOF_DOWN.format(reason=exc.message)) from None
        raise
    if response.status_code != 200:
        raise AppError(502, "source_unavailable", _SIDOF_DOWN.format(reason=f"HTTP {response.status_code}"))
    try:
        note = parse_note_response(json.loads(response.content), cod, datetime.now(timezone.utc))
    except ValueError:
        raise AppError(502, "source_unavailable", _SIDOF_DOWN.format(reason="la nota no llegó en JSON")) from None
    except SourceUnavailable as exc:
        raise AppError(502, "source_unavailable", _SIDOF_DOWN.format(reason=exc.reason)) from None
    procs = parse_procedures(note.html)
    if not procs:
        raise AppError(422, "no_procedures", "La nota no trae ningún número de procedimiento reconocible; "
                                             "captúralo manualmente.")
    proc = _choose(procs, external_id)
    outcome = search_runs.upsert_procedure(db, user.organization_id, proc, note, None, actor_id=user.id)
    opp = db.scalars(select(Opportunity).where(
        Opportunity.organization_id == user.organization_id,
        Opportunity.normalized_id == normalize_external_id(proc.external_id)).order_by(Opportunity.created_at)).first()
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="opportunity.import",
                 resource_type="opportunity", resource_id=opp.id,
                 after={"method": "nota_sidof", "url": note.url, "external_id": proc.external_id,
                        "outcome": outcome, "evidence_sha256": note.sha256})
    return opp, outcome


def _import_metadata(db: Session, user: User, meta: ManualMetadata) -> Opportunity:
    source = _source(db, user.organization_id, "comprasmx")
    url = netguard.validate_public_url(meta.source_url, source.allowed_domains or ["comprasmx.buengobierno.gob.mx"])
    nid = normalize_external_id(meta.external_id)
    if not nid:
        raise AppError(422, "validation_error", "El número de procedimiento no es válido")
    existing = db.scalars(select(Opportunity).where(Opportunity.organization_id == user.organization_id,
                                                    Opportunity.normalized_id == nid)).first()
    if existing is not None:
        raise AppError(409, "duplicate_opportunity", f"Ya existe el procedimiento {existing.external_id}",
                       {"opportunity_id": existing.id})
    submission, assumed = meta.submission_at, False
    if submission is not None:
        if submission.tzinfo is None:
            submission, assumed = submission.replace(tzinfo=MX), True
        submission = submission.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    captured = (f"Capturado manualmente por {user.full_name} el {now.astimezone(MX):%d-%m-%Y %H:%M} "
                "(hora de Ciudad de México). El sistema no consultó Compras MX; confirma bases y fechas ahí.")
    opp = Opportunity(
        organization_id=user.organization_id, external_id=meta.external_id, normalized_id=nid, title=meta.title,
        buyer=meta.buyer, families=search_runs.families_for(meta.title), data_kind=DataKind.REAL.value,
        source_id=source.id, source_url=url, last_checked_at=now, reported_status="importada manualmente",
        verification_status="por_verificar",
        verification_scope="Captura manual de metadatos vistos en Compras MX; el sistema no consultó la fuente.",
        result="desconocido", submission_at=submission, submission_precision="datetime",
        source_timezone="America/Mexico_City" if submission else None, timezone_assumed=assumed,
        requires_human_review=True, notes=" ".join(x for x in (meta.notes, captured) if x),
    )
    db.add(opp)
    db.flush()
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="opportunity.import",
                 resource_type="opportunity", resource_id=opp.id,
                 after={**audit.snapshot(opp, ["external_id", "title", "buyer", "source_url", "submission_at",
                                               "verification_status", "data_kind"]),
                        "method": "captura_comprasmx"})
    return opp


@router.post("/api/v1/opportunities/import", status_code=201, response_model=OpportunityRow)
def import_opportunity(payload: OpportunityImport, response: Response, db: Session = Depends(get_db),
                       user: User = Depends(require_permission(Perm.OPPORTUNITY_IMPORT))):
    """Importa una nota de SIDOF por URL o registra un procedimiento de Compras MX capturado a mano.

    201 si la oportunidad es nueva; 200 si ya existía (se agregó evidencia). `X-Import-Outcome`: new | updated |
    unchanged.
    """
    if payload.metadata is not None:
        opp, outcome = _import_metadata(db, user, payload.metadata), "new"
    else:
        opp, outcome = _import_sidof(db, user, payload.url, payload.external_id)
    db.commit()
    response.status_code = 201 if outcome == "new" else 200
    response.headers["X-Import-Outcome"] = outcome
    counts = _open_counts(db, [opp.id])
    return OpportunityRow(**_row(opp, counts.get(opp.id, 0), datetime.now(timezone.utc)))
