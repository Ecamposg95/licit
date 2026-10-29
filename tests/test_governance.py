"""Frente G: gobierno corporativo (integridad, matriz de permisos, aprobaciones), cuentas demo,
datos del panel de dirección y estado operativo."""
import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from app.core.database import SessionLocal, engine
from app.core.permissions import ROLE_LABELS, ROLE_PERMISSIONS, Perm
from app.models import AuditEvent, DemoRun, Organization, Requirement, User
from app.models.base import utcnow
from app.services import audit

from tests.conftest import login


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
    db.close()

    r = client.get("/api/v1/governance/audit/verify", headers=direccion)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["first_broken_id"] is None
    assert body["checked"] == before and body["checked"] > 0
    assert body["verified_at"]
    # La verificación queda en la bitácora, con quien la pidió y su resultado.
    db = SessionLocal()
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "audit.verify")).one()
    assert event.actor_id == _user(db, "direccion@dipromedic.example").id
    assert event.after["ok"] is True and event.after["checked"] == before
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
    assert body["first_broken_id"] == target_id
    assert body["checked"] == order.index(target_id) + 1


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
                      resource_type="bid_workspace", after={"decision": "participar", "reason": "Ensayo"}).demo_run_id
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
            before={"status": "en_revision"}, after={"status": "cumple_validado", "reason": "Certificado vigente"})
    db.close()

    items = client.get("/api/v1/governance/approvals", headers=direccion).json()

    assert len(items) == 1
    item = items[0]
    assert item["reason"] == "Certificado vigente" and item["outcome"] == "cumple_validado"
    assert item["target"]["requirement_code"] == "DEMO-REQ-005"
    assert item["target"]["opportunity_external_id"] == "DEMO-LIC-001"
    assert item["target"]["data_kind"] == "SYNTHETIC"
    assert item["before"] == {"status": "en_revision"}


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

