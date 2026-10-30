"""Alembic: usa el mismo DATABASE_URL y metadata que la app."""
from logging.config import fileConfig

from alembic import context

import app.models  # noqa: F401  registra todas las tablas
from app.core.database import SQLALCHEMY_DATABASE_URL, Base, engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Tablas del scaffold anterior que quedaron renombradas en producción; no son del modelo y no se tocan.
LEGACY_PREFIX = "legacy_scaffold_"


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table" and name.startswith(LEGACY_PREFIX):
        return False
    if type_ in ("index", "unique_constraint", "foreign_key_constraint") and obj.table.name.startswith(LEGACY_PREFIX):
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(url=SQLALCHEMY_DATABASE_URL, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"},
                      render_as_batch=True, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        # render_as_batch: ALTERs compatibles con SQLite (tests/local).
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True,
                          include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
