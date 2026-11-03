"""T17.1: esquema de clasificación, búsquedas guardadas, barridos y marca de visita."""
from sqlalchemy import inspect, select

from app.core.database import SessionLocal, engine
from app.models import Opportunity


def test_t17_columns_and_tables_exist():
    insp = inspect(engine)
    opp_cols = {c["name"] for c in insp.get_columns("opportunities")}
    assert {"triage_status", "triage_reason", "triage_by_id", "triage_at", "published_at"} <= opp_cols
    assert {"hoy_seen_at", "hoy_prev_seen_at"} <= {c["name"] for c in insp.get_columns("users")}
    assert "sweep_id" in {c["name"] for c in insp.get_columns("search_runs")}
    assert {"saved_searches", "sweeps"} <= set(insp.get_table_names())


def test_seed_opportunities_are_not_triaged():
    db = SessionLocal()
    kinds = {(o.data_kind, o.triage_status) for o in db.scalars(select(Opportunity))}
    assert all(t is None for k, t in kinds if k != "REAL")
    db.close()
