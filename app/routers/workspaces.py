"""Expediente: evidencia, revisión y tareas de requisitos (E4); evaluación, decisión, aprobaciones y compuerta (E5)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import Perm, require_permission
from app.core.security import get_current_user
from app.core.tenant import get_owned
from app.models import Document, MatchAssessment, Opportunity, Requirement, Task, User, Variant
from app.routers.opportunities import _user_ref, requirement_rows, task_out
from app.schemas.v1 import TaskOut
from app.schemas.workspace import (
    ApprovalIn, AssessmentOut, DecisionIn, EvidenceIn, LotPrice, RequirementDetail, ReviewIn, TaskAssignIn,
    TaskPatchIn, WorkspaceOut, WorkspaceView,
)
from app.services import review, workspace

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


# ── Expediente (E5) ──────────────────────────────────────────────────────────

def _users(db: Session, ids) -> dict[str, User]:
    ids = {i for i in ids if i}
    return {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


def workspace_view(db: Session, opportunity: Opportunity) -> WorkspaceView:
    ws = workspace.find_workspace(db, opportunity.id)
    users = _users(db, [ws.decision_by_id, ws.technical_approval_by_id, ws.commercial_approval_by_id] if ws else [])
    ref = lambda uid: _user_ref(users.get(uid))  # noqa: E731
    out = WorkspaceOut(
        id=ws.id if ws else None, opportunity_id=opportunity.id,
        decision=ws.decision if ws else "pendiente", decision_by=ref(ws.decision_by_id) if ws else None,
        decision_at=ws.decision_at if ws else None, decision_reason=ws.decision_reason if ws else None,
        technical_approval_by=ref(ws.technical_approval_by_id) if ws else None,
        technical_approval_at=ws.technical_approval_at if ws else None,
        commercial_approval_by=ref(ws.commercial_approval_by_id) if ws else None,
        commercial_approval_at=ws.commercial_approval_at if ws else None,
        approvals_stale=ws.approvals_stale if ws else False,
        phase=ws.phase if ws else workspace.PHASE_ANALYSIS, version=ws.version if ws else 0,
    )
    lots = {l.id: l for l in opportunity.lots}
    reqs = {r.id: r for r in db.scalars(select(Requirement).where(Requirement.opportunity_id == opportunity.id))}
    rows = db.scalars(select(MatchAssessment).where(MatchAssessment.opportunity_id == opportunity.id)).all()
    variants = {v.id: v for v in db.scalars(select(Variant).where(
        Variant.id.in_({a.variant_id for a in rows if a.variant_id})))} if rows else {}
    assessments = []
    for a in rows:
        lot, req, variant = lots.get(a.lot_id), reqs.get(a.requirement_id), variants.get(a.variant_id)
        assessments.append(AssessmentOut(
            id=a.id, lot_id=a.lot_id, lot_number=lot.number if lot else None, requirement_id=a.requirement_id,
            requirement_code=req.code if req else None, variant_id=a.variant_id,
            variant_sku=variant.sku if variant else None, variant_name=variant.name if variant else None,
            variant_data_kind=variant.data_kind if variant else None,
            product_id=variant.product_id if variant else None, result=a.result, explanation=a.explanation,
            rule=a.rule, engine_version=a.engine_version, catalog_value=a.catalog_value, source_text=a.source_text,
            assessed_at=a.created_at))
    assessments.sort(key=lambda x: (x.lot_number or "", x.requirement_code or ""))
    return WorkspaceView(
        workspace=out, affinity=ws.affinity if ws else None, assessments=assessments,
        blockers=workspace.requirement_blockers(db, opportunity.id),
        lots=[LotPrice(lot_id=l.id, number=l.number, unit_price=l.unit_price, currency=l.currency,
                       price_data_kind=l.price_data_kind,
                       product_id=l.proposed_variant.product_id if l.proposed_variant else None,
                       product_name=l.proposed_variant.product.name if l.proposed_variant else None,
                       product_review_status=l.proposed_variant.product.review_status
                       if l.proposed_variant else None) for l in opportunity.lots])


def _opportunity(db: Session, opportunity_id: str, user: User) -> Opportunity:
    return get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")


@router.get("/workspaces/{opportunity_id}", response_model=WorkspaceView)
def get_workspace(opportunity_id: str, db: Session = Depends(get_db),
                  user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    """Expediente: decisión, aprobaciones, afinidad guardada y la evaluación del motor por requisito."""
    return workspace_view(db, _opportunity(db, opportunity_id, user))


@router.post("/workspaces/{opportunity_id}/assess", response_model=WorkspaceView)
def assess(opportunity_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Ejecuta el motor determinista (requiere opportunity.write o requirement.review)."""
    opp = _opportunity(db, opportunity_id, user)
    workspace.assess(db, user, opp)
    db.commit()
    return workspace_view(db, opp)


@router.post("/workspaces/{opportunity_id}/decision", response_model=WorkspaceView)
def decide(opportunity_id: str, payload: DecisionIn, db: Session = Depends(get_db),
           user: User = Depends(require_permission(Perm.BID_DECIDE))):
    opp = _opportunity(db, opportunity_id, user)
    ws = workspace.get_or_create_workspace(db, opp, user.id, workspace.ORIGIN_DECISION)
    workspace.decide(db, user, ws, payload.decision, payload.reason)
    db.commit()
    return workspace_view(db, opp)


@router.post("/workspaces/{opportunity_id}/approvals", response_model=WorkspaceView)
def approve(opportunity_id: str, payload: ApprovalIn, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    """Técnica (requirement.review) o comercial (pricing.approve); la misma persona no da las dos."""
    opp = _opportunity(db, opportunity_id, user)
    ws = workspace.get_or_create_workspace(db, opp, user.id, workspace.ORIGIN_APPROVAL)
    workspace.approve(db, user, ws, payload.kind)
    db.commit()
    return workspace_view(db, opp)


@router.post("/workspaces/{opportunity_id}/ready", response_model=WorkspaceView)
def mark_ready(opportunity_id: str, db: Session = Depends(get_db),
               user: User = Depends(require_permission(Perm.BID_DECIDE))):
    """Compuerta «listo para revisión final»: 409 `not_ready` con los bloqueantes si falta algo."""
    opp = _opportunity(db, opportunity_id, user)
    workspace.mark_ready(db, user, workspace.get_or_create_workspace(db, opp, user.id, workspace.ORIGIN_READY))
    db.commit()
    return workspace_view(db, opp)
