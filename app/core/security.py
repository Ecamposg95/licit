"""JWT, hashing y usuario autenticado."""
import os
import warnings
from datetime import datetime, timedelta, timezone

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError

_DEFAULT_SECRET = "licit_secret_key_change_me_in_prod"
SECRET_KEY = os.getenv("SESSION_SECRET") or os.getenv("SECRET_KEY") or _DEFAULT_SECRET
if SECRET_KEY == _DEFAULT_SECRET:
    warnings.warn(
        "SESSION_SECRET no configurada — usando valor por defecto. "
        "Establece la variable de entorno SESSION_SECRET en producción.",
        stacklevel=1,
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", str(60 * 8)))

# BCRYPT_ROUNDS sólo se baja en pruebas; producción usa el default (12).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto",
                           bcrypt__rounds=int(os.getenv("BCRYPT_ROUNDS", "12")))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def is_expired(user, now: datetime | None = None) -> bool:
    """¿Venció la cuenta demo? `expires_at` nulo = no vence. SQLite devuelve la fecha sin zona (se guardó en UTC)."""
    expires_at = user.expires_at
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= (now or datetime.now(timezone.utc))


def account_expired_error() -> AppError:
    return AppError(401, "account_expired", "Esta cuenta de demostración venció. Pide a Administración TI que la renueve.")


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.models import User

    unauthorized = AppError(401, "unauthorized", "Sesión inválida o expirada")
    if not token:
        raise unauthorized
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise unauthorized
    user = db.get(User, payload.get("sub") or "")
    if user is None or not user.is_active:
        raise unauthorized
    if is_expired(user):
        raise account_expired_error()
    return user
