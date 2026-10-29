"""Contratos de la generación de borradores (frente F)."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.v1 import ORM, UserRef


class GenerateIn(BaseModel):
    templates: list[str] | None = Field(default=None, description="Claves de plantilla; omitido = las seis")


class GenerateOut(BaseModel):
    job_id: str
    status: str


class ArtifactOut(ORM):
    id: str
    opportunity_id: str
    created_at: datetime
    created_by: UserRef | None = None
    data_version: str
    template_version: str
    warnings: list[str]
    sha256: str
    size_bytes: int
    status: str                      # siempre «borrador»
    filename: str


class TemplateInfo(BaseModel):
    key: str
    label: str
    filename: str


class OpenRequirement(BaseModel):
    code: str | None
    text: str
    status: str
    mandatory: bool | None
    lot: str | None


class GenerationPreview(BaseModel):
    """Lo que se generaría hoy: no crea nada."""
    data_version: str
    generated_at: str
    notice: str
    templates: list[TemplateInfo]
    warnings: list[str]
    open_requirements: list[OpenRequirement]
    totals_text: str
    fiscal_text: str
    affinity_state: str
    last_data_version: str | None
    changed_since_last: bool
