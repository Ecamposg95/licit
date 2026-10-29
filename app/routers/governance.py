"""Gobierno corporativo: integridad de la bitácora, matriz de permisos y quién aprobó qué."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import ROLE_LABELS, ROLE_PERMISSIONS, Perm, Role, require_permission
from app.core.tenant import get_owned
from app.models import (
    AuditEvent, BidWorkspace, DemoRun, GeneratedArtifact, Opportunity, Requirement, User,
)
from app.schemas.governance import (
    PERMISSION_LABELS_ES, ApprovalOut, ApprovalTarget, DemoRunOut, IntegrityResult, PermissionLabel,
    PermissionMatrix, RolePermissions, RoleRef,
)
from app.schemas.v1 import UserRef
from app.services import audit
from app.services.demo_seed import current_demo_run_id

router = APIRouter(prefix="/api/v1", tags=["gobierno"])

# Eventos que muestran «quién aprobó qué». Los emiten E (revisión, decisión, aprobaciones) y F (descarga).
APPROVAL_ACTIONS = (
    "requirement.review", "workspace.decision", "workspace.approval", "workspace.ready", "artifact.download",
)
_APPROVALS_LIMIT = 200

_REASON_KEYS = ("reason", "decision_reason", "motivo", "status_reason")
_OUTCOME_KEYS = ("decision", "status", "kind", "phase", "filename")
_WORKSPACE_TYPES = {"bid_workspace", "workspace"}
_ARTIFACT_TYPES = {"generated_artifact", "artifact"}


# ── Integridad ───────────────────────────────────────────────────────────────

@router.get("/governance/audit/verify", response_model=IntegrityResult)
def verify_audit_chain(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.AUDIT_READ))):
    """Recalcula la cadena SHA-256 de la bitácora de la organización y deja constancia de la verificación."""
    ok, checked, first_broken_id = audit.verify_chain(db, user.organization_id)
    verified_at = datetime.now(timezone.utc)
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="audit.verify",
                 resource_type="organization", resource_id=user.organization_id,
                 after={"ok": ok, "checked": checked, "first_broken_id": first_broken_id})
    db.commit()
    return IntegrityResult(ok=ok, checked=checked, first_broken_id=first_broken_id, verified_at=verified_at)


# ── Matriz de roles y permisos ───────────────────────────────────────────────

@router.get("/governance/permissions", response_model=PermissionMatrix)
def permissions_matrix(user: User = Depends(require_permission(Perm.AUDIT_READ))):
    """La matriz tal como la aplica el backend: sale de `ROLE_PERMISSIONS`, no de una copia."""
    return PermissionMatrix(
        roles=[RolePermissions(role=role.value, label=ROLE_LABELS[role],
                               permissions=sorted(p.value for p in ROLE_PERMISSIONS[role]))
               for role in Role],
        permissions=[PermissionLabel(code=p.value, label_es=PERMISSION_LABELS_ES[p]) for p in Perm],
    )


# ── Decisiones y aprobaciones ────────────────────────────────────────────────

def _first_text(*sources: dict | None, keys: tuple[str, ...]) -> str | None:
    for source in sources:
        for key in keys:
            value = (source or {}).get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _roles(user: User | None) -> list[RoleRef]:
    if user is None:
        return []
    out = []
    for name in user.role_names:
        try:
            role = Role(name)
        except ValueError:
            continue
        out.append(RoleRef(role=role.value, label=ROLE_LABELS[role]))
    return out


def _targets(db: Session, org_id: str, events: list[AuditEvent]) -> dict[str, ApprovalTarget]:
    """Procedimiento (y requisito) sobre el que se decidió, en consultas por lote."""
    ids: dict[str, set[str]] = {"requirement": set(), "workspace": set(), "artifact": set(), "opportunity": set()}
    for e in events:
        if not e.resource_id:
            continue
        if e.resource_type == "requirement":
            ids["requirement"].add(e.resource_id)
        elif e.resource_type in _WORKSPACE_TYPES:
            ids["workspace"].add(e.resource_id)
        elif e.resource_type in _ARTIFACT_TYPES:
            ids["artifact"].add(e.resource_id)
        elif e.resource_type == "opportunity":
            ids["opportunity"].add(e.resource_id)

    def lookup(model, wanted: set[str], *columns):
        if not wanted:
            return {}
        rows = db.execute(select(model.id, *columns).where(model.organization_id == org_id, model.id.in_(wanted)))
        return {row[0]: row[1:] for row in rows}

    requirements = lookup(Requirement, ids["requirement"], Requirement.code, Requirement.opportunity_id)
    workspaces = lookup(BidWorkspace, ids["workspace"], BidWorkspace.opportunity_id)
    artifacts = lookup(GeneratedArtifact, ids["artifact"], GeneratedArtifact.opportunity_id)

    def opportunity_of(e: AuditEvent) -> tuple[str | None, str | None]:
        """(id de la oportunidad, código del requisito)."""
        rid = e.resource_id
        if e.resource_type == "requirement" and rid in requirements:
            code, opp_id = requirements[rid]
            return opp_id, code
        if e.resource_type in _WORKSPACE_TYPES and rid in workspaces:
            return workspaces[rid][0], None
        if e.resource_type in _ARTIFACT_TYPES and rid in artifacts:
            return artifacts[rid][0], None
        if e.resource_type == "opportunity":
            return rid, None
        # Si el evento mismo cita la oportunidad, se usa; si no, no se adivina.
        cited = (e.after or {}).get("opportunity_id") or (e.before or {}).get("opportunity_id")
        return (cited if isinstance(cited, str) else None), None

    resolved = {e.id: opportunity_of(e) for e in events}
    opp_ids = {opp_id for opp_id, _ in resolved.values() if opp_id}
    opportunities = lookup(Opportunity, opp_ids, Opportunity.external_id, Opportunity.title, Opportunity.data_kind)

    out: dict[str, ApprovalTarget] = {}
    for e in events:
        opp_id, req_code = resolved[e.id]
        if opp_id is None and req_code is None:
            continue
        external_id, title, data_kind = opportunities.get(opp_id, (None, None, None))
        out[e.id] = ApprovalTarget(opportunity_id=opp_id, opportunity_external_id=external_id,
                                   opportunity_title=title, requirement_code=req_code, data_kind=data_kind)
    return out


@router.get("/governance/approvals", response_model=list[ApprovalOut])
def approvals(demo_run_id: str | None = Query(None, description="Corrida demo; por omisión, la actual"),
              db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.AUDIT_READ))):
    """Decisiones y aprobaciones de una corrida demo, de la más reciente a la más antigua."""
    if demo_run_id is None:
        run_id = current_demo_run_id(db, user.organization_id)
    else:
        run_id = get_owned(db, DemoRun, demo_run_id, user, "Corrida demo").id
    stmt = select(AuditEvent).where(AuditEvent.organization_id == user.organization_id,
                                    AuditEvent.action.in_(APPROVAL_ACTIONS))
    stmt = stmt.where(AuditEvent.demo_run_id == run_id if run_id else AuditEvent.demo_run_id.is_(None))
    events = list(db.scalars(stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                             .limit(_APPROVALS_LIMIT)).unique())
    targets = _targets(db, user.organization_id, events)
    return [
        ApprovalOut(
            id=e.id, action=e.action, created_at=e.created_at,
            actor=UserRef.model_validate(e.actor) if e.actor else None, roles=_roles(e.actor),
            resource_type=e.resource_type, resource_id=e.resource_id, target=targets.get(e.id),
            reason=_first_text(e.after, e.before, keys=_REASON_KEYS),
            outcome=_first_text(e.after, keys=_OUTCOME_KEYS),
            before=e.before, after=e.after, demo_run_id=e.demo_run_id,
        )
        for e in events
    ]


@router.get("/governance/runs", response_model=list[DemoRunOut])
def demo_runs(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.AUDIT_READ))):
    """Corridas demo (cada reinicio abre una), de la más reciente a la más antigua, con su resumen."""
    org_id = user.organization_id
    runs = list(db.scalars(select(DemoRun).where(DemoRun.organization_id == org_id)
                           .order_by(DemoRun.started_at.desc(), DemoRun.id.desc())))
    rows = db.execute(
        select(AuditEvent.demo_run_id, func.count(),
               func.sum(case((AuditEvent.action.in_(APPROVAL_ACTIONS), 1), else_=0)))
        .where(AuditEvent.organization_id == org_id).group_by(AuditEvent.demo_run_id))
    counts = {run_id: (total, int(approved or 0)) for run_id, total, approved in rows}
    actors = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.actor_id for r in runs if r.actor_id})))}
    return [
        DemoRunOut(
            id=r.id, started_at=r.started_at, summary=r.summary, is_current=i == 0,
            actor=UserRef.model_validate(actors[r.actor_id]) if r.actor_id in actors else None,
            events=counts.get(r.id, (0, 0))[0], approvals=counts.get(r.id, (0, 0))[1],
        )
        for i, r in enumerate(runs)
    ]
