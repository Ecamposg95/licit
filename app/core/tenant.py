"""Aislamiento por organización: todo acceso a un recurso pasa por aquí."""
from typing import TypeVar

from sqlalchemy.orm import Session

from app.core.errors import AppError

M = TypeVar("M")


def get_owned(db: Session, model: type[M], resource_id: str, user, label: str = "Recurso") -> M:
    obj = db.get(model, resource_id)
    # Un recurso de otra organización responde igual que uno inexistente.
    if obj is None or getattr(obj, "organization_id", None) != user.organization_id:
        raise AppError(404, "not_found", f"{label} no encontrado")
    return obj
