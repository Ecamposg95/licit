import enum

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import DataKind, OrgScoped


class SourceStatus(str, enum.Enum):
    NO_PROBADA = "no_probada"
    ACTIVA = "activa"
    BLOQUEADA = "bloqueada"          # CAPTCHA, autenticación o restricción: carga manual
    INACCESIBLE = "inaccesible"      # error de red o del portal en la última consulta


class Source(OrgScoped, Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)

    key = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    base_url = Column(String(1000))
    allowed_domains = Column(JSON, nullable=False, default=list)
    method = Column(String(20), nullable=False)          # manual | scraper | api | fixture
    status = Column(String(20), nullable=False, default=SourceStatus.NO_PROBADA.value)
    last_checked_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
    notes = Column(Text)


class VerificationStatus(str, enum.Enum):
    POR_VERIFICAR = "por_verificar"
    VERIFICADA = "verificada"
    DESACTUALIZADA = "desactualizada"
    FUENTE_INACCESIBLE = "fuente_inaccesible"
    SIMULADA = "simulada"


class Opportunity(OrgScoped, Base):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("organization_id", "external_id"),)

    # Identificador oficial (o código DEMO-LIC-xxx en escenarios) y su forma normalizada para deduplicar.
    external_id = Column(String(120), nullable=False)
    normalized_id = Column(String(120), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    buyer = Column(String(255), nullable=False)
    buying_unit = Column(String(255))
    state = Column(String(100))                          # entidad federativa
    procedure_type = Column(String(40))                  # licitacion_publica | invitacion_3 | adjudicacion_directa
    character = Column(String(40))                       # nacional | internacional_tlc | internacional_abierta
    families = Column(JSON, nullable=False, default=list)

    data_kind = Column(String(12), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("sources.id"))
    source_url = Column(String(1000))
    last_checked_at = Column(DateTime(timezone=True))
    reported_status = Column(String(120))                # tal como lo publica la fuente
    verification_status = Column(String(30), nullable=False)
    verification_scope = Column(String(255))
    result = Column(String(40), nullable=False, default="desconocido")

    # Fechas separadas por tipo; desconocidas permanecen nulas (§5).
    questions_at = Column(DateTime(timezone=True))       # junta de aclaraciones / preguntas
    submission_at = Column(DateTime(timezone=True))      # presentación y apertura de proposiciones
    ruling_at = Column(DateTime(timezone=True))          # fallo
    # "date" cuando la fuente sólo publica el día: la hora guardada (00:00) no es dato de la fuente.
    submission_precision = Column(String(10), nullable=False, default="datetime")
    source_timezone = Column(String(60))
    timezone_assumed = Column(Boolean, nullable=False, default=False)

    estimated_amount = Column(Numeric(16, 2))
    currency = Column(String(3))
    requires_human_review = Column(Boolean, nullable=False, default=True)
    owner_id = Column(String(36), ForeignKey("users.id"))
    notes = Column(Text)
    version = Column(Integer, nullable=False, default=1)

    source = relationship("Source", lazy="joined")
    owner = relationship("User", lazy="joined")
    lots = relationship("Lot", back_populates="opportunity", cascade="all, delete-orphan",
                        order_by="Lot.number")

    @property
    def is_synthetic(self) -> bool:
        return self.data_kind == DataKind.SYNTHETIC.value


class Lot(OrgScoped, Base):
    """Partida de un procedimiento."""
    __tablename__ = "lots"

    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    family = Column(String(100))
    quantity = Column(Numeric(14, 3))
    unit = Column(String(30))
    # Especificaciones exigidas: {"holes": {"value": 6, "unit": "orificios", "operator": "eq"}, ...}
    specs = Column(JSON, nullable=False, default=dict)
    proposed_variant_id = Column(String(36), ForeignKey("variants.id"))

    opportunity = relationship("Opportunity", back_populates="lots")
    proposed_variant = relationship("Variant", lazy="joined")
