"""Contratos del tablero «Hoy» (T17)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.sweep import SweepOut
from app.schemas.v1 import OpportunityRow, TaskOut, UserRef


class HoyKpis(BaseModel):
    new_24h: int
    unclassified: int
    unclassified_mine: int
    submitting_7d: int
    my_overdue_tasks: int


class HoySweep(BaseModel):
    last: SweepOut | None
    scheduled_pending: bool


class MatchedSearch(BaseModel):
    id: str
    name: str
    owner: UserRef | None


class HoyNewItem(OpportunityRow):
    is_new_since_visit: bool
    matched: list[MatchedSearch]
    mine: bool
    in_territory: bool


class KeyDate(BaseModel):
    opportunity: OpportunityRow
    kind: Literal["questions", "submission", "ruling"]
    at: datetime


class HoyOut(BaseModel):
    kpis: HoyKpis
    kpis_warning: str | None
    sweep: HoySweep
    new_items: list[HoyNewItem]
    unassigned: list[HoyNewItem]
    key_dates: list[KeyDate]
    my_tasks: list[TaskOut]
    scope: Literal["mine", "team"]
    last_visit: datetime | None


class HoyBadge(BaseModel):
    new: int
