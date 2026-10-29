from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import OrgScoped, new_id, utcnow


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=new_id)
    name = Column(String(255), nullable=False)
    demo_mode = Column(Boolean, nullable=False, default=True)
    branding = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class User(OrgScoped, Base):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    roles = relationship("UserRole", cascade="all, delete-orphan", lazy="selectin")

    @property
    def role_names(self) -> list[str]:
        return sorted(r.role for r in self.roles)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String(40), primary_key=True)
