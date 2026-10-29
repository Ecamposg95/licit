"""Almacenamiento de archivos: local en disco o S3 compatible (frente D1), con la misma interfaz."""
import os
import uuid
from pathlib import Path
from typing import Protocol

from app.core import config


class Storage(Protocol):
    """Claves relativas con «/» (ver `validate_key`). `get` de una clave inexistente lanza FileNotFoundError;
    `delete` de una clave inexistente no falla."""

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...


def validate_key(key: str) -> str:
    """Rechaza claves absolutas, con «..», «.», segmentos vacíos o «\\» (lanza ValueError)."""
    if not key or key.startswith("/") or "\\" in key or "\x00" in key:
        raise ValueError(f"Clave de almacenamiento inválida: {key!r}")
    if any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError(f"Clave de almacenamiento inválida: {key!r}")
    return key


class LocalStorage(Storage):
    def __init__(self, root: str | os.PathLike | None = None):
        self.root = Path(root if root is not None else config.STORAGE_DIR)

    def _path(self, key: str) -> Path:
        path = self.root / validate_key(key)
        # Además de la validación léxica: un enlace simbólico tampoco puede sacar el archivo de la raíz.
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError(f"Clave de almacenamiento inválida: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Escritura atómica: quien lea durante la carga ve la versión anterior completa, nunca media.
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


def get_storage() -> Storage:
    if os.getenv("OBJECT_STORAGE_BUCKET"):
        # S3Storage lo agrega el frente D1; no se cae a disco local en silencio.
        raise RuntimeError("OBJECT_STORAGE_BUCKET está definido, pero S3Storage aún no está implementado")
    return LocalStorage()
