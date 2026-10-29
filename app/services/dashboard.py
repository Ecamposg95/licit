"""Datos del panel de dirección y del estado operativo (TI).

Regla del panel: los conteos se dan **por tipo de dato** (REAL, HISTORICAL, SYNTHETIC) y jamás se suman entre
tipos. Un escenario simulado con fecha futura no es una oportunidad real, así que `upcoming_real` solo recibe
procedimientos REAL cuyo estado derivado es «abierta verificada».
"""
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core import config
from app.models import (
    DataKind, DemoRun, Job, Opportunity, Requirement, SearchRun, Source, User,
)
from app.services import jobs as jobs_service
from app.services.status import derive_status
from app.services.storage import S3Storage, get_storage

UPCOMING_LIMIT = 10
JOBS_LIMIT = 20
# Requisitos obligatorios que hoy impiden presentar (los mismos que el motor de correspondencia llama «bloqueantes»).
BLOCKING_STATUSES = ("incumple", "faltante", "vencido")


def _aware(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.max.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def direccion(db: Session, org_id: str, now: datetime | None = None) -> dict:
    """Cartera por tipo de dato, próximas oportunidades reales, última búsqueda y escenarios en riesgo."""
    now = now or datetime.now(timezone.utc)
    opportunities = list(db.scalars(select(Opportunity).where(Opportunity.organization_id == org_id)).unique())

    counters: dict[str, Counter] = {kind.value: Counter() for kind in DataKind}
    upcoming: list[Opportunity] = []
    for opp in opportunities:
        state = derive_status(opp, now, config.FRESHNESS_TTL_HOURS).code
        counters.setdefault(opp.data_kind, Counter())[state] += 1
        if opp.data_kind == DataKind.REAL.value and state == "abierta_verificada":
            upcoming.append(opp)
    upcoming.sort(key=lambda o: (_aware(o.submission_at), o.external_id))

    return {
        "by_data_kind": {
            kind: {"total": sum(c.values()), "por_estado": dict(sorted(c.items()))}
            for kind, c in counters.items()
        },
        "upcoming_real": upcoming[:UPCOMING_LIMIT],
        "last_search": db.scalars(
            select(SearchRun).where(SearchRun.organization_id == org_id)
            .order_by(SearchRun.created_at.desc(), SearchRun.id.desc()).limit(1)).first(),
        "scenarios_at_risk": scenarios_at_risk(db, org_id),
    }


def scenarios_at_risk(db: Session, org_id: str) -> list[dict]:
    """Escenarios SYNTHETIC con requisitos obligatorios en incumple, faltante o vencido."""
    rows = db.execute(
        select(Opportunity.id, Opportunity.external_id, Opportunity.title, Requirement.code, Requirement.id)
        .join(Requirement, Requirement.opportunity_id == Opportunity.id)
        .where(Opportunity.organization_id == org_id, Opportunity.data_kind == DataKind.SYNTHETIC.value,
               Requirement.mandatory.is_(True), Requirement.status.in_(BLOCKING_STATUSES))
    )
    grouped: dict[str, dict] = {}
    blocking: dict[str, list[str]] = defaultdict(list)
    for opp_id, external_id, title, code, req_id in rows:
        grouped[opp_id] = {"external_id": external_id, "opportunity_id": opp_id, "title": title,
                           "data_kind": DataKind.SYNTHETIC.value}
        blocking[opp_id].append(code or req_id)
    return [{**grouped[opp_id], "blocking": sorted(blocking[opp_id])}
            for opp_id in sorted(grouped, key=lambda i: grouped[i]["external_id"])]


# ── Estado operativo ─────────────────────────────────────────────────────────

def _alembic_revision(db: Session) -> str | None:
    """Revisión de Alembic aplicada en la base; `None` si el esquema no se creó con Alembic."""
    if not inspect(db.get_bind()).has_table("alembic_version"):
        return None
    revisions = sorted(db.scalars(text("SELECT version_num FROM alembic_version")))
    return ", ".join(revisions) or None


def _storage_backend() -> tuple[str, str | None]:
    try:
        return ("s3" if isinstance(get_storage(), S3Storage) else "local"), None
    except RuntimeError as exc:           # configuración a medias: no se presenta como «local»
        return "invalid", str(exc)


def ops_status(db: Session, org_id: str) -> dict:
    backend, storage_error = _storage_backend()
    demo_run = db.scalars(select(DemoRun).where(DemoRun.organization_id == org_id)
                          .order_by(DemoRun.started_at.desc(), DemoRun.id.desc()).limit(1)).first()
    actor = db.get(User, demo_run.actor_id) if demo_run and demo_run.actor_id else None
    return {
        "version": os.getenv("RAILWAY_GIT_COMMIT_SHA", "local")[:7],
        "alembic_head": _alembic_revision(db),
        "storage_backend": backend,
        "storage_error": storage_error,
        "worker_alive": jobs_service.worker_alive(),
        "sources": list(db.scalars(select(Source).where(Source.organization_id == org_id).order_by(Source.name))),
        "jobs": list(db.scalars(select(Job).where(Job.organization_id == org_id)
                                .order_by(Job.created_at.desc(), Job.id.desc()).limit(JOBS_LIMIT))),
        "demo_run": None if demo_run is None else {
            "id": demo_run.id, "started_at": demo_run.started_at, "actor": actor, "summary": demo_run.summary},
    }
