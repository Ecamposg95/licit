"""Formato es-MX para los documentos generados: dinero, cantidades y fechas en America/Mexico_City.

Todo se calcula con `Decimal` a partir del texto guardado en la instantánea; nunca con `float`.
"""
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core import config

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]


def display_tz() -> ZoneInfo:
    return ZoneInfo(config.DISPLAY_TIMEZONE)


def money(value: str | Decimal | None, currency: str | None) -> str | None:
    """«60,000.00 MXN». None si falta el monto."""
    if value is None or value == "":
        return None
    text = format(Decimal(str(value)), ",.2f")
    return f"{text} {currency}" if currency else text


def quantity(value: str | Decimal | None) -> str | None:
    """«40.000» → «40»; «2.500» → «2.5»; con separador de miles."""
    if value is None or value == "":
        return None
    q = Decimal(str(value))
    if q == q.to_integral_value():
        return format(q, ",.0f")
    return format(q.normalize(), ",f")


def long_date(value: str | date | None) -> str | None:
    """«2026-10-28» → «28 de octubre de 2026». Una fecha de calendario no cambia de zona."""
    if not value:
        return None
    d = value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value)[:10])
    return f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"


def instant(value: str | None, precision: str = "datetime") -> str | None:
    """Instante ISO (UTC) en la zona de visualización. Con precisión `date` solo el día, sin hora."""
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(display_tz())
    text = long_date(local.date())
    if precision == "date":
        return text
    return f"{text}, {local:%H:%M} h"


def stamp(value: str | None) -> str:
    """Fecha y hora de generación para pies de página y README, p. ej. «29/10/2026 10:15 (hora de Ciudad de México)»."""
    if not value:
        return ""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return f"{dt.astimezone(display_tz()):%d/%m/%Y %H:%M} (hora de Ciudad de México)"


def pending(what: str) -> str:
    """Marcador visible de dato faltante."""
    return f"[PENDIENTE: {what}]"


# ── Texto seguro y etiquetas en español ──────────────────────────────────────

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def clean_text(value) -> str:
    """Quita los caracteres de control que XML (DOCX/XLSX) no admite; el resto del texto queda tal cual."""
    return "" if value is None else _CONTROL.sub("", str(value))


STATUS_LABEL = {
    "pendiente": "Pendiente", "desconocido": "Desconocido", "faltante": "Faltante", "vencido": "Vencido",
    "incumple": "Incumple", "en_revision": "En revisión", "cumple_validado": "Cumple · validado",
    "no_aplica_justificado": "No aplica · justificado",
}
REQ_TYPE_LABEL = {"tecnico": "Técnico", "documental": "Documental", "servicio": "Servicio",
                  "capacidad": "Capacidad", "administrativo": "Administrativo"}
SCOPE_LABEL = {"empresa": "Empresa", "producto": "Producto", "partida": "Partida", "servicio": "Servicio",
               "expediente": "Expediente"}
PROCEDURE_LABEL = {"licitacion_publica": "Licitación pública", "invitacion_3": "Invitación a cuando menos tres personas",
                   "adjudicacion_directa": "Adjudicación directa"}
CHARACTER_LABEL = {"nacional": "Nacional", "internacional_tlc": "Internacional bajo tratados",
                   "internacional_abierta": "Internacional abierta"}
DATA_KIND_LABEL = {"REAL": "REAL", "HISTORICAL": "HISTÓRICO", "SYNTHETIC": "SIMULADO · ficticio"}
PRICE_KIND_LABEL = {"REAL": "REAL", "HISTORICAL": "HISTÓRICO", "SYNTHETIC": "SIMULADO"}
DECISION_LABEL = {"pendiente": "Sin decisión registrada", "participar": "Participar", "no_participar": "No participar"}
EVIDENCE_DECISION_LABEL = {"propuesta": "propuesta, sin revisar", "aceptada": "aceptada", "rechazada": "rechazada"}
OPERATOR_LABEL = {"eq": "igual a", "gte": "mínimo", "lte": "máximo", "gt": "mayor que", "lt": "menor que"}


def label(mapping: dict, code: str | None, fallback: str | None = None) -> str:
    if not code:
        return fallback if fallback is not None else ""
    return mapping.get(code, code.replace("_", " "))
