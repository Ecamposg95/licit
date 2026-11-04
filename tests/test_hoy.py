"""Tablero «Hoy»: solo cuenta REAL, territorio, ventana de visita, barrido caído y alcance de fechas."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import DataKind, Opportunity, SavedSearch, Source, Sweep, Task, User
from app.services import hoy
from app.sources.dates_es import MX
from tests.conftest import login

ANALYST = "analista1@dipromedic.example"
OTHER = "analista2@dipromedic.example"
DIRECCION = "direccion@dipromedic.example"
NOW = datetime(2026, 11, 3, 18, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def user(db, email=ANALYST) -> User:
    return db.scalars(select(User).where(User.email == email)).one()


def real_opp(db, external_id, title="Material de osteosíntesis", **kw) -> Opportunity:
    u = user(db)
    fields = dict(organization_id=u.organization_id, external_id=external_id, normalized_id=external_id.lower(),
                  title=title, buyer="IMSS", families=["Osteosíntesis"], data_kind=DataKind.REAL.value,
                  source_id=db.scalars(select(Source)).first().id, verification_status="por_verificar",
                  result="desconocido", requires_human_review=True, triage_status="nueva", created_at=NOW)
    fields.update(kw)
    o = Opportunity(**fields)
    db.add(o)
    db.commit()
    return o


def test_only_real_counts(db):
    d = hoy.dashboard(db, user(db), NOW, "team")
    assert d["kpis"] == {"new_24h": 0, "unclassified": 0, "unclassified_mine": 0, "submitting_7d": 0,
                         "my_overdue_tasks": 0}
    assert d["new_items"] == [] and d["unassigned"] == [] and d["key_dates"] == []
    assert d["kpis_warning"] is None and d["sweep"]["last"] is None


def test_new_items_territory_and_unassigned(db):
    u = user(db)
    db.add(SavedSearch(organization_id=u.organization_id, user_id=u.id, name="Mi osteo", terms=["osteosíntesis"],
                       states=[], families=[], buyers=[]))
    db.commit()
    hit = real_opp(db, "LA-1", title="Placas de osteosíntesis")
    miss = real_opp(db, "LA-2", title="Papelería de oficina", families=[], created_at=NOW - timedelta(hours=1))
    d = hoy.dashboard(db, u, NOW, "mine")
    assert d["kpis"]["unclassified"] == 2 and d["kpis"]["unclassified_mine"] == 1 and d["kpis"]["new_24h"] == 2
    assert [i["id"] for i in d["new_items"]] == [hit.id, miss.id]
    first = d["new_items"][0]
    assert first["matched"][0]["name"] == "Mi osteo" and first["mine"] and first["in_territory"]
    assert first["matched"][0]["owner"].id == u.id
    assert [i["id"] for i in d["unassigned"]] == [miss.id]
    # otra persona ve la coincidencia como territorio ajeno
    other = hoy.dashboard(db, user(db, OTHER), NOW, "mine")
    assert other["kpis"]["unclassified_mine"] == 0 and other["new_items"][0]["in_territory"]


def test_reload_within_30_minutes_keeps_new_list(db):
    u = user(db)
    t0 = NOW
    assert hoy.touch_visit(u, t0) is None
    db.commit()
    real_opp(db, "LA-3", created_at=t0 + timedelta(minutes=5))
    assert hoy.touch_visit(u, t0 + timedelta(minutes=10)) is None
    d = hoy.dashboard(db, u, t0 + timedelta(minutes=10), "mine")
    assert d["last_visit"] is None and d["new_items"][0]["is_new_since_visit"] is True
    db.commit()
    assert hoy.touch_visit(u, t0 + timedelta(minutes=45)) == t0
    d = hoy.dashboard(db, u, t0 + timedelta(minutes=45), "mine")
    assert d["last_visit"] == t0 and d["new_items"][0]["is_new_since_visit"] is True


def test_badge_counts_since_seen_and_does_not_write(client, db):
    u = user(db)
    real_opp(db, "LA-4", created_at=NOW - timedelta(hours=2))
    real_opp(db, "LA-5", created_at=NOW)
    assert hoy.badge_count(db, u) == 2
    u.hoy_seen_at = NOW - timedelta(hours=1)
    db.commit()
    assert hoy.badge_count(db, u) == 1
    r = client.get("/api/v1/hoy/badge", headers=login(client, ANALYST))
    assert r.status_code == 200 and r.json() == {"new": 1}
    db.expire_all()
    seen = user(db).hoy_seen_at
    client.get("/api/v1/hoy/badge", headers=login(client, ANALYST))
    db.expire_all()
    assert user(db).hoy_seen_at == seen


def test_failed_sweep_is_reported_not_zero(db):
    u = user(db)
    db.add(Sweep(organization_id=u.organization_id, day=date(2026, 11, 3), attempt=1, trigger="daily",
                 status="failed", terms=[], dropped_terms=[], counts={}, finished_at=NOW,
                 errors=[{"batch": 1, "term": None, "code": "http_error", "message": "SIDOF no respondió"}]))
    db.commit()
    d = hoy.dashboard(db, u, NOW, "mine")
    assert d["sweep"]["last"].status == "failed"
    assert "SIDOF no respondió" in d["kpis_warning"] and d["kpis_warning"].startswith("El último barrido falló")
    assert d["kpis"]["unclassified"] == 0


def test_key_dates_scope(client, db):
    a2 = user(db, OTHER)
    soon = datetime.now(timezone.utc) + timedelta(days=3)
    far = datetime.now(timezone.utc) + timedelta(days=20)
    near = real_opp(db, "LA-6", triage_status="siguiendo", owner_id=a2.id, submission_at=soon,
                    created_at=datetime.now(timezone.utc))
    real_opp(db, "LA-7", triage_status="siguiendo", owner_id=a2.id, submission_at=far)

    def get(who, **params):
        r = client.get("/api/v1/hoy", headers=login(client, who), params=params)
        assert r.status_code == 200, r.text
        return r.json()

    d = get(DIRECCION)
    assert d["scope"] == "team"
    assert [(k["opportunity"]["id"], k["kind"]) for k in d["key_dates"]] == [(near.id, "submission")]
    assert d["kpis"]["submitting_7d"] == 1
    assert get(ANALYST)["scope"] == "mine" and get(ANALYST)["key_dates"] == []
    assert get(ANALYST, scope="mine")["kpis"]["submitting_7d"] == 0
    assert len(get(ANALYST, scope="team")["key_dates"]) == 1
    assert len(get(OTHER, scope="mine")["key_dates"]) == 1
    assert client.get("/api/v1/hoy?scope=otro", headers=login(client, ANALYST)).status_code == 422


def test_my_tasks_include_demo_but_kpi_counts_real_only(db):
    u = user(db)
    today = NOW.astimezone(MX).date()
    for code, kind, due in (("T-DEMO", "SYNTHETIC", today - timedelta(days=2)), ("T-SIN", "SYNTHETIC", None),
                            ("T-HECHA", "SYNTHETIC", today - timedelta(days=1))):
        db.add(Task(organization_id=u.organization_id, code=code, title=code, assignee_id=u.id, due_date=due,
                    data_kind=kind, status="hecha" if code == "T-HECHA" else "pendiente"))
    db.commit()
    d = hoy.dashboard(db, u, NOW, "mine")
    mine = [t for t in d["my_tasks"] if t.code in ("T-DEMO", "T-SIN", "T-HECHA")]
    assert [t.code for t in mine] == ["T-DEMO", "T-SIN"]      # la hecha no sale; sin fecha al final del grupo
    assert mine[0].data_kind == "SYNTHETIC" and d["kpis"]["my_overdue_tasks"] == 0
    db.add(Task(organization_id=u.organization_id, code="T-REAL", title="r", assignee_id=u.id,
                due_date=today - timedelta(days=1), data_kind="REAL", status="pendiente"))
    db.commit()
    assert hoy.dashboard(db, u, NOW, "mine")["kpis"]["my_overdue_tasks"] == 1


def test_hoy_requires_read(client):
    assert client.get("/api/v1/hoy").status_code == 401
    assert client.get("/api/v1/hoy/badge").status_code == 401


def test_poll_with_touch_false_keeps_visit_mark(client, db):
    u = user(db)
    old = datetime.now(timezone.utc) - timedelta(hours=1)
    u.hoy_seen_at, u.hoy_prev_seen_at = old, None
    db.commit()
    h = login(client, ANALYST)
    assert client.get("/api/v1/hoy?touch=false", headers=h).status_code == 200
    db.expire_all()
    assert hoy._aware(user(db).hoy_seen_at) == old and user(db).hoy_prev_seen_at is None

    assert client.get("/api/v1/hoy", headers=h).status_code == 200            # la carga normal sí la recorre
    db.expire_all()
    assert hoy._aware(user(db).hoy_seen_at) > old and hoy._aware(user(db).hoy_prev_seen_at) == old
