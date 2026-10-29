"""Bitácora de cambios sensibles: actor, acción, recurso, antes, después y correlación."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import correlation_id_var
from app.models import AuditEvent


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def snapshot(obj, fields: list[str]) -> dict:
    return {f: _jsonable(getattr(obj, f)) for f in fields}


def record(db: Session, *, organization_id: str, actor_id: str | None, action: str,
           resource_type: str, resource_id: str | None, before: dict | None = None,
           after: dict | None = None) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before,
        after=after,
        correlation_id=correlation_id_var.get(),
    )
    db.add(event)
    return event
