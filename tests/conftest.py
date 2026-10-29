import os
import shutil
import tempfile

# TEST_DATABASE_URL permite correr la suite contra Postgres.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_licit.db")
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["DEMO_USER_PASSWORD"] = "demo-pass"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ.pop("ADMIN_EMAIL", None)
# Sin worker en segundo plano ni importación del catálogo; archivos en un directorio temporal.
os.environ["JOBS_WORKER"] = "0"
os.environ["IMPORT_CATALOG"] = "0"
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="licit-storage-")
os.environ.pop("OBJECT_STORAGE_BUCKET", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.demo_seed import bootstrap  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _storage_dir():
    yield
    shutil.rmtree(os.environ["STORAGE_DIR"], ignore_errors=True)


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
