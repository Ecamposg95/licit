"""Contratos del barrido diario en SIDOF y de «Volver a barrer» (T17)."""
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.v1 import UserRef


class SweepAccepted(BaseModel):
    sweep_id: str
    job_id: str


class SweepOut(BaseModel):
    id: str
    day: date
    attempt: int
    trigger: str                    # daily | manual
    status: str                     # queued | running | done | partial | failed
    terms: list[str]
    dropped_terms: list[str]        # quedaron fuera por el tope de términos
    counts: dict[str, int]          # notes, procedures, new, updated, unchanged
    errors: list[dict]              # [{batch, term, code, message}]
    created_by: UserRef | None      # nulo = Sistema (barrido diario)
    started_at: datetime | None
    finished_at: datetime | None
