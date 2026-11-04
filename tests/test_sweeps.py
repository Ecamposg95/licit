"""T17 · Barrido diario automático en SIDOF (lotes, reintentos, agregación) y «Volver a barrer».

El reloj se inyecta con `now`; el worker se invoca con `jobs.run_pending_once` y el cliente de SIDOF es falso.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core import config
from app.core.database import SessionLocal
from app.models import AuditEvent, Job, Organization, SavedSearch, SearchRun, Sweep, User
from app.services import jobs, sweeps
from app.services.search_runs import DEFAULT_TERMS
from app.sources.base import SourceUnavailable
from app.sources.dates_es import MX
from tests.conftest import login
from tests.test_search_runs import FakeSidof, all_notes, search_page


def mx(hour: int, minute: int = 0, day: int = 3) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=MX)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(config, "DAILY_SWEEP", True)
    monkeypatch.setattr(config, "DAILY_SWEEP_HOUR", 6)
    monkeypatch.setattr(sweeps, "_last_tick", None)


@pytest.fixture
def fake(monkeypatch):
    """El handler registrado usa este cliente falso (por omisión: SIDOF responde sin resultados)."""
    holder = {"fake": FakeSidof()}
    monkeypatch.setattr(sweeps, "SidofClient", lambda: holder["fake"])
    return holder


def org_id(db) -> str:
    return db.scalars(select(Organization)).first().id


def user(db, email="analista1@dipromedic.example") -> User:
    return db.scalars(select(User).where(User.email == email)).one()


def daily(db) -> list[Sweep]:
    db.expire_all()
    return list(db.scalars(select(Sweep).where(Sweep.trigger == "daily").order_by(Sweep.attempt)))


def save_search(db, name: str, terms: list[str], email="analista1@dipromedic.example") -> None:
    u = user(db, email)
    db.add(SavedSearch(organization_id=u.organization_id, user_id=u.id, name=name, terms=terms))
    db.commit()


def run_worker(db) -> Job | None:
    job = jobs.run_pending_once(db)
    db.expire_all()
    return job


def fail_last(db, finished_at: datetime) -> Sweep:
    """Fija la hora de término del último barrido diario (para medir el reintento con el reloj inyectado)."""
    s = daily(db)[-1]
    s.finished_at = finished_at.astimezone(timezone.utc)      # como lo guarda el worker (UTC)
    db.commit()
    return s


# ── Programación ─────────────────────────────────────────────────────────────

def test_not_before_hour_and_once_per_day(db, on):
    assert sweeps.schedule_due(db, mx(5, 59)) == []
    assert daily(db) == []

    created = sweeps.schedule_due(db, mx(6, 0))
    assert len(created) == 1
    s = daily(db)[0]
    assert (s.day, s.attempt, s.trigger, s.status, s.created_by_id) == (date(2026, 11, 3), 1, "daily", "queued", None)
    job = db.get(Job, s.job_id)
    assert job.kind == sweeps.JOB_KIND and job.created_by_id is None
    assert job.idempotency_key == f"daily_sweep:{org_id(db)}:2026-11-03:1"
    ev = db.scalars(select(AuditEvent).where(AuditEvent.action == "sweep.start")).one()
    assert ev.actor_id is None and ev.resource_type == "sweep" and ev.resource_id == s.id

    assert sweeps.schedule_due(db, mx(7, 0)) == []
    assert len(daily(db)) == 1
    # Al día siguiente toca otro.
    assert len(sweeps.schedule_due(db, mx(6, 0, day=4))) == 1


def test_daily_sweep_off(db, monkeypatch):
    monkeypatch.setattr(config, "DAILY_SWEEP", False)
    assert sweeps.schedule_due(db, mx(9, 0)) == []
    assert daily(db) == []
    state = sweeps.today_state(db, org_id(db), mx(9, 0))
    assert state == {"last": None, "scheduled_pending": False}


def test_today_state_pending(db, on):
    oid = org_id(db)
    assert sweeps.today_state(db, oid, mx(5, 0))["scheduled_pending"] is False
    assert sweeps.today_state(db, oid, mx(6, 30))["scheduled_pending"] is True
    sweeps.schedule_due(db, mx(6, 30))
    state = sweeps.today_state(db, oid, mx(6, 31))
    assert state["scheduled_pending"] is False and state["last"].id == daily(db)[0].id
    assert sweeps.latest(db, oid).id == daily(db)[0].id


# ── Ejecución ────────────────────────────────────────────────────────────────

def test_sweep_runs_batches_and_aggregates(db, on, fake):
    save_search(db, "Rodilla", ["rodilla", "cadera", "columna", "tornillos"])
    save_search(db, "Placas", ["placas", "clavos", "fijadores", "zz cemento oseo"])
    fake["fake"] = FakeSidof(pages={"osteosintesis": search_page("5801639"),
                                    "zz cemento oseo": search_page("5797331")}, notes=all_notes())
    sweeps.schedule_due(db, mx(6, 0))
    job = run_worker(db)
    assert job.status == "done", job.error

    s = daily(db)[0]
    assert len(s.terms) == 12 and s.terms[:4] == DEFAULT_TERMS and s.dropped_terms == []
    runs = list(db.scalars(select(SearchRun).where(SearchRun.sweep_id == s.id).order_by(SearchRun.created_at)))
    assert len(runs) == 2
    assert [len(r.query["terms"]) for r in runs] == [10, 2]
    assert "zz cemento oseo" in runs[1].query["terms"]
    for r in runs:
        assert r.created_by_id is None and r.job_id == job.id and r.status == "done"
        assert date.fromisoformat(r.query["date_to"]) - date.fromisoformat(r.query["date_from"]) == timedelta(days=6)
        assert date.fromisoformat(r.query["date_to"]) == s.day          # la ventana sale del día del barrido
    assert s.status == "done" and s.errors == []
    assert s.counts["notes"] == 2 == sum(r.counts["notes"] for r in runs)
    assert s.counts["new"] == sum(r.counts["new"] for r in runs) >= 1
    assert s.started_at is not None and s.finished_at is not None
    starts = db.scalars(select(AuditEvent).where(AuditEvent.action == "search.start",
                                                 AuditEvent.resource_type == "search_run")).all()
    assert len(starts) == 2 and all(e.actor_id is None and e.after["sweep_id"] == s.id for e in starts)
    fin = db.scalars(select(AuditEvent).where(AuditEvent.action == "sweep.finish")).one()
    assert fin.actor_id is None and fin.resource_id == s.id and fin.after["status"] == "done"


def test_mixed_batches_are_partial(db, on, fake):
    extra = [f"termino {c}" for c in "abcdefgh"]        # 4 + 8 = 12: el lote 2 son «termino g» y «termino h»
    save_search(db, "Muchos", extra)
    down = SourceUnavailable("dof_sidof", "HTTP 503", retryable=True)
    fake["fake"] = FakeSidof(pages={"termino g": down, "termino h": down})
    sweeps.schedule_due(db, mx(6, 0))
    run_worker(db)
    s = daily(db)[0]
    assert s.status == "partial"
    assert s.errors and {e["batch"] for e in s.errors} == {2}
    assert {e["term"] for e in s.errors} == {"termino g", "termino h"}

    # Todo caído → failed.
    fake["fake"] = FakeSidof(pages={t: down for t in DEFAULT_TERMS + extra})
    s2 = sweeps.start_manual(db, user(db), None)
    db.commit()
    run_worker(db)
    s2 = db.get(Sweep, s2.id)
    assert s2.status == "failed" and {e["batch"] for e in s2.errors} == {1, 2}


def test_batch_exception_marks_only_that_batch(db, on, monkeypatch, fake):
    save_search(db, "Muchos", [f"termino {c}" for c in "abcdefgh"])
    from app.services import search_runs
    real = search_runs.execute_run
    calls = {"n": 0}

    def flaky(db_, job, run, client_factory):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("explosión")
        return real(db_, job, run, client_factory)

    monkeypatch.setattr(search_runs, "execute_run", flaky)
    sweeps.schedule_due(db, mx(6, 0))
    assert run_worker(db).status == "done"
    s = daily(db)[0]
    assert s.status == "partial"
    assert [e["code"] for e in s.errors] == ["internal_error"] and s.errors[0]["batch"] == 1
    runs = list(db.scalars(select(SearchRun).where(SearchRun.sweep_id == s.id).order_by(SearchRun.created_at)))
    # La excepción escapó antes del manejo de la corrida: aun así no queda en cola para siempre.
    assert [r.status for r in runs] == ["failed", "done"]
    assert runs[0].finished_at is not None and runs[0].errors[-1]["code"] == "internal_error"


def test_all_batches_raise_is_failed(db, on, monkeypatch, fake):
    save_search(db, "Muchos", [f"termino {c}" for c in "abcdefgh"])
    from app.services import search_runs

    def boom(db_, job, run, client_factory):
        raise RuntimeError("explosión")

    monkeypatch.setattr(search_runs, "execute_run", boom)
    sweeps.schedule_due(db, mx(6, 0))
    run_worker(db)
    s = daily(db)[0]
    assert s.status == "failed" and [e["batch"] for e in s.errors] == [1, 2]
    statuses = db.scalars(select(SearchRun.status).where(SearchRun.sweep_id == s.id)).all()
    assert statuses == ["failed", "failed"]


def test_sweep_internal_error_is_audited(db, on, monkeypatch, fake):
    def broken(db_, org_id):
        raise RuntimeError("sin términos")

    monkeypatch.setattr(sweeps, "compose_terms", broken)
    sweeps.schedule_due(db, mx(6, 0))
    job = run_worker(db)
    assert job.status == "failed"
    s = daily(db)[0]
    assert s.status == "failed" and s.finished_at is not None
    assert [e["code"] for e in s.errors] == ["internal_error"]
    fin = db.scalars(select(AuditEvent).where(AuditEvent.action == "sweep.finish")).one()
    assert fin.actor_id is None and fin.resource_id == s.id
    assert fin.after == {"status": "failed", "errors": ["internal_error"]}


def test_aggregate_status():
    assert sweeps.aggregate_status(["done", "done"]) == "done"
    assert sweeps.aggregate_status(["failed", "failed"]) == "failed"
    assert sweeps.aggregate_status([]) == "failed"
    assert sweeps.aggregate_status(["done", "failed"]) == "partial"
    assert sweeps.aggregate_status(["partial", "done"]) == "partial"


# ── Reintentos ───────────────────────────────────────────────────────────────

def test_failed_sweep_retries_hourly_up_to_three(db, on, fake):
    down = SourceUnavailable("dof_sidof", "HTTP 503", retryable=True)
    fake["fake"] = FakeSidof(pages={t: down for t in DEFAULT_TERMS})
    sweeps.schedule_due(db, mx(6, 0))
    run_worker(db)
    assert daily(db)[0].status == "failed"
    fail_last(db, mx(6, 5))

    assert sweeps.schedule_due(db, mx(7, 4)) == []                 # 59 min
    created = sweeps.schedule_due(db, mx(7, 5))                    # 60 min
    assert [c.attempt for c in created] == [2]
    assert db.get(Job, created[0].job_id).idempotency_key.endswith(":2026-11-03:2")
    run_worker(db)
    assert daily(db)[-1].status == "failed"
    fail_last(db, mx(7, 10))

    assert [c.attempt for c in sweeps.schedule_due(db, mx(8, 10))] == [3]
    run_worker(db)
    fail_last(db, mx(8, 15))
    assert sweeps.schedule_due(db, mx(10, 0)) == []
    assert sweeps.schedule_due(db, mx(23, 0)) == []
    assert [s.attempt for s in daily(db)] == [1, 2, 3]


def test_stale_sweep_is_failed_and_retried(db, on):
    sweeps.schedule_due(db, mx(6, 0))
    s = daily(db)[0]
    s.status = "running"
    job = db.get(Job, s.job_id)
    job.status, job.error = "failed", jobs.STALE_ERROR
    db.commit()

    sweeps.tick(db, mx(7, 0))
    s = daily(db)[0]
    assert s.status == "failed"
    assert s.errors == [{"batch": None, "code": "interrupted", "message": jobs.STALE_ERROR}]
    assert s.finished_at is not None
    assert len(daily(db)) == 1

    sweeps.tick(db, mx(7, 30))
    assert len(daily(db)) == 1
    sweeps.tick(db, mx(8, 0))
    assert [x.attempt for x in daily(db)] == [1, 2]


def test_interrupted_synced_even_when_off(db, monkeypatch):
    monkeypatch.setattr(config, "DAILY_SWEEP", False)
    s = sweeps.start_manual(db, user(db), None)
    s.status = "running"
    job = db.get(Job, s.job_id)
    job.status, job.error = "failed", jobs.STALE_ERROR
    db.commit()

    assert sweeps.schedule_due(db, mx(3, 0)) == []
    db.expire_all()
    s = db.get(Sweep, s.id)
    assert s.status == "failed" and s.finished_at is not None
    assert s.errors == [{"batch": None, "code": "interrupted", "message": jobs.STALE_ERROR}]
    assert daily(db) == []


def _running_from(db, s: Sweep, started_at: datetime) -> SearchRun:
    """Deja el barrido `s` en curso con su trabajo `running` desde `started_at` y un lote a medias."""
    s.status, s.started_at = "running", started_at
    job = db.get(Job, s.job_id)
    job.status, job.started_at, job.attempts = "running", started_at, 1
    run = SearchRun(organization_id=s.organization_id, created_by_id=s.created_by_id,
                    query={"terms": ["placa"]}, status="running", counts={}, errors=[], job_id=job.id,
                    sweep_id=s.id, started_at=started_at)
    db.add(run)
    db.commit()
    return run


def test_running_sweep_from_before_restart_is_interrupted_and_retried(db, on, monkeypatch):
    # El proceso se reinició a las 6:30 (antes de los 10 min de `recover_stale_jobs`): el trabajo sigue `running`.
    monkeypatch.setattr(jobs, "_started_at", mx(6, 30).astimezone(timezone.utc))
    sweeps.schedule_due(db, mx(6, 0))
    s = daily(db)[0]
    run = _running_from(db, s, mx(6, 25).astimezone(timezone.utc))
    sweep_id, job_id, run_id = s.id, s.job_id, run.id

    sweeps.schedule_due(db, mx(6, 31))
    db.expire_all()
    s, job, run = db.get(Sweep, sweep_id), db.get(Job, job_id), db.get(SearchRun, run_id)
    assert s.status == "failed" and s.finished_at is not None
    assert s.errors == [{"batch": None, "code": "interrupted", "message": jobs.STALE_ERROR}]
    assert job.status == "failed" and job.error == jobs.STALE_ERROR and job.finished_at is not None
    assert run.status == "failed" and run.finished_at is not None
    assert [e["code"] for e in run.errors] == ["interrupted"]
    finish = db.scalars(select(AuditEvent).where(AuditEvent.action == "sweep.finish",
                                                 AuditEvent.resource_id == sweep_id)).one()
    assert finish.after["errors"] == ["interrupted"]
    assert db.scalars(select(AuditEvent).where(AuditEvent.action == "search.finish",
                                               AuditEvent.resource_id == run_id)).one()

    assert sweeps.schedule_due(db, mx(7, 30)) == []                 # 59 min después del cierre
    assert [c.attempt for c in sweeps.schedule_due(db, mx(7, 31))] == [2]


def test_running_sweep_of_current_worker_is_left_alone(db, on, monkeypatch):
    sweeps.schedule_due(db, mx(6, 0))
    s = daily(db)[0]
    _running_from(db, s, mx(6, 25).astimezone(timezone.utc))
    sweep_id = s.id

    monkeypatch.setattr(jobs, "_started_at", None)                  # sin worker en este proceso: no se adivina
    sweeps.schedule_due(db, mx(6, 31))
    db.expire_all()
    assert db.get(Sweep, sweep_id).status == "running"

    monkeypatch.setattr(jobs, "_started_at", mx(6, 20).astimezone(timezone.utc))     # lo tomó el worker actual
    sweeps.schedule_due(db, mx(6, 31))
    db.expire_all()
    s = db.get(Sweep, sweep_id)
    assert s.status == "running" and db.get(Job, s.job_id).status == "running"


def test_tick_is_throttled(db, on, monkeypatch):
    calls = []
    monkeypatch.setattr(sweeps, "schedule_due", lambda db_, now: calls.append(now) or [])
    sweeps.tick(db, mx(6, 0))
    sweeps.tick(db, mx(6, 0) + timedelta(seconds=59))
    sweeps.tick(db, mx(6, 0) + timedelta(seconds=60))
    assert calls == [mx(6, 0), mx(6, 0) + timedelta(seconds=60)]


# ── Términos ─────────────────────────────────────────────────────────────────

def test_compose_terms_dedupes_and_caps(db):
    oid = org_id(db)
    save_search(db, "Una", ["osteosíntesis", "rodilla"])
    save_search(db, "Otra", ["Osteosintesis", "Rodilla", "cadera"], email="analista2@dipromedic.example")
    terms, dropped = sweeps.compose_terms(db, oid)
    # «rodilla» la usan dos búsquedas y «cadera» una: los más usados van primero.
    assert terms == DEFAULT_TERMS + ["rodilla", "cadera"] and dropped == []

    # 4 del diccionario + 36 distintos = 40 → 30 dentro y 10 fuera (empate: orden alfabético).
    db.query(SavedSearch).delete()
    db.commit()
    many = [f"t{i:02d}" for i in range(36)]
    for i in range(4):
        save_search(db, f"Lote {i}", list(reversed(many[i * 9:(i + 1) * 9])))
    save_search(db, "Repite", ["t35"], email="analista2@dipromedic.example")     # el más usado entra
    terms, dropped = sweeps.compose_terms(db, oid)
    assert len(terms) == sweeps.MAX_SWEEP_TERMS == 30 and len(dropped) == 10
    assert terms[:5] == DEFAULT_TERMS + ["t35"]
    assert terms[5:] == many[:25] and dropped == many[25:35]


# ── Barrido manual ───────────────────────────────────────────────────────────

def test_manual_sweep_requires_search_run(client, db):
    revisor = login(client, "revisor@dipromedic.example")
    assert client.post("/api/v1/sweeps", headers=revisor).status_code == 403

    analista = login(client, "analista1@dipromedic.example")
    h = {**analista, "Idempotency-Key": "volver-1"}
    r = client.post("/api/v1/sweeps", headers=h)
    assert r.status_code == 202, r.text
    body = r.json()
    s = db.get(Sweep, body["sweep_id"])
    assert s.trigger == "manual" and s.attempt == 0 and s.created_by_id == user(db).id
    assert s.job_id == body["job_id"]
    ev = db.scalars(select(AuditEvent).where(AuditEvent.action == "sweep.start")).one()
    assert ev.actor_id == user(db).id and ev.resource_id == s.id

    again = client.post("/api/v1/sweeps", headers=h)
    assert again.status_code == 202 and again.json()["sweep_id"] == body["sweep_id"]
    assert db.scalar(select(func.count()).select_from(Sweep)) == 1

    listed = client.get("/api/v1/sweeps?limit=10", headers=revisor)
    assert listed.status_code == 200
    item = listed.json()[0]
    assert item["id"] == s.id and item["trigger"] == "manual" and item["status"] == "queued"
    assert item["created_by"]["email"] == "analista1@dipromedic.example"
    assert set(item) >= {"day", "attempt", "terms", "dropped_terms", "counts", "errors", "started_at", "finished_at"}


# ── Ganchos del worker ───────────────────────────────────────────────────────

def test_tick_hook_errors_do_not_stop_worker(monkeypatch):
    monkeypatch.setattr(jobs, "_TICKS", [])
    seen = []

    def boom(db, now):
        raise RuntimeError("gancho roto")

    jobs.register_tick(boom)
    jobs.register_tick(lambda db, now: seen.append(now))
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    jobs.run_ticks(now)                     # no lanza
    assert seen == [now]

    # Después de un gancho roto, el worker sigue tomando trabajos.
    monkeypatch.setattr(jobs, "_HANDLERS", {**jobs._HANDLERS, "test.ok": lambda db, job: {"ok": True}})
    db = SessionLocal()
    try:
        o = db.scalars(select(Organization)).first()
        jobs.enqueue(db, organization_id=o.id, kind="test.ok", payload={}, created_by_id=None)
        db.commit()
        assert jobs.run_pending_once(db).status == "done"
    finally:
        db.close()


def test_sweeps_hook_is_registered():
    assert sweeps.tick in jobs._TICKS
    assert sweeps.JOB_KIND in jobs._HANDLERS
