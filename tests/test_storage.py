"""P0.2: almacenamiento de archivos (local)."""
import os
from pathlib import Path

import pytest

from app.services.storage import LocalStorage, get_storage


def test_local_storage_roundtrip_and_rejects_traversal(tmp_path):
    root = tmp_path / "storage"
    storage = LocalStorage(root)
    key = "org/o1/documents/d1/v1/Ficha técnica.PDF"
    storage.put(key, b"%PDF-1.7 demo", "application/pdf")
    assert storage.exists(key)
    assert storage.get(key) == b"%PDF-1.7 demo"
    storage.put(key, b"%PDF-1.7 v2", "application/pdf")
    assert storage.get(key) == b"%PDF-1.7 v2"
    storage.delete(key)
    assert not storage.exists(key)
    storage.delete(key)                       # borrar lo inexistente no falla
    with pytest.raises(FileNotFoundError):
        storage.get(key)

    for bad in ("../x", "a/../../x", "/etc/passwd", "..\\x", "a//b", "./a", ""):
        with pytest.raises(ValueError):
            storage.put(bad, b"x", "text/plain")
        with pytest.raises(ValueError):
            storage.get(bad)
    assert not (tmp_path / "x").exists()
    assert not [p for p in root.rglob("*") if p.is_file()]


def test_get_storage_is_local_under_storage_dir(monkeypatch):
    monkeypatch.delenv("OBJECT_STORAGE_BUCKET", raising=False)
    storage = get_storage()
    assert isinstance(storage, LocalStorage)
    # conftest apunta STORAGE_DIR a un directorio temporal.
    assert storage.root == Path(os.environ["STORAGE_DIR"])


# ── D1: almacenamiento S3 compatible ─────────────────────────────────────────

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

from app.services.storage import S3Storage  # noqa: E402

_ENDPOINT = "https://s3.us-east-1.amazonaws.com"


@mock_aws
def test_s3_storage_roundtrip():
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="licit-test")
    storage = S3Storage(endpoint=_ENDPOINT, bucket="licit-test", access_key="k", secret_key="s", region="us-east-1")
    key = "org/o1/documents/d1/v1/Ficha técnica.PDF"
    assert not storage.exists(key)
    storage.put(key, b"%PDF-1.7 demo", "application/pdf")
    assert storage.exists(key)
    assert storage.get(key) == b"%PDF-1.7 demo"
    storage.put(key, b"%PDF-1.7 v2", "application/pdf")
    assert storage.get(key) == b"%PDF-1.7 v2"
    obj = boto3.client("s3", region_name="us-east-1").head_object(Bucket="licit-test", Key=key)
    assert obj["ContentType"] == "application/pdf"
    storage.delete(key)
    assert not storage.exists(key)
    storage.delete(key)                       # borrar lo inexistente no falla
    with pytest.raises(FileNotFoundError):
        storage.get(key)


@mock_aws
def test_s3_storage_rejects_bad_keys():
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="licit-test")
    storage = S3Storage(endpoint=_ENDPOINT, bucket="licit-test", access_key="k", secret_key="s", region="us-east-1")
    for bad in ("../x", "a/../../x", "/etc/passwd", "..\\x", "a//b", "./a", ""):
        with pytest.raises(ValueError):
            storage.put(bad, b"x", "text/plain")
        with pytest.raises(ValueError):
            storage.get(bad)
    listing = boto3.client("s3", region_name="us-east-1").list_objects_v2(Bucket="licit-test")
    assert listing.get("KeyCount", 0) == 0


def test_get_storage_picks_s3_when_fully_configured(monkeypatch):
    for name, value in {"OBJECT_STORAGE_ENDPOINT": _ENDPOINT, "OBJECT_STORAGE_BUCKET": "licit-test",
                        "OBJECT_STORAGE_ACCESS_KEY": "k", "OBJECT_STORAGE_SECRET_KEY": "s"}.items():
        monkeypatch.setenv(name, value)
    assert isinstance(get_storage(), S3Storage)
    # Con una variable incompleta no se cae a disco en silencio.
    monkeypatch.delenv("OBJECT_STORAGE_SECRET_KEY")
    with pytest.raises(RuntimeError):
        get_storage()
    # Sin ninguna variable de bucket: disco local.
    for name in ("OBJECT_STORAGE_ENDPOINT", "OBJECT_STORAGE_BUCKET", "OBJECT_STORAGE_ACCESS_KEY"):
        monkeypatch.delenv(name)
    assert isinstance(get_storage(), LocalStorage)
