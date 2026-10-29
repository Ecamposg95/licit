"""B1: importador del catálogo público de Dipromedic (REAL, con cita textual por atributo)."""
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core import config
from app.core.database import SessionLocal
from app.models import AuditEvent, DataKind, Organization, Product, Variant
from app.services import catalog_import
from app.services.catalog_import import ImportSummary, import_catalog, normalize_code
from app.services.demo_seed import bootstrap, reset_demo

CATALOG = Path(catalog_import.__file__).resolve().parent.parent / "fixtures" / "catalogo_dipromedic.json"
REAL = DataKind.REAL.value


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def org(db):
    return db.scalars(select(Organization)).first()


@pytest.fixture
def imported(db, org) -> ImportSummary:
    summary = import_catalog(db, org.id, CATALOG)
    db.commit()
    return summary


def _json_products() -> list[dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return [p for line in data["lines"] for p in line["products"]]


def _real_variants(db) -> list[Variant]:
    return list(db.scalars(select(Variant).where(Variant.data_kind == REAL)))


def _count(db, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for k, v in filters.items():
        stmt = stmt.where(getattr(model, k) == v)
    return db.scalar(stmt)


def _variant(db, sku: str) -> Variant:
    v = db.scalars(select(Variant).where(Variant.sku == sku)).first()
    assert v is not None, f"no existe la variante {sku}"
    return v


# ── normalize_code ───────────────────────────────────────────────────────────

def test_cyrillic_code_normalized():
    assert normalize_code("СL-1") == "CL-1"  # С cirílica
    assert normalize_code("STRAUFIX-РКА-0351") == "STRAUFIX-PKA-0351"  # Р, К, А cirílicas
    assert normalize_code(" stra ufix-ркa-01 ") == "STRAUFIX-PKA-01"  # minúsculas cirílicas y espacios
    assert normalize_code("ВЕНКМОРТХ") == "BEHKMOPTX"
    assert normalize_code("200C") == "200C"


# ── Conteos y forma ──────────────────────────────────────────────────────────

def test_import_counts(db, imported):
    expected = len(_json_products())
    assert expected == 116
    assert imported.products == expected
    assert imported.variants >= 200
    assert _count(db, Product, data_kind=REAL) == expected
    assert _count(db, Variant, data_kind=REAL) == imported.variants
    assert imported.updated == 0


def test_product_fields_and_review_status(db, imported):
    by_ref = {p.external_ref: p for p in db.scalars(select(Product).where(Product.data_kind == REAL))}
    for raw in _json_products():
        p = by_ref[raw["id"]]
        assert p.name == raw["name"]
        assert p.family == raw["family"] and p.subfamily == raw["subfamily"]
        assert p.source_url == raw["page_url"]
        assert p.checked_on.isoformat() == "2026-10-28"
        assert "DIPROMEDIC S.A. DE C.V." in p.attribution and "www.dipromedic.com" in p.attribution
        assert p.images == raw["images"]
        assert p.features == (raw.get("features") or [])
        assert p.data_quality_notes == raw["data_quality_notes"]
        assert p.review_status == ("por_revisar" if raw["data_quality_notes"] else "pendiente")
        assert p.line  # toda ficha conserva su línea (Traufix, Corentec, …)
    assert by_ref["traufix_extremidad-superior_titan"].line == "Traufix"
    assert by_ref["corentec_cadera_vastago-id-stem"].line == "Corentec"
    assert by_ref["traufix_extremidad-superior_clavilock-con-gancho"].review_status == "por_revisar"


def test_titan_large_left(db, imported):
    v = _variant(db, "DPM-570")
    assert v.side == "izquierda"
    assert v.name == "Placa ALP para Húmero Proximal TITAN Large · izquierda"
    assert v.attributes["holes"]["values"] == [4, 6, 8, 10]
    assert v.attributes["holes"]["unit"] == "orificios"
    assert v.attributes["holes"]["source_text"] == "Versión Izq. (Cód. 570) / Der. (Cód. 569) | 4, 6, 8 y 10 orificios"
    assert v.attributes["material"]["value"] == "Aleación de titanio Ti6Al4V ELI"
    assert v.attributes["material"]["source_text"]
    assert v.source_text == "Versión Izq. (Cód. 570) / Der. (Cód. 569) | 4, 6, 8 y 10 orificios"
    right = _variant(db, "DPM-569")
    assert right.side == "derecha" and right.name.endswith(" · derecha")
    assert right.product_id == v.product_id


def test_alp35_single_code(db, imported):
    v = _variant(db, "DPM-198")
    assert v.side is None
    assert v.attributes["holes"]["values"] == [5, 6, 7, 8, 9, 10, 12]
    assert v.name == "Placa Bloqueada ALP 3.5mm Titanio"  # el nombre de la fila, sin sufijo de lado


def test_diameter_and_length_come_only_from_the_row(db, imported):
    t_fix = _variant(db, "DPM-660")
    assert t_fix.attributes["diameter_mm"]["values"] == [8.3]
    assert t_fix.attributes["length_mm"]["values"] == [250, 265, 280, 295, 310, 325, 340, 355, 370]
    assert t_fix.attributes["length_mm"]["source_text"].startswith("Diámetro 8.3mm / Cód. 660")
    assert "holes" not in t_fix.attributes
    # Una fila sin orificios, diámetro ni longitud no inventa nada: sólo los atributos del producto.
    anchor = _variant(db, "DPM-STRAUFIX-TPT-0475")
    assert "diameter_mm" not in anchor.attributes and "length_mm" not in anchor.attributes
    assert "holes" not in anchor.attributes


def test_row_without_quote_loads_no_dimensions_and_warns(db, imported):
    # traufix.com: filas de tabla sin texto original; no se puede citar, así que no se cargan medidas.
    v = _variant(db, "DPM-197.180")
    assert "diameter_mm" not in v.attributes and "length_mm" not in v.attributes
    assert v.source_text is None
    assert any("197.180" in w for w in imported.warnings)


def test_variants_without_rows_come_from_product_codes(db, imported):
    screw = _variant(db, "DPM-106")  # accesorio sin tabla: un Variant por código del producto
    assert screw.product.external_ref == "traufix-accesorio-106"
    assert screw.side is None
    assert screw.attributes["diametro"]["value"] == 3.5
    assert screw.attributes["diametro"]["source_text"]


def test_products_without_codes_have_no_variants(db, imported):
    stem = db.scalars(select(Product).where(Product.external_ref == "corentec_cadera_vastago-id-stem")).first()
    assert stem is not None and stem.variants == []


# ── Citas y datos comerciales ────────────────────────────────────────────────

def test_every_attribute_has_a_literal_quote(db, imported):
    checked = 0
    for v in _real_variants(db):
        for key, attr in v.attributes.items():
            assert isinstance(attr, dict) and ("value" in attr or "values" in attr), (v.sku, key)
            assert attr.get("source_text"), (v.sku, key)
            checked += 1
    assert checked > 500


def test_real_variants_have_no_commercial_data(db, imported):
    variants = _real_variants(db)
    assert variants
    for v in variants:
        assert v.price is None and v.stock_demo is None and v.regulatory_reference is None
        assert v.currency is None
        assert v.field_provenance == {}
        assert v.data_kind == REAL


def test_no_attribute_is_derived_from_the_name(db, imported):
    # «TITAN Large» sólo lo dice el nombre de la fila; nunca se vuelve un atributo propio.
    v = _variant(db, "DPM-570")
    assert "large" not in {k.lower() for k in v.attributes}
    assert set(v.attributes) >= {"material", "holes"}


# ── Códigos con problemas ────────────────────────────────────────────────────

def test_cyrillic_sku_is_normalized_and_original_is_kept(db, imported):
    v = _variant(db, "DPM-STRAUFIX-PKA-0351")
    assert "STRAUFIX-РКА-0351" in v.source_text  # el código original, con sus letras cirílicas
    assert "código original: STRAUFIX-РКА-0351" in v.source_text
    assert all(ord(ch) < 128 for ch in v.sku)
    assert all(all(ord(ch) < 128 for ch in x.sku) for x in _real_variants(db))


def test_unusable_and_duplicate_codes_warn_and_are_skipped(db, imported):
    joined = "\n".join(imported.warnings)
    assert "'igo'" in joined  # Tarfix: el código extraído no es un código
    assert "tarfix" in joined
    assert "DPM-143" in joined  # CLAVILOCK con gancho repite los códigos de «sin gancho»
    assert _count(db, Variant, sku="DPM-143") == 1
    skus = [v.sku for v in _real_variants(db)]
    assert len(skus) == len(set(skus))


# ── Idempotencia, actualización y reinicio ───────────────────────────────────

def test_import_idempotent(db, org, imported):
    ids_before = sorted(db.scalars(select(Product.id).where(Product.data_kind == REAL)))
    vids_before = sorted(v.id for v in _real_variants(db))
    again = import_catalog(db, org.id, CATALOG)
    db.commit()
    assert (again.products, again.variants, again.updated) == (imported.products, imported.variants, 0)
    assert again.warnings == imported.warnings
    assert _count(db, Product, data_kind=REAL) == imported.products
    assert _count(db, Variant, data_kind=REAL) == imported.variants
    assert sorted(db.scalars(select(Product.id).where(Product.data_kind == REAL))) == ids_before
    assert sorted(v.id for v in _real_variants(db)) == vids_before


def test_reimport_updates_changed_rows_and_keeps_commercial_overlay(db, org, imported, tmp_path):
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    titan = next(p for line in data["lines"] for p in line["products"] if p["id"] == "traufix_extremidad-superior_titan")
    titan["description"] = "Descripción corregida en el sitio."
    titan["variants"][1]["orificios"] = [4, 6, 8, 10, 12]
    changed = tmp_path / "catalogo.json"
    changed.write_text(json.dumps(data), encoding="utf-8")

    # Un campo comercial simulado agregado después por la demo no se borra al reimportar.
    from decimal import Decimal
    left = _variant(db, "DPM-570")
    left.price = Decimal("1234.00")
    left.field_provenance = {"price": "SYNTHETIC"}
    db.commit()

    again = import_catalog(db, org.id, changed)
    db.commit()
    db.expire_all()
    assert again.updated >= 3  # el producto y las dos variantes de TITAN Large
    assert _count(db, Product, data_kind=REAL) == imported.products
    p = db.scalars(select(Product).where(Product.external_ref == "traufix_extremidad-superior_titan")).first()
    assert p.description == "Descripción corregida en el sitio."
    left = _variant(db, "DPM-570")
    assert left.attributes["holes"]["values"] == [4, 6, 8, 10, 12]
    assert left.price == Decimal("1234.00") and left.field_provenance == {"price": "SYNTHETIC"}


def test_reset_keeps_real_catalog(db, org, imported):
    reset_demo(db, org, actor_id=None)
    db.commit()
    assert _count(db, Product, data_kind=REAL) == imported.products
    assert _count(db, Variant, data_kind=REAL) == imported.variants


def test_import_audits_once_in_same_transaction(db, org):
    def events():
        return list(db.scalars(select(AuditEvent).where(AuditEvent.action == "catalog.import")))

    summary = import_catalog(db, org.id, CATALOG)
    assert len(events()) == 1  # visible antes del commit: misma transacción
    db.commit()
    event = events()[0]
    assert event.resource_type == "organization" and event.resource_id == org.id
    assert event.after["products"] == summary.products and event.after["variants"] == summary.variants
    assert event.after["source"] == "https://www.dipromedic.com" and event.after["checked_on"] == "2026-10-28"

    import_catalog(db, org.id, CATALOG)  # sin cambios: no hay evento nuevo
    db.commit()
    assert len(events()) == 1


# ── bootstrap ────────────────────────────────────────────────────────────────

def test_bootstrap_imports_only_when_enabled_and_no_real_products(db, monkeypatch):
    calls = []
    real_import = catalog_import.import_catalog

    def spy(*args, **kwargs):
        calls.append(1)
        return real_import(*args, **kwargs)

    monkeypatch.setattr(catalog_import, "import_catalog", spy)

    monkeypatch.setattr(config, "IMPORT_CATALOG", False)
    bootstrap(db)
    assert calls == [] and _count(db, Product, data_kind=REAL) == 0

    monkeypatch.setattr(config, "IMPORT_CATALOG", True)
    bootstrap(db)
    assert calls == [1] and _count(db, Product, data_kind=REAL) == 116

    bootstrap(db)  # ya hay productos REAL: no vuelve a importar
    assert calls == [1] and _count(db, Product, data_kind=REAL) == 116
