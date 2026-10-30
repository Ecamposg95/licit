"""E1: semilla, estado derivado, radar, permisos, aislamiento y errores."""
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import func, select

from app.core import config
from app.core.database import Base, SessionLocal, engine
from app.models import (
    DataKind, Document, Opportunity, Organization, Product, Requirement, Task, User, Variant,
)
from app.services import catalog_import
from app.services.demo_seed import bootstrap, normalize_external_id, reset_demo
from app.services.status import derive_status

NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


def _count(db, model, **filters):
    stmt = select(func.count()).select_from(model)
    for k, v in filters.items():
        stmt = stmt.where(getattr(model, k) == v)
    return db.scalar(stmt)


# ── Semilla ──────────────────────────────────────────────────────────────────

def test_seed_volumes_match_task_pack():
    db = SessionLocal()
    assert _count(db, Variant) == 18
    assert _count(db, Product) == 6
    assert _count(db, Opportunity, data_kind="HISTORICAL") == 3
    assert _count(db, Opportunity, data_kind="SYNTHETIC") == 8
    assert _count(db, Document) == 12
    assert _count(db, Requirement) == 20
    assert _count(db, Task) == 10
    # Ningún registro ficticio lleva un registro sanitario verosímil.
    assert {v.regulatory_reference for v in db.scalars(select(Variant))} == {"DEMO-SIN-VALIDEZ"}
    db.close()


def test_reset_is_deterministic_and_keeps_real_data():
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    real = Opportunity(organization_id=org.id, external_id="LA-REAL-1", normalized_id="LAREAL1",
                       title="Real", buyer="IMSS", data_kind=DataKind.REAL.value,
                       verification_status="por_verificar")
    db.add(real)
    db.commit()
    before = sorted(db.scalars(select(Opportunity.id).where(Opportunity.data_kind != "REAL")))

    reset_demo(db, org, actor_id=None)
    db.commit()

    after = sorted(db.scalars(select(Opportunity.id).where(Opportunity.data_kind != "REAL")))
    assert before == after
    assert db.get(Opportunity, real.id) is not None
    assert _count(db, Requirement) == 20
    db.close()


def test_normalize_external_id():
    assert normalize_external_id("la-50-gyr-050GYR075-i-134-2026") == "LA50GYR050GYR075I1342026"


# ── Estado derivado (§6) ─────────────────────────────────────────────────────

def _opp(**kw):
    base = dict(data_kind="REAL", verification_status="verificada", submission_at=None,
                last_checked_at=NOW, result="desconocido")
    base.update(kw)
    return SimpleNamespace(**base)


def test_historical_with_past_date_is_never_open():
    d = derive_status(_opp(data_kind="HISTORICAL", submission_at=NOW - timedelta(days=50)), NOW, 24)
    assert d.code == "fecha_transcurrida"


def test_real_future_verified_and_fresh_is_open():
    d = derive_status(_opp(submission_at=NOW + timedelta(days=10)), NOW, 24)
    assert d.code == "abierta_verificada"


def test_real_future_but_stale_is_outdated():
    d = derive_status(_opp(submission_at=NOW + timedelta(days=10),
                           last_checked_at=NOW - timedelta(hours=30)), NOW, 24)
    assert d.code == "desactualizada"


def test_real_without_date_is_por_verificar():
    assert derive_status(_opp(), NOW, 24).code == "por_verificar"


def test_clock_after_deadline_closes_real_record():
    d = derive_status(_opp(submission_at=NOW - timedelta(minutes=1)), NOW, 24)
    assert d.code == "fecha_transcurrida"


def test_synthetic_future_date_is_never_real_opportunity():
    d = derive_status(_opp(data_kind="SYNTHETIC", submission_at=NOW + timedelta(days=14)), NOW, 24)
    assert d.code == "simulada"


def test_unreachable_source_is_not_absence():
    d = derive_status(_opp(verification_status="fuente_inaccesible", submission_at=NOW + timedelta(days=3)), NOW, 24)
    assert d.code == "fuente_inaccesible"


# ── Radar ────────────────────────────────────────────────────────────────────

def test_radar_filters_by_data_kind(client, analista):
    r = client.get("/api/v1/opportunities", params={"data_kind": "HISTORICAL"}, headers=analista)
    body = r.json()
    assert r.status_code == 200 and body["total"] == 3
    assert {o["derived"]["code"] for o in body["items"]} == {"fecha_transcurrida"}
    assert all(o["submission_precision"] == "date" for o in body["items"])

    r = client.get("/api/v1/opportunities", params=[("data_kind", "SYNTHETIC"), ("data_kind", "HISTORICAL")],
                   headers=analista)
    assert r.json()["total"] == 11


def test_radar_text_and_family_filters(client, analista):
    r = client.get("/api/v1/opportunities", params={"q": "Medida incompatible"}, headers=analista)
    assert [o["external_id"] for o in r.json()["items"]] == ["DEMO-LIC-002"]
    r = client.get("/api/v1/opportunities", params={"family": "Columna"}, headers=analista)
    assert [o["external_id"] for o in r.json()["items"]] == ["DEMO-LIC-007"]


def test_scenario_without_dates_keeps_nulls(client, analista):
    items = client.get("/api/v1/opportunities", params={"q": "DEMO-LIC-007"}, headers=analista).json()["items"]
    detail = client.get(f"/api/v1/opportunities/{items[0]['id']}", headers=analista).json()
    assert detail["submission_at"] is None and detail["questions_at"] is None and detail["ruling_at"] is None


def test_matrix_for_main_scenario(client, analista):
    opp = client.get("/api/v1/opportunities", params={"q": "DEMO-LIC-001"}, headers=analista).json()["items"][0]
    detail = client.get(f"/api/v1/opportunities/{opp['id']}", headers=analista).json()
    # Sin el catálogo real importado (pruebas), LIC-001 se queda con las variantes ficticias de respaldo.
    assert [l["proposed_variant"]["sku"] for l in detail["lots"]] == ["DEMO-PLA-001", "DEMO-PLA-003", "DEMO-PLA-002"]
    rows = client.get(f"/api/v1/opportunities/{opp['id']}/requirements", headers=analista).json()
    assert len(rows) == 7
    by_code = {r["code"]: r for r in rows}
    assert by_code["DEMO-REQ-005"]["status"] == "faltante" and by_code["DEMO-REQ-005"]["open_task"] is None
    assert by_code["DEMO-REQ-001"]["open_task"]["assignee"].startswith("Analista")


def _lic001_lots(db):
    opp = db.scalars(select(Opportunity).where(Opportunity.external_id == "DEMO-LIC-001")).one()
    return sorted(opp.lots, key=lambda l: l.number)


def test_lic001_uses_real_traufix():
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    catalog_import.import_catalog(db, org.id, catalog_import.CATALOG_PATH)
    reset_demo(db, org, actor_id=None)
    db.commit()
    lots = _lic001_lots(db)
    assert [l.proposed_variant.sku for l in lots] == ["DPM-198", "DPM-198", "DPM-199"]
    assert all(l.proposed_variant.data_kind == "REAL" for l in lots)
    assert all(l.proposed_variant.sku.startswith("DPM-") for l in lots)
    # Precio ficticio, marcado como tal y con moneda explícita; el producto sigue siendo real.
    assert all(l.price_data_kind == "SYNTHETIC" and l.currency == "MXN" for l in lots)
    assert [str(l.unit_price) for l in lots] == ["2450.00", "2680.00", "3120.00"]
    # Los tres casos son ciertos con lo que la página cita (verificado en el JSON del catálogo).
    holes = lots[0].proposed_variant.attributes["holes"]
    assert holes["values"] == [5, 6, 7, 8, 9, 10, 12]
    assert holes["source_text"] == "Cód. 198 | 5, 6, 7, 8, 9, 10 y 12 orificios"
    assert "titanio" in lots[0].proposed_variant.attributes["material"]["value"].lower()
    assert "length_mm" not in lots[2].proposed_variant.attributes
    # Los demás escenarios siguen con variantes ficticias DEMO-*.
    lic002 = db.scalars(select(Opportunity).where(Opportunity.external_id == "DEMO-LIC-002")).one()
    assert lic002.lots[0].proposed_variant.sku == "DEMO-PLA-002"
    db.close()


def test_lic001_falls_back_to_synthetic_without_catalog(caplog):
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    with caplog.at_level("WARNING", logger="app.services.demo_seed"):
        reset_demo(db, org, actor_id=None)
    db.commit()
    lots = _lic001_lots(db)
    assert [l.proposed_variant.sku for l in lots] == ["DEMO-PLA-001", "DEMO-PLA-003", "DEMO-PLA-002"]
    assert all(l.proposed_variant.data_kind == "SYNTHETIC" for l in lots)
    assert all(l.price_data_kind == "SYNTHETIC" for l in lots)
    assert any("DPM-198" in r.getMessage() and "DEMO-PLA-001" in r.getMessage() for r in caplog.records)
    db.close()


def test_bootstrap_imports_catalog_before_seeding(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(config, "IMPORT_CATALOG", True)
    db = SessionLocal()
    bootstrap(db)
    assert [l.proposed_variant.sku for l in _lic001_lots(db)] == ["DPM-198", "DPM-198", "DPM-199"]
    db.close()


# ── Permisos, versiones y aislamiento ────────────────────────────────────────

def _lic(client, headers, code="DEMO-LIC-001"):
    return client.get("/api/v1/opportunities", params={"q": code}, headers=headers).json()["items"][0]


def test_direccion_cannot_modify(client, direccion):
    opp = _lic(client, direccion)
    r = client.patch(f"/api/v1/opportunities/{opp['id']}", json={"expected_version": 1, "notes": "x"},
                     headers=direccion)
    assert r.status_code == 403 and r.json()["code"] == "forbidden"


def test_analista_update_is_audited_and_versioned(client, analista, ti):
    opp = _lic(client, analista)
    r = client.patch(f"/api/v1/opportunities/{opp['id']}", json={"expected_version": 1, "notes": "Revisar bases"},
                     headers=analista)
    assert r.status_code == 200 and r.json()["version"] == 2
    stale = client.patch(f"/api/v1/opportunities/{opp['id']}", json={"expected_version": 1, "notes": "otra"},
                         headers=analista)
    assert stale.status_code == 409 and stale.json()["details"]["current_version"] == 2
    history = client.get(f"/api/v1/opportunities/{opp['id']}/history", headers=analista).json()
    assert history[0]["action"] == "opportunity.update"
    assert history[0]["before"]["notes"].startswith("Escenario ficticio")
    assert history[0]["after"] == {"notes": "Revisar bases"}


def test_demo_reset_requires_admin_ti(client, analista, ti):
    assert client.post("/api/v1/demo/reset", headers=analista).status_code == 403
    r = client.post("/api/v1/demo/reset", headers=ti)
    assert r.status_code == 200 and r.json()["requirements"] == 20


def test_audit_log_restricted(client, analista, direccion):
    assert client.get("/api/v1/audit-events", headers=analista).status_code == 403
    assert client.get("/api/v1/audit-events", headers=direccion).status_code == 200


def test_other_organization_is_invisible(client, analista):
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
    assert client.get(f"/api/v1/opportunities/{fid}", headers=analista).status_code == 404
    ids = [o["id"] for o in client.get("/api/v1/opportunities", params={"page_size": 200}, headers=analista).json()["items"]]
    assert fid not in ids


def test_me_exposes_union_of_permissions(client):
    from tests.conftest import login
    h = login(client, "presentador@dipromedic.example")
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert len(me["role_names"]) == 5
    assert {"demo.reset", "requirement.review", "pricing.approve"} <= set(me["permissions"])


# ── Errores normalizados y seguridad ─────────────────────────────────────────

def test_errors_are_normalized(client, analista):
    r = client.get("/api/v1/opportunities")
    assert r.status_code == 401
    assert set(r.json()) == {"code", "message", "correlation_id", "details"}
    assert r.headers["X-Correlation-ID"] == r.json()["correlation_id"]
    r = client.get("/api/v1/opportunities", params={"page": 0}, headers=analista)
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert client.get("/api/v1/no-existe", headers=analista).json()["code"] == "not_found"


def test_bad_login_is_rejected(client):
    r = client.post("/api/v1/auth/login", data={"username": "analista1@dipromedic.example", "password": "x"})
    assert r.status_code == 401 and r.json()["code"] == "invalid_credentials"


def test_spa_does_not_serve_files_outside_dist(client):
    r = client.get("/%2e%2e/app/core/config.py")
    assert "DEMO_BASE_DATE" not in r.text


# ── Migraciones ──────────────────────────────────────────────────────────────

def test_alembic_upgrade_and_downgrade(tmp_path):
    env = {"DATABASE_URL": f"sqlite:///{tmp_path}/mig.db", "PATH": "/usr/bin:/bin"}
    for args in (["upgrade", "head"], ["downgrade", "base"], ["upgrade", "head"]):
        r = subprocess.run([sys.executable, "-m", "alembic", *args], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_seed_persists_utc_and_spanish_labels():
    db = SessionLocal()
    lic1 = db.scalars(select(Opportunity).where(Opportunity.external_id == "DEMO-LIC-001")).one()
    # 10:00 en Ciudad de México (UTC-6, sin horario de verano) = 16:00 UTC.
    assert lic1.submission_at.hour == 16
    hist = db.scalars(select(Opportunity).where(Opportunity.data_kind == "HISTORICAL")).all()
    assert {h.result for h in hist} == {"desconocido"}
    req20 = db.scalars(select(Requirement).where(Requirement.code == "DEMO-REQ-020")).one()
    assert req20.mandatory is None
    db.close()
