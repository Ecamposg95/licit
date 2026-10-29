from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import ROLE_LABELS, permissions_for
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES, account_expired_error, create_access_token, get_current_user, is_expired,
    verify_password,
)
from app.models import Organization, User
from app.schemas.v1 import Me, Meta, Token
from app.services import audit

router = APIRouter(prefix="/api/v1", tags=["identidad"])


@router.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == form.username.strip().lower())).first()
    if not user or not user.is_active or not verify_password(form.password, user.hashed_password):
        raise AppError(401, "invalid_credentials", "Correo o contraseña incorrectos")
    # Después de verificar la contraseña: con credenciales erróneas no se revela que la cuenta venció.
    if is_expired(user):
        raise account_expired_error()
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action="auth.login",
                 resource_type="user", resource_id=user.id)
    db.commit()
    return Token(access_token=create_access_token(user.id), expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.get("/auth/me", response_model=Me)
def me(user: User = Depends(get_current_user)):
    return Me(
        id=user.id, email=user.email, full_name=user.full_name, is_active=user.is_active,
        role_names=user.role_names, organization_id=user.organization_id,
        permissions=sorted(p.value for p in permissions_for(user.role_names)),
    )


@router.get("/meta", response_model=Meta)
def meta(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id)
    return Meta(
        organization=org.name, demo_mode=org.demo_mode, demo_base_date=config.DEMO_BASE_DATE,
        watermark=config.WATERMARK, display_timezone=config.DISPLAY_TIMEZONE,
        freshness_ttl_hours=config.FRESHNESS_TTL_HOURS, server_time=datetime.now(timezone.utc),
        roles={r.value: label for r, label in ROLE_LABELS.items()},
    )
