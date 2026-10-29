"""E1–E2: motor determinista de correspondencia, afinidad por componente y vigencia a fecha exigida."""
from types import SimpleNamespace

from app.services.matching import ENGINE_VERSION, RequirementSpec, evaluate, variant_attributes

DPM_198 = {
    "material": {"value": "Aleación de titanio Ti6Al4V ELI", "unit": None,
                 "source_text": "Fabricada en aleación de Titanio (Ti6Al4V ELI, ASTM F136)."},
    "holes": {"values": [5, 6, 7, 8, 9, 10, 12], "unit": "orificios",
              "source_text": "Cód. 198 | 5, 6, 7, 8, 9, 10 y 12 orificios"},
}


def _spec(attribute, operator, expected, unit=None):
    return RequirementSpec(attribute=attribute, operator=operator, expected=expected, unit=unit)


# ── E1 · reglas ──────────────────────────────────────────────────────────────

def test_engine_version():
    assert ENGINE_VERSION == "1.0"


def test_case_a_match():
    r = evaluate(_spec("holes", "eq", "6", "orificios"), {"holes": {"values": [5, 6, 7, 8, 9, 10, 12]}})
    assert r.result == "coincide"


def test_case_a_match_cites_the_catalog():
    r = evaluate(_spec("holes", "eq", "6", "orificios"), DPM_198)
    assert r.result == "coincide"
    assert r.source_text == "Cód. 198 | 5, 6, 7, 8, 9, 10 y 12 orificios"
    assert "Cód. 198 | 5, 6, 7, 8, 9, 10 y 12 orificios" in r.explanation
    assert r.catalog_value == "5, 6, 7, 8, 9, 10 y 12 orificios"


def test_case_b_mismatch():
    r = evaluate(_spec("holes", "eq", "6", "orificios"), {"holes": {"value": 8}})
    assert r.result == "incumple"


def test_case_b_mismatch_lists_available_sizes():
    r = evaluate(_spec("holes", "eq", "11", "orificios"), DPM_198)
    assert r.result == "incumple"
    assert "Medidas disponibles: 5, 6, 7, 8, 9, 10 y 12" in r.explanation
    assert "Cód. 198" in r.explanation          # la cita va en la explicación


def test_case_c_unknown():
    r = evaluate(_spec("material", "contains", "titanio"), {"material": {"value": "por validar"}})
    assert r.result == "desconocido"
    assert "No declarado en el catálogo; no se infiere del nombre" in r.explanation


def test_missing_and_null_attribute_are_unknown():
    assert evaluate(_spec("length_mm", "eq", "96", "mm"), DPM_198).result == "desconocido"
    assert evaluate(_spec("holes", "eq", "6"), {"holes": None}).result == "desconocido"
    assert evaluate(_spec("holes", "eq", "6"), {"holes": {"value": None}}).result == "desconocido"
    assert evaluate(_spec("material", "eq", "titanio"), {"material": "Por validar"}).result == "desconocido"


def test_material_contains_real_value():
    r = evaluate(_spec("material", "contains", "titanio"), DPM_198)
    assert r.result == "coincide"
    assert r.catalog_value == "Aleación de titanio Ti6Al4V ELI"
    assert "Fabricada en aleación de Titanio (Ti6Al4V ELI, ASTM F136)." in r.explanation


def test_contains_ignores_accents_and_case():
    assert evaluate(_spec("material", "contains", "ALEACIÓN"), {"material": "aleacion de titanio"}).result == "coincide"
    assert evaluate(_spec("material", "contains", "acero"), {"material": "titanio"}).result == "incumple"


def test_unit_conversion_cm():
    r = evaluate(_spec("diameter_mm", "eq", "10", "mm"), {"diameter_mm": {"value": 1, "unit": "cm"}})
    assert r.result == "coincide"


def test_unit_conversion_m_and_not_convertible():
    assert evaluate(_spec("length_mm", "eq", "96", "mm"), {"length_mm": {"value": "0.096", "unit": "m"}}).result == "coincide"
    r = evaluate(_spec("length_mm", "eq", "96", "mm"), {"length_mm": {"value": 3, "unit": "pulgadas"}})
    assert r.result == "no_comparable"


def test_capacity_gte():
    r = evaluate(_spec("stock_demo", "gte", "200", "pieza"), {"stock_demo": {"value": 25}})
    assert r.result == "incumple"


def test_gte_lte_are_decimal_and_in_operator():
    assert evaluate(_spec("diameter_mm", "lte", "10.0"), {"diameter_mm": {"value": "9.99"}}).result == "coincide"
    assert evaluate(_spec("diameter_mm", "gte", "10.01"), {"diameter_mm": {"value": "10.0"}}).result == "incumple"
    assert evaluate(_spec("holes", "in", "6, 7, 8"), {"holes": 7}).result == "coincide"
    assert evaluate(_spec("holes", "in", "6, 7, 8"), {"holes": 9}).result == "incumple"


def test_text_against_number_is_not_comparable():
    assert evaluate(_spec("holes", "gte", "6"), {"holes": "varios"}).result == "no_comparable"


def test_never_reads_name():
    variant = SimpleNamespace(name="Placa titanio 6 orificios", attributes={}, stock_demo=None)
    attrs = variant_attributes(variant)
    assert evaluate(_spec("material", "contains", "titanio"), attrs).result == "desconocido"
    assert evaluate(_spec("holes", "eq", "6"), attrs).result == "desconocido"


def test_variant_attributes_adds_simulated_capacity():
    variant = SimpleNamespace(name="x", attributes={"holes": 8}, stock_demo=25)
    attrs = variant_attributes(variant)
    assert attrs["holes"] == 8 and attrs["stock_demo"]["value"] == 25
    assert evaluate(_spec("stock_demo", "gte", "200"), attrs).result == "incumple"
