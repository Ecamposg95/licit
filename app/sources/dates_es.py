"""Fechas en español tal como las publica el DOF.

Formatos que conviven en las notas (investigación §1.4): «25 DE AGOSTO DE 2026 10:00 HRS.», «29/09/2026, 10:00 horas»,
«14 OCTUBRE DE 2026; 09:00 HORAS», «7 DE JULIO DEL 2026» y palabras o números partidos por espacios
(«sep tiembre», «09:0 0»). Ninguna nota trae zona horaria: se supone America/Mexico_City y quien llama registra
esa suposición (`timezone_assumed`). Todo se devuelve en UTC.
"""
import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MX = ZoneInfo("America/Mexico_City")

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
# Cada mes admite espacios entre sus letras («sep tiembre»).
_MONTH_RE = "|".join(r"\s?".join(name) for name in sorted(_MONTHS, key=len, reverse=True))

_TEXTUAL = re.compile(
    rf"(?<!\d)(?P<day>\d{{1,2}})\s*(?:[oº°]\.?)?\s*(?:de\s+)?(?P<month>{_MONTH_RE})(?![a-z])"
    r"\s*,?\s*(?:del?\s+)?(?:ano\s+)?(?P<year>\d{4})(?!\d)"
)
_NUMERIC = re.compile(
    r"(?<![\d/-])(?P<day>\d{1,2})\s*(?P<sep>[/-])\s*(?P<month>\d{1,2})\s*(?P=sep)\s*(?P<year>\d{4}|\d{2})(?![\d/-])"
)
_TIME = re.compile(
    r"(?<![\d/])(?P<h>\d{1,2})\s*:\s*(?P<m1>\d)\s*(?P<m2>\d)(?:\s*:\s*\d\s*\d)?"
    r"\s*(?P<ampm>[ap]\.?\s?m\.?(?![a-z]))?"
    r"|(?<![\d/:])(?P<h2>\d{1,2})\s*(?:horas|hrs?\.?)(?![a-z])"
)
_EXPLICIT_MX = re.compile(r"(hora|horario|tiempo) del centro|hora de la ciudad de mexico")

_TIME_WINDOW = 60          # caracteres después (o antes) de la fecha donde se busca la hora


def normalize_text(text: str) -> str:
    """Minúsculas, sin acentos y con espacios normales (para comparar, nunca para mostrar)."""
    text = unicodedata.normalize("NFKD", text.replace("\xa0", " "))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def _year(raw: str) -> int:
    year = int(raw)
    return year + 2000 if year < 100 else year


def _date_matches(text: str) -> list[tuple[int, int, int, int, int]]:
    """(inicio, fin, año, mes, día) de cada fecha candidata, en orden de aparición."""
    found = []
    for m in _TEXTUAL.finditer(text):
        month = _MONTHS[re.sub(r"\s", "", m["month"])]
        found.append((m.start(), m.end(), _year(m["year"]), month, int(m["day"])))
    for m in _NUMERIC.finditer(text):
        found.append((m.start(), m.end(), _year(m["year"]), int(m["month"]), int(m["day"])))
    return sorted(found)


def _parse_time(fragment: str, last: bool = False) -> tuple[int, int] | None:
    matches = list(_TIME.finditer(fragment))
    if last:
        matches.reverse()
    for m in matches:
        if m["h2"] is not None:
            hour, minute = int(m["h2"]), 0
        else:
            hour, minute = int(m["h"]), int(m["m1"] + m["m2"])
            ampm = (m["ampm"] or "").replace(".", "").replace(" ", "")
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
        return None                      # hora imposible: la fecha queda sin hora
    return None


def parse_spanish_datetime(text: str) -> tuple[datetime | None, str]:
    """Primera fecha válida del texto, en UTC, y su precisión: "datetime" o "date".

    Sin hora, la fecha es las 00:00 de Ciudad de México (convertidas a UTC) con precisión "date": esa hora no la
    publica la fuente. Si no hay ninguna fecha válida devuelve (None, "date").
    """
    if not text:
        return None, "date"
    norm = normalize_text(text)
    candidates = _date_matches(norm)
    for i, (start, end, year, month, day) in enumerate(candidates):
        if not 1990 <= year <= 2100:
            continue
        try:
            datetime(year, month, day)
        except ValueError:
            continue
        next_start = candidates[i + 1][0] if i + 1 < len(candidates) else len(norm)
        after = norm[end:min(end + _TIME_WINDOW, next_start)]
        before = norm[max(0, start - _TIME_WINDOW):start]
        hm = _parse_time(after) or _parse_time(before, last=True)
        if hm is None:
            local = datetime(year, month, day, 0, 0, tzinfo=MX)
            return local.astimezone(timezone.utc), "date"
        local = datetime(year, month, day, hm[0], hm[1], tzinfo=MX)
        return local.astimezone(timezone.utc), "datetime"
    return None, "date"


def has_explicit_mx_timezone(text: str) -> bool:
    """La nota dice expresamente «hora del centro» (o equivalente) junto a la fecha."""
    return bool(text) and bool(_EXPLICIT_MX.search(normalize_text(text)))
