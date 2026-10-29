import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, String, Text

from app.core.database import Base


class TipoProcedimiento(str, enum.Enum):
    LICITACION_PUBLICA = "licitacion_publica"
    INVITACION_3 = "invitacion_3"            # invitación a cuando menos tres personas
    ADJUDICACION_DIRECTA = "adjudicacion_directa"


class Caracter(str, enum.Enum):
    NACIONAL = "nacional"
    INTERNACIONAL_TLC = "internacional_tlc"
    INTERNACIONAL_ABIERTA = "internacional_abierta"


class EstatusLicitacion(str, enum.Enum):
    DETECTADA = "detectada"
    EN_ANALISIS = "en_analisis"
    EN_PREPARACION = "en_preparacion"
    PRESENTADA = "presentada"
    GANADA = "ganada"
    PERDIDA = "perdida"
    DESIERTA = "desierta"
    CANCELADA = "cancelada"
    DESCARTADA = "descartada"                # se decidió no participar


class Licitacion(Base):
    __tablename__ = "licitaciones"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    numero_procedimiento = Column(String(100), unique=True, index=True, nullable=False)
    titulo = Column(String(500), nullable=False)
    dependencia = Column(String(255), nullable=False, index=True)   # IMSS, ISSSTE, SSA, estatal…
    unidad_compradora = Column(String(255))
    entidad_federativa = Column(String(100))
    tipo = Column(String(30), nullable=False, default=TipoProcedimiento.LICITACION_PUBLICA.value)
    caracter = Column(String(30), nullable=False, default=Caracter.NACIONAL.value)
    estatus = Column(String(30), nullable=False, default=EstatusLicitacion.DETECTADA.value, index=True)

    fecha_publicacion = Column(Date)
    fecha_junta_aclaraciones = Column(DateTime(timezone=True))
    fecha_apertura = Column(DateTime(timezone=True))
    fecha_fallo = Column(DateTime(timezone=True))

    monto_estimado = Column(Numeric(16, 2))
    url_fuente = Column(String(1000))
    notas = Column(Text)

    responsable_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
