"""Bitácora de cambios sensibles: actor, acción, recurso, antes, después y correlación.

Cada evento se encadena con el anterior de su organización: `hash` = SHA-256 de `prev_hash` más el
payload canónico. `verify_chain` recalcula la cadena desde las columnas guardadas para detectar
ediciones. En Postgres, además, un trigger hace la tabla de solo inserción.
"""
import copy
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import correlation_id_var
from app.models import AuditEvent
from app.models.base import new_id, utcnow

# Campos que entran al hash, además de created_at (en ISO UTC).
_HASHED = ("organization_id", "actor_id", "action", "resource_type", "resource_id", "before", "after",
           "correlation_id", "demo_run_id")


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def snapshot(obj, fields: list[str]) -> dict:
    return {f: _jsonable(getattr(obj, f)) for f in fields}


def _utc(dt: datetime) -> datetime:
    # SQLite devuelve la fecha sin zona (se guardó en UTC); Postgres la devuelve con zona.
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _payload(values) -> dict:
    data = {f: values[f] for f in _HASHED}
    data["created_at"] = _utc(values["created_at"]).isoformat()
    return data


def compute_event_hash(prev_hash: str | None, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(((prev_hash or "") + canonical).encode("utf-8")).hexdigest()


def record(db: Session, *, organization_id: str, actor_id: str | None, action: str,
           resource_type: str, resource_id: str | None, before: dict | None = None,
           after: dict | None = None) -> AuditEvent:
    from app.services.demo_seed import current_demo_run_id  # demo_seed importa este módulo

    # Lo pendiente en la sesión (eventos previos, una corrida demo nueva) debe verse en las consultas.
    db.flush()
    if db.get_bind().dialect.name == "postgresql":
        # Serializa la cadena de la organización hasta que termine la transacción. Si otra transacción
        # olvidó cerrarse, falla en 5 s (lock_not_available) en lugar de quedarse esperando para siempre.
        db.execute(text("SET LOCAL lock_timeout = '5s'"))
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:org))"), {"org": organization_id})
    last = db.execute(
        select(AuditEvent.hash, AuditEvent.created_at)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(1)
    ).first()
    created_at = utcnow()
    if last is not None:
        # Estrictamente creciente: el orden de la cadena no depende de la resolución del reloj.
        created_at = max(created_at, _utc(last.created_at) + timedelta(microseconds=1))
    values = dict(
        organization_id=organization_id, actor_id=actor_id, action=action, resource_type=resource_type,
        resource_id=resource_id, before=copy.deepcopy(before), after=copy.deepcopy(after),
        correlation_id=correlation_id_var.get(), demo_run_id=current_demo_run_id(db, organization_id),
        created_at=created_at,
    )
    prev_hash = last.hash if last is not None else None
    event = AuditEvent(id=new_id(), prev_hash=prev_hash, hash=compute_event_hash(prev_hash, _payload(values)),
                       **values)
    db.add(event)
    return event


def verify_chain(db: Session, organization_id: str) -> tuple[bool, int, str | None]:
    """(válida, eventos revisados, id del primer evento roto)."""
    columns = [getattr(AuditEvent, f) for f in _HASHED]
    rows = db.execute(
        select(AuditEvent.id, AuditEvent.created_at, AuditEvent.prev_hash, AuditEvent.hash, *columns)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at, AuditEvent.id)
    )
    prev_hash = None
    checked = 0
    for row in rows:
        values = row._mapping
        checked += 1
        if values["prev_hash"] != prev_hash or values["hash"] != compute_event_hash(prev_hash, _payload(values)):
            return False, checked, values["id"]
        prev_hash = values["hash"]
    return True, checked, None
