"""Búsquedas guardadas por usuario (T17)."""
from sqlalchemy import JSON, Column, ForeignKey, String, UniqueConstraint

from app.core.database import Base
from app.models.base import OrgScoped


class SavedSearch(OrgScoped, Base):
    __tablename__ = "saved_searches"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    terms = Column(JSON, nullable=False, default=list)
    states = Column(JSON, nullable=False, default=list)
    families = Column(JSON, nullable=False, default=list)
    buyers = Column(JSON, nullable=False, default=list)
