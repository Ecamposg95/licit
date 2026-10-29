import os

# TEST_DATABASE_URL permite correr la suite contra Postgres.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_licit.db")
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["DEMO_USER_PASSWORD"] = "demo-pass"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ.pop("ADMIN_EMAIL", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.demo_seed import bootstrap  # noqa: E402


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    bootstrap(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def login(client, email: str) -> dict:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": "demo-pass"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def analista(client):
    return login(client, "analista1@dipromedic.example")


@pytest.fixture
def direccion(client):
    return login(client, "direccion@dipromedic.example")


@pytest.fixture
def ti(client):
    return login(client, "ti@dipromedic.example")
