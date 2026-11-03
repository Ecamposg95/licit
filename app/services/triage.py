"""Clasificación de oportunidades REAL nuevas: Seguir (con responsable) o Descartar (con motivo).

Descartar no borra nada: la oportunidad y su evidencia siguen en el sistema. Cada cambio se audita
como `opportunity.triage` en la misma transacción (el commit lo hace quien llama).
"""
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenant import get_owned
from app.models import DataKind, Opportunity, TriageStatus, User
from app.services import audit

_FIELDS = ["triage_status", "owner_id", "triage_reason"]
REASON_MAX = 500


def apply(db: Session, opp: Opportunity, actor: User, action: Literal["seguir", "descartar"], *,
          owner_id: str | None, reason: str | None) -> None:
    if opp.data_kind != DataKind.REAL.value:
        raise AppError(422, "not_triageable", "Solo se clasifican oportunidades REAL; esta no lo es.")
    target = TriageStatus.SIGUIENDO.value if action == "seguir" else TriageStatus.DESCARTADA.value
    clean_reason = (reason or "").strip()
    if action == "seguir" and not owner_id:
        raise AppError(422, "owner_required", "Para seguir una oportunidad indica quién será el responsable.")
    if action == "descartar" and not clean_reason:
        raise AppError(422, "reason_required", "Para descartar una oportunidad indica el motivo.")
    if opp.triage_status == target:
        raise AppError(422, "triage_unchanged", "La oportunidad ya está en ese estado.")
    owner = get_owned(db, User, owner_id, actor, "Usuario") if action == "seguir" else None

    before = audit.snapshot(opp, _FIELDS)
    opp.triage_status = target
    if action == "seguir":
        opp.owner_id = owner.id
        opp.triage_reason = None
    else:
        opp.triage_reason = clean_reason[:REASON_MAX]
    opp.triage_by_id = actor.id
    opp.triage_at = datetime.now(timezone.utc)
    opp.version += 1
    audit.record(db, organization_id=actor.organization_id, actor_id=actor.id, action="opportunity.triage",
                 resource_type="opportunity", resource_id=opp.id, before=before,
                 after=audit.snapshot(opp, _FIELDS))


def on_owner_assigned(db: Session, opp: Opportunity, actor: User) -> None:
    """Asignar responsable a una oportunidad `nueva` equivale a seguirla."""
    if opp.triage_status != TriageStatus.NUEVA.value or not opp.owner_id:
        return
    before = audit.snapshot(opp, _FIELDS)
    opp.triage_status = TriageStatus.SIGUIENDO.value
    opp.triage_reason = None
    opp.triage_by_id = actor.id
    opp.triage_at = datetime.now(timezone.utc)
    audit.record(db, organization_id=actor.organization_id, actor_id=actor.id, action="opportunity.triage",
                 resource_type="opportunity", resource_id=opp.id, before=before,
                 after={**audit.snapshot(opp, _FIELDS), "via": "asignacion"})
