"""Fuentes, tareas, usuarios, auditoría y operación del demo (el catálogo vive en `routers/catalog.py`)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import Perm, require_permission
from app.models import AuditEvent, Organization, Source, Task, User
from app.routers.opportunities import _user_ref, task_out
from app.schemas.v1 import AuditOut, Page, SourceOut, TaskOut, UserOut
from app.services.demo_seed import reset_demo

router = APIRouter(prefix="/api/v1", tags=["recursos"])


@router.get("/sources", response_model=list[SourceOut], tags=["fuentes"])
def list_sources(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    return [SourceOut.model_validate(s) for s in db.scalars(
        select(Source).where(Source.organization_id == user.organization_id).order_by(Source.name))]


@router.get("/tasks", response_model=list[TaskOut], tags=["tareas"])
def list_tasks(mine: bool = False, status: str | None = None, db: Session = Depends(get_db),
               user: User = Depends(require_permission(Perm.TASK_READ))):
    stmt = select(Task).where(Task.organization_id == user.organization_id)
    if mine:
        stmt = stmt.where(Task.assignee_id == user.id)
    if status:
        stmt = stmt.where(Task.status == status)
    return [task_out(t) for t in db.scalars(stmt.order_by(Task.due_date.nullslast(), Task.code)).unique()]


@router.get("/users", response_model=list[UserOut], tags=["identidad"])
def list_users(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    return [UserOut.model_validate(u) for u in db.scalars(
        select(User).where(User.organization_id == user.organization_id, User.is_active.is_(True))
        .order_by(User.full_name))]


@router.get("/audit-events", response_model=Page[AuditOut], tags=["auditoría"])
def list_audit(resource_type: str | None = None, action: str | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
               db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.AUDIT_READ))):
    stmt = select(AuditEvent).where(AuditEvent.organization_id == user.organization_id)
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    events = db.scalars(stmt.order_by(AuditEvent.created_at.desc())
                        .offset((page - 1) * page_size).limit(page_size)).unique()
    return Page(items=[AuditOut(id=e.id, actor=_user_ref(e.actor), action=e.action,
                                resource_type=e.resource_type, resource_id=e.resource_id, before=e.before,
                                after=e.after, correlation_id=e.correlation_id, created_at=e.created_at)
                       for e in events], total=total, page=page, page_size=page_size)


@router.post("/demo/reset", tags=["operación"])
def demo_reset(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.DEMO_RESET))):
    """Borra y vuelve a sembrar los datos SYNTHETIC e HISTORICAL. No toca datos REAL."""
    org = db.get(Organization, user.organization_id)
    summary = reset_demo(db, org, actor_id=user.id)
    db.commit()
    return summary
