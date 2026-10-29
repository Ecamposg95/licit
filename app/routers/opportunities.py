from collections import Counter
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import Perm, require_permission
from app.core.tenant import get_owned
from app.models import (
    AuditEvent, Document, EvidenceLink, Lot, Opportunity, Requirement, RequirementStatus, Source, Task,
    User, Variant,
)
from app.schemas.v1 import (
    AuditOut, Derived, DocumentOut, EvidenceOut, LotOut, OpportunityDetail, OpportunityPatch,
    OpportunityRow, Page, RequirementRow, SourceRef, TaskOut, UserRef,
)
from app.services import audit
from app.services.status import derive_status

router = APIRouter(prefix="/api/v1/opportunities", tags=["oportunidades"])

_CLOSED = {RequirementStatus.CUMPLE_VALIDADO.value, RequirementStatus.NO_APLICA_JUSTIFICADO.value}


def _user_ref(u: User | None) -> UserRef | None:
    return UserRef.model_validate(u) if u else None


def _row(opp: Opportunity, open_reqs: int, now: datetime) -> dict:
    d = derive_status(opp, now, config.FRESHNESS_TTL_HOURS)
    return dict(
        id=opp.id, external_id=opp.external_id, title=opp.title, buyer=opp.buyer, state=opp.state,
        procedure_type=opp.procedure_type, families=opp.families or [], data_kind=opp.data_kind,
        source=SourceRef.model_validate(opp.source) if opp.source else None, source_url=opp.source_url,
        last_checked_at=opp.last_checked_at, submission_at=opp.submission_at,
        submission_precision=opp.submission_precision, verification_status=opp.verification_status,
        derived=Derived(code=d.code, label=d.label, reason=d.reason), owner=_user_ref(opp.owner),
        affinity=None, open_requirements=open_reqs,
    )


def _open_counts(db: Session, opp_ids: list[str]) -> dict[str, int]:
    if not opp_ids:
        return {}
    rows = db.execute(
        select(Requirement.opportunity_id, func.count())
        .where(Requirement.opportunity_id.in_(opp_ids), Requirement.status.not_in(_CLOSED))
        .group_by(Requirement.opportunity_id)
    )
    return dict(rows.all())


@router.get("", response_model=Page[OpportunityRow])
def list_opportunities(
    q: str | None = None,
    family: str | None = None,
    state: str | None = None,
    source: str | None = Query(None, description="Clave de la fuente"),
    data_kind: list[str] = Query(default=[], description="REAL, HISTORICAL, SYNTHETIC (repetible)"),
    period_from: date | None = None,
    period_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.OPPORTUNITY_READ)),
):
    stmt = select(Opportunity).where(Opportunity.organization_id == user.organization_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Opportunity.title.ilike(like), Opportunity.external_id.ilike(like),
                              Opportunity.buyer.ilike(like)))
    if state:
        stmt = stmt.where(Opportunity.state == state)
    if source:
        stmt = stmt.join(Source, Opportunity.source_id == Source.id).where(Source.key == source)
    if data_kind:
        stmt = stmt.where(Opportunity.data_kind.in_(data_kind))
    if period_from:
        stmt = stmt.where(Opportunity.submission_at >= datetime.combine(period_from, time.min, tzinfo=timezone.utc))
    if period_to:
        stmt = stmt.where(Opportunity.submission_at <= datetime.combine(period_to, time.max, tzinfo=timezone.utc))

    rows = list(db.scalars(stmt.order_by(Opportunity.data_kind, Opportunity.submission_at.desc().nullslast(),
                                         Opportunity.external_id)).unique())
    # families es JSON: se filtra en Python para mantener compatibilidad SQLite/Postgres.
    if family:
        rows = [o for o in rows if family in (o.families or [])]
    total = len(rows)
    rows = rows[(page - 1) * page_size: page * page_size]
    counts = _open_counts(db, [o.id for o in rows])
    now = datetime.now(timezone.utc)
    return Page(items=[OpportunityRow(**_row(o, counts.get(o.id, 0), now)) for o in rows],
                total=total, page=page, page_size=page_size)


@router.get("/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: str, db: Session = Depends(get_db),
                    user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    statuses = list(db.scalars(select(Requirement.status).where(Requirement.opportunity_id == opp.id)))
    counts = Counter(statuses)
    open_reqs = sum(v for k, v in counts.items() if k not in _CLOSED)
    return OpportunityDetail(
        **_row(opp, open_reqs, datetime.now(timezone.utc)),
        buying_unit=opp.buying_unit, character=opp.character, reported_status=opp.reported_status,
        verification_scope=opp.verification_scope, result=opp.result, questions_at=opp.questions_at,
        ruling_at=opp.ruling_at, source_timezone=opp.source_timezone, timezone_assumed=opp.timezone_assumed,
        estimated_amount=opp.estimated_amount, currency=opp.currency,
        requires_human_review=opp.requires_human_review, notes=opp.notes, version=opp.version,
        lots=[LotOut.model_validate(l) for l in opp.lots], requirement_counts=dict(counts),
    )


_PATCHABLE = ["owner_id", "notes", "families"]


@router.patch("/{opportunity_id}", response_model=OpportunityDetail)
def patch_opportunity(opportunity_id: str, payload: OpportunityPatch, db: Session = Depends(get_db),
                      user: User = Depends(require_permission(Perm.OPPORTUNITY_WRITE))):
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    if payload.expected_version != opp.version:
        raise AppError(409, "version_conflict", "La oportunidad cambió desde que la abriste; recarga.",
                       {"current_version": opp.version})
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if "owner_id" in changes and changes["owner_id"]:
        get_owned(db, User, changes["owner_id"], user, "Usuario")
    before = audit.snapshot(opp, list(changes))
    for k, v in changes.items():
        setattr(opp, k, v)
    opp.version += 1
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="opportunity.update",
                 resource_type="opportunity", resource_id=opp.id, before=before,
                 after=audit.snapshot(opp, list(changes)))
    db.commit()
    return get_opportunity(opp.id, db, user)


@router.get("/{opportunity_id}/requirements", response_model=list[RequirementRow])
def opportunity_requirements(opportunity_id: str, db: Session = Depends(get_db),
                             user: User = Depends(require_permission(Perm.REQUIREMENT_READ))):
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    reqs = list(db.scalars(select(Requirement).where(Requirement.opportunity_id == opp.id)
                           .order_by(Requirement.code)).unique())
    tasks = {t.requirement_id: t for t in db.scalars(
        select(Task).where(Task.opportunity_id == opp.id, Task.status.in_(["pendiente", "en_progreso"]))).unique()}
    out = []
    for r in reqs:
        t = tasks.get(r.id)
        out.append(RequirementRow(
            id=r.id, code=r.code, text=r.text, req_type=r.req_type, mandatory=r.mandatory, scope=r.scope,
            lot={"id": r.lot.id, "number": r.lot.number, "description": r.lot.description} if r.lot else None,
            attribute=r.attribute, operator=r.operator, expected_value=r.expected_value, unit=r.unit,
            page=r.page, fragment=r.fragment, source_label=r.source_label, bases_version=r.bases_version,
            status=r.status, status_reason=r.status_reason, reviewer=_user_ref(r.reviewer),
            due_date=r.due_date, required_valid_until=r.required_valid_until, next_action=r.next_action,
            data_kind=r.data_kind, version=r.version,
            evidence=[EvidenceOut(
                id=e.id, document_id=e.document_id, document_code=e.document.code,
                document_title=e.document.title, document_valid_until=e.document.valid_until,
                page=e.page, fragment=e.fragment, decision=e.decision) for e in r.evidence],
            open_task={"id": t.id, "status": t.status, "assignee": t.assignee.full_name if t.assignee else None,
                       "due_date": t.due_date.isoformat() if t.due_date else None} if t else None,
        ))
    return out


@router.get("/{opportunity_id}/documents", response_model=list[DocumentOut])
def opportunity_documents(opportunity_id: str, db: Session = Depends(get_db),
                          user: User = Depends(require_permission(Perm.DOCUMENT_READ))):
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    product_ids = [v.product_id for v in db.scalars(
        select(Variant).join(Lot, Lot.proposed_variant_id == Variant.id).where(Lot.opportunity_id == opp.id))]
    linked_doc_ids = select(EvidenceLink.document_id).join(
        Requirement, EvidenceLink.requirement_id == Requirement.id).where(Requirement.opportunity_id == opp.id)
    docs = db.scalars(select(Document).where(
        Document.organization_id == user.organization_id,
        or_(Document.opportunity_id == opp.id, Document.product_id.in_(product_ids),
            Document.id.in_(linked_doc_ids)),
    ).order_by(Document.code)).unique()
    return [DocumentOut.model_validate(d) for d in docs]


def task_out(t: Task) -> TaskOut:
    return TaskOut(id=t.id, code=t.code, title=t.title, status=t.status, assignee=_user_ref(t.assignee),
                   due_date=t.due_date, opportunity_id=t.opportunity_id, requirement_id=t.requirement_id,
                   data_kind=t.data_kind)


@router.get("/{opportunity_id}/tasks", response_model=list[TaskOut])
def opportunity_tasks(opportunity_id: str, db: Session = Depends(get_db),
                      user: User = Depends(require_permission(Perm.TASK_READ))):
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    return [task_out(t) for t in db.scalars(
        select(Task).where(Task.opportunity_id == opp.id).order_by(Task.due_date.nullslast(), Task.code)).unique()]


@router.get("/{opportunity_id}/history", response_model=list[AuditOut])
def opportunity_history(opportunity_id: str, db: Session = Depends(get_db),
                        user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    ids = [opp.id]
    ids += list(db.scalars(select(Requirement.id).where(Requirement.opportunity_id == opp.id)))
    ids += list(db.scalars(select(Task.id).where(Task.opportunity_id == opp.id)))
    events = db.scalars(select(AuditEvent).where(
        AuditEvent.organization_id == user.organization_id, AuditEvent.resource_id.in_(ids))
        .order_by(AuditEvent.created_at.desc())).unique()
    return [AuditOut(id=e.id, actor=_user_ref(e.actor), action=e.action, resource_type=e.resource_type,
                     resource_id=e.resource_id, before=e.before, after=e.after,
                     correlation_id=e.correlation_id, created_at=e.created_at) for e in events]
