"""Almacenamiento de archivos: local en disco o S3 compatible (frente D1), con la misma interfaz."""
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

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


class S3Storage(Storage):
    """Cualquier servicio compatible con S3 (bucket de Railway, R2, MinIO…) por medio de boto3.

    `addressing_style` es opcional (`"path"` o `"virtual"`); con `None` decide botocore. Mismas reglas de clave
    que `LocalStorage`: se valida con `validate_key` antes de tocar el servicio.
    """

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str, region: str = "auto",
                 addressing_style: str | None = None):
        self.bucket = bucket
        s3_config = {"addressing_style": addressing_style} if addressing_style else {}
        self._client = boto3.client(
            "s3", endpoint_url=endpoint, region_name=region,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4", s3=s3_config, connect_timeout=10, read_timeout=60,
                          retries={"max_attempts": 3, "mode": "standard"}),
        )

    @staticmethod
    def _is_missing(err: ClientError) -> bool:
        return err.response.get("Error", {}).get("Code", "") in {"404", "NoSuchKey", "NotFound"}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self.bucket, Key=validate_key(key), Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        try:
            return self._client.get_object(Bucket=self.bucket, Key=validate_key(key))["Body"].read()
        except ClientError as err:
            if self._is_missing(err):
                raise FileNotFoundError(key) from err
            raise

    def delete(self, key: str) -> None:
        # S3 no falla al borrar una clave inexistente.
        self._client.delete_object(Bucket=self.bucket, Key=validate_key(key))

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=validate_key(key))
            return True
        except ClientError as err:
            if self._is_missing(err):
                return False
            raise


_S3_VARS = ("OBJECT_STORAGE_ENDPOINT", "OBJECT_STORAGE_BUCKET", "OBJECT_STORAGE_ACCESS_KEY",
            "OBJECT_STORAGE_SECRET_KEY")


def get_storage() -> Storage:
    """S3 compatible si están las cuatro variables `OBJECT_STORAGE_*`; disco local si no hay ninguna.
    Una configuración a medias es un error: no se cae a disco en silencio (en Railway se perdería al reiniciar)."""
    values = {name: (os.getenv(name) or "").strip() for name in _S3_VARS}
    if not any(values.values()):
        return LocalStorage()
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("Configuración de almacenamiento incompleta; faltan: " + ", ".join(missing))
    return _s3_storage(
        values["OBJECT_STORAGE_ENDPOINT"], values["OBJECT_STORAGE_BUCKET"], values["OBJECT_STORAGE_ACCESS_KEY"],
        values["OBJECT_STORAGE_SECRET_KEY"], (os.getenv("OBJECT_STORAGE_REGION") or "auto").strip(),
        (os.getenv("OBJECT_STORAGE_URL_STYLE") or "").strip() or None,
    )


@lru_cache(maxsize=4)
def _s3_storage(endpoint: str, bucket: str, access_key: str, secret_key: str, region: str,
                addressing_style: str | None) -> S3Storage:
    # Crear un cliente de boto3 cuesta decenas de ms; el cliente es seguro entre hilos, así que se reutiliza.
    return S3Storage(endpoint, bucket, access_key, secret_key, region, addressing_style)
