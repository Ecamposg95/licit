import os

os.environ["DATABASE_URL"] = "sqlite:///./test_licit.db"
os.environ.setdefault("SECRET_KEY", "test-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import Role, User  # noqa: E402


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _make_user(email: str, role: Role) -> None:
    db = SessionLocal()
    db.add(User(email=email, full_name=email, hashed_password=get_password_hash("secret"), role=role.value))
    db.commit()
    db.close()


def _token(client, email: str) -> dict:
    r = client.post("/api/auth/login", data={"username": email, "password": "secret"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    _make_user("admin@test.mx", Role.ADMIN)
    return _token(client, "admin@test.mx")


@pytest.fixture
def viewer_headers(client):
    _make_user("viewer@test.mx", Role.VIEWER)
    return _token(client, "viewer@test.mx")
