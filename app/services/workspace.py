"""Expediente de licitación (`BidWorkspace`): evaluación, decisión, aprobaciones segregadas y compuerta.

- `assess` corre el motor determinista sobre cada requisito comparable y guarda la afinidad; nunca cambia el
  estado de un requisito (eso lo decide una persona en la revisión).
- La aprobación técnica y la comercial las dan personas distintas, aunque alguien acumule los dos permisos.
- Cualquier evidencia vinculada o revisión de un requisito borra ambas aprobaciones (deben volver a darse sobre
  los datos actuales), marca el expediente desactualizado si había alguna y lo regresa a «preparación» si ya
  estaba listo para revisión final.
- «Listo para revisión final» exige decisión de participar, todos los obligatorios aplicables validados (o no
  aplicables justificados) con evidencia vigente y sin conflicto con el motor, y ambas aprobaciones al día. No es
  «listo para presentación»: la revisión final humana sigue siendo necesaria.
"""
from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import Perm, permissions_for
from app.models import BidWorkspace, MatchAssessment, Opportunity, Requirement
from app.models.base import new_id, utcnow
from app.services import audit
from app.services.affinity import Affinity, check_validity, compute_affinity, serialize_affinity
from app.services.matching import ENGINE_VERSION, RuleResult, evaluate, spec_from_requirement, variant_attributes

PHASE_ANALYSIS = "analisis"
PHASE_PREPARATION = "preparacion"
PHASE_READY = "listo_revision_final"
PHASE_DISCARDED = "descartada"
DECISIONS = ("participar", "no_participar")

_APPROVAL_FIELDS = ("technical_approval_by_id", "technical_approval_at",
                    "commercial_approval_by_id", "commercial_approval_at")


def find_workspace(db: Session, opportunity_id: str) -> BidWorkspace | None:
    return db.scalars(select(BidWorkspace).where(BidWorkspace.opportunity_id == opportunity_id)).first()


def get_or_create_workspace(db: Session, opportunity: Opportunity) -> BidWorkspace:
    """El expediente de la oportunidad; se crea si no existe (sin duplicar ante dos solicitudes simultáneas)."""
    ws = find_workspace(db, opportunity.id)
    if ws is not None:
        return ws
    insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    now = utcnow()
    db.execute(insert(BidWorkspace).values(
        id=new_id(), organization_id=opportunity.organization_id, opportunity_id=opportunity.id,
        decision="pendiente", approvals_stale=False, phase=PHASE_ANALYSIS, version=1,
        created_at=now, updated_at=now,
    ).on_conflict_do_nothing(index_elements=["opportunity_id"]))
    return find_workspace(db, opportunity.id)


def on_requirement_change(db: Session, requirement, actor_id: str | None) -> dict | None:
    """Invalida las aprobaciones del expediente tras un cambio en uno de sus requisitos.

    Devuelve lo que cambió en el expediente (para la bitácora del requisito) o `None` si no hay expediente. Si
    había aprobaciones, su anulación queda además como evento propio (`workspace.approvals_invalidated`).
    """
    ws = find_workspace(db, requirement.opportunity_id)
    if ws is None:
        return None
    lock_workspace(db, ws)
    before = audit.snapshot(ws, [*_APPROVAL_FIELDS, "approvals_stale", "phase"])
    had_approvals = bool(ws.technical_approval_by_id or ws.commercial_approval_by_id)
    was_ready = ws.phase == PHASE_READY
    for f in _APPROVAL_FIELDS:
        setattr(ws, f, None)
    if had_approvals or was_ready:
        ws.approvals_stale = True
    if was_ready:
        ws.phase = PHASE_PREPARATION
    ws.version += 1
    refresh_affinity(db, ws)
    if had_approvals or was_ready:
        audit.record(db, organization_id=ws.organization_id, actor_id=actor_id,
                     action="workspace.approvals_invalidated", resource_type="bid_workspace", resource_id=ws.id,
                     before=before, after={**audit.snapshot(ws, [*_APPROVAL_FIELDS, "approvals_stale", "phase"]),
                                           "requirement_id": requirement.id, "requirement_code": requirement.code})
    return {"workspace_id": ws.id, "approvals_cleared": had_approvals, "approvals_stale": ws.approvals_stale,
            "phase": ws.phase}


# ── Evaluación (motor determinista + afinidad) ───────────────────────────────

def _require(user, *perms: Perm) -> None:
    have = permissions_for(user.role_names)
    if not any(p in have for p in perms):
        raise AppError(403, "forbidden", f"Tu rol no tiene el permiso {' o '.join(p.value for p in perms)}")


def _requirements(db: Session, opportunity_id: str) -> list[Requirement]:
    return list(db.scalars(select(Requirement).where(Requirement.opportunity_id == opportunity_id)
                           .order_by(Requirement.code)).unique())


def _assessments(db: Session, opportunity_id: str) -> list[MatchAssessment]:
    return list(db.scalars(select(MatchAssessment).where(MatchAssessment.opportunity_id == opportunity_id)))


def refresh_affinity(db: Session, ws: BidWorkspace) -> None:
    """Recalcula la afinidad guardada con los estados y evaluaciones actuales (sin volver a evaluar)."""
    if ws.affinity is None:
        return
    db.flush()
    opportunity = db.get(Opportunity, ws.opportunity_id)
    ws.affinity = serialize_affinity(compute_affinity(
        opportunity, _requirements(db, opportunity.id), _assessments(db, opportunity.id)))


def assess(db: Session, user, opportunity: Opportunity) -> Affinity:
    """Evalúa cada requisito comparable contra la variante propuesta de su partida y guarda la afinidad.

    Reemplaza las evaluaciones anteriores de la oportunidad. No cambia el estado de ningún requisito.
    """
    _require(user, Perm.OPPORTUNITY_WRITE, Perm.REQUIREMENT_REVIEW)
    ws = get_or_create_workspace(db, opportunity)
    reqs = _requirements(db, opportunity.id)
    db.execute(delete(MatchAssessment).where(MatchAssessment.opportunity_id == opportunity.id)
               .execution_options(synchronize_session=False))
    rows: list[MatchAssessment] = []
    for r in reqs:
        spec = spec_from_requirement(r)
        if spec is None or r.lot is None:
            continue
        variant = r.lot.proposed_variant
        if variant is None:
            result = RuleResult("desconocido", "La partida no tiene variante propuesta: no hay con qué comparar y no "
                                "se infiere cumplimiento.", "sin_variante_propuesta", None, None)
        else:
            result = evaluate(spec, variant_attributes(variant))
        row = MatchAssessment(id=new_id(), organization_id=opportunity.organization_id,
                              opportunity_id=opportunity.id, lot_id=r.lot_id,
                              variant_id=variant.id if variant else None, requirement_id=r.id,
                              result=result.result, explanation=result.explanation, rule=result.rule,
                              engine_version=ENGINE_VERSION, catalog_value=result.catalog_value,
                              source_text=result.source_text)
        db.add(row)
        rows.append(row)
    db.flush()
    affinity = compute_affinity(opportunity, reqs, rows)
    before = {"assessed": ws.affinity is not None, "total": (ws.affinity or {}).get("total"),
              "blocking": (ws.affinity or {}).get("blocking")}
    ws.affinity = serialize_affinity(affinity)
    ws.version += 1
    audit.record(db, organization_id=opportunity.organization_id, actor_id=user.id, action="workspace.assess",
                 resource_type="bid_workspace", resource_id=ws.id, before=before,
                 after={"engine_version": ENGINE_VERSION, "assessments": len(rows),
                        "results": dict(Counter(r.result for r in rows)), "affinity": ws.affinity})
    return affinity


# ── Decisión, aprobaciones y compuerta ───────────────────────────────────────

_DECISION_FIELDS = ["decision", "decision_by_id", "decision_at", "decision_reason", "phase"]
_APPROVAL_KINDS = {"tecnica": ("technical", Perm.REQUIREMENT_REVIEW, "commercial"),
                   "comercial": ("commercial", Perm.PRICING_APPROVE, "technical")}
_STATUS_LABELS = {"pendiente": "Pendiente", "desconocido": "Desconocido", "faltante": "Faltante",
                  "vencido": "Vencido", "incumple": "Incumple", "en_revision": "En revisión"}


def lock_workspace(db: Session, ws: BidWorkspace) -> None:
    """Bloquea la fila del expediente (Postgres) y la relee antes de decidir o aprobar: dos solicitudes simultáneas
    de la misma persona no pueden dejarle las dos aprobaciones. En SQLite no hay FOR UPDATE."""
    db.execute(select(BidWorkspace.id).where(BidWorkspace.id == ws.id).with_for_update())
    db.refresh(ws)


def decide(db: Session, user, ws: BidWorkspace, decision: str, reason: str) -> BidWorkspace:
    """Decisión de participar o no, con motivo. Participar abre la preparación del expediente."""
    _require(user, Perm.BID_DECIDE)
    reason = (reason or "").strip()
    if not reason:
        raise AppError(422, "reason_required", "Indica el motivo de la decisión.")
    if decision not in DECISIONS:
        raise AppError(422, "invalid_decision", "La decisión debe ser participar o no_participar.")
    lock_workspace(db, ws)
    before = audit.snapshot(ws, _DECISION_FIELDS)
    ws.decision, ws.decision_by_id, ws.decision_at, ws.decision_reason = decision, user.id, utcnow(), reason
    ws.phase = PHASE_PREPARATION if decision == "participar" else PHASE_DISCARDED
    ws.version += 1
    audit.record(db, organization_id=ws.organization_id, actor_id=user.id, action="workspace.decision",
                 resource_type="bid_workspace", resource_id=ws.id, before=before,
                 after=audit.snapshot(ws, _DECISION_FIELDS))
    return ws


def approve(db: Session, user, ws: BidWorkspace, kind: str) -> BidWorkspace:
    """Aprobación técnica (`requirement.review`) o comercial (`pricing.approve`). Nunca las dos la misma persona."""
    if kind not in _APPROVAL_KINDS:
        raise AppError(422, "invalid_kind", "La aprobación debe ser tecnica o comercial.")
    mine, perm, other = _APPROVAL_KINDS[kind]
    _require(user, perm)
    lock_workspace(db, ws)
    if getattr(ws, f"{other}_approval_by_id") == user.id:
        raise AppError(403, "segregation", "La aprobación técnica y la comercial deben darlas personas distintas; "
                                           "tú ya diste la otra.")
    before = audit.snapshot(ws, [*_APPROVAL_FIELDS, "approvals_stale"])
    setattr(ws, f"{mine}_approval_by_id", user.id)
    setattr(ws, f"{mine}_approval_at", utcnow())
    ws.approvals_stale = False
    ws.version += 1
    audit.record(db, organization_id=ws.organization_id, actor_id=user.id, action="workspace.approval",
                 resource_type="bid_workspace", resource_id=ws.id, before=before,
                 after={**audit.snapshot(ws, [*_APPROVAL_FIELDS, "approvals_stale"]), "kind": kind})
    return ws


def readiness_blockers(db: Session, ws: BidWorkspace) -> list[dict]:
    """Lo que impide marcar el expediente «listo para revisión final» (task pack §10, US06)."""
    from app.services import review  # review importa este módulo

    items: list[dict] = []
    if ws.decision != "participar":
        items.append({"code": "decision", "kind": "decision",
                      "message": "Falta la decisión de participar del responsable comercial."})
    reqs = _requirements(db, ws.opportunity_id)
    by_req = {a.requirement_id: a for a in _assessments(db, ws.opportunity_id)}
    today = review.today_mx()
    for r in reqs:
        if r.mandatory is False or r.status == "no_aplica_justificado":
            continue
        code = r.code or r.id
        if r.status != "cumple_validado":
            if r.mandatory is None:
                message = "Obligatoriedad no determinable en las bases: una persona debe decidir si aplica."
            else:
                message = (f"Obligatorio en estado «{_STATUS_LABELS.get(r.status, r.status)}»: debe quedar "
                           "validado o justificado como no aplicable.")
            if getattr(by_req.get(r.id), "result", None) == "incumple":
                message += " El motor indica que la variante propuesta no lo cumple."
            items.append({"code": code, "kind": "requisito", "status": r.status, "message": message})
            continue
        by = review.required_by(db, r)
        expired = [e for e in r.evidence if e.decision == "aceptada"
                   and check_validity(e.document.valid_until, by, today) in review.EXPIRED]
        if expired:
            items.append({"code": code, "kind": "vigencia", "status": r.status,
                          "message": "La evidencia validada venció o vence antes de la fecha exigida."})
        elif getattr(by_req.get(r.id), "result", None) == "incumple":
            items.append({"code": code, "kind": "conflicto", "status": r.status,
                          "message": "Validado, pero la evaluación objetiva del catálogo indica que incumple."})
    if not ws.technical_approval_by_id:
        items.append({"code": "aprobacion_tecnica", "kind": "aprobacion", "message": "Falta la aprobación técnica."})
    if not ws.commercial_approval_by_id:
        items.append({"code": "aprobacion_comercial", "kind": "aprobacion",
                      "message": "Falta la aprobación comercial."})
    if ws.approvals_stale:
        items.append({"code": "aprobaciones_desactualizadas", "kind": "aprobacion",
                      "message": "Las aprobaciones anteriores quedaron sin efecto por un cambio posterior."})
    return items


def mark_ready(db: Session, user, ws: BidWorkspace) -> BidWorkspace:
    """Marca el expediente listo para la revisión final humana; nunca «listo para presentación»."""
    _require(user, Perm.BID_DECIDE)
    lock_workspace(db, ws)
    items = readiness_blockers(db, ws)
    if items:
        raise AppError(409, "not_ready", "El expediente aún no puede pasar a revisión final.",
                       {"blockers": [i["code"] for i in items], "items": items})
    before = audit.snapshot(ws, ["phase", "version"])
    ws.phase = PHASE_READY
    ws.version += 1
    audit.record(db, organization_id=ws.organization_id, actor_id=user.id, action="workspace.ready",
                 resource_type="bid_workspace", resource_id=ws.id, before=before,
                 after={**audit.snapshot(ws, ["phase", "version", "technical_approval_by_id",
                                              "commercial_approval_by_id", "decision"])})
    return ws
