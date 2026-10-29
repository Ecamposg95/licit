"""E1–E2: motor determinista de correspondencia, afinidad por componente y vigencia a fecha exigida."""
from datetime import date, timedelta
from types import SimpleNamespace

from app.services.affinity import (
    WEIGHTS, blocking_details, check_validity, compute_affinity, serialize_affinity,
)
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


# ── E2 · afinidad y vigencia ─────────────────────────────────────────────────

def _req(code, req_type, status="pendiente", mandatory=True, attribute=None, rid=None):
    return SimpleNamespace(id=rid or code, code=code, req_type=req_type, status=status, mandatory=mandatory,
                           attribute=attribute)


def _ass(requirement_id, result):
    return SimpleNamespace(requirement_id=requirement_id, result=result)


def _opportunity(*lot_families):
    lots = []
    for lot_family, product_family in lot_families:
        variant = None if product_family is None else SimpleNamespace(product=SimpleNamespace(family=product_family))
        lots.append(SimpleNamespace(family=lot_family, proposed_variant=variant))
    return SimpleNamespace(lots=lots)


def _full_scenario(doc_status="cumple_validado"):
    opp = _opportunity(("Osteosíntesis", "Osteosíntesis"), ("Osteosíntesis", "Osteosíntesis"))
    reqs = [_req("R1", "tecnico", attribute="holes"), _req("R2", "tecnico", attribute="material"),
            _req("R3", "documental", status=doc_status), _req("R4", "capacidad", attribute="stock_demo")]
    asses = [_ass("R1", "coincide"), _ass("R2", "coincide"), _ass("R4", "coincide")]
    return opp, reqs, asses


def test_weights_exact():
    assert WEIGHTS == {"familia": 40, "atributos": 30, "documental": 20, "capacidad": 10}
    assert sum(WEIGHTS.values()) == 100


def test_complete_scenario_has_total_and_components():
    a = compute_affinity(*_full_scenario())
    assert a.total == 100 and a.coverage_complete is True and a.blocking == []
    assert a.components["atributos"] == {"weight": 30, "score": 1.0, "known": 2, "total": 2}
    assert a.components["familia"]["known"] == 2 and a.components["familia"]["total"] == 2


def test_incomplete_coverage_total_none():
    opp, reqs, asses = _full_scenario()
    reqs = [r for r in reqs if r.req_type != "capacidad"]
    asses = [a for a in asses if a.requirement_id != "R4"]
    a = compute_affinity(opp, reqs, asses)
    assert a.components["capacidad"] == {"weight": 10, "score": None, "known": 0, "total": 0}
    assert a.total is None and a.coverage_complete is False


def test_unknown_attribute_lowers_coverage_not_hidden():
    opp, reqs, asses = _full_scenario()
    asses = [_ass("R1", "coincide"), _ass("R2", "desconocido"), _ass("R4", "coincide")]
    a = compute_affinity(opp, reqs, asses)
    assert a.components["atributos"] == {"weight": 30, "score": 0.5, "known": 1, "total": 2}
    assert a.coverage_complete is False
    assert a.total == 85                          # 40 + 15 + 20 + 10


def test_blocking_listed_even_with_high_score():
    opp, reqs, asses = _full_scenario(doc_status="faltante")
    reqs.append(_req("R5", "documental", status="vencido"))
    reqs.append(_req("R6", "documental", status="faltante", mandatory=False))
    a = compute_affinity(opp, reqs, asses)
    assert a.total is not None and a.total >= 70
    assert a.blocking == ["R3", "R5"]


def test_objective_mismatch_blocks_even_when_status_is_pending():
    opp, reqs, asses = _full_scenario()
    asses = [_ass("R1", "incumple"), _ass("R2", "coincide"), _ass("R4", "coincide")]
    assert compute_affinity(opp, reqs, asses).blocking == ["R1"]


def test_component_without_known_data_has_no_score():
    """M1: total > 0 pero nada conocido → sin puntuación y total «cobertura incompleta», nunca un 0 % aparente."""
    opp, reqs, asses = _full_scenario()
    asses = [_ass("R1", "desconocido"), _ass("R2", "desconocido"), _ass("R4", "coincide")]
    a = compute_affinity(opp, reqs, asses)
    assert a.components["atributos"] == {"weight": 30, "score": None, "known": 0, "total": 2}
    assert a.total is None and a.coverage_complete is False


def test_human_negative_status_wins_over_engine_match():
    """M2: si una persona marcó el requisito incumple/faltante/vencido, la coincidencia del motor no suma."""
    opp, reqs, asses = _full_scenario()
    reqs[0].status = "incumple"
    reqs[3].status = "faltante"
    a = compute_affinity(opp, reqs, asses)
    assert a.components["atributos"] == {"weight": 30, "score": 0.5, "known": 2, "total": 2}
    assert a.components["capacidad"] == {"weight": 10, "score": 0.0, "known": 1, "total": 1}
    assert a.blocking == ["R1", "R4"]


def test_blocking_details_reasons():
    reqs = [_req("R1", "tecnico", attribute="holes"), _req("R2", "documental", status="faltante"),
            _req("R3", "documental", status="pendiente", mandatory=None),
            _req("R4", "tecnico", status="no_aplica_justificado", attribute="holes"),
            _req("R5", "documental", status="faltante", mandatory=False)]
    asses = [_ass("R1", "incumple"), _ass("R4", "incumple")]
    assert blocking_details(reqs, asses) == [
        {"code": "R1", "reason": "motor", "status": "pendiente"},
        {"code": "R2", "reason": "estado", "status": "faltante"},
        {"code": "R3", "reason": "no_determinable", "status": "pendiente"},
    ]
    # La lista de bloqueantes de la afinidad (la que lee F) solo trae obligatorios y omite «no aplica».
    assert compute_affinity(_opportunity(), reqs, asses).blocking == ["R1", "R2"]


def test_family_component_counts_lots_without_product():
    opp = _opportunity(("Artroplastia de rodilla", "Artroplastia de rodilla"), ("Instrumental", None))
    a = compute_affinity(opp, [], [])
    assert a.components["familia"] == {"weight": 40, "score": 0.5, "known": 2, "total": 2}


def test_serialize_affinity_shape():
    data = serialize_affinity(compute_affinity(*_full_scenario()))
    assert set(data) == {"components", "total", "coverage_complete", "blocking"}
    assert set(data["components"]) == {"familia", "atributos", "documental", "capacidad"}
    for comp in data["components"].values():
        assert set(comp) == {"weight", "score", "known", "total"}


TODAY = date(2026, 10, 28)


def test_valid_today_expires_before_required():
    assert check_validity(TODAY + timedelta(days=90), TODAY + timedelta(days=120), TODAY) == "vence_antes"


def test_valid_until_required_date():
    assert check_validity(TODAY + timedelta(days=120), TODAY + timedelta(days=120), TODAY) == "vigente"
    assert check_validity(TODAY + timedelta(days=5), None, TODAY) == "vigente"


def test_expired():
    assert check_validity(TODAY - timedelta(days=10), TODAY + timedelta(days=30), TODAY) == "vencido"
    assert check_validity(TODAY - timedelta(days=1), None, TODAY) == "vencido"


def test_no_valid_until_is_sin_vigencia():
    assert check_validity(None, TODAY + timedelta(days=30), TODAY) == "sin_vigencia"
