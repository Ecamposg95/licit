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
