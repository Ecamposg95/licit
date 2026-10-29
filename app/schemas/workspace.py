"""Contratos del expediente (frente E): evidencia, revisión, tareas, evaluación y compuerta de revisión final."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.v1 import EvidenceOut, RequirementRow, UserRef


# ── Matriz de requisitos (amplía RequirementRow de E1) ───────────────────────

class EvidenceDetail(EvidenceOut):
    document_version_id: str | None = None
    document_version: int | None = None
    document_data_kind: str | None = None
    document_page_count: int | None = None
    created_by: UserRef | None = None          # quién vinculó la evidencia
    uploaded_by: UserRef | None = None         # quién subió la versión del documento
    reviewer: UserRef | None = None
    reviewed_at: datetime | None = None
    reason: str | None = None
    # Vigencia del documento hoy y a la fecha exigida: vigente | vence_antes | vencido | sin_vigencia.
    validity: str


class RequirementDetail(RequirementRow):
    evidence: list[EvidenceDetail]
    required_by: date | None = None            # fecha contra la que se revisa la vigencia de la evidencia


# ── Entradas ─────────────────────────────────────────────────────────────────

class EvidenceIn(BaseModel):
    document_id: str
    version: int = Field(ge=1)
    page: int | None = Field(None, ge=1)
    fragment: str | None = Field(None, max_length=2000)


class ReviewIn(BaseModel):
    decision: str
    reason: str = ""
    expected_version: int


class TaskAssignIn(BaseModel):
    assignee_id: str
    due_date: date | None = None
    title: str | None = Field(None, max_length=500)


class TaskPatchIn(BaseModel):
    status: str


class DecisionIn(BaseModel):
    decision: Literal["participar", "no_participar"]
    reason: str = ""


class ApprovalIn(BaseModel):
    kind: Literal["tecnica", "comercial"]


# ── Expediente ───────────────────────────────────────────────────────────────

class WorkspaceOut(BaseModel):
    id: str | None                             # None: el expediente aún no se ha abierto (sin cambios)
    opportunity_id: str
    decision: str
    decision_by: UserRef | None
    decision_at: datetime | None
    decision_reason: str | None
    technical_approval_by: UserRef | None
    technical_approval_at: datetime | None
    commercial_approval_by: UserRef | None
    commercial_approval_at: datetime | None
    approvals_stale: bool
    phase: str
    version: int


class AssessmentOut(BaseModel):
    id: str
    lot_id: str
    lot_number: str | None
    requirement_id: str | None
    requirement_code: str | None
    variant_id: str | None
    variant_sku: str | None
    variant_name: str | None
    variant_data_kind: str | None
    product_id: str | None
    result: str
    explanation: str
    rule: str
    engine_version: str
    catalog_value: str | None
    source_text: str | None
    assessed_at: datetime


class LotPrice(BaseModel):
    lot_id: str
    number: str
    unit_price: Decimal | None
    currency: str | None
    price_data_kind: str | None                # procedencia del precio, independiente del producto
    product_id: str | None = None              # ficha del producto propuesto
    product_name: str | None = None
    product_review_status: str | None = None


class WorkspaceView(BaseModel):
    workspace: WorkspaceOut
    # Forma de services.affinity.serialize_affinity; None = sin evaluar.
    affinity: dict[str, Any] | None
    assessments: list[AssessmentOut]
    lots: list[LotPrice]
