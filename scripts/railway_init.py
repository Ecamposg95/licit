#!/usr/bin/env python3
"""Inicialización en cada deploy (idempotente).

1. create_all — tablas nuevas se crean solas al registrar el modelo en app/models/__init__.py.
2. MIGRACIONES — ALTERs incrementales para columnas nuevas en tablas existentes.
3. Seed del admin inicial desde ADMIN_EMAIL / ADMIN_PASSWORD.

No usamos Alembic: toda DDL incremental vive en MIGRACIONES.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models  # noqa: E402,F401
from sqlalchemy import inspect, text  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models.user import Role, User  # noqa: E402

# (tabla, columna, DDL). Se aplica solo si la columna no existe.
MIGRACIONES: list[tuple[str, str, str]] = []


def run_migrations() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, column, ddl in MIGRACIONES:
            if table not in insp.get_table_names():
                continue
            if column in {c["name"] for c in insp.get_columns(table)}:
                continue
            print(f"🔧 {table}.{column}")
            conn.execute(text(ddl))


def seed_admin() -> None:
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    if not email or not password:
        print("ℹ️  ADMIN_EMAIL/ADMIN_PASSWORD no definidas — sin seed de admin")
        return
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email.lower()).first():
            return
        db.add(User(
            email=email.lower(),
            full_name="Administrador",
            hashed_password=get_password_hash(password),
            role=Role.ADMIN.value,
        ))
        db.commit()
        print(f"✅ Admin creado: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    run_migrations()
    seed_admin()
    print("✅ DB lista")
