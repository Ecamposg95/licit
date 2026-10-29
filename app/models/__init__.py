# Registrar aquí cada modelo: create_all en scripts/railway_init.py crea sus tablas.
from app.models.user import User, Role  # noqa: F401
from app.models.licitacion import (  # noqa: F401
    Caracter,
    EstatusLicitacion,
    Licitacion,
    TipoProcedimiento,
)
