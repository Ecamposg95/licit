"""Contratos del frente G: gobierno corporativo, cuentas demo, panel de dirección y estado operativo."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.core.permissions import Perm
from app.schemas.v1 import ORM, OpportunityRow, SourceOut, UserRef

# Texto en español de cada permiso para la matriz de gobierno. Una prueba exige que no falte ninguno.
PERMISSION_LABELS_ES: dict[Perm, str] = {
    Perm.OPPORTUNITY_READ: "Consultar oportunidades",
    Perm.OPPORTUNITY_WRITE: "Clasificar y editar oportunidades",
    Perm.OPPORTUNITY_IMPORT: "Importar oportunidades desde una nota oficial",
    Perm.SEARCH_RUN: "Lanzar búsquedas en fuentes oficiales",
    Perm.CATALOG_READ: "Consultar el catálogo",
    Perm.CATALOG_IMPORT: "Importar productos al catálogo",
    Perm.CATALOG_EDIT: "Editar fichas técnicas",
    Perm.DOCUMENT_READ: "Consultar documentos",
    Perm.DOCUMENT_UPLOAD: "Cargar documentos y versiones",
    Perm.DOCUMENT_VALIDATE: "Validar documentos",
    Perm.REQUIREMENT_READ: "Consultar requisitos",
    Perm.REQUIREMENT_REVIEW: "Revisar y validar requisitos (aprobación técnica)",
    Perm.TASK_READ: "Consultar pendientes",
    Perm.TASK_ASSIGN: "Asignar pendientes",
    Perm.TASK_UPDATE: "Actualizar pendientes",
    Perm.BID_DECIDE: "Decidir si se participa",
    Perm.PRICING_APPROVE: "Aprobar la propuesta económica (aprobación comercial)",
    Perm.PROPOSAL_GENERATE: "Generar borradores del expediente",
    Perm.ARTIFACT_DOWNLOAD: "Descargar expedientes generados",
    Perm.AUDIT_READ: "Consultar la bitácora y la vista de gobierno",
    Perm.USER_MANAGE: "Administrar usuarios",
    Perm.SOURCE_MANAGE: "Administrar fuentes",
    Perm.DEMO_RESET: "Reiniciar el demo",
}


class RoleRef(BaseModel):
    role: str
    label: str


class RolePermissions(BaseModel):
    role: str
    label: str
    permissions: list[str]


class PermissionLabel(BaseModel):
    code: str
    label_es: str


class PermissionMatrix(BaseModel):
    roles: list[RolePermissions]
    permissions: list[PermissionLabel]


class IntegrityResult(BaseModel):
    ok: bool
    checked: int
    first_broken_id: str | None
    verified_at: datetime
    # Cabeza de la cadena verificada: hash y hora del evento número `checked`. Nulos si la cadena está rota
    # o no hay eventos. Para una garantía mayor, este hash debe anclarse fuera de la base de datos.
    last_hash: str | None = None
    last_event_at: datetime | None = None


class ApprovalTarget(BaseModel):
    """Sobre qué se decidió: el procedimiento y, si aplica, el requisito."""
    opportunity_id: str | None = None
    opportunity_external_id: str | None = None
    opportunity_title: str | None = None
    requirement_code: str | None = None
    data_kind: str | None = None


class ApprovalOut(BaseModel):
    id: str
    action: str
    created_at: datetime
    actor: UserRef | None
    roles: list[RoleRef]
    resource_type: str
    resource_id: str | None
    target: ApprovalTarget | None
    reason: str | None
    outcome: str | None
    before: dict | None
    after: dict | None
    demo_run_id: str | None


class DemoRunOut(BaseModel):
    id: str
    started_at: datetime
    actor: UserRef | None
    summary: dict[str, Any] | None
    is_current: bool
    events: int
    approvals: int


# ── Cuentas demo ─────────────────────────────────────────────────────────────

class DemoAccount(BaseModel):
    """Lo único que se publica de una cuenta demo: nunca contraseñas, hashes ni identificadores."""
    email: str
    full_name: str
    roles: list[str]


# ── Panel de dirección ───────────────────────────────────────────────────────

class KindSummary(BaseModel):
    total: int
    por_estado: dict[str, int]


class SearchRunBrief(ORM):
    """Mínimo de una corrida de búsqueda para el panel (el frente C tiene el serializador completo)."""
    id: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    counts: dict[str, Any]
    errors: list[Any]


class ScenarioAtRisk(BaseModel):
    external_id: str
    opportunity_id: str
    title: str
    blocking: list[str]
    data_kind: str


class DirectionDashboard(BaseModel):
    by_data_kind: dict[str, KindSummary]
    upcoming_real: list[OpportunityRow]
    last_search: SearchRunBrief | None
    scenarios_at_risk: list[ScenarioAtRisk]


# ── Estado operativo (TI) ────────────────────────────────────────────────────

class JobBrief(ORM):
    id: str
    kind: str
    status: str
    progress: int
    message: str | None
    error: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class DemoRunBrief(BaseModel):
    id: str
    started_at: datetime
    actor: UserRef | None
    summary: dict[str, Any] | None


class OpsStatus(BaseModel):
    version: str
    alembic_head: str | None
    storage_backend: str            # "s3" | "local" | "invalid" (configuración a medias)
    storage_error: str | None
    worker_alive: bool
    sources: list[SourceOut]
    jobs: list[JobBrief]
    demo_run: DemoRunBrief | None
