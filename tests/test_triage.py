"""Clasificación de oportunidades REAL nuevas (Seguir / Descartar), auditada."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import AuditEvent, DataKind, Opportunity, Source, User
from app.services import audit
from app.sources.sidof import parse_procedures
from tests.conftest import login
from tests.test_search_runs import FakeSidof, all_notes, launch, opp as find_opp, search_page, T104

ANALYST = "analista1@dipromedic.example"
REVISOR = "revisor@dipromedic.example"


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def user(db, email=ANALYST) -> User:
    return db.scalars(select(User).where(User.email == email)).one()


def real_opp(db, external_id="LA-99-TRI-001", **kw) -> Opportunity:
    u = user(db)
    src = db.scalars(select(Source)).first()
    fields = dict(organization_id=u.organization_id, external_id=external_id, normalized_id=external_id.lower(),
                  title="Material de osteosíntesis", buyer="IMSS", families=["Osteosíntesis"],
                  data_kind=DataKind.REAL.value, source_id=src.id, verification_status="por_verificar",
                  result="desconocido", requires_human_review=True, triage_status="nueva")
    fields.update(kw)
    o = Opportunity(**fields)
    db.add(o)
    db.commit()
    return o


def triage_events(db):
    return list(db.scalars(select(AuditEvent).where(AuditEvent.action == "opportunity.triage")
                           .order_by(AuditEvent.created_at)))


def post(client, headers, opp_id, version, action, **kw):
    return client.post(f"/api/v1/opportunities/{opp_id}/triage", headers=headers,
                       json={"expected_version": version, "action": action, **kw})


def test_follow_requires_owner_and_is_audited(client, db):
    o = real_opp(db)
    h = login(client, ANALYST)
    r = post(client, h, o.id, o.version, "seguir")
    assert r.status_code == 422 and r.json()["code"] == "owner_required"
    me = user(db)
    r = post(client, h, o.id, o.version, "seguir", owner_id=me.id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["triage_status"] == "siguiendo" and body["owner"]["id"] == me.id
    assert body["triage_by"]["id"] == me.id and body["triage_at"] and body["version"] == o.version + 1
    ev = triage_events(db)
    assert len(ev) == 1 and ev[0].after["triage_status"] == "siguiendo"
    assert ev[0].before["triage_status"] == "nueva" and ev[0].after["owner_id"] == me.id


def test_discard_requires_reason_and_keeps_record(client, db):
    o = real_opp(db)
    h = login(client, ANALYST)
    r = post(client, h, o.id, o.version, "descartar", reason="  ")
    assert r.status_code == 422 and r.json()["code"] == "reason_required"
    r = post(client, h, o.id, o.version, "descartar", reason="No manejamos esa familia")
    assert r.status_code == 200, r.text
    assert r.json()["triage_reason"] == "No manejamos esa familia"
    rows = client.get("/api/v1/opportunities?data_kind=REAL", headers=h).json()["items"]
    assert [x["triage_status"] for x in rows if x["id"] == o.id] == ["descartada"]


def test_discarded_can_be_followed_again(client, db):
    o = real_opp(db)
    h = login(client, ANALYST)
    me = user(db)
    v = post(client, h, o.id, o.version, "descartar", reason="Duplicada").json()["version"]
    r = post(client, h, o.id, v, "seguir", owner_id=me.id)
    assert r.status_code == 200 and r.json()["triage_status"] == "siguiendo"
    assert r.json()["triage_reason"] is None


def test_same_state_rejected(client, db):
    o = real_opp(db)
    h = login(client, ANALYST)
    v = post(client, h, o.id, o.version, "descartar", reason="Fuera de alcance").json()["version"]
    r = post(client, h, o.id, v, "descartar", reason="Otra vez")
    assert r.status_code == 422 and r.json()["code"] == "triage_unchanged"


def test_version_conflict(client, db):
    o = real_opp(db)
    h = login(client, ANALYST)
    r = post(client, h, o.id, o.version + 5, "descartar", reason="x")
    assert r.status_code == 409 and r.json()["code"] == "version_conflict"


def test_triage_rejects_non_real(client, db):
    synth = db.scalars(select(Opportunity).where(Opportunity.data_kind == DataKind.SYNTHETIC.value)).first()
    h = login(client, ANALYST)
    before = len(triage_events(db))
    r = post(client, h, synth.id, synth.version, "descartar", reason="x")
    assert r.status_code == 422 and r.json()["code"] == "not_triageable"
    assert len(triage_events(db)) == before


def test_triage_needs_write_permission(client, db):
    o = real_opp(db)
    r = post(client, login(client, REVISOR), o.id, o.version, "descartar", reason="x")
    assert r.status_code == 403


def test_owner_must_belong_to_org(client, db):
    o = real_opp(db)
    r = post(client, login(client, ANALYST), o.id, o.version, "seguir", owner_id="no-existe")
    assert r.status_code == 404


def test_patch_owner_on_new_moves_to_following(client, db):
    o = real_opp(db)
    h = login(client, ANALYST)
    me = user(db)
    r = client.patch(f"/api/v1/opportunities/{o.id}", headers=h,
                     json={"expected_version": o.version, "owner_id": me.id})
    assert r.status_code == 200, r.text
    assert r.json()["triage_status"] == "siguiendo"
    ev = triage_events(db)
    assert len(ev) == 1 and ev[0].after["via"] == "asignacion"
    actions = {e.action for e in db.scalars(select(AuditEvent).where(AuditEvent.resource_id == o.id))}
    assert {"opportunity.update", "opportunity.triage"} <= actions


def test_patch_owner_on_discarded_keeps_status(client, db):
    o = real_opp(db, triage_status="descartada", triage_reason="x")
    h = login(client, ANALYST)
    r = client.patch(f"/api/v1/opportunities/{o.id}", headers=h,
                     json={"expected_version": o.version, "owner_id": user(db).id})
    assert r.status_code == 200 and r.json()["triage_status"] == "descartada"
    assert triage_events(db) == []


def test_new_real_from_search_and_import_start_as_nueva(client, db):
    fake = FakeSidof(pages={"osteosintesis": search_page("5801639")}, notes=all_notes())
    launch(db, fake, ["osteosintesis"])
    o = find_opp(db, T104)
    assert o.triage_status == "nueva"
    expected = parse_procedures(fake.notes["5801639"].html)[0].published_at
    assert expected is not None and o.published_at.replace(tzinfo=None) == expected.replace(tzinfo=None)
    h = login(client, ANALYST)
    meta = {"external_id": "LA-12-ABC-012ABC001-N-9-2026", "title": "Material de osteosíntesis", "buyer": "Hospital",
            "source_url": "https://comprasmx.buengobierno.gob.mx/sitiopublico/#/sitiopublico/detalle/abc/1"}
    r = client.post("/api/v1/opportunities/import", json={"metadata": meta}, headers=h)
    assert r.status_code == 201 and r.json()["triage_status"] == "nueva"
    assert r.json()["created_at"]


def test_audit_chain_still_valid(client, db):
    h = login(client, ANALYST)
    me = user(db)
    for i in range(3):
        o = real_opp(db, f"LA-99-TRI-{i}")
        post(client, h, o.id, o.version, "seguir", owner_id=me.id)
        post(client, h, o.id, o.version + 1, "descartar", reason="Cambio de prioridades")
    assert len(triage_events(db)) == 6
    ok, _, broken = audit.verify_chain(db, me.organization_id)
    assert ok and broken is None


def test_patch_cannot_clear_owner_of_followed(client, db):
    me = user(db)
    o = real_opp(db, triage_status="siguiendo", owner_id=me.id)
    h = login(client, ANALYST)
    r = client.patch(f"/api/v1/opportunities/{o.id}", headers=h,
                     json={"expected_version": o.version, "owner_id": None})
    assert r.status_code == 422 and r.json()["code"] == "owner_required"
    db.expire_all()
    o = db.get(Opportunity, o.id)
    assert o.owner_id == me.id and o.version == 1 and o.triage_status == "siguiendo"

    # En una oportunidad nueva (o descartada) quitar el responsable sigue permitido.
    n = real_opp(db, external_id="LA-99-TRI-002", owner_id=me.id)
    r = client.patch(f"/api/v1/opportunities/{n.id}", headers=h,
                     json={"expected_version": n.version, "owner_id": None})
    assert r.status_code == 200 and r.json()["owner"] is None
