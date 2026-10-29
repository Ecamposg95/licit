"""Expediente: evidencia, revisión y tareas de requisitos (E4)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import Perm, require_permission
from app.core.tenant import get_owned
from app.models import Document, Requirement, Task, User
from app.routers.opportunities import requirement_rows, task_out
from app.schemas.v1 import TaskOut
from app.schemas.workspace import EvidenceIn, RequirementDetail, ReviewIn, TaskAssignIn, TaskPatchIn
from app.services import review

router = APIRouter(prefix="/api/v1", tags=["expediente"])


def _row(db: Session, requirement: Requirement) -> RequirementDetail:
    db.refresh(requirement)
    return requirement_rows(db, requirement.opportunity_id, [requirement])[0]


@router.post("/requirements/{requirement_id}/evidence", response_model=RequirementDetail, status_code=201)
def link_evidence(requirement_id: str, payload: EvidenceIn, db: Session = Depends(get_db),
                  user: User = Depends(require_permission(Perm.DOCUMENT_UPLOAD))):
    """Vincula una versión de documento como evidencia: el requisito pasa a revisión (nunca a validado)."""
    requirement = get_owned(db, Requirement, requirement_id, user, "Requisito")
    document = get_owned(db, Document, payload.document_id, user, "Documento")
    version = next((v for v in document.versions if v.version == payload.version), None)
    if version is None:
        raise AppError(404, "not_found", "Versión del documento no encontrada")
    review.link_evidence(db, user, requirement, version, payload.page, payload.fragment)
    db.commit()
    return _row(db, requirement)


@router.patch("/requirements/{requirement_id}/review", response_model=RequirementDetail)
def review_requirement(requirement_id: str, payload: ReviewIn, db: Session = Depends(get_db),
                       user: User = Depends(require_permission(Perm.REQUIREMENT_REVIEW))):
    """Decisión humana con motivo y versión esperada; sin autoaprobación ni evidencia vencida."""
    requirement = get_owned(db, Requirement, requirement_id, user, "Requisito")
    review.review_requirement(db, user, requirement, payload.decision, payload.reason, payload.expected_version)
    db.commit()
    return _row(db, requirement)


@router.post("/requirements/{requirement_id}/tasks", response_model=TaskOut, status_code=201)
def assign_task(requirement_id: str, payload: TaskAssignIn, db: Session = Depends(get_db),
                user: User = Depends(require_permission(Perm.TASK_ASSIGN))):
    requirement = get_owned(db, Requirement, requirement_id, user, "Requisito")
    task = review.assign_task(db, user, requirement, payload.assignee_id, payload.due_date, payload.title)
    db.commit()
    db.refresh(task)
    return task_out(task)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: str, payload: TaskPatchIn, db: Session = Depends(get_db),
                user: User = Depends(require_permission(Perm.TASK_UPDATE))):
    task = get_owned(db, Task, task_id, user, "Actividad")
    review.update_task(db, user, task, payload.status)
    db.commit()
    db.refresh(task)
    return task_out(task)
