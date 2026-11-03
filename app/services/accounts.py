"""Operación de cuentas (beta): rotar contraseña, retirar o devolver el acceso y fijar vencimiento.

Lo usa `scripts/cuentas.py`, que se corre en el contenedor; por eso el actor de la bitácora es nulo
(operación de TI fuera de la interfaz). Cada cambio queda auditado en la misma transacción y la
bitácora nunca guarda la contraseña ni su hash. Quien llama hace `commit`.

El estado activo y el vencimiento se revisan en cada petición (`get_current_user`): desactivar o
vencer una cuenta corta también las sesiones abiertas. Cambiar la contraseña no: el token ya
emitido sigue vigente hasta que expira; para cortarlas todas, rotar `SESSION_SECRET`.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import User
from app.services import audit
from app.services.demo_seed import DEMO_USERS

MIN_PASSWORD_LENGTH = 10


class AccountError(ValueError):
    """Operación de cuenta rechazada (correo desconocido, contraseña corta, fecha sin zona)."""


def _get(db: Session, email: str) -> User:
    user = db.scalars(select(User).where(User.email == email.strip().lower())).first()
    if user is None:
        raise AccountError(f"No existe la cuenta {email!r}")
    return user


def _record(db: Session, user: User, action: str, before: dict | None, after: dict) -> None:
    audit.record(db, organization_id=user.organization_id, actor_id=None, action=action,
                 resource_type="user", resource_id=user.id, before=before, after=after)


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres")


def list_accounts(db: Session) -> list[dict]:
    users = db.scalars(select(User).order_by(User.email)).all()
    return [{"email": u.email, "full_name": u.full_name, "roles": u.role_names, "is_active": u.is_active,
             "expires_at": u.expires_at.isoformat() if u.expires_at else None} for u in users]


def set_password(db: Session, email: str, password: str) -> None:
    _check_password(password)
    user = _get(db, email)
    user.hashed_password = get_password_hash(password)
    _record(db, user, "account.password_set", None, {"email": user.email})


def set_demo_password(db: Session, password: str) -> int:
    """Rota la contraseña de todas las cuentas demo que existan. Devuelve cuántas cambió."""
    _check_password(password)
    hashed = get_password_hash(password)
    changed = 0
    for email, _name, _roles in DEMO_USERS:
        user = db.scalars(select(User).where(User.email == email)).first()
        if user is None:
            continue
        user.hashed_password = hashed
        _record(db, user, "account.password_set", None, {"email": user.email})
        changed += 1
    return changed


def deactivate(db: Session, email: str) -> None:
    user = _get(db, email)
    before = {"is_active": user.is_active}
    user.is_active = False
    _record(db, user, "account.deactivated", before, {"is_active": False})


def activate(db: Session, email: str) -> None:
    user = _get(db, email)
    before = {"is_active": user.is_active}
    user.is_active = True
    _record(db, user, "account.activated", before, {"is_active": True})


def set_expiry(db: Session, email: str, expires_at: datetime | None) -> None:
    """Fija o quita (None) el vencimiento. La fecha debe llevar zona para no adivinar UTC u hora local."""
    if expires_at is not None and expires_at.tzinfo is None:
        raise AccountError("La fecha de vencimiento debe llevar zona horaria")
    user = _get(db, email)
    before = {"expires_at": user.expires_at.isoformat() if user.expires_at else None}
    user.expires_at = expires_at
    _record(db, user, "account.expiry_set", before,
            {"expires_at": expires_at.isoformat() if expires_at else None})
