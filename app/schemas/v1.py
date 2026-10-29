"""Contratos de la API v1. Fuente de la especificación OpenAPI (/openapi.json)."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


# ── Identidad ────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRef(ORM):
    id: str
    full_name: str
    email: str


class UserOut(UserRef):
    role_names: list[str]
    is_active: bool


class Me(UserOut):
    permissions: list[str]
    organization_id: str


class Meta(BaseModel):
    organization: str
    demo_mode: bool
    demo_base_date: date
    watermark: str
    display_timezone: str
    freshness_ttl_hours: int
    server_time: datetime
    roles: dict[str, str]


# ── Fuentes y oportunidades ──────────────────────────────────────────────────

class SourceOut(ORM):
    id: str
    key: str
    name: str
    base_url: str | None
    method: str
    status: str
    last_checked_at: datetime | None
    last_error: str | None
    notes: str | None


class SourceRef(ORM):
    key: str
    name: str
    status: str


class Derived(BaseModel):
    code: str
    label: str
    reason: str


class OpportunityRow(BaseModel):
    id: str
    external_id: str
    title: str
    buyer: str
    state: str | None
    procedure_type: str | None
    families: list[str]
    data_kind: str
    source: SourceRef | None
    source_url: str | None
    last_checked_at: datetime | None
    submission_at: datetime | None
    submission_precision: str
    verification_status: str
    derived: Derived
    owner: UserRef | None
    affinity: dict | None          # se calcula en E3 (motor de correspondencia)
    open_requirements: int


class VariantRef(ORM):
    id: str
    sku: str
    name: str
    attributes: dict[str, Any]
    data_kind: str


class LotOut(ORM):
    id: str
    number: str
    description: str
    family: str | None
    quantity: Decimal | None
    unit: str | None
    specs: dict[str, Any]
    proposed_variant: VariantRef | None


class OpportunityDetail(OpportunityRow):
    buying_unit: str | None
    character: str | None
    reported_status: str | None
    verification_scope: str | None
    result: str
    questions_at: datetime | None
    ruling_at: datetime | None
    source_timezone: str | None
    timezone_assumed: bool
    estimated_amount: Decimal | None
    currency: str | None
    requires_human_review: bool
    notes: str | None
    version: int
    lots: list[LotOut]
    requirement_counts: dict[str, int]


class OpportunityPatch(BaseModel):
    expected_version: int
    owner_id: str | None = None
    notes: str | None = None
    families: list[str] | None = None


# ── Catálogo ─────────────────────────────────────────────────────────────────

class VariantOut(ORM):
    id: str
    sku: str
    name: str
    attributes: dict[str, Any]
    unit: str
    price: Decimal | None
    currency: str | None
    stock_demo: int | None
    regulatory_reference: str | None
    data_kind: str
    review_status: str


class ProductOut(ORM):
    id: str
    name: str
    family: str
    brand: str | None
    manufacturer: str | None
    data_kind: str
    review_status: str
    variants: list[VariantOut]


# ── Documentos, requisitos y tareas ──────────────────────────────────────────

class DocumentVersionOut(ORM):
    id: str
    version: int
    filename: str | None
    content_type: str | None
    size_bytes: int | None
    sha256: str | None
    note: str | None
    created_at: datetime


class DocumentOut(ORM):
    id: str
    code: str | None
    title: str
    scope: str
    doc_type: str | None
    issuer_declared: str | None
    valid_until: date | None
    review_status: str
    data_kind: str
    watermark: str | None
    product_id: str | None
    opportunity_id: str | None
    current_version: int
    owner: UserRef | None
    versions: list[DocumentVersionOut]


class EvidenceOut(BaseModel):
    id: str
    document_id: str
    document_code: str | None
    document_title: str
    document_valid_until: date | None
    page: int | None
    fragment: str | None
    decision: str


class RequirementRow(BaseModel):
    id: str
    code: str | None
    text: str
    req_type: str | None
    mandatory: bool | None
    scope: str | None
    lot: dict | None
    attribute: str | None
    operator: str | None
    expected_value: str | None
    unit: str | None
    page: int | None
    fragment: str | None
    source_label: str | None
    bases_version: str | None
    status: str
    status_reason: str | None
    reviewer: UserRef | None
    due_date: date | None
    required_valid_until: date | None
    next_action: str | None
    data_kind: str
    version: int
    evidence: list[EvidenceOut]
    open_task: dict | None
    # Evaluación del motor de correspondencia (frente E); None si no es comparable o no se ha evaluado.
    assessment: dict | None = None


class TaskOut(BaseModel):
    id: str
    code: str | None
    title: str
    status: str
    assignee: UserRef | None
    due_date: date | None
    opportunity_id: str | None
    requirement_id: str | None
    data_kind: str


class AuditOut(BaseModel):
    id: str
    actor: UserRef | None
    action: str
    resource_type: str
    resource_id: str | None
    before: dict | None
    after: dict | None
    correlation_id: str | None
    created_at: datetime
