"""Tipos comunes de los adaptadores de fuentes oficiales.

Un adaptador nunca convierte un fallo de la fuente en «cero resultados»: lanza `SourceUnavailable` y quien lo
llama lo registra como error de la corrida (CLAUDE.md, regla 3).
"""
from dataclasses import dataclass
from datetime import date, datetime


class SourceUnavailable(Exception):
    """La fuente no respondió o respondió algo que no se puede interpretar."""

    def __init__(self, source: str, reason: str, retryable: bool):
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason
        self.retryable = retryable


@dataclass
class NoteHit:
    """Una nota encontrada por la búsqueda (solo metadatos; el contenido se lee aparte)."""
    cod_nota: str
    title: str
    published_on: date | None
    organism: str | None
    url: str


@dataclass
class SearchPage:
    hits: list[NoteHit]
    total: int | None
    # False cuando la respuesta no trae `messageCode`: «cero sin confirmar», nunca «no hay licitaciones».
    confirmed: bool


@dataclass
class NoteDetail:
    cod_nota: str
    html: str
    sha256: str                          # SHA-256 del HTML de la nota (cadenaContenido, UTF-8)
    fetched_at: datetime                 # UTC
    url: str                             # URL pública de la nota oficial
    title: str | None = None
    published_on: date | None = None     # fecha de la edición del DOF
    organism: str | None = None
    http_status: int = 200


@dataclass
class ProcedureParsed:
    """Un procedimiento extraído por reglas de una nota. Cada campo no encontrado queda en None."""
    external_id: str
    buyer: str | None
    title: str | None
    state: str | None
    volume: str | None
    published_at: datetime | None        # publicación en Compras MX
    questions_at: datetime | None        # junta de aclaraciones
    submission_at: datetime | None       # presentación y apertura de proposiciones
    ruling_at: datetime | None           # fallo
    submission_precision: str            # "datetime" | "date"
    timezone_assumed: bool               # ninguna fecha trae zona: se supone America/Mexico_City
    excerpt: str                         # filas del procedimiento en texto plano (se recorta al guardar)
    buying_unit: str | None = None
    procedure_type: str | None = None    # licitacion_publica | invitacion_3 | adjudicacion_directa
    character: str | None = None         # nacional | internacional_tlc | internacional_abierta
    notice: str = "convocatoria"         # convocatoria | fallo | aviso
    expediente: str | None = None        # código de expediente de Compras MX, si la nota lo trae
