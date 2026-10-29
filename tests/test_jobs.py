"""P0.2: cola de trabajos en la base de datos y endpoint de consulta."""
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import config
from app.core.database import SessionLocal, engine
from app.core.errors import AppError
from app.main import app
from app.models import Job, Organization, User
from app.services import jobs


@pytest.fixture(autouse=True)
def _handlers(monkeypatch):
    # Los handlers registrados por una prueba no se filtran a las demás.
    monkeypatch.setattr(jobs, "_HANDLERS", dict(jobs._HANDLERS))


def _context(db) -> tuple[Organization, User]:
    org = db.scalars(select(Organization)).first()
    user = db.scalars(select(User).where(User.email == "analista1@dipromedic.example")).one()
    return org, user


def _enqueue(db, kind: str, key: str | None = None, payload: dict | None = None) -> Job:
    org, user = _context(db)
    return jobs.enqueue(db, organization_id=org.id, kind=kind, payload=payload or {}, created_by_id=user.id,
                        idempotency_key=key)


def test_enqueue_idempotent():
    db = SessionLocal()
    first = _enqueue(db, "test.ok", key="doble-clic-1")
    db.commit()
    again = _enqueue(db, "test.ok", key="doble-clic-1")
    db.commit()
    other = _enqueue(db, "test.ok", key="doble-clic-2")
    no_key = [_enqueue(db, "test.ok"), _enqueue(db, "test.ok")]
    db.commit()
    assert again.id == first.id
    assert other.id != first.id and no_key[0].id != no_key[1].id
    assert first.status == "queued" and first.progress == 0 and first.attempts == 0
    assert db.scalar(select(func.count()).select_from(Job)) == 4
    db.close()


def test_enqueue_same_key_concurrently_returns_same_job():
    if engine.dialect.name != "postgresql":
        pytest.skip("La carrera de dos transacciones se prueba en Postgres (producción)")
    first_session = SessionLocal()
    first_id = _enqueue(first_session, "test.ok", key="carrera").id      # sin commit todavía
    seen = {}

    def second_click():
        db = SessionLocal()
        seen["id"] = _enqueue(db, "test.ok", key="carrera").id
        db.commit()
        db.close()

    t = threading.Thread(target=second_click)
    t.start()
    time.sleep(0.3)
    assert t.is_alive()                   # espera a que la primera transacción termine
    first_session.commit()
    t.join(10)
    assert seen["id"] == first_id
    assert first_session.scalar(select(func.count()).select_from(Job)) == 1
    first_session.close()


def test_run_pending_executes_handler():
    seen = {}

    def handler(db, job):
        jobs.set_progress(db, job, 40, "Consultando SIDOF")
        other = SessionLocal()                # el avance ya es visible desde otra sesión (polling)
        polled = other.get(Job, job.id)
        seen.update(progress=polled.progress, message=polled.message, status=polled.status)
        other.close()
        return {"ok": 1, "payload": job.payload}

    jobs.register("test.ok", handler)
    db = SessionLocal()
    job_id = _enqueue(db, "test.ok", payload={"terms": ["osteosintesis"]}).id
    db.commit()

    job = jobs.run_pending_once(db)
    assert job.id == job_id
    assert job.status == "done" and job.result == {"ok": 1, "payload": {"terms": ["osteosintesis"]}}
    assert job.attempts == 1 and job.progress == 100 and job.error is None
    assert job.started_at is not None and job.finished_at is not None
    assert seen == {"progress": 40, "message": "Consultando SIDOF", "status": "running"}
    assert jobs.run_pending_once(db) is None
    db.close()


def test_failing_handler_marks_failed():
    def handler(db, job):
        org = db.scalars(select(Organization)).first()
        org.name = "Cambio a medias"
        db.flush()
        raise RuntimeError("x")

    jobs.register("test.falla", handler)
    db = SessionLocal()
    failing = _enqueue(db, "test.falla").id
    unknown = _enqueue(db, "test.sin_handler").id
    db.commit()

    ran = [jobs.run_pending_once(db).id, jobs.run_pending_once(db).id]
    db.close()

    db = SessionLocal()
    job = db.get(Job, failing)
    assert ran == [failing, unknown]
    assert job.status == "failed" and "x" in job.error and job.attempts == 1
    assert job.finished_at is not None and job.result is None
    # Lo que el handler dejó a medias se revierte.
    assert db.scalars(select(Organization)).first().name == config.ORGANIZATION_NAME
    assert db.get(Job, unknown).status == "failed"
    assert "test.sin_handler" in db.get(Job, unknown).error
    db.close()


def test_job_endpoint_scoped(client, analista):
    db = SessionLocal()
    own = _enqueue(db, "test.ok", payload={"a": 1})
    other = Organization(name="Otra")
    db.add(other)
    db.flush()
    foreign = jobs.enqueue(db, organization_id=other.id, kind="test.ok", payload={}, created_by_id=None)
    db.commit()
    own_id, foreign_id = own.id, foreign.id
    db.close()

    r = client.get(f"/api/v1/jobs/{own_id}", headers=analista)
    assert r.status_code == 200
    assert set(r.json()) == {"id", "kind", "status", "progress", "message", "result", "error",
                             "created_at", "started_at", "finished_at"}
    assert r.json()["status"] == "queued" and r.json()["progress"] == 0
    assert client.get(f"/api/v1/jobs/{foreign_id}", headers=analista).status_code == 404
    assert client.get(f"/api/v1/jobs/{own_id}").status_code == 401


def test_idempotency_key_of_other_org_is_not_shared():
    db = SessionLocal()
    _enqueue(db, "test.ok", key="compartida")
    other = Organization(name="Otra")
    db.add(other)
    db.commit()
    with pytest.raises(AppError) as exc:
        jobs.enqueue(db, organization_id=other.id, kind="test.ok", payload={}, created_by_id=None,
                     idempotency_key="compartida")
    assert exc.value.status == 409
    db.close()


def test_worker_runs_with_lifespan_and_stops(monkeypatch):
    jobs.register("test.ok", lambda db, job: {"ok": 1})
    with TestClient(app):
        assert not jobs.worker_alive()       # JOBS_WORKER=0 en pruebas

    monkeypatch.setattr(config, "JOBS_WORKER", True)
    db = SessionLocal()
    job_id = _enqueue(db, "test.ok").id
    db.commit()
    db.close()
    with TestClient(app):
        assert jobs.worker_alive()
        deadline = time.monotonic() + 10
        status = None
        while time.monotonic() < deadline and status != "done":
            time.sleep(0.1)
            db = SessionLocal()
            status = db.get(Job, job_id).status
            db.close()
        assert status == "done"
    assert not jobs.worker_alive()
