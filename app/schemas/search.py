"""Contratos de la búsqueda en vivo (corridas) y de la importación manual de oportunidades."""
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.v1 import UserRef

MAX_RANGE_DAYS = 366
# El robots.txt de SIDOF prohíbe notas concretas de 2011 a 2020: la búsqueda empieza, como mínimo, en 2021.
MIN_DATE = date(2021, 1, 1)


class SearchRunCreate(BaseModel):
    """Sin términos se usan los del diccionario; sin fechas, del 1 de enero del año en curso a hoy."""
    terms: list[str] | None = Field(None, max_length=10)
    date_from: date | None = None
    date_to: date | None = None

    @field_validator("terms")
    @classmethod
    def _terms(cls, value: list[str] | None):
        if value is None:
            return value
        cleaned = [" ".join(t.split()) for t in value]
        for t in cleaned:
            if not 2 <= len(t) <= 80:
                raise ValueError("Cada término debe tener entre 2 y 80 caracteres")
        return cleaned

    @model_validator(mode="after")
    def _range(self):
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValueError("La fecha inicial es posterior a la final")
            if (self.date_to - self.date_from).days > MAX_RANGE_DAYS:
                raise ValueError(f"El rango no puede pasar de {MAX_RANGE_DAYS} días")
        return self


class SearchRunAccepted(BaseModel):
    search_run_id: str
    job_id: str


class SearchCounts(BaseModel):
    notes: int = 0               # notas leídas
    procedures: int = 0          # procedimientos cuyo objeto coincide con algún término
    new: int = 0
    updated: int = 0
    unchanged: int = 0


class SearchTermOut(BaseModel):
    term: str
    status: str                  # pendiente | buscando | buscado | leyendo | terminado | incompleto | unconfirmed | error
    checked_at: datetime | None = None
    total: int | None = None     # notas que reportó SIDOF (None si no confirmó o falló)
    notes: int = 0               # notas de convocatorias asignadas a este término
    read: int = 0
    skipped_non_cv: int = 0      # notas fuera de la sección de convocatorias
    seen_other_term: int = 0     # notas que ya había encontrado otro término
    procedures: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    unparsed: int = 0            # notas leídas sin ningún número de procedimiento reconocible
    discarded_object: int = 0    # procedimientos cuyo objeto no menciona el término
    fallo_without_convocatoria: int = 0          # avisos de fallo de procedimientos no registrados
    other_notice_without_convocatoria: int = 0   # cancelaciones o modificaciones de procedimientos no registrados
    errors: int = 0


class NoteRef(BaseModel):
    cod_nota: str
    url: str                     # URL pública de la nota oficial


class SearchErrorOut(BaseModel):
    source: str
    term: str | None = None
    # source_unavailable | zero_unconfirmed | aborted | truncated | no_procedure | internal_error
    code: str
    message: str
    notes: list[NoteRef] = []    # no_procedure: notas que conviene abrir o importar a mano


class SearchQueryOut(BaseModel):
    terms: list[str]
    date_from: date
    date_to: date


class SearchRunOut(BaseModel):
    id: str
    status: str                  # queued | running | done | partial | failed
    query: SearchQueryOut
    counts: SearchCounts
    terms: list[SearchTermOut]
    errors: list[SearchErrorOut]
    job_id: str | None
    created_by: UserRef | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ManualMetadata(BaseModel):
    """Captura de un procedimiento visto en Compras MX (no se descarga nada)."""
    external_id: str = Field(min_length=3, max_length=120)
    title: str = Field(min_length=3, max_length=500)
    buyer: str = Field(min_length=2, max_length=255)
    source_url: str = Field(max_length=1000)
    submission_at: datetime | None = None     # sin zona → hora de Ciudad de México (supuesta)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("external_id", "title", "buyer", "source_url")
    @classmethod
    def _strip(cls, value: str) -> str:
        return " ".join(value.split())


class OpportunityImport(BaseModel):
    """Exactamente una de dos formas: `url` de una nota de SIDOF o `metadata` capturados de Compras MX."""
    url: str | None = Field(None, max_length=1000)
    metadata: ManualMetadata | None = None
    external_id: str | None = Field(None, max_length=120,
                                    description="Con `url`: qué procedimiento importar si la nota trae varios")

    @model_validator(mode="after")
    def _one_form(self):
        if (self.url is None) == (self.metadata is None):
            raise ValueError("Envía `url` o `metadata`, no ambos ni ninguno")
        return self


class ProcedureChoice(BaseModel):
    external_id: str
    title: str | None
