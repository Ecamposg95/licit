"""Contrato del estado de un trabajo asíncrono (polling desde la UI)."""
from datetime import datetime
from typing import Any

from app.schemas.v1 import ORM


class JobOut(ORM):
    id: str
    kind: str
    status: str                       # queued | running | done | failed
    progress: int                     # 0–100
    message: str | None
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
