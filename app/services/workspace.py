"""Expediente de licitación (`BidWorkspace`): aprobaciones que se invalidan con cada cambio de requisito.

Cualquier evidencia vinculada o revisión de un requisito borra las aprobaciones técnica y comercial del
expediente (deben volver a darse sobre los datos actuales), lo marca desactualizado si había alguna y lo regresa
a «preparación» si ya estaba listo para revisión final.
"""
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models import BidWorkspace, Opportunity
from app.models.base import new_id, utcnow
from app.services import audit

PHASE_ANALYSIS = "analisis"
PHASE_PREPARATION = "preparacion"
PHASE_READY = "listo_revision_final"

_APPROVAL_FIELDS = ("technical_approval_by_id", "technical_approval_at",
                    "commercial_approval_by_id", "commercial_approval_at")


def find_workspace(db: Session, opportunity_id: str) -> BidWorkspace | None:
    return db.scalars(select(BidWorkspace).where(BidWorkspace.opportunity_id == opportunity_id)).first()


def get_or_create_workspace(db: Session, opportunity: Opportunity) -> BidWorkspace:
    """El expediente de la oportunidad; se crea si no existe (sin duplicar ante dos solicitudes simultáneas)."""
    ws = find_workspace(db, opportunity.id)
    if ws is not None:
        return ws
    insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    now = utcnow()
    db.execute(insert(BidWorkspace).values(
        id=new_id(), organization_id=opportunity.organization_id, opportunity_id=opportunity.id,
        decision="pendiente", approvals_stale=False, phase=PHASE_ANALYSIS, version=1,
        created_at=now, updated_at=now,
    ).on_conflict_do_nothing(index_elements=["opportunity_id"]))
    return find_workspace(db, opportunity.id)


def on_requirement_change(db: Session, requirement, actor_id: str | None) -> dict | None:
    """Invalida las aprobaciones del expediente tras un cambio en uno de sus requisitos.

    Devuelve lo que cambió en el expediente (para la bitácora del requisito) o `None` si no hay expediente. Si
    había aprobaciones, su anulación queda además como evento propio (`workspace.approvals_invalidated`).
    """
    ws = find_workspace(db, requirement.opportunity_id)
    if ws is None:
        return None
    before = audit.snapshot(ws, [*_APPROVAL_FIELDS, "approvals_stale", "phase"])
    had_approvals = bool(ws.technical_approval_by_id or ws.commercial_approval_by_id)
    was_ready = ws.phase == PHASE_READY
    for f in _APPROVAL_FIELDS:
        setattr(ws, f, None)
    if had_approvals or was_ready:
        ws.approvals_stale = True
    if was_ready:
        ws.phase = PHASE_PREPARATION
    ws.version += 1
    if had_approvals or was_ready:
        audit.record(db, organization_id=ws.organization_id, actor_id=actor_id,
                     action="workspace.approvals_invalidated", resource_type="bid_workspace", resource_id=ws.id,
                     before=before, after={**audit.snapshot(ws, [*_APPROVAL_FIELDS, "approvals_stale", "phase"]),
                                           "requirement_id": requirement.id, "requirement_code": requirement.code})
    return {"workspace_id": ws.id, "approvals_cleared": had_approvals, "approvals_stale": ws.approvals_stale,
            "phase": ws.phase}
