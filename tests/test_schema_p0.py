"""P0.1: bitácora encadenada e inmutable, corridas demo y migración del esquema común."""
import hashlib
import json
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.models import AuditEvent, DemoRun, Organization
from app.services import audit
from app.services.demo_seed import current_demo_run_id, reset_demo


def _org(db) -> Organization:
    return db.scalars(select(Organization)).first()


def _record(db, org_id: str, action: str, **kw) -> AuditEvent:
    return audit.record(db, organization_id=org_id, actor_id=None, action=action,
                        resource_type="organization", resource_id=org_id, **kw)


def _events(db, org_id: str) -> int:
    return db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.organization_id == org_id))


# ── Cadena de hashes ─────────────────────────────────────────────────────────

def test_compute_event_hash_formula():
    payload = {"b": 1, "a": "señal"}
    expected = hashlib.sha256(('abc{"a": "señal", "b": 1}').encode("utf-8")).hexdigest()
    assert audit.compute_event_hash("abc", payload) == expected
    assert audit.compute_event_hash(None, payload) == hashlib.sha256(
        '{"a": "señal", "b": 1}'.encode("utf-8")).hexdigest()


def test_audit_chain_links_events():
    db = SessionLocal()
    org = _org(db)
    e1 = _record(db, org.id, "test.uno", after={"n": 1})
    e2 = _record(db, org.id, "test.dos", before={"n": 1}, after={"n": 2, "texto": "Tornillo ñ · 3.5 mm"})
    db.commit()
    assert len(e1.hash) == 64
    assert e2.prev_hash == e1.hash
    run_id = current_demo_run_id(db, org.id)
    assert run_id is not None and e1.demo_run_id == run_id
    db.close()

    # Se verifica desde otra sesión: lo que se recalcula sale de las columnas guardadas.
    db = SessionLocal()
    assert audit.verify_chain(db, org.id) == (True, _events(db, org.id), None)
    db.close()


def test_verify_detects_tamper():
    if engine.dialect.name != "sqlite":
        pytest.skip("En Postgres el trigger impide modificar la bitácora")
    db = SessionLocal()
    org = _org(db)
    _record(db, org.id, "test.uno")
    target = _record(db, org.id, "test.dos", after={"monto": "100.00"})
    _record(db, org.id, "test.tres")
    db.commit()
    order = list(db.scalars(select(AuditEvent.id).where(AuditEvent.organization_id == org.id)
                            .order_by(AuditEvent.created_at, AuditEvent.id)))

    db.execute(text("UPDATE audit_events SET after = :v WHERE id = :id"),
               {"v": json.dumps({"monto": "1.00"}), "id": target.id})
    db.commit()

    assert audit.verify_chain(db, org.id) == (False, order.index(target.id) + 1, target.id)
    db.close()


def test_audit_immutable_in_postgres():
    if engine.dialect.name != "postgresql":
        pytest.skip("El trigger de solo inserción existe sólo en Postgres")
    db = SessionLocal()
    with pytest.raises(DBAPIError, match="solo inserción"):
        db.execute(text("UPDATE audit_events SET action = 'x'"))
    db.rollback()
    with pytest.raises(DBAPIError, match="solo inserción"):
        db.execute(text("DELETE FROM audit_events"))
    db.rollback()
    db.close()


# ── Corridas demo ────────────────────────────────────────────────────────────

def test_reset_keeps_audit_and_opens_new_run():
    db = SessionLocal()
    org = _org(db)
    previous = set(db.scalars(select(AuditEvent.id)))
    first_run = current_demo_run_id(db, org.id)

    reset_demo(db, org, actor_id=None)
    db.commit()
    reset_demo(db, org, actor_id=None)
    db.commit()

    assert db.scalar(select(func.count()).select_from(DemoRun)) == 3
    assert previous <= set(db.scalars(select(AuditEvent.id)))
    reset_runs = db.scalars(select(AuditEvent.demo_run_id).where(AuditEvent.action == "demo.reset")).all()
    assert len(set(reset_runs)) == 3
    assert current_demo_run_id(db, org.id) not in (None, first_run)
    run = db.get(DemoRun, current_demo_run_id(db, org.id))
    assert run.summary["requirements"] == 20
    assert audit.verify_chain(db, org.id)[0] is True
    db.close()


def test_history_shows_only_current_run(client, analista, ti):
    opp = client.get("/api/v1/opportunities", params={"q": "DEMO-LIC-001"}, headers=analista).json()["items"][0]
    url = f"/api/v1/opportunities/{opp['id']}/history"
    r = client.patch(f"/api/v1/opportunities/{opp['id']}", json={"expected_version": 1, "notes": "Ensayo"},
                     headers=analista)
    assert r.status_code == 200
    assert [e["action"] for e in client.get(url, headers=analista).json()] == ["opportunity.update"]

    assert client.post("/api/v1/demo/reset", headers=ti).status_code == 200

    assert "opportunity.update" not in {e["action"] for e in client.get(url, headers=analista).json()}
    db = SessionLocal()
    # El evento del ensayo sigue en la bitácora; sólo deja de mostrarse en el historial.
    assert db.scalar(select(func.count()).select_from(AuditEvent)
                     .where(AuditEvent.action == "opportunity.update")) == 1
    db.close()


# ── Migración sobre una base con datos de E1 ─────────────────────────────────

def _alembic(url: str, *args: str) -> None:
    env = {"DATABASE_URL": url, "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, "-m", "alembic", *args], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_migration_backfills_existing_rows(tmp_path):
    url = f"sqlite:///{tmp_path}/e1.db"
    _alembic(url, "upgrade", "e37c23f4881e")
    legacy = create_engine(url)
    ts = "2026-10-28 12:00:00.000000"
    with legacy.begin() as c:
        c.execute(text("INSERT INTO organizations (id, name, demo_mode, branding, created_at) "
                       "VALUES ('org', 'Org', 1, '{}', :ts)"), {"ts": ts})
        c.execute(text("INSERT INTO products (id, organization_id, name, family, data_kind, review_status, "
                       "created_at, updated_at) VALUES ('p', 'org', 'Placa', 'Osteosíntesis', 'SYNTHETIC', "
                       "'pendiente', :ts, :ts)"), {"ts": ts})
        c.execute(text("INSERT INTO variants (id, organization_id, product_id, sku, name, attributes, unit, "
                       "data_kind, review_status, created_at, updated_at) VALUES ('v', 'org', 'p', 'DEMO-1', "
                       "'Placa 1', '{}', 'pieza', 'SYNTHETIC', 'pendiente', :ts, :ts)"), {"ts": ts})
        c.execute(text("INSERT INTO documents (id, organization_id, title, scope, review_status, data_kind, "
                       "current_version, created_at, updated_at) VALUES ('d', 'org', 'Doc', 'empresa', "
                       "'pendiente', 'SYNTHETIC', 1, :ts, :ts)"), {"ts": ts})
        c.execute(text("INSERT INTO document_versions (id, organization_id, document_id, version, created_at, "
                       "updated_at) VALUES ('dv', 'org', 'd', 1, :ts, :ts)"), {"ts": ts})
        for i,(action, after) in enumerate([("demo.reset", '{"tasks": 10}'), ("auth.login", None)]):
            c.execute(text("INSERT INTO audit_events (id, organization_id, action, resource_type, resource_id, "
                           "after, correlation_id, created_at) VALUES (:id, 'org', :a, 'organization', 'org', "
                           ":after, '-', :ts)"),
                      {"id": f"e{i}", "a": action, "after": after, "ts": f"2026-10-28 12:0{i}:00.000000"})

    _alembic(url, "upgrade", "head")

    with Session(legacy) as s:
        # Recrear tablas en modo batch no debe disparar cascadas sobre las hijas.
        assert s.scalar(text("SELECT count(*) FROM variants")) == 1
        assert s.scalar(text("SELECT count(*) FROM document_versions")) == 1
        row = s.execute(text("SELECT images, features, data_quality_notes FROM products")).one()
        assert [json.loads(v) for v in row] == [[], [], []]
        assert json.loads(s.scalar(text("SELECT field_provenance FROM variants"))) == {}
        assert s.scalar(text("SELECT third_party FROM documents")) == 0
        assert audit.verify_chain(s, "org") == (True, 2, None)
        # Un evento nuevo continúa la cadena heredada.
        new = audit.record(s, organization_id="org", actor_id=None, action="test.nuevo",
                           resource_type="organization", resource_id="org")
        s.commit()
        assert new.prev_hash == s.scalar(text("SELECT hash FROM audit_events WHERE id = 'e1'"))
        assert audit.verify_chain(s, "org") == (True, 3, None)
    legacy.dispose()
