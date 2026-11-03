"""Operación de cuentas del beta: rotar contraseña, retirar acceso y vencimiento, siempre auditado."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import AuditEvent, User
from app.services import accounts, audit
from tests.conftest import login

EMAIL = "analista2@dipromedic.example"


def _events(db, action):
    return db.scalars(select(AuditEvent).where(AuditEvent.action == action)).all()


def test_set_password_changes_login_and_is_audited(client):
    db = SessionLocal()
    accounts.set_password(db, EMAIL, "nueva-clave-beta")
    db.commit()
    assert client.post("/api/v1/auth/login", data={"username": EMAIL, "password": "demo-pass"}).status_code == 401
    r = client.post("/api/v1/auth/login", data={"username": EMAIL, "password": "nueva-clave-beta"})
    assert r.status_code == 200
    ev = _events(db, "account.password_set")
    assert len(ev) == 1 and ev[0].actor_id is None
    # La bitácora nunca guarda la contraseña ni su hash.
    assert "nueva-clave-beta" not in str(ev[0].after) and "$2" not in str(ev[0].after)
    db.close()


def test_short_password_rejected():
    db = SessionLocal()
    with pytest.raises(accounts.AccountError):
        accounts.set_password(db, EMAIL, "corta")
    db.close()


def test_unknown_email_rejected():
    db = SessionLocal()
    with pytest.raises(accounts.AccountError):
        accounts.deactivate(db, "nadie@dipromedic.example")
    db.close()


def test_deactivate_cuts_existing_session_and_activate_restores(client):
    headers = login(client, EMAIL)
    db = SessionLocal()
    accounts.deactivate(db, EMAIL)
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/login", data={"username": EMAIL, "password": "demo-pass"}).status_code == 401
    accounts.activate(db, EMAIL)
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert [e.after for e in _events(db, "account.deactivated")] == [{"is_active": False}]
    assert len(_events(db, "account.activated")) == 1
    db.close()


def test_expiry_in_past_blocks_and_clearing_restores(client):
    db = SessionLocal()
    accounts.set_expiry(db, EMAIL, datetime.now(timezone.utc) - timedelta(minutes=1))
    db.commit()
    r = client.post("/api/v1/auth/login", data={"username": EMAIL, "password": "demo-pass"})
    assert r.status_code == 401 and r.json()["code"] == "account_expired"
    accounts.set_expiry(db, EMAIL, None)
    db.commit()
    assert client.post("/api/v1/auth/login", data={"username": EMAIL, "password": "demo-pass"}).status_code == 200
    assert [e.after["expires_at"] for e in _events(db, "account.expiry_set")][-1] is None
    db.close()


def test_naive_expiry_rejected():
    db = SessionLocal()
    with pytest.raises(accounts.AccountError):
        accounts.set_expiry(db, EMAIL, datetime(2026, 12, 1))
    db.close()


def test_list_accounts_has_no_secrets():
    db = SessionLocal()
    rows = accounts.list_accounts(db)
    assert {r["email"] for r in rows} >= {EMAIL, "presentador@dipromedic.example"}
    assert all(set(r) == {"email", "full_name", "roles", "is_active", "expires_at"} for r in rows)
    db.close()


def test_demo_password_applies_to_all_demo_users(client):
    db = SessionLocal()
    changed = accounts.set_demo_password(db, "rotada-para-beta")
    db.commit()
    assert changed == len(db.scalars(select(User).where(User.email.like("%@dipromedic.example"))).all())
    r = client.post("/api/v1/auth/login", data={"username": "revisor@dipromedic.example",
                                                 "password": "rotada-para-beta"})
    assert r.status_code == 200
    db.close()


def test_account_events_keep_audit_chain_valid():
    db = SessionLocal()
    accounts.deactivate(db, EMAIL)
    accounts.set_expiry(db, EMAIL, datetime.now(timezone.utc) + timedelta(days=7))
    accounts.set_demo_password(db, "rotada-para-beta")
    db.commit()
    org_id = db.scalars(select(User.organization_id).where(User.email == EMAIL)).one()
    ok, checked, broken = audit.verify_chain(db, org_id)
    assert ok and broken is None and checked >= 10
    db.close()
