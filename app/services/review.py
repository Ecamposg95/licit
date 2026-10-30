"""Revisión de requisitos: evidencia a revisión, validación sin autoaprobación y tareas (task pack US04).

- Una evidencia nueva lleva el requisito a `en_revision`, nunca a `cumple_validado`.
- Solo una persona con `requirement.review` decide, con motivo y sobre la versión que tiene a la vista.
- Nadie aprueba evidencia que subió o vinculó, aunque acumule todos los roles (la cuenta `presentador` tampoco).
- No se valida con un documento vencido o que vence antes de la fecha exigida.
- Todo cambio se audita en la misma transacción e invalida las aprobaciones del expediente.

Ninguna función hace commit: lo hace quien llama.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.core.errors import AppError
from app.core.permissions import Perm, permissions_for
from app.core.tenant import get_owned
from app.models import (
    DataKind, Document, DocumentVersion, EvidenceLink, Opportunity, Requirement, RequirementStatus, Task, User,
)
from app.models.base import new_id, utcnow
from app.services import audit, workspace
from app.services.affinity import check_validity

MX = ZoneInfo(config.DISPLAY_TIMEZONE)

S = RequirementStatus
REVIEW_DECISIONS = {s.value for s in S} - {S.EN_REVISION.value}
# Decisiones que cierran el requisito para la compuerta: nadie las toma sobre evidencia propia.
CLOSING_DECISIONS = {S.CUMPLE_VALIDADO.value, S.NO_APLICA_JUSTIFICADO.value}
# Decisiones con las que la evidencia propuesta no sirve como prueba de cumplimiento.
REJECTING_DECISIONS = {S.INCUMPLE.value, S.FALTANTE.value, S.VENCIDO.value}
EXPIRED = ("vencido", "vence_antes")

TASK_STATUSES = ("pendiente", "en_progreso", "hecha", "cancelada")
OPEN_TASK_STATUSES = ("pendiente", "en_progreso")

SELF_APPROVAL_MESSAGE = "No puedes aprobar evidencia que tú cargaste. Cambia a la cuenta del revisor"

_REQ_FIELDS = ["status", "status_reason", "reviewer_id", "version"]
_TASK_FIELDS = ["title", "status", "assignee_id", "due_date"]


def today_mx() -> date:
    """Hoy en la zona de la demostración (la vigencia se compara por día de calendario)."""
    return datetime.now(MX).date()


def require(user, *perms: Perm) -> None:
    """El usuario debe tener al menos uno de los permisos (el router ya lo exige; aquí se vuelve a validar)."""
    have = permissions_for(user.role_names)
    if not any(p in have for p in perms):
        raise AppError(403, "forbidden", f"Tu rol no tiene el permiso {perms[0].value}")


def _local_date(moment: datetime | None) -> date | None:
    if moment is None:
        return None
    if moment.tzinfo is None:          # SQLite devuelve UTC sin zona
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(MX).date()


def required_by(db: Session, requirement: Requirement) -> date | None:
    """Fecha a la que la evidencia debe estar vigente: la del requisito o, si no hay, la de presentación."""
    if requirement.required_valid_until is not None:
        return requirement.required_valid_until
    opp = db.get(Opportunity, requirement.opportunity_id)
    return _local_date(opp.submission_at) if opp is not None else None


def evidence_validity(db: Session, requirement: Requirement, link: EvidenceLink, today: date | None = None) -> str:
    valid_until = link.document.valid_until if link.document is not None else None
    return check_validity(valid_until, required_by(db, requirement), today or today_mx())


def uploaders(db: Session, requirement: Requirement) -> set[str]:
    """Quienes vincularon una evidencia del requisito o subieron la versión de documento vinculada."""
    ids = {e.created_by_id for e in requirement.evidence if e.created_by_id}
    version_ids = [e.document_version_id for e in requirement.evidence if e.document_version_id]
    if version_ids:
        ids |= {u for u in db.scalars(select(DocumentVersion.uploaded_by_id).where(
            DocumentVersion.id.in_(version_ids), DocumentVersion.uploaded_by_id.is_not(None)))}
    return ids


def lock_requirement(db: Session, requirement: Requirement) -> None:
    """Bloquea la fila (Postgres) y relee el requisito: la versión esperada se compara con lo confirmado, no con
    una lectura que otra solicitud simultánea pudo dejar atrás. En SQLite no hay FOR UPDATE."""
    db.execute(select(Requirement.id).where(Requirement.id == requirement.id).with_for_update())
    db.refresh(requirement)


def opportunity_uploaders(db: Session, opportunity_id: str) -> set[str]:
    """Quienes vincularon o subieron evidencia de cualquier requisito de la oportunidad."""
    links = db.execute(select(EvidenceLink.created_by_id, EvidenceLink.document_version_id)
                       .join(Requirement, EvidenceLink.requirement_id == Requirement.id)
                       .where(Requirement.opportunity_id == opportunity_id)).all()
    ids = {created for created, _v in links if created}
    version_ids = [v for _c, v in links if v]
    if version_ids:
        ids |= set(db.scalars(select(DocumentVersion.uploaded_by_id).where(
            DocumentVersion.id.in_(version_ids), DocumentVersion.uploaded_by_id.is_not(None))))
    return ids


# ── Evidencia ────────────────────────────────────────────────────────────────

def link_evidence(db: Session, user, requirement: Requirement, document_version: DocumentVersion,
                  page: int | None, fragment: str | None) -> EvidenceLink:
    """Vincula una versión de documento como evidencia. El requisito pasa a `en_revision` (también si ya estaba
    validado: la evidencia nueva se revisa de nuevo)."""
    require(user, Perm.DOCUMENT_UPLOAD)
    if user.organization_id != requirement.organization_id or user.organization_id != document_version.organization_id:
        raise AppError(404, "not_found", "Documento no encontrado")
    lock_requirement(db, requirement)
    document = db.get(Document, document_version.document_id)
    if requirement.data_kind == DataKind.REAL.value and document.data_kind == DataKind.SYNTHETIC.value:
        raise AppError(422, "synthetic_evidence",
                       "Un documento ficticio no puede ser evidencia de un procedimiento real.")
    if page is not None and (page < 1 or (document.page_count and page > document.page_count)):
        raise AppError(422, "page_out_of_range", f"La página {page} no existe en el documento.",
                       {"page_count": document.page_count})
    if any(e.document_version_id == document_version.id and e.decision != "rechazada" for e in requirement.evidence):
        raise AppError(409, "evidence_already_linked", "Esa versión del documento ya es evidencia de este requisito.")

    before = audit.snapshot(requirement, _REQ_FIELDS)
    link = EvidenceLink(id=new_id(), organization_id=requirement.organization_id, document_id=document.id,
                        document_version_id=document_version.id, page=page,
                        fragment=(fragment or "").strip() or None, decision="propuesta", created_by_id=user.id)
    requirement.evidence.append(link)
    label = f"{document.code or document.title} v{document_version.version}"
    requirement.status = S.EN_REVISION.value
    requirement.status_reason = (f"Evidencia nueva ({label}) en revisión. La valida una persona distinta de quien "
                                 "la cargó o la vinculó.")
    requirement.reviewer_id = None
    requirement.version += 1
    ws_change = workspace.on_requirement_change(db, requirement, user.id)
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="requirement.evidence_linked",
                 resource_type="requirement", resource_id=requirement.id, before=before,
                 after={**audit.snapshot(requirement, _REQ_FIELDS), "evidence_id": link.id,
                        "document_id": document.id, "document_code": document.code,
                        "document_version": document_version.version, "page": page, "fragment": link.fragment,
                        "workspace": ws_change})
    return link


# ── Revisión ─────────────────────────────────────────────────────────────────

def review_requirement(db: Session, user, requirement: Requirement, decision: str, reason: str,
                       expected_version: int) -> Requirement:
    """Decisión humana sobre un requisito, con motivo y versión esperada."""
    require(user, Perm.REQUIREMENT_REVIEW)
    reason = (reason or "").strip()
    if not reason:
        raise AppError(422, "reason_required", "Indica el motivo de la revisión.")
    lock_requirement(db, requirement)
    if expected_version != requirement.version:
        raise AppError(409, "version_conflict", "El requisito cambió desde que lo abriste; recarga.",
                       {"current_version": requirement.version})
    if decision not in REVIEW_DECISIONS:
        raise AppError(422, "invalid_decision", "Decisión de revisión no reconocida.",
                       {"allowed": sorted(REVIEW_DECISIONS)})
    evidence = [e for e in requirement.evidence if e.decision != "rechazada"]
    if decision == S.CUMPLE_VALIDADO.value and not evidence:
        raise AppError(422, "evidence_required", "No se valida un requisito sin evidencia vinculada.")
    if decision in CLOSING_DECISIONS and user.id in uploaders(db, requirement):
        raise AppError(403, "self_approval", SELF_APPROVAL_MESSAGE)
    if decision == S.CUMPLE_VALIDADO.value:
        by, today = required_by(db, requirement), today_mx()
        expired = []
        for e in evidence:
            validity = check_validity(e.document.valid_until, by, today)
            if validity in EXPIRED:
                expired.append({"evidence_id": e.id, "document_code": e.document.code, "validity": validity,
                                "valid_until": e.document.valid_until.isoformat()})
        if expired:
            raise AppError(422, "evidence_expired",
                           "La evidencia está vencida o vence antes de la fecha exigida; no se puede validar.",
                           {"required_by": by.isoformat() if by else None, "evidence": expired})

    before = audit.snapshot(requirement, _REQ_FIELDS)
    now = utcnow()
    requirement.status = decision
    requirement.status_reason = reason
    requirement.reviewer_id = user.id
    requirement.version += 1
    touched, new_decision = [], None
    if decision == S.CUMPLE_VALIDADO.value:
        touched = evidence
        new_decision = "aceptada"
    elif decision in REJECTING_DECISIONS:
        touched = [e for e in evidence if e.decision == "propuesta"]
        new_decision = "rechazada"
    for e in touched:
        e.decision, e.reviewer_id, e.reviewed_at, e.reason = new_decision, user.id, now, reason
    ws_change = workspace.on_requirement_change(db, requirement, user.id)
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="requirement.review",
                 resource_type="requirement", resource_id=requirement.id, before=before,
                 after={**audit.snapshot(requirement, _REQ_FIELDS), "decision": decision,
                        "evidence": [{"id": e.id, "decision": e.decision} for e in touched],
                        "workspace": ws_change})
    return requirement


# ── Tareas ───────────────────────────────────────────────────────────────────

def open_task(db: Session, requirement: Requirement) -> Task | None:
    return db.scalars(select(Task).where(Task.requirement_id == requirement.id,
                                         Task.status.in_(OPEN_TASK_STATUSES))
                      .order_by(Task.created_at, Task.code)).first()


def assign_task(db: Session, user, requirement: Requirement, assignee_id: str, due_date: date | None,
                title: str | None) -> Task:
    """Asigna el requisito a una persona. Si ya tiene una actividad abierta, se reasigna esa misma."""
    require(user, Perm.TASK_ASSIGN)
    assignee = get_owned(db, User, assignee_id, user, "Usuario")
    if not assignee.is_active:
        raise AppError(422, "inactive_user", "No se puede asignar a una cuenta inactiva.")
    title = " ".join((title or "").split()) or f"Atender requisito {requirement.code}: {requirement.text}"[:500]
    task = open_task(db, requirement)
    before = audit.snapshot(task, _TASK_FIELDS) if task else None
    if task is None:
        tid = new_id()
        task = Task(id=tid, organization_id=requirement.organization_id, code=f"TASK-{tid[:8].upper()}",
                    title=title, status="pendiente", assignee_id=assignee.id, due_date=due_date,
                    opportunity_id=requirement.opportunity_id, requirement_id=requirement.id,
                    created_by_id=user.id, data_kind=requirement.data_kind)
        db.add(task)
    else:
        task.assignee_id, task.title = assignee.id, title
        if due_date is not None:
            task.due_date = due_date
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="task.assign",
                 resource_type="task", resource_id=task.id, before=before,
                 after={**audit.snapshot(task, _TASK_FIELDS), "assignee": assignee.full_name,
                        "requirement_id": requirement.id, "requirement_code": requirement.code})
    return task


def update_task(db: Session, user, task: Task, status: str) -> Task:
    require(user, Perm.TASK_UPDATE)
    if status not in TASK_STATUSES:
        raise AppError(422, "invalid_status", "Estado de actividad no reconocido.", {"allowed": list(TASK_STATUSES)})
    before = audit.snapshot(task, _TASK_FIELDS)
    task.status = status
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="task.update",
                 resource_type="task", resource_id=task.id, before=before,
                 after=audit.snapshot(task, _TASK_FIELDS))
    return task
