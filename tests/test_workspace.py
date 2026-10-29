"""E5: evaluación del expediente, decisión, aprobaciones segregadas y compuerta «listo para revisión final»."""
import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.core.errors import AppError
from app.models import (
    AuditEvent, BidWorkspace, Lot, MatchAssessment, Opportunity, Organization, Requirement, User, Variant,
)
from app.services import catalog_import, workspace
from app.services.demo_documents import render_upload_sample
from app.services.demo_seed import reset_demo
from tests.conftest import login

PDF = render_upload_sample()


@pytest.fixture
def real_catalog():
    """DEMO-LIC-001 sobre el catálogo real de Traufix (en las pruebas no se importa por omisión)."""
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    catalog_import.import_catalog(db, org.id, catalog_import.CATALOG_PATH)
    reset_demo(db, org, actor_id=None)
    db.commit()
    db.close()


def _h(client, who: str) -> dict:
    return login(client, f"{who}@dipromedic.example")


def _opp(client, headers, code="DEMO-LIC-001") -> dict:
    return client.get("/api/v1/opportunities", params={"q": code}, headers=headers).json()["items"][0]


def _ws(client, headers, opp_id: str) -> dict:
    r = client.get(f"/api/v1/workspaces/{opp_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _assess(client, headers, opp_id: str) -> dict:
    r = client.post(f"/api/v1/workspaces/{opp_id}/assess", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _by_code(view: dict) -> dict:
    return {a["requirement_code"]: a for a in view["assessments"]}


def _events(action: str) -> list[AuditEvent]:
    db = SessionLocal()
    try:
        return list(db.scalars(select(AuditEvent).where(AuditEvent.action == action)
                               .order_by(AuditEvent.created_at)))
    finally:
        db.close()


def _approve(client, headers, opp_id, kind):
    return client.post(f"/api/v1/workspaces/{opp_id}/approvals", headers=headers, json={"kind": kind})


def _decide(client, headers, opp_id, decision="participar", reason="Cartera y plazos viables"):
    return client.post(f"/api/v1/workspaces/{opp_id}/decision", headers=headers,
                       json={"decision": decision, "reason": reason})


# ── Evaluación ───────────────────────────────────────────────────────────────

def test_workspace_before_any_action(client, analista):
    opp = _opp(client, analista)
    view = _ws(client, analista, opp["id"])
    assert view["workspace"]["id"] is None and view["workspace"]["decision"] == "pendiente"
    assert view["workspace"]["phase"] == "analisis" and view["affinity"] is None and view["assessments"] == []
    db = SessionLocal()
    assert db.scalar(select(BidWorkspace.id)) is None          # consultar no crea nada
    db.close()


def test_assess_lic001_three_cases(client, analista, real_catalog):
    opp = _opp(client, analista)
    view = _assess(client, analista, opp["id"])
    by = _by_code(view)
    # Partida 1, 2 y 3 contra productos reales de Traufix: coincide, medida incompatible y desconocido.
    assert by["DEMO-REQ-002"]["result"] == "coincide" and by["DEMO-REQ-002"]["lot_number"] == "1"
    assert by["DEMO-REQ-003"]["result"] == "incumple" and by["DEMO-REQ-003"]["lot_number"] == "2"
    assert by["DEMO-REQ-004"]["result"] == "desconocido" and by["DEMO-REQ-004"]["lot_number"] == "3"
    assert by["DEMO-REQ-001"]["result"] == "coincide"
    assert {a["variant_sku"] for a in view["assessments"]} == {"DPM-198", "DPM-199"}
    assert all(a["variant_data_kind"] == "REAL" and a["engine_version"] == "1.0" for a in view["assessments"])
    mismatch = by["DEMO-REQ-003"]
    assert "Medidas disponibles: 5, 6, 7, 8, 9, 10 y 12" in mismatch["explanation"]
    assert mismatch["source_text"] == "Cód. 198 | 5, 6, 7, 8, 9, 10 y 12 orificios"
    assert mismatch["catalog_value"] == "5, 6, 7, 8, 9, 10 y 12 orificios"
    assert by["DEMO-REQ-001"]["source_text"] == "Fabricada en aleación de Titanio (Ti6Al4V ELI, ASTM F136)."
    assert by["DEMO-REQ-004"]["source_text"] is None and "no se infiere del nombre" in by["DEMO-REQ-004"]["explanation"]

    # Se guarda la evaluación y la afinidad con la forma acordada; la bitácora la registra.
    db = SessionLocal()
    rows = list(db.scalars(select(MatchAssessment).where(MatchAssessment.opportunity_id == opp["id"])))
    assert len(rows) == 4 and {r.engine_version for r in rows} == {"1.0"}
    assert {r.source_text for r in rows if r.result == "incumple"} == {"Cód. 198 | 5, 6, 7, 8, 9, 10 y 12 orificios"}
    ws = db.scalars(select(BidWorkspace).where(BidWorkspace.opportunity_id == opp["id"])).one()
    assert set(ws.affinity) == {"components", "total", "coverage_complete", "blocking"}
    db.close()
    affinity = view["affinity"]
    assert affinity["components"]["atributos"] == {"weight": 30, "score": 0.5, "known": 3, "total": 4}
    assert affinity["coverage_complete"] is False
    assert {"DEMO-REQ-003", "DEMO-REQ-005", "DEMO-REQ-006", "DEMO-REQ-007"} <= set(affinity["blocking"])
    [event] = _events("workspace.assess")
    assert event.after["engine_version"] == "1.0" and event.after["results"]["incumple"] == 1

    # Reevaluar reemplaza (no acumula) las evaluaciones.
    _assess(client, analista, opp["id"])
    db = SessionLocal()
    assert len(list(db.scalars(select(MatchAssessment).where(MatchAssessment.opportunity_id == opp["id"])))) == 4
    db.close()


def test_assess_three_cases_with_fallback_variants(client, analista):
    by = _by_code(_assess(client, analista, _opp(client, analista)["id"]))
    assert [by[c]["result"] for c in ("DEMO-REQ-002", "DEMO-REQ-003", "DEMO-REQ-004")] == \
        ["coincide", "incumple", "desconocido"]
    assert by["DEMO-REQ-002"]["variant_sku"] == "DEMO-PLA-001"


def test_assess_does_not_change_status(client, analista):
    opp = _opp(client, analista)
    before = {r["code"]: (r["status"], r["version"])
              for r in client.get(f"/api/v1/opportunities/{opp['id']}/requirements", headers=analista).json()}
    _assess(client, analista, opp["id"])
    rows = client.get(f"/api/v1/opportunities/{opp['id']}/requirements", headers=analista).json()
    assert {r["code"]: (r["status"], r["version"]) for r in rows} == before
    # La matriz lleva la evaluación de cada requisito comparable.
    by = {r["code"]: r for r in rows}
    assert by["DEMO-REQ-003"]["assessment"]["result"] == "incumple"
    assert by["DEMO-REQ-005"]["assessment"] is None


def test_assess_permissions(client, direccion, analista):
    opp = _opp(client, analista)
    r = client.post(f"/api/v1/workspaces/{opp['id']}/assess", headers=direccion)
    assert r.status_code == 403
    assert client.post(f"/api/v1/workspaces/{opp['id']}/assess", headers=_h(client, "revisor")).status_code == 200


def test_capacity_scenario_uses_simulated_stock(client, analista):
    by = _by_code(_assess(client, analista, _opp(client, analista, "DEMO-LIC-006")["id"]))
    assert by["DEMO-REQ-017"]["result"] == "incumple"
    assert "simulado" in by["DEMO-REQ-017"]["explanation"].lower()


# ── Decisión y aprobaciones ──────────────────────────────────────────────────

def test_decision_requires_permission_and_reason(client, analista):
    opp = _opp(client, analista)
    assert _decide(client, analista, opp["id"]).status_code == 403
    responsable = _h(client, "responsable")
    r = _decide(client, responsable, opp["id"], reason=" ")
    assert r.status_code == 422 and r.json()["code"] == "reason_required"
    r = _decide(client, responsable, opp["id"])
    assert r.status_code == 200
    ws = r.json()["workspace"]
    assert ws["decision"] == "participar" and ws["decision_by"]["email"] == "responsable@dipromedic.example"
    assert ws["phase"] == "preparacion"
    [event] = _events("workspace.decision")
    assert event.before["decision"] == "pendiente" and event.after["decision"] == "participar"


def test_approval_permissions(client, analista):
    opp = _opp(client, analista)
    assert _approve(client, analista, opp["id"], "tecnica").status_code == 403
    assert _approve(client, _h(client, "revisor"), opp["id"], "comercial").status_code == 403
    assert _approve(client, _h(client, "responsable"), opp["id"], "tecnica").status_code == 403


def test_segregation_same_user_both_approvals_403(client):
    presentador = _h(client, "presentador")
    opp = _opp(client, presentador)
    r = _approve(client, presentador, opp["id"], "tecnica")
    assert r.status_code == 200 and r.json()["workspace"]["technical_approval_by"]["email"].startswith("presentador")
    r = _approve(client, presentador, opp["id"], "comercial")
    assert r.status_code == 403 and r.json()["code"] == "segregation"
    # Otra persona sí puede dar la aprobación comercial.
    r = _approve(client, _h(client, "responsable"), opp["id"], "comercial")
    assert r.status_code == 200
    ws = r.json()["workspace"]
    assert ws["commercial_approval_by"]["email"] == "responsable@dipromedic.example"
    assert ws["approvals_stale"] is False
    assert [e.after["kind"] for e in _events("workspace.approval")] == ["tecnica", "comercial"]


def test_change_after_approval_marks_stale(client):
    revisor, responsable, analista = _h(client, "revisor"), _h(client, "responsable"), _h(client, "analista1")
    opp = _opp(client, analista)
    assert _approve(client, revisor, opp["id"], "tecnica").status_code == 200
    assert _approve(client, responsable, opp["id"], "comercial").status_code == 200

    doc = client.post("/api/v1/documents", headers=analista,
                      files={"file": ("ficha.pdf", PDF, "application/pdf")},
                      data={"title": "Ficha técnica DEMO", "scope": "expediente", "data_kind": "SYNTHETIC",
                            "opportunity_id": opp["id"]}).json()
    req = next(r for r in client.get(f"/api/v1/opportunities/{opp['id']}/requirements", headers=analista).json()
               if r["code"] == "DEMO-REQ-005")
    r = client.post(f"/api/v1/requirements/{req['id']}/evidence", headers=analista,
                    json={"document_id": doc["id"], "version": 1, "page": 1})
    assert r.status_code == 201

    ws = _ws(client, analista, opp["id"])["workspace"]
    assert ws["approvals_stale"] is True
    assert ws["technical_approval_by"] is None and ws["commercial_approval_by"] is None
    [event] = _events("requirement.evidence_linked")
    assert event.after["workspace"]["approvals_cleared"] is True
    [invalidated] = _events("workspace.approvals_invalidated")
    assert invalidated.before["technical_approval_by_id"] is not None

    # Una aprobación nueva deja el expediente al día otra vez.
    r = _approve(client, revisor, opp["id"], "tecnica")
    assert r.json()["workspace"]["approvals_stale"] is False


# ── Compuerta «listo para revisión final» ────────────────────────────────────

def test_ready_requires_bid_decide(client, analista):
    r = client.post(f"/api/v1/workspaces/{_opp(client, analista)['id']}/ready", headers=analista)
    assert r.status_code == 403


def test_ready_blocked_with_missing_mandatory(client):
    """US06: un requisito obligatorio faltante bloquea el expediente aunque haya decisión y aprobaciones."""
    responsable, revisor = _h(client, "responsable"), _h(client, "revisor")
    opp = _opp(client, responsable)
    assert _decide(client, responsable, opp["id"]).status_code == 200
    assert _approve(client, revisor, opp["id"], "tecnica").status_code == 200
    assert _approve(client, responsable, opp["id"], "comercial").status_code == 200
    r = client.post(f"/api/v1/workspaces/{opp['id']}/ready", headers=responsable)
    assert r.status_code == 409 and r.json()["code"] == "not_ready"
    blockers = r.json()["details"]["blockers"]
    assert "DEMO-REQ-005" in blockers
    assert "aprobacion_tecnica" not in blockers and "decision" not in blockers
    items = {i["code"]: i for i in r.json()["details"]["items"]}
    assert items["DEMO-REQ-005"]["message"]
    # El bloqueante de la medida incompatible dice por qué, aunque el estado capturado siga «pendiente» y nadie
    # haya pulsado «Evaluar»: la compuerta corre el motor de nuevo.
    assert "El motor indica" in items["DEMO-REQ-003"]["message"]
    assert _ws(client, responsable, opp["id"])["workspace"]["phase"] == "preparacion"


def test_ready_lists_missing_decision_and_approvals(client):
    responsable = _h(client, "responsable")
    r = client.post(f"/api/v1/workspaces/{_opp(client, responsable)['id']}/ready", headers=responsable)
    blockers = r.json()["details"]["blockers"]
    assert {"decision", "aprobacion_tecnica", "aprobacion_comercial"} <= set(blockers)


def _scenario_ready_to_validate() -> tuple[str, list[str]]:
    """Oportunidad ficticia mínima: una partida con DEMO-PLA-001 y dos requisitos obligatorios."""
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    variant = db.scalars(select(Variant).where(Variant.sku == "DEMO-PLA-001")).one()
    opp = Opportunity(organization_id=org.id, external_id="DEMO-TEST-READY", normalized_id="DEMOTESTREADY",
                      title="Prueba de compuerta", buyer="Institución ficticia", data_kind="SYNTHETIC",
                      verification_status="simulada", families=["Osteosíntesis"])
    opp.lots.append(Lot(organization_id=org.id, number="1", description="Placa de 6 orificios",
                        family="Osteosíntesis", quantity=Decimal("10"), unit="pieza", specs={},
                        proposed_variant_id=variant.id))
    db.add(opp)
    db.flush()
    reqs = [
        Requirement(organization_id=org.id, code="TEST-REQ-1", opportunity_id=opp.id, lot_id=opp.lots[0].id,
                    text="Placa con 6 orificios", req_type="tecnico", mandatory=True, attribute="holes",
                    operator="eq", expected_value="6", unit="orificios", status="pendiente", data_kind="SYNTHETIC"),
        Requirement(organization_id=org.id, code="TEST-REQ-2", opportunity_id=opp.id, lot_id=opp.lots[0].id,
                    text="Ficha técnica", req_type="documental", mandatory=True, status="faltante",
                    data_kind="SYNTHETIC"),
        Requirement(organization_id=org.id, code="TEST-REQ-3", opportunity_id=opp.id, text="Carta opcional",
                    req_type="documental", mandatory=False, status="faltante", data_kind="SYNTHETIC"),
    ]
    db.add_all(reqs)
    db.commit()
    out = opp.id, [r.id for r in reqs[:2]]
    db.close()
    return out


def test_ready_succeeds_when_all_validated(client):
    opp_id, req_ids = _scenario_ready_to_validate()
    analista, revisor, responsable = _h(client, "analista1"), _h(client, "revisor"), _h(client, "responsable")
    _assess(client, analista, opp_id)
    doc = client.post("/api/v1/documents", headers=analista,
                      files={"file": ("ficha.pdf", PDF, "application/pdf")},
                      data={"title": "Ficha técnica DEMO", "scope": "expediente", "data_kind": "SYNTHETIC",
                            "opportunity_id": opp_id}).json()
    for rid in req_ids:
        row = client.post(f"/api/v1/requirements/{rid}/evidence", headers=analista,
                          json={"document_id": doc["id"], "version": 1, "page": 1}).json()
        r = client.patch(f"/api/v1/requirements/{rid}/review", headers=revisor,
                         json={"decision": "cumple_validado", "reason": "Revisado contra las bases",
                               "expected_version": row["version"]})
        assert r.status_code == 200, r.text
    assert _decide(client, responsable, opp_id).status_code == 200
    assert _approve(client, revisor, opp_id, "tecnica").status_code == 200
    assert _approve(client, responsable, opp_id, "comercial").status_code == 200
    r = client.post(f"/api/v1/workspaces/{opp_id}/ready", headers=responsable)
    assert r.status_code == 200, r.text
    assert r.json()["workspace"]["phase"] == "listo_revision_final"
    [event] = _events("workspace.ready")
    assert event.after["phase"] == "listo_revision_final"
    # La afinidad guardada ya refleja la documentación validada.
    assert r.json()["affinity"]["components"]["documental"]["score"] == 1.0

    # Un cambio posterior regresa el expediente a preparación y deja las aprobaciones sin efecto.
    second = client.post("/api/v1/documents", headers=analista,
                         files={"file": ("ficha2.pdf", PDF, "application/pdf")},
                         data={"title": "Ficha técnica DEMO v2", "scope": "expediente", "data_kind": "SYNTHETIC",
                               "opportunity_id": opp_id}).json()
    client.post(f"/api/v1/requirements/{req_ids[1]}/evidence", headers=analista,
                json={"document_id": second["id"], "version": 1})
    ws = _ws(client, analista, opp_id)["workspace"]
    assert ws["phase"] == "preparacion" and ws["approvals_stale"] is True


def test_validated_requirement_with_objective_mismatch_blocks(client):
    """Un requisito validado cuya evaluación objetiva es «incumple» es un conflicto: bloquea la compuerta."""
    opp_id, req_ids = _scenario_ready_to_validate()
    db = SessionLocal()
    req = db.get(Requirement, req_ids[0])
    req.expected_value = "8"
    db.commit()
    db.close()
    analista, revisor, responsable = _h(client, "analista1"), _h(client, "revisor"), _h(client, "responsable")
    doc = client.post("/api/v1/documents", headers=analista,
                      files={"file": ("ficha.pdf", PDF, "application/pdf")},
                      data={"title": "Ficha", "scope": "expediente", "data_kind": "SYNTHETIC",
                            "opportunity_id": opp_id}).json()
    for rid in req_ids:
        row = client.post(f"/api/v1/requirements/{rid}/evidence", headers=analista,
                          json={"document_id": doc["id"], "version": 1}).json()
        client.patch(f"/api/v1/requirements/{rid}/review", headers=revisor,
                     json={"decision": "cumple_validado", "reason": "Revisado", "expected_version": row["version"]})
    # Sin ninguna evaluación previa: la compuerta corre el motor y detecta el conflicto.
    db = SessionLocal()
    assert db.scalar(select(MatchAssessment.id).where(MatchAssessment.opportunity_id == opp_id)) is None
    db.close()
    _decide(client, responsable, opp_id)
    _approve(client, revisor, opp_id, "tecnica")
    _approve(client, responsable, opp_id, "comercial")
    r = client.post(f"/api/v1/workspaces/{opp_id}/ready", headers=responsable)
    assert r.status_code == 409 and r.json()["details"]["blockers"] == ["TEST-REQ-1"]
    assert r.json()["details"]["items"][0]["kind"] == "conflicto"


def _validate_all(client, opp_id, req_ids, uploader="analista1", reviewer="revisor"):
    up, rv = _h(client, uploader), _h(client, reviewer)
    doc = client.post("/api/v1/documents", headers=up, files={"file": ("ficha.pdf", PDF, "application/pdf")},
                      data={"title": "Ficha", "scope": "expediente", "data_kind": "SYNTHETIC",
                            "opportunity_id": opp_id}).json()
    for rid in req_ids:
        row = client.post(f"/api/v1/requirements/{rid}/evidence", headers=up,
                          json={"document_id": doc["id"], "version": 1}).json()
        r = client.patch(f"/api/v1/requirements/{rid}/review", headers=rv,
                         json={"decision": "cumple_validado", "reason": "Revisado", "expected_version": row["version"]})
        assert r.status_code == 200, r.text


def test_gate_rechecks_after_variant_change(client):
    """Evaluado y validado con una variante que coincide; si después cambia la variante propuesta, la compuerta
    vuelve a correr el motor y bloquea, aunque la evaluación guardada diga «coincide»."""
    opp_id, req_ids = _scenario_ready_to_validate()
    analista, revisor, responsable = _h(client, "analista1"), _h(client, "revisor"), _h(client, "responsable")
    assert _by_code(_assess(client, analista, opp_id))["TEST-REQ-1"]["result"] == "coincide"
    _validate_all(client, opp_id, req_ids)
    db = SessionLocal()
    lot = db.scalars(select(Lot).where(Lot.opportunity_id == opp_id)).one()
    lot.proposed_variant_id = db.scalars(select(Variant.id).where(Variant.sku == "DEMO-PLA-002")).one()  # 8 orificios
    db.commit()
    db.close()
    _decide(client, responsable, opp_id)
    _approve(client, revisor, opp_id, "tecnica")
    _approve(client, responsable, opp_id, "comercial")
    r = client.post(f"/api/v1/workspaces/{opp_id}/ready", headers=responsable)
    assert r.status_code == 409 and r.json()["details"]["blockers"] == ["TEST-REQ-1"]
    assert r.json()["details"]["items"][0]["kind"] == "conflicto"


def test_ready_blocked_without_requirements(client):
    """Un expediente sin requisitos obligatorios aplicables no pasa la compuerta aunque tenga decisión y aprobaciones."""
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    opp = Opportunity(organization_id=org.id, external_id="DEMO-TEST-EMPTY", normalized_id="DEMOTESTEMPTY",
                      title="Sin requisitos", buyer="Institución ficticia", data_kind="SYNTHETIC",
                      verification_status="simulada")
    db.add(opp)
    db.flush()
    db.add(Requirement(organization_id=org.id, code="TEST-OPT", opportunity_id=opp.id, text="Opcional",
                       req_type="documental", mandatory=False, status="faltante", data_kind="SYNTHETIC"))
    db.commit()
    opp_id = opp.id
    db.close()
    revisor, responsable = _h(client, "revisor"), _h(client, "responsable")
    _decide(client, responsable, opp_id)
    assert _approve(client, revisor, opp_id, "tecnica").status_code == 200
    assert _approve(client, responsable, opp_id, "comercial").status_code == 200
    r = client.post(f"/api/v1/workspaces/{opp_id}/ready", headers=responsable)
    assert r.status_code == 409 and r.json()["details"]["blockers"] == ["sin_requisitos"]
    assert r.json()["details"]["items"][0]["message"] == "No hay requisitos obligatorios aplicables capturados."


def test_historical_opportunity_is_never_a_workspace(client):
    presentador = _h(client, "presentador")
    hist = client.get("/api/v1/opportunities", params={"data_kind": "HISTORICAL"}, headers=presentador).json()["items"][0]
    calls = [
        client.post(f"/api/v1/workspaces/{hist['id']}/assess", headers=presentador),
        _decide(client, presentador, hist["id"]),
        _approve(client, presentador, hist["id"], "comercial"),
        client.post(f"/api/v1/workspaces/{hist['id']}/ready", headers=presentador),
    ]
    for r in calls:
        assert r.status_code == 409 and r.json()["code"] == "historical_opportunity", r.text
    assert r.json()["message"] == "Las referencias históricas no se preparan como expediente."
    db = SessionLocal()
    assert db.scalar(select(BidWorkspace.id).where(BidWorkspace.opportunity_id == hist["id"])) is None
    db.close()


def test_technical_approval_blocked_for_evidence_uploader(client):
    """Quien cargó o vinculó evidencia en la oportunidad no da la aprobación técnica; la comercial sí."""
    presentador = _h(client, "presentador")
    opp = _opp(client, presentador)
    doc = client.post("/api/v1/documents", headers=presentador, files={"file": ("ficha.pdf", PDF, "application/pdf")},
                      data={"title": "Ficha", "scope": "expediente", "data_kind": "SYNTHETIC",
                            "opportunity_id": opp["id"]}).json()
    req = next(r for r in client.get(f"/api/v1/opportunities/{opp['id']}/requirements", headers=presentador).json()
               if r["code"] == "DEMO-REQ-005")
    assert client.post(f"/api/v1/requirements/{req['id']}/evidence", headers=presentador,
                       json={"document_id": doc["id"], "version": 1}).status_code == 201
    r = _approve(client, presentador, opp["id"], "tecnica")
    assert r.status_code == 403 and r.json()["code"] == "self_approval"
    assert r.json()["message"] == ("No puedes aprobar técnicamente un expediente en el que cargaste evidencia. "
                                   "Cambia a la cuenta del revisor")
    assert _approve(client, presentador, opp["id"], "comercial").status_code == 200
    # Subir la versión (aunque otra persona la vincule) cuenta igual.
    revisor, analista = _h(client, "revisor"), _h(client, "analista1")
    doc2 = client.post("/api/v1/documents", headers=revisor, files={"file": ("f2.pdf", PDF, "application/pdf")},
                       data={"title": "Ficha 2", "scope": "expediente", "data_kind": "SYNTHETIC",
                             "opportunity_id": opp["id"]}).json()
    req6 = next(r for r in client.get(f"/api/v1/opportunities/{opp['id']}/requirements", headers=analista).json()
                if r["code"] == "DEMO-REQ-006")
    client.post(f"/api/v1/requirements/{req6['id']}/evidence", headers=analista,
                json={"document_id": doc2["id"], "version": 1})
    r = _approve(client, revisor, opp["id"], "tecnica")
    assert r.status_code == 403 and r.json()["code"] == "self_approval"


def test_existing_approval_is_not_replaced(client):
    revisor, presentador, analista = _h(client, "revisor"), _h(client, "presentador"), _h(client, "analista1")
    opp = _opp(client, revisor)
    assert _approve(client, revisor, opp["id"], "tecnica").status_code == 200
    version = _ws(client, revisor, opp["id"])["workspace"]["version"]
    r = _approve(client, presentador, opp["id"], "tecnica")
    assert r.status_code == 409 and r.json()["code"] == "already_approved"
    assert r.json()["message"] == ("Ya existe una aprobación técnica de Revisor técnico documental (demo); "
                                   "cualquier cambio en requisitos la invalida.")
    # Repetir la propia no cambia nada ni deja otro evento.
    assert _approve(client, revisor, opp["id"], "tecnica").status_code == 200
    assert _ws(client, revisor, opp["id"])["workspace"]["version"] == version
    assert len(_events("workspace.approval")) == 1
    # Un cambio en requisitos anula la aprobación y entonces otra persona sí puede darla.
    doc = client.post("/api/v1/documents", headers=analista, files={"file": ("f.pdf", PDF, "application/pdf")},
                      data={"title": "Ficha", "scope": "expediente", "data_kind": "SYNTHETIC",
                            "opportunity_id": opp["id"]}).json()
    req = next(r for r in client.get(f"/api/v1/opportunities/{opp['id']}/requirements", headers=analista).json()
               if r["code"] == "DEMO-REQ-005")
    client.post(f"/api/v1/requirements/{req['id']}/evidence", headers=analista,
                json={"document_id": doc["id"], "version": 1})
    r = _approve(client, presentador, opp["id"], "tecnica")
    assert r.status_code == 200
    assert r.json()["workspace"]["technical_approval_by"]["email"] == "presentador@dipromedic.example"


def test_view_blockers_match_the_gate(client, analista):
    """El panel lista los bloqueantes con su motivo, con el motor corrido sobre los datos actuales (sin «Evaluar»)."""
    view = _ws(client, analista, _opp(client, analista)["id"])
    assert view["assessments"] == []
    blockers = {b["code"]: b for b in view["blockers"]}
    assert blockers["DEMO-REQ-003"] == {"code": "DEMO-REQ-003", "reason": "motor", "status": "pendiente"}
    assert blockers["DEMO-REQ-005"]["reason"] == "estado"
    assert "DEMO-REQ-001" not in blockers
    lic008 = _ws(client, analista, _opp(client, analista, "DEMO-LIC-008")["id"])
    assert {b["code"]: b["reason"] for b in lic008["blockers"]}["DEMO-REQ-020"] == "no_determinable"


def test_history_includes_workspace_events(client):
    responsable = _h(client, "responsable")
    opp = _opp(client, responsable)
    assert _decide(client, responsable, opp["id"]).status_code == 200
    history = client.get(f"/api/v1/opportunities/{opp['id']}/history", headers=responsable).json()
    assert "workspace.decision" in [e["action"] for e in history]


def test_workspace_of_other_organization_is_404(client, analista):
    db = SessionLocal()
    other = Organization(name="Otra")
    db.add(other)
    db.flush()
    foreign = Opportunity(organization_id=other.id, external_id="X-1", normalized_id="X1", title="Ajena",
                          buyer="X", data_kind="REAL", verification_status="por_verificar")
    db.add(foreign)
    db.commit()
    fid = foreign.id
    db.close()
    assert client.get(f"/api/v1/workspaces/{fid}", headers=analista).status_code == 404
    assert client.post(f"/api/v1/workspaces/{fid}/assess", headers=analista).status_code == 404


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="sólo Postgres (SQLite no tiene FOR UPDATE)")
def test_concurrent_approvals_by_same_user_cannot_both_succeed():
    """Doble clic simultáneo: la misma persona no puede quedarse con la aprobación técnica y la comercial."""
    db = SessionLocal()
    opp = db.scalars(select(Opportunity).where(Opportunity.external_id == "DEMO-LIC-001")).one()
    ws_id = workspace.get_or_create_workspace(db, opp).id
    user_id = db.scalars(select(User.id).where(User.email == "presentador@dipromedic.example")).one()
    db.commit()
    db.close()
    barrier, results = threading.Barrier(2), []

    def worker(kind: str):
        s = SessionLocal()
        try:
            user, ws = s.get(User, user_id), s.get(BidWorkspace, ws_id)
            barrier.wait()
            workspace.approve(s, user, ws, kind)
            time.sleep(0.5)                       # la transacción sigue abierta: la otra debe esperar
            s.commit()
            results.append("ok")
        except AppError as e:
            s.rollback()
            results.append(e.code)
        finally:
            s.close()

    threads = [threading.Thread(target=worker, args=(k,)) for k in ("tecnica", "comercial")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert sorted(results) == ["ok", "segregation"]
