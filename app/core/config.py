"""Configuración por entorno. Ningún secreto vive en el repositorio."""
import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "si", "sí"}


DEMO_MODE = _bool("DEMO_MODE", True)
# Fecha base de los escenarios SYNTHETIC. Nunca altera la vigencia de datos REAL/HISTORICAL.
DEMO_BASE_DATE = date.fromisoformat(os.getenv("DEMO_BASE_DATE", "2026-10-28"))
# Tiempo tras el cual una verificación de fuente se considera desactualizada.
FRESHNESS_TTL_HOURS = int(os.getenv("FRESHNESS_TTL_HOURS", "24"))
DISPLAY_TIMEZONE = os.getenv("DISPLAY_TIMEZONE", "America/Mexico_City")

ORGANIZATION_NAME = os.getenv("ORGANIZATION_NAME", "Dipromedic · Demo")

# Contraseña de los usuarios demo (@dipromedic.example). Si no se define, no se crean.
DEMO_USER_PASSWORD = os.getenv("DEMO_USER_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

WATERMARK = "DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN"
FICTITIOUS_REGISTRY = "DEMO-SIN-VALIDEZ"
