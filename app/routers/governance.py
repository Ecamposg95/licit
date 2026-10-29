"""Gobierno corporativo: integridad de la bitácora, matriz de permisos y quién aprobó qué."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import ROLE_LABELS, ROLE_PERMISSIONS, Perm, Role, permissions_for, require_permission
from app.core.security import get_current_user, is_expired
from app.core.tenant import get_owned
from app.models import (
    AuditEvent, BidWorkspace, DemoRun, GeneratedArtifact, Opportunity, Requirement, User,
)
from app.routers.opportunities import _open_counts, _row
from app.schemas.governance import (
    PERMISSION_LABELS_ES, ApprovalOut, ApprovalTarget, DemoAccount, DemoRunOut, DirectionDashboard,
    IntegrityResult, OpsStatus, PermissionLabel, PermissionMatrix, RolePermissions, RoleRef,
)
from app.schemas.v1 import OpportunityRow, UserRef
from app.services import audit, dashboard
from app.services.demo_seed import DEMO_USERS, current_demo_run_id

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
    """Recalcula la cadena SHA-256 de la bitácora de la organización y deja constancia de la verificación.

    Detecta eventos modificados o borrados en medio de la cadena. No detecta que se hayan borrado los más
    recientes ni que quien escribe en la base recalcule todos los hashes: por eso se devuelve el último hash
    verificado, para anclarlo fuera de la base de datos.
    """
    org_id = user.organization_id
    ok, checked, first_broken_id = audit.verify_chain(db, org_id)
    verified_at = datetime.now(timezone.utc)
    last_hash = last_event_at = None
    if ok and checked:
        # El evento número `checked` en el mismo orden de la verificación: coincide con lo revisado aunque
        # otro proceso agregue eventos mientras tanto.
        head = db.execute(select(AuditEvent.hash, AuditEvent.created_at).where(AuditEvent.organization_id == org_id)
                          .order_by(AuditEvent.created_at, AuditEvent.id).offset(checked - 1).limit(1)).first()
        if head is not None:
            last_hash, last_event_at = head.hash, head.created_at
    audit.record(db, organization_id=org_id, actor_id=user.id, action="audit.verify",
                 resource_type="organization", resource_id=org_id,
                 after={"ok": ok, "checked": checked, "first_broken_id": first_broken_id, "last_hash": last_hash})
    db.commit()
    return IntegrityResult(ok=ok, checked=checked, first_broken_id=first_broken_id, verified_at=verified_at,
                           last_hash=last_hash, last_event_at=last_event_at)


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
            # Solo `after`: la decisión muestra su propio motivo, nunca el del estado anterior.
            reason=_first_text(e.after, keys=_REASON_KEYS),
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


# ── Cuentas demo ─────────────────────────────────────────────────────────────

DEMO_EMAIL_DOMAIN = "@dipromedic.example"


@router.get("/demo/accounts", response_model=list[DemoAccount])
def demo_accounts(db: Session = Depends(get_db)):
    """Cuentas que el selector del demo puede ofrecer. Sin autenticación y solo con DEMO_MODE.

    Publica únicamente correo, nombre y etiquetas de rol de las cuentas demo activas y vigentes:
    nunca contraseñas, hashes ni identificadores. La contraseña la teclea quien presenta.
    """
    if not config.DEMO_MODE:
        raise AppError(404, "not_found", "Ruta no encontrada")
    users = [u for u in db.scalars(select(User).where(User.is_active.is_(True),
                                                      User.email.like(f"%{DEMO_EMAIL_DOMAIN}")))
             if not is_expired(u)]
    order = {email: i for i, (email, *_rest) in enumerate(DEMO_USERS)}
    users.sort(key=lambda u: (order.get(u.email, len(order)), u.email))
    return [DemoAccount(email=u.email, full_name=u.full_name,
                        roles=[r.label for r in _roles(u)]) for u in users]


# ── Panel de dirección ───────────────────────────────────────────────────────

@router.get("/dashboard/direccion", response_model=DirectionDashboard)
def direction_dashboard(db: Session = Depends(get_db),
                        user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    """Cartera separada por tipo de dato. No hay total combinado: sumar REAL con SYNTHETIC sería engañoso."""
    now = datetime.now(timezone.utc)
    data = dashboard.direccion(db, user.organization_id, now)
    upcoming = data["upcoming_real"]
    counts = _open_counts(db, [o.id for o in upcoming])
    return DirectionDashboard(
        by_data_kind=data["by_data_kind"],
        upcoming_real=[OpportunityRow(**_row(o, counts.get(o.id, 0), now)) for o in upcoming],
        last_search=data["last_search"],
        scenarios_at_risk=data["scenarios_at_risk"],
    )


# ── Estado operativo (TI) ────────────────────────────────────────────────────

def require_any_permission(*perms: Perm):
    def checker(user: User = Depends(get_current_user)):
        have = permissions_for(user.role_names)
        if not any(p in have for p in perms):
            raise AppError(403, "forbidden", "Tu rol no tiene ninguno de los permisos requeridos: "
                           + ", ".join(p.value for p in perms))
        return user

    return checker


@router.get("/ops/status", response_model=OpsStatus)
def ops_status(db: Session = Depends(get_db),
               user: User = Depends(require_any_permission(Perm.SOURCE_MANAGE, Perm.AUDIT_READ))):
    """Versión desplegada, esquema, almacenamiento, worker, fuentes y trabajos recientes. Solo hechos, sin secretos."""
    return OpsStatus.model_validate(dashboard.ops_status(db, user.organization_id))
