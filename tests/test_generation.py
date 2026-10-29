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
    assert snap["affinity"]["state"] == "no_calculada"
    empty = snap["workspace"]          # sin espacio creado: los valores de uno recién abierto
    assert empty["decision"] == "pendiente" and empty["technical_approval"] is None
    ws = BidWorkspace(organization_id=opp.organization_id, opportunity_id=opp.id,
                      affinity={"components": {"familia": 40}, "total": None, "coverage_complete": False,
                                "blocking": ["documental"]})
    db.add(ws)
    db.flush()
    snap = build_snapshot(db, opp)
    aff = snap["affinity"]
    assert aff["state"] == "calculada" and aff["total"] is None and aff["coverage_complete"] is False
    assert aff["blocking"] == ["documental"] and aff["components"] == {"familia": 40}
    assert snap["workspace"] == empty        # crear el espacio vacío no cambia el contenido del borrador


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


# ── F2 · plantillas DOCX ─────────────────────────────────────────────────────

from docx import Document as DocxDocument  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from app.services.generation.docx_templates import HEADER_TEXT, TEMPLATE_VERSION, TEMPLATES  # noqa: E402


def _paragraph_texts(element) -> list[str]:
    return ["".join(t.text or "" for t in p.iter(qn("w:t"))) for p in element.iter(qn("w:p"))]


def docx_parts(data: bytes) -> dict:
    """Texto del cuerpo (incluye tablas), del encabezado y del pie de un DOCX."""
    doc = DocxDocument(io.BytesIO(data))
    section = doc.sections[0]
    return {
        "body": "\n".join(_paragraph_texts(doc.element.body)),
        "header": "\n".join(_paragraph_texts(section.header._element)),
        "footer": "\n".join(_paragraph_texts(section.footer._element)),
        "doc": doc,
    }


def render_all(snapshot: dict) -> dict[str, bytes]:
    return {key: render(snapshot) for key, render in TEMPLATES.items()}


def tables_of(data: bytes) -> list[list[list[str]]]:
    doc = DocxDocument(io.BytesIO(data))
    return [[[c.text for c in row.cells] for row in t.rows] for t in doc.tables]


SIX = ["resumen", "matriz", "faltantes", "indice", "propuesta_tecnica", "propuesta_economica"]


def test_template_registry():
    assert TEMPLATE_VERSION == "1.0"
    assert list(TEMPLATES) == SIX


def test_all_templates_have_watermark(db):
    snap = snapshot_of(db)
    for key, data in render_all(snap).items():
        parts = docx_parts(data)
        assert config.WATERMARK in parts["footer"], key
        assert snap["data_version"] in parts["footer"], key
        assert HEADER_TEXT == "Dipromedic · Borrador de expediente · DEMO"
        assert parts["header"].strip() == HEADER_TEXT, key
        assert "Borrador · no apto para presentación" in parts["body"], key
        # La fecha de generación está en el pie, en hora de Ciudad de México.
        assert re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", parts["footer"]), key


def test_economic_totals_text(db):
    snap = snapshot_of(db)
    parts = docx_parts(render_all(snap)["propuesta_economica"])
    assert "60,000.00" in parts["body"]
    assert "Total: 162,000.00 MXN" in parts["body"]
    assert snap["fiscal"]["text"] in parts["body"]
    [table] = tables_of(render_all(snap)["propuesta_economica"])
    assert table[0] == ["Partida", "Descripción", "Cantidad", "Unidad", "Precio unitario", "Moneda", "Subtotal",
                        "Origen del precio"]
    row1 = table[1]
    assert row1[0] == "1" and row1[2] == "40" and row1[3] == "pieza" and row1[4] == "1,500.00"
    assert row1[5] == "MXN" and row1[6] == "60,000.00" and row1[7].startswith("SIMULADO")


def test_economic_partial_total_shows_pending_prices(db):
    opp = lic(db)
    next(l for l in opp.lots if l.number == "2").proposed_variant_id = real_variant(db, opp.organization_id).id
    db.flush()
    db.expire_all()
    snap = snapshot_of(db)
    data = render_all(snap)["propuesta_economica"]
    body = docx_parts(data)["body"]
    assert "Total parcial: 120,000.00 MXN" in body
    row2 = tables_of(data)[0][2]
    assert "[PENDIENTE: precio]" in row2[4] and "[PENDIENTE: precio]" in row2[6]
    assert "SIMULADO" not in row2[7]
    assert "[PENDIENTE: aprobación comercial de precios]" in body


def test_pending_markers_for_open_requirements(db):
    snap = snapshot_of(db)
    open_mandatory = [r for r in snap["requirements"] if r["open"] and r["mandatory"] is not False]
    assert len(open_mandatory) >= 5
    texts = {k: docx_parts(v)["body"] for k, v in render_all(snap).items()}
    for key in ("matriz", "faltantes"):
        assert texts[key].count("[PENDIENTE") >= len(open_mandatory), key
    # El código de cada requisito abierto aparece en la lista de faltantes.
    for req in open_mandatory:
        assert req["code"] in texts["faltantes"]


def test_faltantes_assigns_owner_and_due_date_or_marks_pending(db):
    snap = snapshot_of(db)
    [table, *_] = tables_of(render_all(snap)["faltantes"])
    header = table[0]
    assert header[:2] == ["No.", "Código"] and "Responsable" in header and "Fecha límite" in header
    by_code = {row[1]: dict(zip(header, row)) for row in table[1:]}
    task_reqs = {r["code"]: r["open_task"] for r in snap["requirements"] if r["open_task"]}
    assert task_reqs, "el escenario trae tareas abiertas"
    code, task = next(iter(task_reqs.items()))
    assert task["assignee"] in by_code[code]["Responsable"]
    no_task = next(r["code"] for r in snap["requirements"] if r["open"] and not r["open_task"] and r["code"] in by_code)
    assert "[PENDIENTE: responsable]" in by_code[no_task]["Responsable"]


def test_no_signature_words(db):
    # El texto de los datos se cita tal cual (las bases reales pueden decir «firmado»); aquí se neutraliza el único
    # texto de los fixtures que contiene la subcadena, para probar que las plantillas no la introducen.
    req = db.scalars(select(Requirement).where(Requirement.code == "DEMO-REQ-006")).one()
    req.next_action = "Solicitar a planta la evidencia"
    db.flush()
    db.expire_all()
    snap = snapshot_of(db)
    forbidden = re.compile(r"firma|sello|presentado", re.IGNORECASE)
    for key, data in render_all(snap).items():
        parts = docx_parts(data)
        text = "\n".join([parts["body"], parts["header"], parts["footer"]]).replace(config.WATERMARK, "")
        assert not forbidden.search(text), (key, forbidden.search(text).group(0))
        # Tampoco hay espacios para rubricas ni líneas de firma.
        assert "____" not in text, key


def test_templates_render_with_minimal_data_and_mark_everything_pending(db):
    """Una oportunidad sin partidas, sin requisitos ni fechas: nada se inventa y todo queda pendiente."""
    org = db.scalars(select(Organization)).first()
    opp = Opportunity(organization_id=org.id, external_id="DEMO-VACIA", normalized_id="DEMOVACIA", title="Vacía",
                      buyer="Institución ficticia", data_kind="SYNTHETIC", verification_status="simulada")
    db.add(opp)
    db.flush()
    snap = build_snapshot(db, opp)
    assert snap["totals"]["lots_total"] == 0 and snap["totals"]["known_total"] is None
    texts = {k: docx_parts(v)["body"] for k, v in render_all(snap).items()}
    assert "[PENDIENTE: fecha de presentación]" in texts["resumen"]
    assert "[PENDIENTE: unidad compradora]" in texts["resumen"]
    assert "Afinidad no calculada" in texts["resumen"]
    assert "Sin evaluación técnica" in texts["propuesta_tecnica"] or "partidas" in texts["propuesta_tecnica"]
    assert "Total no calculable" in texts["propuesta_economica"]
    assert "No hay requisitos capturados" in texts["matriz"]


def test_technical_proposal_shows_both_values_and_never_grants_compliance(db):
    snap = snapshot_of(db)
    data = render_all(snap)["propuesta_tecnica"]
    body = docx_parts(data)["body"]
    assert "Sin evaluación técnica" in body
    assert "DEMO-PLA-003" in body and "DEMO-SIN-VALIDEZ" in body
    # Medida incompatible a la vista: la partida 2 exige 12 orificios y el catálogo declara 10.
    tables = tables_of(data)
    flat = [cell for t in tables for row in t for cell in row]
    assert any("12" in c for c in flat) and any(c.strip() == "10" or c.startswith("10 ") for c in flat)
    assert "Cumple ·" not in body and "cumple_validado" not in body


def test_technical_proposal_cites_assessments_and_catalog_credit(db):
    opp = lic(db)
    lot = next(l for l in opp.lots if l.number == "1")
    variant = real_variant(db, opp.organization_id)
    lot.proposed_variant_id = variant.id
    req = db.scalars(select(Requirement).where(Requirement.code == "DEMO-REQ-002")).one()
    db.add(MatchAssessment(organization_id=opp.organization_id, opportunity_id=opp.id, lot_id=lot.id,
                           variant_id=variant.id, requirement_id=req.id, result="coincide",
                           explanation="La ficha lista 6 orificios.", rule="eq", engine_version="1",
                           catalog_value="6", source_text="6 orificios"))
    db.flush()
    db.expire_all()
    snap = snapshot_of(db)
    body = docx_parts(render_all(snap)["propuesta_tecnica"])["body"]
    assert "La ficha lista 6 orificios." in body and "6 orificios" in body
    assert ("Contenido de catálogo: DIPROMEDIC S.A. DE C.V. · www.dipromedic.com · consultado el 2026-10-28"
            in body)
    assert "[PENDIENTE: precio]" not in body


def test_index_lists_documents_without_bundling_them(db):
    snap = snapshot_of(db)
    body = docx_parts(render_all(snap)["indice"])["body"]
    assert snap["documents"], "el escenario trae documentos"
    for doc in snap["documents"]:
        assert doc["code"] in body
    assert "No se incluye el archivo" in body
    assert "01_resumen_oportunidad.docx" in body and "manifest.json" in body
    assert "[PENDIENTE: documento" in body      # requisitos abiertos sin evidencia


def test_xml_control_characters_do_not_break_rendering(db):
    req = db.scalars(select(Requirement).where(Requirement.code == "DEMO-REQ-001")).one()
    req.text = "Placa\x1f de\x0b titanio"      # Postgres no admite NUL; el resto de los controles sí
    db.flush()
    db.expire_all()
    body = docx_parts(render_all(snapshot_of(db))["matriz"])["body"]
    assert "Placa de titanio" in body


# ── F3 · paquete ZIP con manifiesto ──────────────────────────────────────────

import csv  # noqa: E402

import openpyxl  # noqa: E402

from app.services.generation.package import build_package  # noqa: E402


def make_package(db, snapshot=None):
    snap = snapshot or snapshot_of(db)
    data, manifest = build_package(snap, render_all(snap))
    return snap, data, manifest


def open_zip(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data))


def test_zip_layout(db):
    snap, data, manifest = make_package(db)
    names = open_zip(data).namelist()
    assert sorted(n for n in names if n.startswith("docx/")) == [
        "docx/01_resumen_oportunidad.docx", "docx/02_matriz_cumplimiento.docx", "docx/03_lista_faltantes.docx",
        "docx/04_indice_expediente.docx", "docx/05_propuesta_tecnica_preliminar.docx",
        "docx/06_propuesta_economica_demo.docx"]
    assert {"matriz.csv", "matriz.xlsx", "README_PENDIENTES.md", "manifest.json"} <= set(names)
    assert len(names) == 10 and len(set(names)) == 10


def test_manifest_hashes_match(db):
    snap, data, manifest = make_package(db)
    zf = open_zip(data)
    listed = {f["name"]: f for f in manifest["files"]}
    assert set(listed) == set(zf.namelist()) - {"manifest.json"}      # el manifiesto no se lista a sí mismo
    for name, entry in listed.items():
        content = zf.read(name)
        assert entry["sha256"] == hashlib.sha256(content).hexdigest(), name
        assert entry["size_bytes"] == len(content), name
    assert json.loads(zf.read("manifest.json").decode("utf-8")) == manifest
    assert manifest["template_version"] == TEMPLATE_VERSION
    assert manifest["generated_at"] == snap["generated_at"] and manifest["data_version"] == snap["data_version"]
    assert manifest["opportunity"] == {"external_id": "DEMO-LIC-001", "data_kind": "SYNTHETIC"}
    assert manifest["warnings"] == snap["warnings"] and manifest["notice"] == config.WATERMARK
    assert set(manifest["provenance"]) == {"REAL", "SYNTHETIC", "HISTORICAL"}
    assert manifest["provenance"]["SYNTHETIC"] > 0 and manifest["provenance"]["REAL"] == 0


def test_zip_is_reproducible_from_the_same_inputs(db):
    snap = snapshot_of(db)
    rendered = render_all(snap)
    first, _ = build_package(snap, rendered)
    again, _ = build_package(snap, rendered)
    # Mismas entradas, mismos bytes: ni la fecha de las entradas del ZIP ni el orden cambian.
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(again).hexdigest()
    dates = {i.date_time for i in open_zip(first).infolist()}
    assert len(dates) == 1


def test_provenance_counts_real_records(db):
    opp = lic(db)
    next(l for l in opp.lots if l.number == "2").proposed_variant_id = real_variant(db, opp.organization_id).id
    db.flush()
    db.expire_all()
    _, _, manifest = make_package(db)
    assert manifest["provenance"]["REAL"] == 1       # la variante REAL
    assert manifest["provenance_detail"]["variants"] == {"REAL": 1, "SYNTHETIC": 2}


def test_csv_utf8_bom_and_one_row_per_requirement(db):
    snap, data, _ = make_package(db)
    raw = open_zip(data).read("matriz.csv")
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0][:3] == ["Código", "Partida", "Requisito"]
    assert len(rows) - 1 == len(snap["requirements"])
    assert all(r[-1] == config.WATERMARK for r in rows[1:])
    by_code = {r[0]: r for r in rows[1:]}
    assert "[PENDIENTE: evidencia vinculada]" in by_code["DEMO-REQ-005"]


def test_xlsx_has_exact_money_and_watermark(db):
    snap, data, _ = make_package(db)
    wb = openpyxl.load_workbook(io.BytesIO(open_zip(data).read("matriz.xlsx")))
    assert wb.sheetnames == ["Resumen", "Matriz", "Partidas"]
    for ws in wb.worksheets:
        assert ws["A1"].value == config.WATERMARK, ws.title
    lots = wb["Partidas"]
    header = [c.value for c in lots[3]]
    assert header[:8] == ["Partida", "Descripción", "Cantidad", "Unidad", "Precio unitario", "Moneda", "Subtotal",
                          "Origen del precio"]
    row1 = [c.value for c in lots[4]]
    assert row1[0] == "1" and Decimal(str(row1[2])) == Decimal("40") and Decimal(str(row1[4])) == Decimal("1500")
    assert Decimal(str(row1[6])) == Decimal("60000.00") and row1[7].startswith("SIMULADO")
    assert lots["G4"].number_format == "#,##0.00"
    summary = {r[0].value: r[1].value for r in wb["Resumen"].iter_rows(min_row=3) if r[0].value}
    assert summary["Versión de datos"] == snap["data_version"]
    assert summary["Total"] == "Total: 162,000.00 MXN"


def test_spreadsheet_formula_injection_is_neutralised(db):
    req = db.scalars(select(Requirement).where(Requirement.code == "DEMO-REQ-001")).one()
    req.text = '=HYPERLINK("http://x","clic")'
    db.flush()
    db.expire_all()
    _, data, _ = make_package(db)
    zf = open_zip(data)
    rows = list(csv.reader(io.StringIO(zf.read("matriz.csv").decode("utf-8-sig"))))
    assert next(r for r in rows if r[0] == "DEMO-REQ-001")[2].startswith("'=HYPERLINK(\"http://x\",\"clic\")")
    wb = openpyxl.load_workbook(io.BytesIO(zf.read("matriz.xlsx")))
    cell = next(r[2] for r in wb["Matriz"].iter_rows(min_row=4) if r[0].value == "DEMO-REQ-001")
    assert cell.data_type == "s" and cell.value.startswith("'=")


def test_readme_lists_pending(db):
    snap, data, _ = make_package(db)
    readme = open_zip(data).read("README_PENDIENTES.md").decode("utf-8")
    assert config.WATERMARK in readme and "Borrador · no apto para presentación" in readme
    assert snap["data_version"] in readme
    for req in snap["requirements"]:
        if req["open"]:
            assert req["code"] in readme
    for warning in snap["warnings"]:
        assert warning in readme
    assert "manifest.json" in readme
    assert not re.search(r"\b(firma\w*|sello\w*|presentad[oa]s?)\b", readme.replace(config.WATERMARK, ""), re.I)


def test_third_party_excluded(db):
    opp = lic(db)
    secret = b"%PDF-1.4 contenido de un tercero que no debe viajar en el ZIP"
    third = Document(organization_id=opp.organization_id, code="TER-001", title="Certificado de un tercero",
                     scope="expediente", data_kind="REAL", opportunity_id=opp.id, third_party=True,
                     external_url="https://tercero.example/cert.pdf", review_status="pendiente")
    db.add(third)
    db.flush()
    db.expire_all()
    snap, data, manifest = make_package(db)
    zf = open_zip(data)
    entry = next(d for d in manifest["excluded_documents"] if d["code"] == "TER-001")
    assert entry["third_party"] is True and "tercero" in entry["reason"].lower()
    assert entry["external_url"] == "https://tercero.example/cert.pdf"
    # Ningún archivo de documentos viaja en el paquete: solo plantillas, matriz, README y manifiesto.
    assert all(n.startswith("docx/") or n in {"matriz.csv", "matriz.xlsx", "README_PENDIENTES.md", "manifest.json"}
               for n in zf.namelist())
    assert not any(secret in zf.read(n) for n in zf.namelist())
    # También se lista el resto de los documentos del expediente, con su motivo.
    assert {d["code"] for d in manifest["excluded_documents"]} >= {d["code"] for d in snap["documents"]}
    assert all(d["reason"] for d in manifest["excluded_documents"])

