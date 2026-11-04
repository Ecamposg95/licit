"""Búsquedas guardadas por persona y filtro del Radar (T17)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import AuditEvent, DataKind, Opportunity, OpportunityEvidence, SavedSearch, Source, User
from app.services import saved_searches
from tests.conftest import login

ANALYST = "analista1@dipromedic.example"
OTHER = "analista2@dipromedic.example"
URL = "/api/v1/saved-searches"


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def make_opp(db, external_id, title="Material de osteosíntesis", **kw) -> Opportunity:
    u = db.scalars(select(User).where(User.email == ANALYST)).one()
    src = db.scalars(select(Source)).first()
    fields = dict(organization_id=u.organization_id, external_id=external_id, normalized_id=external_id.lower(),
                  title=title, buyer="IMSS UMAE Jalisco", state="Jalisco", families=["Osteosíntesis"],
                  data_kind=DataKind.REAL.value, source_id=src.id, verification_status="por_verificar",
                  result="desconocido", requires_human_review=True)
    fields.update(kw)
    o = Opportunity(**fields)
    db.add(o)
    db.commit()
    return o


def ss(**kw) -> SavedSearch:
    base = dict(name="x", terms=[], states=[], families=[], buyers=[])
    base.update(kw)
    return SavedSearch(**base)


def test_crud_is_per_user_and_audited(client, db):
    a, b = login(client, ANALYST), login(client, OTHER)
    r = client.post(URL, headers=a, json={"name": "Jalisco", "terms": ["osteosintesis"], "states": ["Jalisco"]})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert client.get(URL, headers=a).json()[0]["id"] == sid
    assert client.get(URL, headers=b).json() == []
    assert client.put(f"{URL}/{sid}", headers=b, json={"name": "x", "terms": ["a"]}).status_code == 404
    assert client.delete(f"{URL}/{sid}", headers=b).status_code == 404
    r = client.put(f"{URL}/{sid}", headers=a, json={"name": "Jalisco 2", "terms": ["osteosintesis"]})
    assert r.status_code == 200 and r.json()["name"] == "Jalisco 2"
    assert client.delete(f"{URL}/{sid}", headers=a).status_code == 204
    actions = [e.action for e in db.scalars(select(AuditEvent).where(AuditEvent.resource_type == "saved_search")
                                            .order_by(AuditEvent.created_at))]
    assert actions == ["saved_search.create", "saved_search.update", "saved_search.delete"]


def test_saved_search_requires_a_condition(client):
    a = login(client, ANALYST)
    r = client.post(URL, headers=a, json={"name": "Vacía", "terms": [" "], "states": []})
    assert r.status_code == 422 and r.json()["code"] == "saved_search_empty"


def test_limits_and_duplicates(client):
    a = login(client, ANALYST)
    assert client.post(URL, headers=a, json={"name": "Uno", "terms": ["a1"]}).status_code == 201
    r = client.post(URL, headers=a, json={"name": " uno ", "terms": ["b1"]})
    assert r.status_code == 409 and r.json()["code"] == "saved_search_duplicate"
    r = client.post(URL, headers=a, json={"name": "Muchos", "terms": [f"t{i}" for i in range(11)]})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    for i in range(19):
        assert client.post(URL, headers=a, json={"name": f"n{i}", "terms": ["z"]}).status_code == 201
    r = client.post(URL, headers=a, json={"name": "n20", "terms": ["z"]})
    assert r.status_code == 422 and r.json()["code"] == "saved_search_limit"


def test_clean_dedupes_accents():
    out = saved_searches.clean({"name": " N ", "terms": ["Osteosíntesis", "osteosintesis "], "states": ["Jalisco", "jalisco"],
                                "families": [], "buyers": [" "]})
    assert out["terms"] == ["Osteosíntesis"] and out["states"] == ["Jalisco"] and out["buyers"] == []
    assert out["name"] == "N"


def test_matches_all_defined_conditions(db):
    o = make_opp(db, "LA-99-SS-001")
    assert saved_searches.matches(ss(terms=["osteosintesis"], states=["jalisco"]), o, [])
    assert not saved_searches.matches(ss(terms=["osteosintesis"], states=["Sonora"]), o, [])
    assert saved_searches.matches(ss(buyers=["umae"]), o, [])
    assert saved_searches.matches(ss(families=["Endoprótesis", "osteosintesis"]), o, [])
    assert not saved_searches.matches(ss(terms=["clavo"]), o, [])
    assert saved_searches.matches(ss(terms=["clavo"]), o, ["Se requiere clavo centromedular"])


def test_territory_and_excerpts(db):
    o = make_opp(db, "LA-99-SS-002")
    src = db.scalars(select(Source)).first()
    db.add(OpportunityEvidence(organization_id=o.organization_id, opportunity_id=o.id, source_id=src.id,
                               url="https://x.example", fetched_at=datetime.now(timezone.utc), sha256="0" * 64,
                               excerpt="incluye clavo"))
    for email, name, terms in ((ANALYST, "a", ["clavo"]), (OTHER, "b", ["tornillo"])):
        u = db.scalars(select(User).where(User.email == email)).one()
        db.add(SavedSearch(organization_id=u.organization_id, user_id=u.id, name=name, terms=terms,
                           states=[], families=[], buyers=[]))
    db.commit()
    assert saved_searches.excerpts_by_opportunity(db, [o.id]) == {o.id: ["incluye clavo"]}
    assert saved_searches.excerpts_by_opportunity(db, []) == {}
    terr = saved_searches.territory(db, o.organization_id, [o])
    assert [s.name for s in terr[o.id]] == ["a"]


def test_radar_filter_by_saved_search(client, db):
    a, b = login(client, ANALYST), login(client, OTHER)
    make_opp(db, "LA-99-SS-010", state="Jalisco")
    make_opp(db, "LA-99-SS-011", state="Sonora")
    sid = client.post(URL, headers=a, json={"name": "Jal", "states": ["jalisco"]}).json()["id"]
    r = client.get(f"/api/v1/opportunities?saved_search_id={sid}&data_kind=REAL", headers=a)
    assert r.status_code == 200
    assert [i["external_id"] for i in r.json()["items"]] == ["LA-99-SS-010"] and r.json()["total"] == 1
    assert client.get(f"/api/v1/opportunities?saved_search_id={sid}", headers=b).status_code == 404


def test_blank_name_rejected(client):
    a = login(client, "analista1@dipromedic.example")
    r = client.post(URL, headers=a, json={"name": "   ", "terms": ["osteosintesis"]})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert "nombre" in r.json()["message"].lower()
    sid = client.post(URL, headers=a, json={"name": "Buena", "terms": ["osteosintesis"]}).json()["id"]
    r = client.put(f"{URL}/{sid}", headers=a, json={"name": " \t ", "terms": ["osteosintesis"]})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
