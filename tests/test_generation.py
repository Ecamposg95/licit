"""Frente F · generación de borradores: instantánea exacta, plantillas DOCX, paquete ZIP y trabajo asíncrono."""
import hashlib
import io
import json
import re
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core import config
from app.core.database import SessionLocal
from app.models import (
    AuditEvent, BidWorkspace, DataKind, Document, GeneratedArtifact, Lot, MatchAssessment, Opportunity,
    Organization, Product, Requirement, Variant,
)
from app.services import audit
from app.services.generation.snapshot import FISCAL, build_snapshot, line_subtotal


# ── Escenario propio (no depende del re-sembrado de E) ───────────────────────

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def lic(db, code: str = "DEMO-LIC-001") -> Opportunity:
    return db.scalars(select(Opportunity).where(Opportunity.external_id == code)).one()


def set_lot_price(db, opp: Opportunity, number: str, price: str | None, kind: str | None = "SYNTHETIC",
                  currency: str | None = "MXN") -> Lot:
    lot = next(l for l in opp.lots if l.number == number)
    lot.unit_price = Decimal(price) if price is not None else None
    lot.currency = currency
    lot.price_data_kind = kind
    db.flush()
    return lot


def real_variant(db, org_id: str) -> Variant:
    """Variante REAL sin precio: el catálogo público no publica precios."""
    product = Product(organization_id=org_id, name="Placa real de prueba", family="Osteosíntesis",
                      data_kind="REAL", source_url="https://www.dipromedic.com/x", checked_on=date(2026, 10, 28))
    variant = Variant(organization_id=org_id, product=product, sku="DPM-TEST-1", name="Placa real 6 orificios",
                      unit="pieza", data_kind="REAL", attributes={"holes": {"values": [6], "unit": "orificios",
                                                                              "source_text": "6 orificios"}})
    db.add_all([product, variant])
    db.flush()
    return variant


def db_warnings(db) -> list[str]:
    return build_snapshot(db, lic(db))["warnings"]


def snapshot_of(db, code: str = "DEMO-LIC-001") -> dict:
    return build_snapshot(db, lic(db, code))


# ── F1 · instantánea y aritmética ────────────────────────────────────────────

def test_subtotal_exact():
    assert line_subtotal(Decimal("40"), Decimal("1500.00")) == Decimal("60000.00")
    assert str(line_subtotal(Decimal("40.000"), Decimal("1500.00"))) == "60000.00"
    # Redondeo comercial a centavos (mitad hacia arriba), sin errores de binario.
    assert line_subtotal(Decimal("3"), Decimal("0.125")) == Decimal("0.38")
    assert line_subtotal(Decimal("0.1"), Decimal("0.1")) == Decimal("0.01")
    assert line_subtotal(Decimal("3"), Decimal("33.335")) == Decimal("100.01")
    assert line_subtotal(None, Decimal("1")) is None
    assert line_subtotal(Decimal("1"), None) is None


def test_lot_price_beats_variant_price_and_is_exact(db):
    opp = lic(db)
    set_lot_price(db, opp, "1", "1500.00", "SYNTHETIC")
    snap = build_snapshot(db, opp)
    lot1 = next(l for l in snap["lots"] if l["number"] == "1")
    assert lot1["unit_price"] == "1500.00" and lot1["subtotal"] == "60000.00" and lot1["currency"] == "MXN"
    assert lot1["price_source"] == "partida"


def test_missing_price_warning_and_partial_total(db):
    opp = lic(db)
    # Partida 1: precio propio; partida 2: variante REAL (sin precio); partida 3: sin variante.
    set_lot_price(db, opp, "1", "1500.00", "SYNTHETIC")
    lot2 = next(l for l in opp.lots if l.number == "2")
    lot2.proposed_variant_id = real_variant(db, opp.organization_id).id
    lot3 = next(l for l in opp.lots if l.number == "3")
    lot3.proposed_variant_id = None
    db.flush()
    db.expire_all()
    snap = build_snapshot(db, lic(db))
    lots = {l["number"]: l for l in snap["lots"]}
    assert lots["1"]["subtotal"] == "60000.00"
    assert lots["2"]["unit_price"] is None and lots["2"]["subtotal"] is None
    assert lots["3"]["unit_price"] is None and lots["3"]["subtotal"] is None
    assert "Partida 2: precio pendiente" in snap["warnings"]
    assert "Partida 3: precio pendiente" in snap["warnings"]
    totals = snap["totals"]
    assert totals["known_total"] == "60000.00" and totals["currency"] == "MXN"
    assert totals["complete"] is False and totals["lots_priced"] == 1 and totals["lots_pending"] == 2
    assert "parcial" in totals["text"].lower() and "60,000.00 MXN" in totals["text"]
    assert snap["fiscal"] == FISCAL == {
        "status": "pendiente",
        "text": "Tratamiento fiscal pendiente de configurar; no se aplicaron impuestos."}


def test_complete_total_sums_known_subtotals(db):
    snap = snapshot_of(db)    # variantes DEMO-*: 40×1500 + 20×2100 + 15×4000
    assert [l["subtotal"] for l in snap["lots"]] == ["60000.00", "42000.00", "60000.00"]
    assert snap["totals"]["known_total"] == "162000.00" and snap["totals"]["complete"] is True
    assert not [w for w in snap["warnings"] if "precio pendiente" in w]


def test_mixed_currencies_are_never_added_together(db):
    opp = lic(db)
    set_lot_price(db, opp, "1", "100.00", "SYNTHETIC", "MXN")
    set_lot_price(db, opp, "2", "10.00", "SYNTHETIC", "USD")
    db.expire_all()
    totals = build_snapshot(db, lic(db))["totals"]
    assert totals["currency"] is None and totals["known_total"] is None
    # Partida 1: 40×100; partida 3 (catálogo ficticio): 15×4000; partida 2 en dólares: 20×10.
    assert totals["by_currency"] == {"MXN": "64000.00", "USD": "200.00"}
    assert any("monedas" in w.lower() for w in db_warnings(db))


def test_data_version_stable(db):
    first = snapshot_of(db)
    second = snapshot_of(db)
    assert first["data_version"] == second["data_version"]
    assert re.fullmatch(r"[0-9a-f]{64}", first["data_version"])
    # Es el SHA-256 del JSON canónico sin generated_at.
    body = {k: v for k, v in first.items() if k not in ("generated_at", "data_version")}
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert first["data_version"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    # Un cambio real de datos cambia la versión.
    opp = lic(db)
    set_lot_price(db, opp, "1", "1600.00")
    db.expire_all()
    assert snapshot_of(db)["data_version"] != first["data_version"]


def test_synthetic_prices_flagged(db):
    snap = snapshot_of(db)
    assert snap["lots"], "el escenario debe tener partidas"
    for lot in snap["lots"]:
        assert lot["price_data_kind"] == "SYNTHETIC"
        assert lot["price_source"] == "variante"          # el precio viene del catálogo ficticio
        assert lot["variant"]["data_kind"] == "SYNTHETIC"
    assert any("SIMULADO" in w for w in snap["warnings"])
    assert snap["totals"]["has_synthetic_prices"] is True
    assert snap["notice"] == config.WATERMARK


def test_price_without_declared_origin_is_warned(db):
    opp = lic(db)
    set_lot_price(db, opp, "1", "1500.00", None)
    db.expire_all()
    snap = snapshot_of(db)
    lot1 = next(l for l in snap["lots"] if l["number"] == "1")
    assert lot1["price_data_kind"] is None
    assert any(w.startswith("Partida 1:") and "procedencia" in w for w in snap["warnings"])


def test_open_requirements_evidence_and_task_in_snapshot(db):
    snap = snapshot_of(db)
    reqs = {r["code"]: r for r in snap["requirements"]}
    assert len(reqs) == len(snap["requirements"]) >= 6
    faltante = reqs["DEMO-REQ-005"]
    assert faltante["status"] == "faltante" and faltante["open"] is True and faltante["mandatory"] is True
    assert faltante["evidence"] == []
    assert snap["open_requirements"] == sum(1 for r in snap["requirements"] if r["open"])
    # Ningún requisito se cierra solo por tener evidencia.
    assert all(r["status"] != "cumple_validado" for r in snap["requirements"] if r["evidence"])


def test_affinity_is_opaque_and_null_means_not_computed(db):
    opp = lic(db)
    snap = build_snapshot(db, opp)
    assert snap["affinity"]["state"] == "no_calculada" and snap["workspace"] is None
    ws = BidWorkspace(organization_id=opp.organization_id, opportunity_id=opp.id,
                      affinity={"components": {"familia": 40}, "total": None, "coverage_complete": False,
                                "blocking": ["documental"]})
    db.add(ws)
    db.flush()
    snap = build_snapshot(db, opp)
    aff = snap["affinity"]
    assert aff["state"] == "calculada" and aff["total"] is None and aff["coverage_complete"] is False
    assert aff["blocking"] == ["documental"] and aff["components"] == {"familia": 40}
    assert snap["workspace"]["decision"] == "pendiente"


def test_assessments_are_read_when_present(db):
    opp = lic(db)
    lot = next(l for l in opp.lots if l.number == "1")
    req = db.scalars(select(Requirement).where(Requirement.code == "DEMO-REQ-001")).one()
    db.add(MatchAssessment(organization_id=opp.organization_id, opportunity_id=opp.id, lot_id=lot.id,
                           variant_id=lot.proposed_variant_id, requirement_id=req.id, result="coincide",
                           explanation="El catálogo declara titanio.", rule="eq", engine_version="1",
                           catalog_value="titanio", source_text="Material: titanio"))
    db.flush()
    snap = build_snapshot(db, opp)
    row = next(r for r in snap["requirements"] if r["code"] == "DEMO-REQ-001")
    assert row["assessments"][0]["result"] == "coincide"
    assert row["assessments"][0]["catalog_value"] == "titanio"
    other = next(r for r in snap["requirements"] if r["code"] == "DEMO-REQ-002")
    assert other["assessments"] == []

