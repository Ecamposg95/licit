"""Contratos de las búsquedas guardadas por persona (T17)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    terms: list[str] = Field(default_factory=list, max_length=10)
    states: list[str] = Field(default_factory=list, max_length=40)
    families: list[str] = Field(default_factory=list, max_length=40)
    buyers: list[str] = Field(default_factory=list, max_length=40)


class SavedSearchOut(SavedSearchIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
