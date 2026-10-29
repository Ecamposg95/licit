"""E4: evidencia a revisión, validación sin autoaprobación, vigencia a fecha exigida y tareas."""
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import AuditEvent, Opportunity, Organization, Requirement, Task
from app.services.demo_documents import render_upload_sample
from tests.conftest import login

PDF = render_upload_sample()


def _headers(client, who: str) -> dict:
    return login(client, f"{who}@dipromedic.example")


def _opp(client, headers, code="DEMO-LIC-001") -> dict:
    return client.get("/api/v1/opportunities", params={"q": code}, headers=headers).json()["items"][0]


def _req(client, headers, code: str, opp_code="DEMO-LIC-001") -> dict:
    opp = _opp(client, headers, opp_code)
    rows = client.get(f"/api/v1/opportunities/{opp['id']}/requirements", headers=headers).json()
    return next(r for r in rows if r["code"] == code)


def _upload(client, headers, opp_id: str, title="Ficha técnica DEMO para carga") -> dict:
    r = client.post("/api/v1/documents", headers=headers,
                    files={"file": ("Ficha_tecnica_DEMO_para_carga.pdf", PDF, "application/pdf")},
                    data={"title": title, "scope": "expediente", "doc_type": "ficha_tecnica",
                          "data_kind": "SYNTHETIC", "opportunity_id": opp_id})
    assert r.status_code == 201, r.text
    return r.json()


def _link(client, headers, req_id: str, doc: dict, page=1, fragment="Ficha técnica del producto propuesto"):
    return client.post(f"/api/v1/requirements/{req_id}/evidence", headers=headers,
                       json={"document_id": doc["id"], "version": doc["versions"][-1]["version"],
                             "page": page, "fragment": fragment})


def _review(client, headers, req: dict, decision="cumple_validado", reason="Ficha revisada contra las bases",
            version=None):
    return client.patch(f"/api/v1/requirements/{req['id']}/review", headers=headers,
                        json={"decision": decision, "reason": reason,
                              "expected_version": req["version"] if version is None else version})


def _events(action: str, resource_id: str) -> list[AuditEvent]:
    db = SessionLocal()
    try:
        return list(db.scalars(select(AuditEvent).where(AuditEvent.action == action,
                                                        AuditEvent.resource_id == resource_id)))
    finally:
        db.close()


def _uploaded_and_linked(client, who: str, code="DEMO-REQ-005") -> tuple[dict, dict]:
    h = _headers(client, who)
    opp = _opp(client, h)
    doc = _upload(client, h, opp["id"])
    req = _req(client, h, code)
    r = _link(client, h, req["id"], doc)
    assert r.status_code == 201, r.text
    return r.json(), doc


# ── Evidencia ────────────────────────────────────────────────────────────────

def test_new_evidence_goes_to_review_not_valid(client):
    before = _req(client, _headers(client, "analista1"), "DEMO-REQ-005")
    assert before["status"] == "faltante"
    row, doc = _uploaded_and_linked(client, "analista1")
    assert row["status"] == "en_revision"            # US04: nunca directo a cumple_validado
    assert row["version"] == before["version"] + 1
    ev = row["evidence"][-1]
    assert ev["decision"] == "propuesta" and ev["document_id"] == doc["id"] and ev["page"] == 1
    assert ev["created_by"]["email"] == "analista1@dipromedic.example"
    assert ev["uploaded_by"]["email"] == "analista1@dipromedic.example"
    assert ev["document_version"] == 1 and ev["validity"] == "sin_vigencia"
    [event] = _events("requirement.evidence_linked", row["id"])
    assert event.before["status"] == "faltante" and event.after["status"] == "en_revision"
    assert event.after["document_version"] == 1


def test_link_evidence_requires_upload_permission(client):
    h = _headers(client, "direccion")
    req = _req(client, h, "DEMO-REQ-005")
    doc = _upload(client, _headers(client, "analista1"), _opp(client, h)["id"])
    assert _link(client, h, req["id"], doc).status_code == 403


def test_same_version_cannot_be_linked_twice(client):
    h = _headers(client, "analista1")
    row, doc = _uploaded_and_linked(client, "analista1")
    r = _link(client, h, row["id"], doc)
    assert r.status_code == 409 and r.json()["code"] == "evidence_already_linked"


# ── Revisión ─────────────────────────────────────────────────────────────────

def test_self_approval_blocked_even_for_presentador(client):
    row, _doc = _uploaded_and_linked(client, "presentador")
    r = _review(client, _headers(client, "presentador"), row)
    assert r.status_code == 403 and r.json()["code"] == "self_approval"
    assert r.json()["message"] == "No puedes aprobar evidencia que tú cargaste. Cambia a la cuenta del revisor"
    after = _req(client, _headers(client, "presentador"), "DEMO-REQ-005")
    assert after["status"] == "en_revision" and after["version"] == row["version"]
    # Tampoco puede cerrarlo como «no aplica».
    r = _review(client, _headers(client, "presentador"), row, decision="no_aplica_justificado")
    assert r.status_code == 403 and r.json()["code"] == "self_approval"


def test_uploader_of_linked_version_cannot_approve(client):
    """Subir la versión cuenta igual que vincularla: el revisor no aprueba su propio archivo."""
    revisor, analista = _headers(client, "revisor"), _headers(client, "analista1")
    doc = _upload(client, revisor, _opp(client, revisor)["id"])
    req = _req(client, analista, "DEMO-REQ-005")
    row = _link(client, analista, req["id"], doc).json()
    r = _review(client, revisor, row)
    assert r.status_code == 403 and r.json()["code"] == "self_approval"


def test_reviewer_can_validate_others_evidence(client):
    row, _doc = _uploaded_and_linked(client, "analista1")
    r = _review(client, _headers(client, "revisor"), row)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "cumple_validado"
    assert body["reviewer"]["email"] == "revisor@dipromedic.example"
    assert body["status_reason"] == "Ficha revisada contra las bases"
    assert body["evidence"][-1]["decision"] == "aceptada"
    assert body["evidence"][-1]["reviewer"]["email"] == "revisor@dipromedic.example"
    [event] = _events("requirement.review", row["id"])
    assert event.before["status"] == "en_revision" and event.after["status"] == "cumple_validado"
    assert event.after["decision"] == "cumple_validado"


def test_new_evidence_on_validated_requirement_goes_back_to_review(client):
    row, _doc = _uploaded_and_linked(client, "analista1")
    assert _review(client, _headers(client, "revisor"), row).status_code == 200
    h = _headers(client, "analista1")
    second = _upload(client, h, _opp(client, h)["id"], title="Ficha técnica corregida")
    r = _link(client, h, row["id"], second)
    assert r.status_code == 201 and r.json()["status"] == "en_revision"
    assert r.json()["reviewer"] is None


def test_stale_version_409(client):
    row, _doc = _uploaded_and_linked(client, "analista1")
    r = _review(client, _headers(client, "revisor"), row, version=row["version"] - 1)
    assert r.status_code == 409 and r.json()["code"] == "version_conflict"
    assert r.json()["details"]["current_version"] == row["version"]


def test_expired_evidence_blocks_validation(client):
    """DEMO-DOC-002 de LIC-005 está vigente hoy (+90 días) pero vence antes de la entrega exigida (+120)."""
    revisor = _headers(client, "revisor")
    req = _req(client, revisor, "DEMO-REQ-014", "DEMO-LIC-005")
    assert req["evidence"][0]["document_code"] == "DEMO-DOC-002"
    assert req["evidence"][0]["validity"] == "vence_antes"
    r = _review(client, revisor, req, reason="Certificado del fabricante revisado")
    assert r.status_code == 422 and r.json()["code"] == "evidence_expired"
    assert r.json()["details"]["evidence"][0]["validity"] == "vence_antes"
    assert _req(client, revisor, "DEMO-REQ-014", "DEMO-LIC-005")["status"] == "vencido"


def test_expired_today_blocks_validation(client):
    revisor = _headers(client, "revisor")
    req = _req(client, revisor, "DEMO-REQ-012", "DEMO-LIC-004")
    r = _review(client, revisor, req, reason="Certificado revisado")
    assert r.status_code == 422 and r.json()["details"]["evidence"][0]["validity"] == "vencido"


def test_reason_required(client):
    row, _doc = _uploaded_and_linked(client, "analista1")
    r = _review(client, _headers(client, "revisor"), row, reason="   ")
    assert r.status_code == 422 and r.json()["code"] == "reason_required"


def test_validation_requires_evidence(client):
    revisor = _headers(client, "revisor")
    req = _req(client, revisor, "DEMO-REQ-006")
    r = _review(client, revisor, req, reason="Sin evidencia")
    assert r.status_code == 422 and r.json()["code"] == "evidence_required"


def test_rejecting_marks_evidence_rejected(client):
    row, _doc = _uploaded_and_linked(client, "analista1")
    r = _review(client, _headers(client, "revisor"), row, decision="faltante", reason="La ficha no es del producto")
    assert r.status_code == 200 and r.json()["status"] == "faltante"
    assert r.json()["evidence"][-1]["decision"] == "rechazada"


def test_analista_cannot_review(client):
    analista = _headers(client, "analista1")
    row, _doc = _uploaded_and_linked(client, "analista2")
    r = _review(client, analista, row)
    assert r.status_code == 403 and r.json()["code"] == "forbidden"


def test_other_organization_requirement_is_404(client):
    db = SessionLocal()
    other = Organization(name="Otra")
    db.add(other)
    db.flush()
    opp = Opportunity(organization_id=other.id, external_id="X-1", normalized_id="X1", title="Ajena", buyer="X",
                      data_kind="REAL", verification_status="por_verificar")
    db.add(opp)
    db.flush()
    foreign = Requirement(organization_id=other.id, opportunity_id=opp.id, text="Ajeno", status="en_revision",
                          data_kind="REAL")
    db.add(foreign)
    db.commit()
    rid = foreign.id
    db.close()
    r = client.patch(f"/api/v1/requirements/{rid}/review", headers=_headers(client, "presentador"),
                     json={"decision": "cumple_validado", "reason": "x", "expected_version": 1})
    assert r.status_code == 404
    analista = _headers(client, "analista1")
    doc = _upload(client, analista, _opp(client, analista)["id"])
    assert _link(client, analista, rid, doc).status_code == 404


# ── Tareas ───────────────────────────────────────────────────────────────────

def test_assign_task_audited(client):
    analista = _headers(client, "analista1")
    users = {u["email"]: u for u in client.get("/api/v1/users", headers=analista).json()}
    req = _req(client, analista, "DEMO-REQ-005")
    assert req["open_task"] is None
    r = client.post(f"/api/v1/requirements/{req['id']}/tasks", headers=analista,
                    json={"assignee_id": users["analista2@dipromedic.example"]["id"], "due_date": "2026-11-04"})
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["assignee"]["email"] == "analista2@dipromedic.example" and task["status"] == "pendiente"
    assert task["title"].startswith("Atender requisito DEMO-REQ-005")
    assert task["data_kind"] == "SYNTHETIC"
    row = _req(client, analista, "DEMO-REQ-005")
    assert row["open_task"]["assignee"] == users["analista2@dipromedic.example"]["full_name"]
    [event] = _events("task.assign", task["id"])
    assert event.actor_id == users["analista1@dipromedic.example"]["id"]
    assert event.after["requirement_code"] == "DEMO-REQ-005" and event.before is None

    # Reasignar no duplica la actividad abierta: se reasigna la misma y queda en la bitácora.
    r = client.post(f"/api/v1/requirements/{req['id']}/tasks", headers=analista,
                    json={"assignee_id": users["analista3@dipromedic.example"]["id"]})
    assert r.status_code == 201 and r.json()["id"] == task["id"]
    assert r.json()["due_date"] == "2026-11-04"
    events = _events("task.assign", task["id"])
    assert len(events) == 2 and any(e.before for e in events)


def test_assign_requires_permission(client):
    revisor = _headers(client, "revisor")
    users = client.get("/api/v1/users", headers=revisor).json()
    req = _req(client, revisor, "DEMO-REQ-005")
    r = client.post(f"/api/v1/requirements/{req['id']}/tasks", headers=revisor, json={"assignee_id": users[0]["id"]})
    assert r.status_code == 403


def test_task_status_update(client):
    analista = _headers(client, "analista1")
    db = SessionLocal()
    task_id = db.scalars(select(Task.id).where(Task.code == "DEMO-TASK-001")).one()
    db.close()
    r = client.patch(f"/api/v1/tasks/{task_id}", headers=analista, json={"status": "en_progreso"})
    assert r.status_code == 200 and r.json()["status"] == "en_progreso"
    [event] = _events("task.update", task_id)
    assert event.before["status"] == "pendiente" and event.after["status"] == "en_progreso"
    assert client.patch(f"/api/v1/tasks/{task_id}", headers=analista, json={"status": "x"}).status_code == 422
    assert client.patch(f"/api/v1/tasks/{task_id}", headers=_headers(client, "direccion"),
                        json={"status": "hecha"}).status_code == 403
