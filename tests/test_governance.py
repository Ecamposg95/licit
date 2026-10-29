"""Frente G: gobierno corporativo (integridad, matriz de permisos, aprobaciones), cuentas demo,
datos del panel de dirección y estado operativo."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text

from app.core.database import SessionLocal, engine
from app.core.permissions import ROLE_LABELS, ROLE_PERMISSIONS, Perm
from app.models import AuditEvent, DemoRun, Organization, Requirement, User
from app.models.base import utcnow
from app.services import audit

from tests.conftest import login


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _org_id(db) -> str:
    return db.scalars(select(Organization)).first().id


def _user(db, email: str) -> User:
    return db.scalars(select(User).where(User.email == email)).one()


def _record(db, action: str, *, email: str = "revisor@dipromedic.example", resource_type: str = "requirement",
            resource_id: str | None = None, before: dict | None = None, after: dict | None = None):
    """Inserta un evento de auditoría directamente (el frente E los emite en paralelo)."""
    event = audit.record(db, organization_id=_org_id(db), actor_id=_user(db, email).id, action=action,
                         resource_type=resource_type, resource_id=resource_id, before=before, after=after)
    db.commit()
    return event


def _count_events(db, action: str) -> int:
    return db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action))


# ── G1 · Integridad de la bitácora ───────────────────────────────────────────

def test_verify_ok(client, direccion):
    db = SessionLocal()
    before = db.scalar(select(func.count()).select_from(AuditEvent))
    head = db.execute(select(AuditEvent.hash, AuditEvent.created_at).order_by(
        AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(1)).one()
    db.close()

    r = client.get("/api/v1/governance/audit/verify", headers=direccion)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["first_broken_id"] is None
    assert body["checked"] == before and body["checked"] > 0
    assert body["verified_at"]
    # Se informa el último hash verificado (el del evento número `checked`) y la hora de ese evento,
    # para que quien presenta pueda anotarlo y anclarlo fuera de la base de datos.
    assert body["last_hash"] == head.hash and len(body["last_hash"]) == 64
    assert _utc(datetime.fromisoformat(body["last_event_at"])) == _utc(head.created_at)
    # La verificación queda en la bitácora, con quien la pidió y su resultado.
    db = SessionLocal()
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "audit.verify")).one()
    assert event.actor_id == _user(db, "direccion@dipromedic.example").id
    assert event.after["ok"] is True and event.after["checked"] == before and event.after["last_hash"] == head.hash
    # Y la cadena sigue íntegra después de registrar la verificación.
    assert audit.verify_chain(db, _org_id(db)) == (True, before + 1, None)
    db.close()


def test_verify_detects_tamper_sqlite(client, direccion):
    if engine.dialect.name != "sqlite":
        pytest.skip("En Postgres el trigger impide modificar la bitácora")
    db = SessionLocal()
    _record(db, "test.uno", resource_type="organization")
    target_id = _record(db, "test.dos", resource_type="organization", after={"monto": "100.00"}).id
    _record(db, "test.tres", resource_type="organization")
    order = list(db.scalars(select(AuditEvent.id).where(AuditEvent.organization_id == _org_id(db))
                            .order_by(AuditEvent.created_at, AuditEvent.id)))
    db.execute(text("UPDATE audit_events SET after = :v WHERE id = :id"),
               {"v": json.dumps({"monto": "1.00"}), "id": target_id})
    db.commit()
    db.close()

    r = client.get("/api/v1/governance/audit/verify", headers=direccion)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert body["last_hash"] is None and body["last_event_at"] is None    # una cadena rota no tiene cabeza que anotar
    assert body["first_broken_id"] == target_id
    assert body["checked"] == order.index(target_id) + 1


def test_verify_empty_log_has_no_hash(client):
    from app.core.security import create_access_token, get_password_hash
    from app.models import UserRole

    db = SessionLocal()
    org = Organization(name="Otra organización", demo_mode=True)
    db.add(org)
    db.flush()
    user = User(organization_id=org.id, email="auditor@otra.example", full_name="Auditor",
                hashed_password=get_password_hash("x"))
    user.roles = [UserRole(role="direccion")]
    db.add(user)
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}       # sin login: sin eventos
    db.close()

    body = client.get("/api/v1/governance/audit/verify", headers=headers).json()

    assert body["checked"] == 0 and body["ok"] is True
    assert body["last_hash"] is None and body["last_event_at"] is None           # nada que verificar, nada que anotar
    again = client.get("/api/v1/governance/audit/verify", headers=headers).json()
    assert again["checked"] == 1 and len(again["last_hash"]) == 64                # el evento audit.verify anterior


def test_permissions_matrix_matches_code(client, direccion):
    r = client.get("/api/v1/governance/permissions", headers=direccion)

    assert r.status_code == 200, r.text
    body = r.json()
    roles = {row["role"]: row for row in body["roles"]}
    assert list(roles) == [role.value for role in ROLE_PERMISSIONS]
    for role, perms in ROLE_PERMISSIONS.items():
        assert roles[role.value]["label"] == ROLE_LABELS[role]
        assert set(roles[role.value]["permissions"]) == {p.value for p in perms}
    # Cada permiso del código tiene su texto en español, y la matriz no menciona permisos desconocidos.
    labels = {p["code"]: p["label_es"] for p in body["permissions"]}
    assert set(labels) == {p.value for p in Perm}
    assert all(label.strip() and label != code for code, label in labels.items())
    assert [p["code"] for p in body["permissions"]] == [p.value for p in Perm]


@pytest.mark.parametrize("path", [
    "/api/v1/governance/audit/verify",
    "/api/v1/governance/permissions",
    "/api/v1/governance/approvals",
    "/api/v1/governance/runs",
])
def test_analista_forbidden(client, analista, path):
    r = client.get(path, headers=analista)
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"
    assert client.get(path).status_code == 401


def test_verify_forbidden_leaves_no_event(client, analista):
    client.get("/api/v1/governance/audit/verify", headers=analista)
    db = SessionLocal()
    assert _count_events(db, "audit.verify") == 0
    db.close()


APPROVAL_ACTIONS = ["requirement.review", "workspace.decision", "workspace.approval", "workspace.ready",
                    "artifact.download"]


def test_approvals_lists_only_approval_events_of_current_run(client, direccion):
    db = SessionLocal()
    old_run = _record(db, "workspace.decision", email="responsable@dipromedic.example",
                      resource_type="bid_workspace", after={"decision": "participar", "decision_reason": "Ensayo"}).demo_run_id
    # Un reinicio del demo abre una corrida nueva: los eventos del ensayo salen de la lista por omisión.
    db.add(DemoRun(organization_id=_org_id(db), started_at=utcnow() + timedelta(seconds=1)))
    db.commit()
    for action in APPROVAL_ACTIONS:
        _record(db, action, resource_type="bid_workspace", after={"reason": f"motivo de {action}"})
    _record(db, "opportunity.update", resource_type="opportunity")       # no es una aprobación
    db.close()

    r = client.get("/api/v1/governance/approvals", headers=direccion)

    assert r.status_code == 200, r.text
    items = r.json()
    assert sorted(i["action"] for i in items) == sorted(APPROVAL_ACTIONS)
    assert "ensayo" not in json.dumps(items).lower()
    first = items[0]
    assert first["actor"]["email"] == "revisor@dipromedic.example"
    assert first["roles"] == [{"role": "revisor_tecnico", "label": "Revisor técnico documental"}]
    assert first["created_at"] and first["demo_run_id"]
    # Con la corrida anterior indicada, salen sus eventos y no los de la actual.
    old = client.get("/api/v1/governance/approvals", params={"demo_run_id": old_run}, headers=direccion).json()
    assert [i["action"] for i in old] == ["workspace.decision"]
    assert old[0]["reason"] == "Ensayo" and old[0]["outcome"] == "participar"
    assert old[0]["actor"]["email"] == "responsable@dipromedic.example"
    # Una corrida que no existe es 404, no una lista vacía que parezca «sin aprobaciones».
    assert client.get("/api/v1/governance/approvals", params={"demo_run_id": "no-existe"},
                      headers=direccion).status_code == 404


def test_approvals_resolve_target_and_reason(client, direccion):
    db = SessionLocal()
    req = db.scalars(select(Requirement).where(Requirement.code == "DEMO-REQ-005")).one()
    _record(db, "requirement.review", resource_type="requirement", resource_id=req.id,
            before={"status": "en_revision"},
            after={"status": "cumple_validado", "status_reason": "Certificado vigente", "decision": "cumple_validado"})
    db.close()

    items = client.get("/api/v1/governance/approvals", headers=direccion).json()

    assert len(items) == 1
    item = items[0]
    assert item["reason"] == "Certificado vigente" and item["outcome"] == "cumple_validado"
    assert item["target"]["requirement_code"] == "DEMO-REQ-005"
    assert item["target"]["opportunity_external_id"] == "DEMO-LIC-001"
    assert item["target"]["data_kind"] == "SYNTHETIC"
    assert item["before"] == {"status": "en_revision"}


def test_approvals_reason_comes_only_from_after(client, direccion):
    db = SessionLocal()
    req = db.scalars(select(Requirement).where(Requirement.code == "DEMO-REQ-005")).one()
    _record(db, "requirement.review", resource_type="requirement", resource_id=req.id,
            before={"status": "en_revision", "status_reason": "Motivo del estado anterior"},
            after={"status": "incumple", "decision": "incumple"})
    db.close()

    item = client.get("/api/v1/governance/approvals", headers=direccion).json()[0]

    assert item["outcome"] == "incumple"
    assert item["reason"] is None             # una decisión nunca muestra el motivo del estado previo
    assert item["before"]["status_reason"] == "Motivo del estado anterior"


def test_approvals_from_the_real_workspace_flow(client, direccion):
    """Integración 2: con los servicios reales de E (y la descarga de F), cada evento trae objetivo y resultado, y la
    revisión y la decisión traen su motivo. La aprobación, la compuerta y la descarga no piden motivo: se muestran
    sin él en lugar de inventarlo."""
    from app.services import jobs
    from tests.test_workspace import _scenario_ready_to_validate, _validate_all

    opp_id, req_ids = _scenario_ready_to_validate()
    revisor, responsable = login(client, "revisor@dipromedic.example"), login(client, "responsable@dipromedic.example")
    analista = login(client, "analista1@dipromedic.example")
    _validate_all(client, opp_id, req_ids)
    assert client.post(f"/api/v1/workspaces/{opp_id}/decision", headers=responsable,
                       json={"decision": "participar", "reason": "Plazos y cartera viables"}).status_code == 200
    assert client.post(f"/api/v1/workspaces/{opp_id}/approvals", headers=revisor,
                       json={"kind": "tecnica"}).status_code == 200
    assert client.post(f"/api/v1/workspaces/{opp_id}/approvals", headers=responsable,
                       json={"kind": "comercial"}).status_code == 200
    r = client.post(f"/api/v1/workspaces/{opp_id}/ready", headers=responsable)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/workspaces/{opp_id}/generate", headers={**analista, "Idempotency-Key": "gov-flow"})
    assert r.status_code == 202, r.text
    with SessionLocal() as db:
        while jobs.run_pending_once(db) is not None:
            pass
    [artifact] = client.get(f"/api/v1/workspaces/{opp_id}/artifacts", headers=direccion).json()
    assert client.get(f"/api/v1/artifacts/{artifact['id']}/download", headers=direccion).status_code == 200

    items = client.get("/api/v1/governance/approvals", headers=direccion).json()

    by_action: dict[str, list[dict]] = {}
    for item in items:
        by_action.setdefault(item["action"], []).append(item)
    assert set(by_action) == set(APPROVAL_ACTIONS)
    for item in items:
        assert item["target"] and item["target"]["opportunity_id"] == opp_id, item
        assert item["target"]["opportunity_external_id"] == "DEMO-TEST-READY"
        assert item["outcome"], item
    reviews = by_action["requirement.review"]
    assert len(reviews) == 2
    assert {i["target"]["requirement_code"] for i in reviews} == {"TEST-REQ-1", "TEST-REQ-2"}
    assert all(i["reason"] == "Revisado" and i["outcome"] == "cumple_validado" for i in reviews)
    [decision] = by_action["workspace.decision"]
    assert decision["reason"] == "Plazos y cartera viables" and decision["outcome"] == "participar"
    assert sorted(i["outcome"] for i in by_action["workspace.approval"]) == ["comercial", "tecnica"]
    [ready] = by_action["workspace.ready"]
    assert ready["outcome"] == "listo_revision_final"
    [download] = by_action["artifact.download"]
    assert download["outcome"] == artifact["filename"]
    assert all(i["reason"] is None for a in ("workspace.approval", "workspace.ready", "artifact.download")
               for i in by_action[a])


def test_approvals_without_events_is_empty_list(client, direccion):
    assert client.get("/api/v1/governance/approvals", headers=direccion).json() == []


def test_runs_listed_with_summary(client, direccion):
    db = SessionLocal()
    first_id = db.scalars(select(DemoRun)).one().id
    db.add(DemoRun(organization_id=_org_id(db), started_at=utcnow() + timedelta(seconds=1),
                   summary={"scenarios": 3}))
    db.commit()
    _record(db, "workspace.decision", resource_type="bid_workspace", after={"decision": "participar"})
    db.close()

    runs = client.get("/api/v1/governance/runs", headers=direccion).json()

    assert len(runs) == 2
    assert [r["is_current"] for r in runs] == [True, False]
    assert runs[1]["id"] == first_id and runs[1]["summary"]["scenarios"] == 8     # el resumen del reinicio semilla
    assert runs[0]["summary"] == {"scenarios": 3}
    assert runs[0]["approvals"] == 1 and runs[1]["approvals"] == 0
    assert runs[1]["events"] >= 1


# ── G2 · Cuentas demo y vencimiento ──────────────────────────────────────────

def test_demo_accounts_listed_without_secrets(client):
    r = client.get("/api/v1/demo/accounts")      # sin autenticación

    assert r.status_code == 200, r.text
    accounts = r.json()
    assert [a["email"] for a in accounts] == [
        "direccion@dipromedic.example", "analista1@dipromedic.example", "analista2@dipromedic.example",
        "analista3@dipromedic.example", "revisor@dipromedic.example", "responsable@dipromedic.example",
        "ti@dipromedic.example", "presentador@dipromedic.example",
    ]
    for account in accounts:
        assert set(account) == {"email", "full_name", "roles"}
        assert not any("pass" in key.lower() for key in account)
        assert account["full_name"] and account["roles"]
    by_email = {a["email"]: a for a in accounts}
    assert by_email["revisor@dipromedic.example"]["roles"] == ["Revisor técnico documental"]
    assert len(by_email["presentador@dipromedic.example"]["roles"]) == len(ROLE_LABELS)
    # Nada que sirva para entrar o para identificar filas: ni la contraseña de demo, ni hashes, ni ids.
    raw = r.text
    assert "demo-pass" not in raw and "$2b$" not in raw and "hashed" not in raw
    db = SessionLocal()
    assert not any(u.id in raw for u in db.scalars(select(User)))
    db.close()


def test_demo_accounts_only_active_unexpired_demo_domain(client):
    from app.core.security import get_password_hash

    db = SessionLocal()
    org_id = _org_id(db)
    _user(db, "analista2@dipromedic.example").is_active = False
    _user(db, "analista3@dipromedic.example").expires_at = utcnow() - timedelta(minutes=1)
    _user(db, "revisor@dipromedic.example").expires_at = utcnow() + timedelta(days=1)     # vigente: se lista
    db.add(User(organization_id=org_id, email="gerente@cliente.example", full_name="Cuenta real",
                hashed_password=get_password_hash("x")))
    db.commit()
    db.close()

    emails = [a["email"] for a in client.get("/api/v1/demo/accounts").json()]

    assert "analista2@dipromedic.example" not in emails           # inactiva
    assert "analista3@dipromedic.example" not in emails           # vencida: no podría entrar
    assert "gerente@cliente.example" not in emails                # otro dominio
    assert "revisor@dipromedic.example" in emails
    assert "analista1@dipromedic.example" in emails


def test_demo_accounts_404_when_not_demo(client, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config, "DEMO_MODE", False)

    r = client.get("/api/v1/demo/accounts")

    assert r.status_code == 404
    assert r.json()["code"] == "not_found"
    assert "dipromedic" not in r.text


def test_expired_account_login_401(client):
    db = SessionLocal()
    _user(db, "analista1@dipromedic.example").expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    db.close()

    r = client.post("/api/v1/auth/login", data={"username": "analista1@dipromedic.example", "password": "demo-pass"})

    assert r.status_code == 401
    assert r.json()["code"] == "account_expired"
    assert "venci" in r.json()["message"].lower()
    # Con la contraseña equivocada no se revela que la cuenta venció.
    bad = client.post("/api/v1/auth/login", data={"username": "analista1@dipromedic.example", "password": "otra"})
    assert bad.status_code == 401 and bad.json()["code"] == "invalid_credentials"
    # Una cuenta que vence en el futuro sí entra.
    db = SessionLocal()
    _user(db, "analista1@dipromedic.example").expires_at = utcnow() + timedelta(hours=1)
    db.commit()
    db.close()
    ok = client.post("/api/v1/auth/login", data={"username": "analista1@dipromedic.example", "password": "demo-pass"})
    assert ok.status_code == 200


def test_expired_account_token_rejected(client):
    headers = login(client, "analista1@dipromedic.example")
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    db = SessionLocal()
    _user(db, "analista1@dipromedic.example").expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    db.close()

    for path in ("/api/v1/auth/me", "/api/v1/opportunities", "/api/v1/meta"):
        r = client.get(path, headers=headers)
        assert r.status_code == 401, path
        assert r.json()["code"] == "account_expired"
    # Otra cuenta no se ve afectada.
    assert client.get("/api/v1/auth/me", headers=login(client, "revisor@dipromedic.example")).status_code == 200


# ── G3 · Datos para dirección y TI ───────────────────────────────────────────

def _real_opportunity(db, external_id: str, *, verified: bool = True, submission_in_days: int | None = 10,
                      checked_hours_ago: int = 1) -> str:
    from app.models import Opportunity, Source

    org_id = _org_id(db)
    source = db.scalars(select(Source).where(Source.key == "dof_sidof")).one()
    now = utcnow()
    opp = Opportunity(
        organization_id=org_id, external_id=external_id, normalized_id=external_id.replace("-", ""),
        title=f"Procedimiento real {external_id}", buyer="IMSS", data_kind="REAL", source_id=source.id,
        source_url="https://sidof.segob.gob.mx/notas/1", last_checked_at=now - timedelta(hours=checked_hours_ago),
        verification_status="verificada" if verified else "por_verificar",
        submission_at=now + timedelta(days=submission_in_days) if submission_in_days is not None else None,
        families=["Osteosíntesis"])
    db.add(opp)
    db.commit()
    return opp.id


def test_dashboard_never_mixes_kinds(client, direccion):
    db = SessionLocal()
    _real_opportunity(db, "REAL-A")
    _real_opportunity(db, "REAL-B", verified=False)
    db.close()

    r = client.get("/api/v1/dashboard/direccion", headers=direccion)

    assert r.status_code == 200, r.text
    body = r.json()
    assert "total" not in body                                   # nunca un total combinado
    assert set(body["by_data_kind"]) == {"REAL", "HISTORICAL", "SYNTHETIC"}
    kinds = body["by_data_kind"]
    assert kinds["REAL"]["total"] == 2
    assert kinds["REAL"]["por_estado"] == {"abierta_verificada": 1, "por_verificar": 1}
    assert kinds["HISTORICAL"]["total"] == 3
    assert kinds["SYNTHETIC"]["total"] == 8
    assert set(kinds["SYNTHETIC"]["por_estado"]) == {"simulada"}  # lo simulado no se mezcla con estados reales
    for kind, summary in kinds.items():
        assert set(summary) == {"total", "por_estado"}, kind
        assert sum(summary["por_estado"].values()) == summary["total"], kind


def test_dashboard_empty_kind_is_zero_not_missing(client, direccion):
    body = client.get("/api/v1/dashboard/direccion", headers=direccion).json()
    assert body["by_data_kind"]["REAL"] == {"total": 0, "por_estado": {}}
    assert body["upcoming_real"] == []
    assert body["last_search"] is None


def test_upcoming_real_excludes_synthetic_future(client, direccion):
    db = SessionLocal()
    later = _real_opportunity(db, "REAL-LATER", submission_in_days=20)
    sooner = _real_opportunity(db, "REAL-SOONER", submission_in_days=5)
    _real_opportunity(db, "REAL-UNVERIFIED", verified=False, submission_in_days=3)
    _real_opportunity(db, "REAL-STALE", checked_hours_ago=72, submission_in_days=4)      # desactualizada
    _real_opportunity(db, "REAL-PAST", submission_in_days=-2)                             # fecha transcurrida
    _real_opportunity(db, "REAL-NODATE", submission_in_days=None)
    db.close()

    body = client.get("/api/v1/dashboard/direccion", headers=direccion).json()

    ids = [o["id"] for o in body["upcoming_real"]]
    assert ids == [sooner, later]                                 # por fecha de presentación
    assert all(o["data_kind"] == "REAL" and o["derived"]["code"] == "abierta_verificada"
               for o in body["upcoming_real"])
    # Los escenarios simulados con fecha futura (los 8 de la semilla) jamás aparecen como oportunidad real.
    assert not any(o["external_id"].startswith("DEMO-") for o in body["upcoming_real"])
    assert body["by_data_kind"]["SYNTHETIC"]["total"] == 8


def test_upcoming_real_empty_when_only_synthetic_is_open(client, direccion):
    body = client.get("/api/v1/dashboard/direccion", headers=direccion).json()
    assert body["by_data_kind"]["SYNTHETIC"]["total"] == 8 and body["upcoming_real"] == []


def test_scenarios_at_risk_are_synthetic_with_blockers(client, direccion):
    db = SessionLocal()
    expected = {}
    for req in db.scalars(select(Requirement)):
        if req.mandatory is True and req.status in ("incumple", "faltante", "vencido"):
            expected.setdefault(req.opportunity_id, []).append(req.code)
    db.close()

    body = client.get("/api/v1/dashboard/direccion", headers=direccion).json()

    risks = body["scenarios_at_risk"]
    assert [r["external_id"] for r in risks] == sorted(r["external_id"] for r in risks)
    assert {r["opportunity_id"] for r in risks} == set(expected)
    for risk in risks:
        assert risk["data_kind"] == "SYNTHETIC" and risk["external_id"].startswith("DEMO-LIC-")
        assert risk["blocking"] == sorted(expected[risk["opportunity_id"]]) and risk["title"]
    by_id = {r["external_id"]: r["blocking"] for r in risks}
    assert by_id["DEMO-LIC-001"] == ["DEMO-REQ-005", "DEMO-REQ-006", "DEMO-REQ-007"]
    assert "DEMO-LIC-007" not in by_id                            # solo pendientes: aún no es un bloqueo


def test_last_search_uses_the_search_run_contract(client, direccion):
    """El panel muestra la última corrida con el mismo contrato que la API de búsqueda (`serialize_run` de C)."""
    from app.models import SearchRun
    from app.services.search_runs import serialize_run

    db = SessionLocal()
    org_id = _org_id(db)
    now = utcnow()
    query = {"terms": ["placa"], "date_from": "2026-01-01", "date_to": "2026-10-29"}
    db.add(SearchRun(organization_id=org_id, query=query, status="done",
                     started_at=now - timedelta(minutes=9), finished_at=now - timedelta(minutes=8),
                     counts={"notes": 3, "procedures": 2, "new": 2}, errors=[], created_at=now - timedelta(minutes=10)))
    newest = SearchRun(organization_id=org_id, query={**query, "terms": ["clavo", "tornillo"]}, status="partial",
                       started_at=now - timedelta(minutes=2), finished_at=now - timedelta(minutes=1),
                       counts={"notes": 1, "procedures": 1, "unchanged": 1},
                       errors=[{"source": "dof_sidof", "term": "tornillo", "code": "source_unavailable",
                                "message": "Tiempo de espera agotado"}], created_at=now)
    db.add(newest)
    db.commit()
    newest_id = newest.id
    expected = serialize_run(db, newest).model_dump(mode="json")
    db.close()

    run = client.get("/api/v1/dashboard/direccion", headers=direccion).json()["last_search"]

    assert run == expected
    assert run["id"] == newest_id and run["status"] == "partial"
    assert run["counts"] == {"notes": 1, "procedures": 1, "new": 0, "updated": 0, "unchanged": 1}
    assert run["query"]["terms"] == ["clavo", "tornillo"]
    assert run["errors"][0]["code"] == "source_unavailable" and run["errors"][0]["term"] == "tornillo"


def test_dashboard_requires_login_and_read_permission(client):
    assert client.get("/api/v1/dashboard/direccion").status_code == 401


def test_ops_status_for_ti(client, ti, monkeypatch):
    from app.models import Job
    from app.services import jobs as jobs_service

    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
    monkeypatch.setattr(jobs_service, "worker_alive", lambda: True)
    db = SessionLocal()
    org_id = _org_id(db)
    for i in range(25):
        db.add(Job(organization_id=org_id, kind="test.ok", payload={}, status="done" if i % 2 else "queued",
                   created_at=utcnow() + timedelta(seconds=i), message=f"trabajo {i}"))
    db.commit()
    db.close()

    r = client.get("/api/v1/ops/status", headers=ti)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == "abcdef1"
    assert body["storage_backend"] == "local" and body["storage_error"] is None
    assert body["worker_alive"] is True
    assert body["alembic_head"] is None                            # las pruebas crean el esquema sin Alembic
    assert {s["key"] for s in body["sources"]} == {"dof_sidof", "comprasmx", "imss", "escenarios_demo"}
    assert len(body["jobs"]) == 20
    assert [j["message"] for j in body["jobs"]][:2] == ["trabajo 24", "trabajo 23"]     # los más recientes
    assert "result" not in body["jobs"][0] and "payload" not in body["jobs"][0]
    assert body["demo_run"]["id"] and body["demo_run"]["summary"]["scenarios"] == 8


def test_ops_status_reports_what_is_true(client, ti, monkeypatch):
    from app.services import jobs as jobs_service, storage

    monkeypatch.setattr(storage, "_s3_storage", storage._s3_storage.__wrapped__)       # sin caché entre pruebas

    monkeypatch.setattr(jobs_service, "worker_alive", lambda: False)
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "demo")                 # configuración a medias: no es «local»
    body = client.get("/api/v1/ops/status", headers=ti).json()
    assert body["worker_alive"] is False
    assert body["storage_backend"] == "invalid" and "OBJECT_STORAGE_ENDPOINT" in body["storage_error"]

    for var, value in (("OBJECT_STORAGE_ENDPOINT", "https://bucket.example"), ("OBJECT_STORAGE_ACCESS_KEY", "k"),
                       ("OBJECT_STORAGE_SECRET_KEY", "s")):
        monkeypatch.setenv(var, value)
    body = client.get("/api/v1/ops/status", headers=ti).json()
    assert body["storage_backend"] == "s3" and body["storage_error"] is None
    assert "bucket.example" not in json.dumps(body)               # el estado dice el tipo, no la configuración


def test_ops_status_reads_alembic_revision(client, ti):
    db = SessionLocal()
    db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    db.execute(text("INSERT INTO alembic_version (version_num) VALUES ('05442fa8b315')"))
    db.commit()
    try:
        assert client.get("/api/v1/ops/status", headers=ti).json()["alembic_head"] == "05442fa8b315"
    finally:
        db.execute(text("DROP TABLE alembic_version"))
        db.commit()
        db.close()


def test_ops_status_permissions(client, analista, direccion, ti):
    assert client.get("/api/v1/ops/status", headers=analista).status_code == 403
    assert client.get("/api/v1/ops/status").status_code == 401
    assert client.get("/api/v1/ops/status", headers=direccion).status_code == 200      # audit.read
    assert client.get("/api/v1/ops/status", headers=ti).status_code == 200            # source.manage y audit.read
