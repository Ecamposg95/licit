import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import declared_attr


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DataKind(str, enum.Enum):
    """Procedencia del dato. Independiente del estado del procedimiento."""
    REAL = "REAL"
    HISTORICAL = "HISTORICAL"
    SYNTHETIC = "SYNTHETIC"


class OrgScoped:
    """UUID, organización y marcas de tiempo para todo recurso de negocio."""

    id = Column(String(36), primary_key=True, default=new_id)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    @declared_attr
    def organization_id(cls):
        return Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
