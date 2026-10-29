from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.licitacion import Caracter, EstatusLicitacion, TipoProcedimiento


class LicitacionBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    numero_procedimiento: str
    titulo: str
    dependencia: str
    unidad_compradora: str | None = None
    entidad_federativa: str | None = None
    tipo: TipoProcedimiento = TipoProcedimiento.LICITACION_PUBLICA
    caracter: Caracter = Caracter.NACIONAL
    estatus: EstatusLicitacion = EstatusLicitacion.DETECTADA
    fecha_publicacion: date | None = None
    fecha_junta_aclaraciones: datetime | None = None
    fecha_apertura: datetime | None = None
    fecha_fallo: datetime | None = None
    monto_estimado: Decimal | None = None
    url_fuente: str | None = None
    notas: str | None = None
    responsable_id: str | None = None


class LicitacionCreate(LicitacionBase):
    pass


class LicitacionUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    titulo: str | None = None
    dependencia: str | None = None
    unidad_compradora: str | None = None
    entidad_federativa: str | None = None
    tipo: TipoProcedimiento | None = None
    caracter: Caracter | None = None
    estatus: EstatusLicitacion | None = None
    fecha_publicacion: date | None = None
    fecha_junta_aclaraciones: datetime | None = None
    fecha_apertura: datetime | None = None
    fecha_fallo: datetime | None = None
    monto_estimado: Decimal | None = None
    url_fuente: str | None = None
    notas: str | None = None
    responsable_id: str | None = None


class LicitacionOut(LicitacionBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
