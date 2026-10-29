"""Corridas de búsqueda (C3): trabajo asíncrono, deduplicación, evidencia y honestidad ante fallos de la fuente.

El cliente de SIDOF es falso y devuelve las respuestas reales capturadas en C1 (tests/fixtures/sidof).
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import (
    AuditEvent, Job, Opportunity, OpportunityEvidence, Organization, SearchRun, Source, User,
)
from app.services import audit, jobs, search_runs
from app.services.demo_seed import normalize_external_id, reset_demo
from app.services.search_runs import DEFAULT_TERMS, run_search_job, start_search, upsert_procedure
from app.sources.base import ProcedureParsed, SearchPage, SourceUnavailable
from app.sources.sidof import parse_note_response, parse_search_response
from tests.conftest import login

FIX = Path(__file__).parent / "fixtures" / "sidof"
FETCHED = datetime(2026, 10, 29, 16, 0, tzinfo=timezone.utc)
T104 = "LA-50-GYR-050GYR010-T-104-2026"
T111 = "LA-50-GYR-050GYR028-T-111-2026"
I134 = "LA-50-GYR-050GYR075-I-134-2026"          # también es una referencia HISTORICAL del demo
T82 = "LA-50-GYR-050GYR069-T-82-2026"


def search_page(*cods: str, confirmed: bool = True) -> SearchPage:
    full = parse_search_response(json.loads((FIX / "search_osteosintesis_2026.json").read_bytes()))
    hits = [h for h in full.hits if h.cod_nota in cods]
    return SearchPage(hits=hits, total=full.total, confirmed=confirmed)


def note(cod: str, fetched_at: datetime = FETCHED):
    return parse_note_response(json.loads((FIX / f"nota_{cod}.json").read_bytes()), cod, fetched_at)


class FakeSidof:
    def __init__(self, pages: dict | None = None, notes: dict | None = None):
        self.pages = pages or {}
        self.notes = notes or {}
        self.searched: list[tuple[str, int]] = []
        self.fetched: list[str] = []
        self.closed = False

    def search(self, term, date_from, date_to, start=0, length=100, **kw):
        self.searched.append((term, start))
        result = self.pages.get(term, SearchPage(hits=[], total=0, confirmed=True))
        if isinstance(result, Exception):
            raise result
        return result if start == 0 else SearchPage(hits=[], total=result.total, confirmed=True)

    def get_note(self, cod):
        self.fetched.append(cod)
        result = self.notes.get(cod)
        if result is None:
            raise SourceUnavailable("dof_sidof", "HTTP 404", retryable=False)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        self.closed = True


def all_notes() -> dict:
    return {c: note(c) for c in ("5801639", "5797331", "5800141", "5800121", "5799326")}


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def analyst(db) -> User:
    return db.scalars(select(User).where(User.email == "analista1@dipromedic.example")).one()


def launch(db, fake: FakeSidof, terms: list[str]) -> SearchRun:
    run = start_search(db, analyst(db), terms, date(2026, 1, 1), date(2026, 10, 29), None)
    db.commit()
    job = db.get(Job, run.job_id)
    run_search_job(db, job, client_factory=lambda: fake)
    db.expire_all()
    return db.get(SearchRun, run.id)


def opp(db, external_id: str) -> Opportunity | None:
    return db.scalars(select(Opportunity).where(
        Opportunity.normalized_id == normalize_external_id(external_id))).first()


def evidence_count(db, o: Opportunity) -> int:
    return db.scalar(select(func.count()).select_from(OpportunityEvidence)
                     .where(OpportunityEvidence.opportunity_id == o.id))


def sidof(db) -> Source:
    return db.scalars(select(Source).where(Source.key == "dof_sidof")).one()


# ── Pruebas del brief ────────────────────────────────────────────────────────

def test_search_creates_real_opportunities_with_evidence(db):
    fake = FakeSidof(pages={"osteosintesis": search_page("5801639")}, notes=all_notes())
    run = launch(db, fake, ["osteosintesis"])

    assert run.status == "done" and run.errors == []
    assert {k: run.counts[k] for k in ("notes", "procedures", "new", "updated", "unchanged")} == \
        {"notes": 1, "procedures": 1, "new": 1, "updated": 0, "unchanged": 0}
    o = opp(db, T104)
    assert o.data_kind == "REAL"
    assert o.source.key == "dof_sidof"
    assert o.source_url == "https://sidof.segob.gob.mx/notas/docFuente/5801639"
    assert o.verification_status == "verificada"
    assert o.families == ["Osteosíntesis", "Endoprótesis"]
    assert "IMSS" in o.buyer and o.state == "Durango"
    assert o.timezone_assumed is True and o.source_timezone == "America/Mexico_City"
    assert o.requires_human_review is True
    ev = db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.opportunity_id == o.id)).all()
    assert len(ev) == 1
    assert ev[0].sha256 == note("5801639").sha256 and ev[0].search_run_id == run.id
    assert ev[0].url == o.source_url and ev[0].http_status == 200
    assert 0 < len(ev[0].excerpt) <= 500 and T104 in ev[0].excerpt
    assert fake.closed is True


def test_same_note_twice_is_unchanged(db):
    pages = {"osteosintesis": search_page("5801639")}
    launch(db, FakeSidof(pages=pages, notes=all_notes()), ["osteosintesis"])
    second = launch(db, FakeSidof(pages=pages, notes=all_notes()), ["osteosintesis"])

    assert second.status == "done"
    assert second.counts["unchanged"] >= 1 and second.counts["new"] == 0
    assert db.scalar(select(func.count()).select_from(Opportunity)
                     .where(Opportunity.normalized_id == normalize_external_id(T104))) == 1
    assert evidence_count(db, opp(db, T104)) == 2           # cada lectura queda como evidencia


def test_source_failure_partial_and_no_records(db):
    down = SourceUnavailable("dof_sidof", "tiempo de espera agotado tras 3 intentos", retryable=True)
    run = launch(db, FakeSidof(pages={"osteosintesis": search_page("5801639"), "endoprotesis": down},
                               notes=all_notes()), ["osteosintesis", "endoprotesis"])
    assert run.status == "partial"
    assert run.errors[0]["code"] == "source_unavailable"
    assert run.errors[0]["term"] == "endoprotesis" and run.errors[0]["source"] == "dof_sidof"
    assert "tiempo de espera" in run.errors[0]["message"]
    assert run.counts["new"] == 1

    real_before = db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.data_kind == "REAL"))
    failed = launch(db, FakeSidof(pages={"osteosintesis": down, "endoprotesis": down}, notes=all_notes()),
                    ["osteosintesis", "endoprotesis"])
    assert failed.status == "failed"
    assert failed.counts["new"] == 0
    assert [e["code"] for e in failed.errors] == ["source_unavailable", "source_unavailable"]
    assert db.scalar(select(func.count()).select_from(Opportunity)
                     .where(Opportunity.data_kind == "REAL")) == real_before
    source = sidof(db)
    assert source.status == "inaccesible" and "tiempo de espera" in source.last_error
    assert source.last_checked_at is not None


def test_past_dates_never_open(db, client):
    launch(db, FakeSidof(pages={"osteosintesis": search_page("5801639")}, notes=all_notes()), ["osteosintesis"])
    db.commit()
    headers = login(client, "analista1@dipromedic.example")
    rows = client.get("/api/v1/opportunities", params={"data_kind": "REAL"}, headers=headers).json()["items"]
    row = next(r for r in rows if r["external_id"] == T104)
    assert row["derived"]["code"] == "fecha_transcurrida"          # la presentación fue el 21-10-2026
    assert row["data_kind"] == "REAL" and row["source"]["key"] == "dof_sidof"


def test_unconfirmed_zero_is_reported(db):
    run = launch(db, FakeSidof(pages={"osteosintesis": search_page(confirmed=False)}), ["osteosintesis"])
    assert run.status == "partial"
    assert [e["code"] for e in run.errors] == ["zero_unconfirmed"]
    assert run.counts["new"] == 0
    term = run.counts["by_term"][0]
    assert term["term"] == "osteosintesis" and term["status"] == "unconfirmed" and term["total"] is None


# ── Más casos ────────────────────────────────────────────────────────────────

def test_multi_procedure_note_keeps_only_matching_objects(db):
    run = launch(db, FakeSidof(pages={"osteosintesis": search_page("5800141")}, notes=all_notes()),
                 ["osteosintesis"])
    assert run.counts["new"] == 1 and run.counts["procedures"] == 1
    assert run.counts["by_term"][0]["discarded"] == 14     # los otros 14 procedimientos no son del objeto
    assert opp(db, T111).data_kind == "REAL"
    assert opp(db, "LA-50-GYR-050GYR028-N-103-2026") is None


def test_non_convocatoria_hits_are_not_fetched(db):
    full = parse_search_response(json.loads((FIX / "search_osteosintesis_2026.json").read_bytes()))
    executive = [h for h in full.hits if h.organism == "PODER EJECUTIVO"]
    page = SearchPage(hits=executive + search_page("5801639").hits, total=full.total, confirmed=True)
    fake = FakeSidof(pages={"osteosintesis": page}, notes=all_notes())
    run = launch(db, fake, ["osteosintesis"])
    assert fake.fetched == ["5801639"]
    assert run.counts["by_term"][0]["skipped_non_cv"] == len(executive) == 4


def test_notes_shared_by_terms_are_read_once(db):
    pages = {"osteosintesis": search_page("5801639"), "endoprotesis": search_page("5801639", "5797331")}
    fake = FakeSidof(pages=pages, notes=all_notes())
    run = launch(db, fake, ["osteosintesis", "endoprotesis"])
    assert sorted(fake.fetched) == ["5797331", "5801639"]
    by_term = {t["term"]: t for t in run.counts["by_term"]}
    assert by_term["osteosintesis"]["notes"] == 1 and by_term["endoprotesis"]["notes"] == 1
    assert by_term["endoprotesis"]["seen_other_term"] == 1
    assert by_term["osteosintesis"]["checked_at"] is not None


def test_existing_historical_is_not_duplicated_nor_converted(db):
    historical = opp(db, I134)
    assert historical.data_kind == "HISTORICAL"
    run = launch(db, FakeSidof(pages={"osteosintesis": search_page("5797331")}, notes=all_notes()),
                 ["osteosintesis"])
    assert run.counts["new"] == 0 and run.counts["updated"] == 1
    again = opp(db, I134)
    assert again.id == historical.id and again.data_kind == "HISTORICAL"
    assert evidence_count(db, again) == 1
    # El reinicio del demo sigue funcionando (no hay un REAL con el mismo número que choque con la semilla).
    reset_demo(db, db.get(Organization, again.organization_id), actor_id=None)
    db.commit()
    assert opp(db, I134).data_kind == "HISTORICAL"


def test_fallo_without_convocatoria_is_not_an_opportunity(db):
    run = launch(db, FakeSidof(pages={"osteosintesis": search_page("5799326")}, notes=all_notes()),
                 ["osteosintesis"])
    assert opp(db, T82) is None
    assert run.counts["new"] == 0 and run.counts["by_term"][0]["discarded"] == 2


def test_fallo_note_closes_existing_opportunity(db):
    user = analyst(db)
    conv = ProcedureParsed(
        external_id=T82, buyer="IMSS", title="ADQUISICION DE MATERIAL DE OSTEOSINTESIS Y ENDOPROTESIS",
        state="Campeche", volume=None, published_at=None, questions_at=None, submission_at=None, ruling_at=None,
        submission_precision="datetime", timezone_assumed=False, excerpt=f"No. licitación: {T82}")
    other = note("5801639")
    other.url = "https://sidof.segob.gob.mx/notas/docFuente/1"
    assert upsert_procedure(db, user.organization_id, conv, other, None, actor_id=user.id) == "new"
    db.commit()

    launch(db, FakeSidof(pages={"osteosintesis": search_page("5799326")}, notes=all_notes()), ["osteosintesis"])
    closed = opp(db, T82)
    assert closed.result == "fallo publicado"
    assert closed.reported_status == "Fallo publicado en el DOF"
    assert closed.ruling_at is not None and closed.version == 2
    assert evidence_count(db, closed) == 2


def test_note_failures_are_reported_and_abort_after_three(db):
    flaky = SourceUnavailable("dof_sidof", "HTTP 503 tras 3 intentos", retryable=True)
    cods = ["5801639", "5797331", "5800141", "5800121"]
    fake = FakeSidof(pages={"osteosintesis": search_page(*cods)}, notes={c: flaky for c in cods})
    run = launch(db, fake, ["osteosintesis"])
    assert len(fake.fetched) == 3                           # la cuarta ya no se pide
    assert run.status == "partial"
    assert [e["code"] for e in run.errors] == ["source_unavailable"] * 3 + ["aborted"]
    assert run.counts["new"] == 0


def test_start_search_is_idempotent_and_audited(db):
    user = analyst(db)
    first = start_search(db, user, ["osteosintesis"], date(2026, 1, 1), date(2026, 10, 29), "clic-1")
    db.commit()
    again = start_search(db, user, ["osteosintesis"], date(2026, 1, 1), date(2026, 10, 29), "clic-1")
    db.commit()
    assert again.id == first.id and again.job_id == first.job_id
    assert first.status == "queued"
    assert first.query == {"terms": ["osteosintesis"], "date_from": "2026-01-01", "date_to": "2026-10-29"}
    job = db.get(Job, first.job_id)
    # Carga JSON nativa: fechas como texto ISO (un objeto date haría fallar el INSERT).
    assert job.kind == "search_run"
    assert job.payload == {"terms": ["osteosintesis"], "date_from": "2026-01-01", "date_to": "2026-10-29"}
    assert job.idempotency_key.endswith(":clic-1")
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "search.start")) == 1
    assert db.scalar(select(func.count()).select_from(SearchRun)) == 1


def test_run_is_audited_and_chain_stays_valid(db):
    run = launch(db, FakeSidof(pages={"osteosintesis": search_page("5801639")}, notes=all_notes()),
                 ["osteosintesis"])
    actions = list(db.scalars(select(AuditEvent.action).order_by(AuditEvent.created_at)))
    assert actions[-3:] == ["search.start", "opportunity.create", "search.finish"]
    finish = db.scalars(select(AuditEvent).where(AuditEvent.action == "search.finish")).one()
    assert finish.resource_id == run.id and finish.after["status"] == "done"
    assert finish.actor_id == analyst(db).id
    assert audit.verify_chain(db, run.organization_id)[0] is True
    assert sidof(db).status == "activa" and sidof(db).last_error is None


def test_worker_runs_registered_handler(db, monkeypatch):
    monkeypatch.setattr(search_runs, "SidofClient",
                        lambda: FakeSidof(pages={"osteosintesis": search_page("5801639")}, notes=all_notes()))
    run = start_search(db, analyst(db), ["osteosintesis"], date(2026, 1, 1), date(2026, 10, 29), None)
    db.commit()
    job = jobs.run_pending_once(db)
    assert job.id == run.job_id and job.status == "done" and job.progress == 100
    assert job.result["search_run_id"] == run.id and job.result["status"] == "done"
    assert job.result["counts"]["new"] == 1


def test_unexpected_error_fails_run_and_job(db, monkeypatch):
    class Broken(FakeSidof):
        def search(self, *a, **kw):
            raise RuntimeError("fallo interno simulado")

    monkeypatch.setattr(search_runs, "SidofClient", Broken)
    run = start_search(db, analyst(db), ["osteosintesis"], date(2026, 1, 1), date(2026, 10, 29), None)
    db.commit()
    job = jobs.run_pending_once(db)
    assert job.status == "failed" and "fallo interno simulado" in job.error
    db.expire_all()
    failed = db.get(SearchRun, run.id)
    assert failed.status == "failed" and failed.finished_at is not None
    assert failed.errors[-1]["code"] == "internal_error"


def test_default_terms():
    assert DEFAULT_TERMS == ["osteosintesis", "endoprotesis", "implantes ortopedicos", "material de osteosintesis"]
