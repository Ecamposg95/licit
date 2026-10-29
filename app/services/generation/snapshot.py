"""Instantánea versionada del expediente (F1).

`build_snapshot` lee la base de datos y produce un dict JSON nativo (los montos son texto Decimal) con todo lo que
necesitan las plantillas. Es una función de solo lectura: no crea registros. `data_version` es el SHA-256 del JSON
canónico sin `generated_at`, así que dos instantáneas seguidas sin cambios de datos tienen la misma versión.
La aritmética se hace aquí, con `Decimal`, y nunca en las plantillas ni con un modelo de lenguaje.
"""
import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import config
from app.models import (
    BidWorkspace, DataKind, Document, EvidenceLink, Lot, MatchAssessment, Opportunity, Requirement,
    RequirementStatus, Task, User, Variant,
)
from app.models.base import utcnow
from app.services.generation.formatting import money

CENT = Decimal("0.01")
CLOSED_STATUSES = {RequirementStatus.CUMPLE_VALIDADO.value, RequirementStatus.NO_APLICA_JUSTIFICADO.value}
OPEN_TASK_STATUSES = ("pendiente", "en_progreso")

FISCAL = {"status": "pendiente",
          "text": "Tratamiento fiscal pendiente de configurar; no se aplicaron impuestos."}

CATALOG_CREDIT = "Contenido de catálogo: DIPROMEDIC S.A. DE C.V. · www.dipromedic.com · consultado el {checked_on}"


def line_subtotal(quantity: Decimal | None, unit_price: Decimal | None) -> Decimal | None:
    """cantidad × precio unitario, a centavos (mitad hacia arriba); None si falta alguno."""
    if quantity is None or unit_price is None:
        return None
    return (quantity * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)


# ── Utilidades ───────────────────────────────────────────────────────────────

def _iso_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:           # SQLite devuelve sin zona lo que se guardó en UTC
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _natural(text: str) -> list:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text or "")]


def _dec(value) -> str | None:
    return None if value is None else str(Decimal(value))


def compute_data_version(body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Bloques ──────────────────────────────────────────────────────────────────

def _opportunity_block(opp: Opportunity) -> dict:
    return {
        "id": opp.id, "external_id": opp.external_id, "title": opp.title, "buyer": opp.buyer,
        "buying_unit": opp.buying_unit, "state": opp.state, "procedure_type": opp.procedure_type,
        "character": opp.character, "families": list(opp.families or []), "data_kind": opp.data_kind,
        "source": {"key": opp.source.key, "name": opp.source.name} if opp.source else None,
        "source_url": opp.source_url, "last_checked_at": _iso_dt(opp.last_checked_at),
        "reported_status": opp.reported_status, "verification_status": opp.verification_status,
        "verification_scope": opp.verification_scope, "result": opp.result,
        "questions_at": _iso_dt(opp.questions_at), "submission_at": _iso_dt(opp.submission_at),
        "submission_precision": opp.submission_precision, "ruling_at": _iso_dt(opp.ruling_at),
        "source_timezone": opp.source_timezone, "timezone_assumed": bool(opp.timezone_assumed),
        "estimated_amount": _dec(opp.estimated_amount), "currency": opp.currency,
        "requires_human_review": bool(opp.requires_human_review),
        "owner": opp.owner.full_name if opp.owner else None,
    }


def _variant_block(variant: Variant | None) -> dict | None:
    if variant is None:
        return None
    product = variant.product
    block = {
        "id": variant.id, "sku": variant.sku, "name": variant.name, "data_kind": variant.data_kind,
        "unit": variant.unit, "attributes": variant.attributes or {},
        "regulatory_reference": variant.regulatory_reference, "review_status": variant.review_status,
        "product": {
            "name": product.name, "family": product.family, "brand": product.brand,
            "manufacturer": product.manufacturer, "source_url": product.source_url,
            "checked_on": _iso_date(product.checked_on),
        } if product else None,
        "catalog_credit": None,
    }
    if variant.data_kind == DataKind.REAL.value and product is not None:
        checked = _iso_date(product.checked_on)
        block["catalog_credit"] = CATALOG_CREDIT.format(checked_on=checked or "[PENDIENTE: fecha de consulta]")
    return block


def _price(lot: Lot) -> dict:
    """Precio unitario de la partida y su procedencia.

    1) El precio propio de la partida con su `price_data_kind` declarado.
    2) Sin precio propio, el precio de la variante propuesta, solo si es SYNTHETIC (catálogo ficticio).
       Una variante REAL no se usa aunque tuviera precio: el catálogo público no publica precios.
    """
    variant = lot.proposed_variant
    if lot.unit_price is not None:
        return {"unit_price": lot.unit_price, "currency": lot.currency or (variant.currency if variant else None),
                "price_data_kind": lot.price_data_kind, "price_source": "partida"}
    if variant is not None and variant.price is not None and variant.data_kind == DataKind.SYNTHETIC.value:
        return {"unit_price": variant.price, "currency": variant.currency or lot.currency,
                "price_data_kind": DataKind.SYNTHETIC.value, "price_source": "variante"}
    return {"unit_price": None, "currency": lot.currency, "price_data_kind": None, "price_source": None}


def _assessment_block(a: MatchAssessment) -> dict:
    return {"lot_id": a.lot_id, "requirement_id": a.requirement_id, "variant_id": a.variant_id, "result": a.result,
            "explanation": a.explanation, "rule": a.rule, "engine_version": a.engine_version,
            "catalog_value": a.catalog_value, "source_text": a.source_text}


def _lots_block(opp: Opportunity, assessments: list[MatchAssessment]) -> tuple[list[dict], list[str]]:
    out, warnings = [], []
    for lot in sorted(opp.lots, key=lambda l: _natural(l.number)):
        price = _price(lot)
        subtotal = None
        if price["unit_price"] is None:
            warnings.append(f"Partida {lot.number}: precio pendiente")
        elif price["currency"] is None:
            warnings.append(f"Partida {lot.number}: moneda pendiente")
        elif lot.quantity is None:
            warnings.append(f"Partida {lot.number}: cantidad pendiente")
        else:
            subtotal = line_subtotal(lot.quantity, price["unit_price"])
        if price["unit_price"] is not None and price["price_data_kind"] is None:
            warnings.append(f"Partida {lot.number}: precio sin procedencia declarada")
        if lot.proposed_variant is None:
            warnings.append(f"Partida {lot.number}: sin variante propuesta")
        out.append({
            "id": lot.id, "number": lot.number, "description": lot.description, "family": lot.family,
            "quantity": _dec(lot.quantity), "unit": lot.unit, "specs": lot.specs or {},
            "variant": _variant_block(lot.proposed_variant),
            "unit_price": _dec(price["unit_price"]), "currency": price["currency"],
            "price_data_kind": price["price_data_kind"], "price_source": price["price_source"],
            "subtotal": _dec(subtotal),
            "assessments": [_assessment_block(a) for a in assessments
                            if a.lot_id == lot.id and a.requirement_id is None],
        })
    return out, warnings


def _totals(lots: list[dict]) -> dict:
    by_currency: dict[str, Decimal] = {}
    priced, pending = 0, []
    for lot in lots:
        if lot["subtotal"] is None:
            pending.append(lot["number"])
            continue
        priced += 1
        by_currency[lot["currency"]] = by_currency.get(lot["currency"], Decimal("0.00")) + Decimal(lot["subtotal"])
    complete = bool(lots) and not pending and len(by_currency) == 1
    currency = next(iter(by_currency)) if len(by_currency) == 1 else None
    known = by_currency[currency] if currency else None
    if not lots:
        text = "Total no calculable: el procedimiento no tiene partidas capturadas"
    elif len(by_currency) > 1:
        parts = "; ".join(money(v, c) for c, v in sorted(by_currency.items()))
        text = f"Monedas mezcladas ({parts}): no se calcula un total único"
    elif not by_currency:
        text = "Total no calculable: ninguna partida tiene precio"
    elif complete:
        text = f"Total: {money(known, currency)}"
    else:
        text = (f"Total parcial: {money(known, currency)} (solo {priced} de {len(lots)} partidas con precio; "
                f"faltan las partidas {', '.join(pending)})")
    return {
        "currency": currency, "known_total": str(known) if known is not None else None,
        "by_currency": {c: str(v) for c, v in sorted(by_currency.items())},
        "lots_total": len(lots), "lots_priced": priced, "lots_pending": len(pending), "pending_lots": pending,
        "complete": complete,
        "has_synthetic_prices": any(l["price_data_kind"] == DataKind.SYNTHETIC.value and l["unit_price"] is not None
                                    for l in lots),
        "text": text,
    }


def _document_block(doc: Document) -> dict:
    version = next((v for v in doc.versions if v.version == doc.current_version), None)
    return {
        "id": doc.id, "code": doc.code, "title": doc.title, "doc_type": doc.doc_type, "scope": doc.scope,
        "data_kind": doc.data_kind, "review_status": doc.review_status, "valid_until": _iso_date(doc.valid_until),
        "current_version": doc.current_version, "third_party": bool(doc.third_party),
        "external_url": doc.external_url, "filename": version.filename if version else None,
        "sha256": version.sha256 if version else None, "has_file": bool(version and version.storage_key),
    }


def _documents(db: Session, opp: Opportunity, evidence_doc_ids: set[str]) -> list[Document]:
    """Los mismos documentos que ve el expediente: del procedimiento, de los productos propuestos o enlazados."""
    product_ids = {l.proposed_variant.product_id for l in opp.lots if l.proposed_variant is not None}
    conditions = [Document.opportunity_id == opp.id]
    if product_ids:
        conditions.append(Document.product_id.in_(product_ids))
    if evidence_doc_ids:
        conditions.append(Document.id.in_(evidence_doc_ids))
    docs = db.scalars(select(Document).where(Document.organization_id == opp.organization_id, or_(*conditions))).unique()
    return sorted(docs, key=lambda d: (d.code or "", d.title, d.id))


def _requirements_block(db: Session, opp: Opportunity, assessments: list[MatchAssessment]) -> tuple[list[dict], set]:
    reqs = sorted(db.scalars(select(Requirement).where(Requirement.opportunity_id == opp.id)).unique(),
                  key=lambda r: (r.code or "", r.id))
    tasks: dict[str, Task] = {}
    open_tasks = db.scalars(select(Task).where(Task.opportunity_id == opp.id, Task.status.in_(OPEN_TASK_STATUSES))
                            .order_by(Task.due_date.nullslast(), Task.code)).unique()
    for t in open_tasks:
        tasks.setdefault(t.requirement_id, t)
    out, doc_ids = [], set()
    for r in reqs:
        task = tasks.get(r.id)
        evidence = []
        for e in sorted(r.evidence, key=lambda e: (e.document.code or "", e.id)):
            doc_ids.add(e.document_id)
            evidence.append({
                "document_id": e.document_id, "document_code": e.document.code, "document_title": e.document.title,
                "document_data_kind": e.document.data_kind, "document_valid_until": _iso_date(e.document.valid_until),
                "third_party": bool(e.document.third_party), "decision": e.decision, "page": e.page,
                "fragment": e.fragment,
            })
        out.append({
            "id": r.id, "code": r.code, "text": r.text, "req_type": r.req_type, "mandatory": r.mandatory,
            "scope": r.scope, "lot": r.lot.number if r.lot else None, "attribute": r.attribute,
            "operator": r.operator, "expected_value": r.expected_value, "unit": r.unit, "page": r.page,
            "fragment": r.fragment, "source_label": r.source_label, "status": r.status,
            "status_reason": r.status_reason, "open": r.status not in CLOSED_STATUSES,
            "reviewer": r.reviewer.full_name if r.reviewer else None, "due_date": _iso_date(r.due_date),
            "required_valid_until": _iso_date(r.required_valid_until), "next_action": r.next_action,
            "data_kind": r.data_kind, "evidence": evidence,
            "open_task": {
                "code": task.code, "title": task.title, "status": task.status,
                "assignee": task.assignee.full_name if task.assignee else None, "due_date": _iso_date(task.due_date),
            } if task else None,
            "assessments": [_assessment_block(a) for a in assessments if a.requirement_id == r.id],
        })
    return out, doc_ids


def _workspace_block(db: Session, ws: BidWorkspace | None) -> dict | None:
    if ws is None:
        return None

    def approval(user_id, at):
        if not user_id and not at:
            return None
        user = db.get(User, user_id) if user_id else None
        return {"by": user.full_name if user else None, "at": _iso_dt(at)}

    return {
        "decision": ws.decision, "decision_reason": ws.decision_reason, "phase": ws.phase,
        "approvals_stale": bool(ws.approvals_stale),
        "technical_approval": approval(ws.technical_approval_by_id, ws.technical_approval_at),
        "commercial_approval": approval(ws.commercial_approval_by_id, ws.commercial_approval_at),
    }


def _affinity_block(ws: BidWorkspace | None) -> dict:
    """`bid_workspaces.affinity` es JSON opaco: {components, total, coverage_complete, blocking}."""
    raw = ws.affinity if ws is not None else None
    if not isinstance(raw, dict):
        return {"state": "no_calculada", "components": {}, "total": None, "coverage_complete": False, "blocking": []}
    return {"state": "calculada", "components": raw.get("components") or {}, "total": raw.get("total"),
            "coverage_complete": bool(raw.get("coverage_complete")), "blocking": list(raw.get("blocking") or [])}


def _warnings(opp: dict, lot_warnings: list[str], totals: dict, reqs: list[dict], affinity: dict,
              workspace: dict | None, has_assessments: bool) -> list[str]:
    warnings = list(lot_warnings)
    if not totals["lots_total"]:
        warnings.append("El procedimiento no tiene partidas capturadas")
    elif totals["lots_priced"] and not totals["complete"] and totals["currency"] is not None:
        warnings.append("Total parcial: solo suma las partidas con precio")
    if len(totals["by_currency"]) > 1:
        warnings.append("Monedas mezcladas: no se calcula un total único")
    if totals["has_synthetic_prices"]:
        warnings.append("Precios SIMULADOS (catálogo ficticio): no constituyen una cotización")
    open_reqs = [r for r in reqs if r["open"]]
    if not reqs:
        warnings.append("Sin requisitos capturados: no hay matriz de cumplimiento que evaluar")
    elif open_reqs:
        mandatory = sum(1 for r in open_reqs if r["mandatory"] is not False)
        warnings.append(f"{len(open_reqs)} requisito(s) abierto(s), {mandatory} obligatorio(s) o por determinar")
    if affinity["state"] == "no_calculada":
        warnings.append("Afinidad no calculada")
    elif affinity["total"] is None:
        warnings.append("Afinidad con cobertura incompleta: no hay total")
    if not has_assessments:
        warnings.append("Sin evaluación técnica")
    if workspace and workspace["approvals_stale"]:
        warnings.append("Las aprobaciones quedaron desactualizadas por cambios posteriores")
    if opp["submission_at"] is None:
        warnings.append("Fecha de presentación sin verificar")
    if opp["data_kind"] == DataKind.SYNTHETIC.value:
        warnings.append("Procedimiento ficticio (SYNTHETIC): no existe en ninguna fuente oficial")
    warnings.append(FISCAL["text"])
    return warnings


# ── Instantánea ──────────────────────────────────────────────────────────────

def build_snapshot(db: Session, opportunity: Opportunity, *, now: datetime | None = None) -> dict:
    """Instantánea de solo lectura del expediente de `opportunity` (JSON nativo)."""
    now = now or utcnow()
    assessments = list(db.scalars(select(MatchAssessment).where(
        MatchAssessment.opportunity_id == opportunity.id, MatchAssessment.organization_id == opportunity.organization_id
    ).order_by(MatchAssessment.lot_id, MatchAssessment.requirement_id, MatchAssessment.id)))
    ws = db.scalars(select(BidWorkspace).where(BidWorkspace.opportunity_id == opportunity.id)).first()

    opp_block = _opportunity_block(opportunity)
    lots, lot_warnings = _lots_block(opportunity, assessments)
    totals = _totals(lots)
    reqs, evidence_doc_ids = _requirements_block(db, opportunity, assessments)
    workspace = _workspace_block(db, ws)
    affinity = _affinity_block(ws)
    documents = [_document_block(d) for d in _documents(db, opportunity, evidence_doc_ids)]
    open_reqs = [r for r in reqs if r["open"]]

    body = {
        "opportunity": opp_block, "lots": lots, "requirements": reqs, "documents": documents,
        "workspace": workspace, "affinity": affinity, "totals": totals, "fiscal": dict(FISCAL),
        "open_requirements": len(open_reqs),
        "warnings": _warnings(opp_block, lot_warnings, totals, reqs, affinity, workspace, bool(assessments)),
        "notice": config.WATERMARK,
    }
    return {**body, "generated_at": _iso_dt(now), "data_version": compute_data_version(body)}
