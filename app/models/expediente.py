"""Documentos, requisitos, evidencia, tareas y auditoría."""
import enum

from sqlalchemy import (
    DDL, JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, event,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import OrgScoped, new_id, utcnow


class Document(OrgScoped, Base):
    __tablename__ = "documents"

    code = Column(String(60), index=True)
    title = Column(String(500), nullable=False)
    scope = Column(String(20), nullable=False)            # empresa | producto | expediente
    doc_type = Column(String(60))
    issuer_declared = Column(String(255))
    valid_until = Column(Date)
    owner_id = Column(String(36), ForeignKey("users.id"))
    review_status = Column(String(20), nullable=False, default="pendiente")
    data_kind = Column(String(12), nullable=False, index=True)
    watermark = Column(String(255))
    product_id = Column(String(36), ForeignKey("products.id"))
    opportunity_id = Column(String(36), ForeignKey("opportunities.id"))
    current_version = Column(Integer, nullable=False, default=1)
    external_url = Column(String(1000))
    third_party = Column(Boolean, nullable=False, default=False)   # documento de tercero: sólo se enlaza
    page_count = Column(Integer)

    owner = relationship("User", lazy="joined")
    versions = relationship("DocumentVersion", cascade="all, delete-orphan",
                            order_by="DocumentVersion.version", lazy="selectin")


class DocumentVersion(OrgScoped, Base):
    __tablename__ = "document_versions"

    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    filename = Column(String(255))
    content_type = Column(String(120))
    size_bytes = Column(Integer)
    sha256 = Column(String(64))
    storage_key = Column(String(500))
    uploaded_by_id = Column(String(36), ForeignKey("users.id"))
    note = Column(Text)


class RequirementStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    DESCONOCIDO = "desconocido"
    FALTANTE = "faltante"
    VENCIDO = "vencido"
    INCUMPLE = "incumple"
    EN_REVISION = "en_revision"                    # evidencia nueva aguardando revisor (US04)
    CUMPLE_VALIDADO = "cumple_validado"
    NO_APLICA_JUSTIFICADO = "no_aplica_justificado"


class Requirement(OrgScoped, Base):
    __tablename__ = "requirements"

    code = Column(String(60), index=True)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    lot_id = Column(String(36), ForeignKey("lots.id", ondelete="SET NULL"))
    text = Column(Text, nullable=False)
    req_type = Column(String(30))                  # tecnico | documental | servicio | capacidad | administrativo
    mandatory = Column(Boolean)                    # null = no determinable desde las bases
    scope = Column(String(20))                     # empresa | producto | partida | servicio
    attribute = Column(String(60))                 # atributo comparable del catálogo
    operator = Column(String(10))                  # eq | gte | lte
    expected_value = Column(String(120))
    unit = Column(String(30))
    page = Column(Integer)
    fragment = Column(Text)
    source_label = Column(String(255))
    bases_version = Column(String(40))
    status = Column(String(30), nullable=False, default=RequirementStatus.PENDIENTE.value, index=True)
    status_reason = Column(Text)
    reviewer_id = Column(String(36), ForeignKey("users.id"))
    due_date = Column(Date)
    required_valid_until = Column(Date)            # fecha a la que la evidencia debe estar vigente
    next_action = Column(String(255))
    data_kind = Column(String(12), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    lot = relationship("Lot", lazy="joined")
    reviewer = relationship("User", lazy="joined")
    evidence = relationship("EvidenceLink", cascade="all, delete-orphan", lazy="selectin")


class EvidenceLink(OrgScoped, Base):
    __tablename__ = "evidence_links"

    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    document_version_id = Column(String(36), ForeignKey("document_versions.id"))
    page = Column(Integer)
    fragment = Column(Text)
    decision = Column(String(20), nullable=False, default="propuesta")   # propuesta | aceptada | rechazada
    reviewer_id = Column(String(36), ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    reason = Column(Text)
    created_by_id = Column(String(36), ForeignKey("users.id"))

    document = relationship("Document", lazy="joined")


class Task(OrgScoped, Base):
    __tablename__ = "tasks"

    code = Column(String(60), index=True)
    title = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="pendiente")   # pendiente | en_progreso | hecha | cancelada
    assignee_id = Column(String(36), ForeignKey("users.id"))
    due_date = Column(Date)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"))
    created_by_id = Column(String(36), ForeignKey("users.id"))
    notes = Column(Text)
    data_kind = Column(String(12), nullable=False)

    assignee = relationship("User", foreign_keys=[assignee_id], lazy="joined")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=new_id)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.id"))
    action = Column(String(80), nullable=False)
    resource_type = Column(String(60), nullable=False)
    resource_id = Column(String(36), index=True)
    before = Column(JSON)
    after = Column(JSON)
    correlation_id = Column(String(40))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    demo_run_id = Column(String(36), ForeignKey("demo_runs.id"), index=True)
    # Cadena SHA-256 por organización (services.audit.compute_event_hash).
    prev_hash = Column(String(64))
    hash = Column(String(64), nullable=False)

    actor = relationship("User", lazy="joined")


# En Postgres la bitácora es de solo inserción. La migración crea lo mismo; esto cubre create_all (pruebas).
AUDIT_IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events es de solo inserción';
END;
$$ LANGUAGE plpgsql
"""
AUDIT_IMMUTABLE_TRIGGER = """
CREATE TRIGGER audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION audit_events_immutable()
"""
for _ddl in (AUDIT_IMMUTABLE_FUNCTION, AUDIT_IMMUTABLE_TRIGGER):
    event.listen(AuditEvent.__table__, "after_create", DDL(_ddl).execute_if(dialect="postgresql"))
