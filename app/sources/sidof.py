"""Adaptador de SIDOF (Diario Oficial de la Federación): búsqueda por palabra y lectura de notas.

- Búsqueda: `POST /busqueda/CargaNotasAvanzadas/` [OBSERVADO]. La usa el propio sitio, pero no está documentada.
- Nota: `GET /dof/sidof/notas/nota/{codNota}` [OFICIAL, datos abiertos], JSON con el HTML en `Nota.cadenaContenido`.

Reglas (docs/research/fuentes-licitaciones.md §1.3, §1.9): una petición a la vez y al menos 1 s entre peticiones;
10 s para conectar y 20 s para leer; 2 reintentos (1 s y luego 3 s) solo ante error de red, tiempo agotado o 5xx;
un 4xx no se reintenta. Una respuesta sin `messageCode` es «cero sin confirmar» y nunca «no hay licitaciones».
Sus campos `URL`/`BODY` (de un backend interno) no se guardan ni se registran.

Cada cliente lleva su propio estado de ritmo; no hay estado global entre instancias.
"""
import hashlib
import json
import re
import time
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Callable

import httpx

from app.core.netguard import USER_AGENT
from app.sources.base import NoteDetail, NoteHit, ProcedureParsed, SearchPage, SourceUnavailable
from app.sources.dates_es import has_explicit_mx_timezone, normalize_text, parse_spanish_datetime

SOURCE_KEY = "dof_sidof"
BASE_URL = "https://sidof.segob.gob.mx"
SEARCH_PATH = "/busqueda/CargaNotasAvanzadas/"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)
RETRY_WAITS = (1.0, 3.0)
MAX_BYTES = 5_000_000
CV_PREFIX = "CONVOCATORIAS PARA CONCURSOS DE ADQUISICIONES"

_COD_NOTA = re.compile(r"^\d{1,12}$")


def note_url(cod_nota: str | int) -> str:
    """URL pública de la nota oficial (la que se cita y enlaza)."""
    return f"{BASE_URL}/notas/docFuente/{cod_nota}"


_NOTE_URL = re.compile(r"^/(?:notas/docFuente|notas|dof/sidof/notas/nota)/(\d{1,12})/?$")


def cod_nota_from_url(url: str) -> str | None:
    """Código de nota si la URL es de una nota de SIDOF (docFuente, /notas/{id} o el servicio JSON)."""
    try:
        parsed = httpx.URL(url)
    except Exception:
        return None
    if parsed.scheme != "https" or parsed.host != "sidof.segob.gob.mx":
        return None
    m = _NOTE_URL.match(parsed.path)
    return m.group(1) if m else None


def search_form(term: str, date_from: date, date_to: date, start: int = 0, length: int = 100,
                mode: str = "Y") -> dict[str, str]:
    """Cuerpo del POST tal como lo arma `/assets/js/busqueda2.js` (investigación §1.3)."""
    return {
        "draw": "1",
        "columns[0][data]": "fecha",
        "columns[1][data]": "titulo",
        "columns[2][data]": "codOrgaUno",
        "columns[3][data]": "codOrgaDos",
        "order[0][column]": "0",
        "order[0][dir]": "desc",
        "start": str(start),
        "length": str(length),
        "tipoBus": "C",                     # C = contenido
        "textoBus": term,
        "fechaIni": date_from.strftime("%d-%m-%Y"),
        "fechaFin": date_to.strftime("%d-%m-%Y"),
        "idOrg": "TODOS",                   # obligatorio: con "" devuelve 0 siempre
        "codNotas": "",
        "sinonimos": "false",
        "tipoTexto": mode,                  # Y = todas las palabras; F = frase exacta; O = alguna
    }


def _parse_date(raw) -> date | None:
    if not isinstance(raw, str):
        return None
    for fmt in ("%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _json(content: bytes, what: str):
    try:
        return json.loads(content)
    except ValueError:
        raise SourceUnavailable(SOURCE_KEY, f"La {what} no devolvió JSON válido", retryable=True) from None


def parse_search_response(data) -> SearchPage:
    if not isinstance(data, dict):
        raise SourceUnavailable(SOURCE_KEY, "La búsqueda devolvió una estructura inesperada", retryable=True)
    if "messageCode" not in data:
        # Respuesta ambigua: puede ser cero resultados o un error. No se conserva nada de ella.
        return SearchPage(hits=[], total=None, confirmed=False)
    if data.get("messageCode") != 200:
        raise SourceUnavailable(SOURCE_KEY, f"La búsqueda respondió messageCode {data.get('messageCode')!r}",
                                retryable=True)
    notes = data.get("Notas") or []
    if not isinstance(notes, list):
        raise SourceUnavailable(SOURCE_KEY, "La búsqueda devolvió «Notas» con un formato inesperado", retryable=True)
    hits = []
    for n in notes:
        if not isinstance(n, dict) or not _COD_NOTA.match(str(n.get("codNota", ""))):
            continue
        cod = str(n["codNota"])
        hits.append(NoteHit(cod_nota=cod, title=str(n.get("titulo") or "").strip(),
                            published_on=_parse_date(n.get("fecha")),
                            organism=(n.get("codOrgaUno") or None), url=note_url(cod)))
    total = data.get("totalRegistros")
    return SearchPage(hits=hits, total=total if isinstance(total, int) else None, confirmed=True)


def parse_note_response(data, cod_nota: str, fetched_at: datetime) -> NoteDetail:
    if not isinstance(data, dict) or data.get("messageCode") != 200 or not isinstance(data.get("Nota"), dict):
        code = data.get("messageCode") if isinstance(data, dict) else None
        raise SourceUnavailable(SOURCE_KEY, f"La nota {cod_nota} no se pudo leer (messageCode {code!r})",
                                retryable=True)
    nota = data["Nota"]
    html = nota.get("cadenaContenido")
    if not isinstance(html, str) or not html.strip():
        reason = "es demasiado grande para el servicio" if data.get("tamanioExcesivo") else "no trae contenido"
        raise SourceUnavailable(SOURCE_KEY, f"La nota {cod_nota} {reason}", retryable=False)
    return NoteDetail(
        cod_nota=cod_nota, html=html, sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
        fetched_at=fetched_at, url=note_url(cod_nota), title=(nota.get("titulo") or None),
        published_on=_parse_date(nota.get("fecha")), organism=(nota.get("codOrgaUno") or None),
    )


class SidofClient:
    def __init__(self, http: httpx.Client | None = None, *, rate_limit_s: float = 1.0,
                 clock: Callable[[], float] | None = None, sleep: Callable[[float], None] | None = None,
                 retry_waits: tuple[float, ...] = RETRY_WAITS, max_bytes: int = MAX_BYTES):
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=TIMEOUT, follow_redirects=False)
        self._rate_limit_s = rate_limit_s
        self._clock = clock or time.monotonic
        self._sleep_fn = sleep               # None → time.sleep, resuelto en cada espera
        self._retry_waits = retry_waits
        self._max_bytes = max_bytes
        self._last_done: float | None = None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _sleep(self, seconds: float) -> None:
        (self._sleep_fn or time.sleep)(seconds)

    def _throttle(self) -> None:
        if self._last_done is None:
            return
        wait = self._rate_limit_s - (self._clock() - self._last_done)
        if wait > 0:
            self._sleep(wait)

    def _send_once(self, method: str, path: str, data: dict | None) -> tuple[int, bytes]:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.8"}
        if data is not None:
            headers["X-Requested-With"] = "XMLHttpRequest"
        request = self._http.build_request(method, BASE_URL + path, data=data, headers=headers, timeout=TIMEOUT)
        response = self._http.send(request, stream=True, follow_redirects=False)
        try:
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > self._max_bytes:
                    raise SourceUnavailable(SOURCE_KEY, f"La respuesta supera {self._max_bytes} bytes",
                                            retryable=False)
            return response.status_code, bytes(body)
        finally:
            response.close()

    def _request(self, method: str, path: str, data: dict | None = None) -> bytes:
        attempts = len(self._retry_waits) + 1
        reason = "sin respuesta"
        for attempt in range(attempts):
            self._throttle()
            try:
                status, body = self._send_once(method, path, data)
            except httpx.TimeoutException as exc:
                reason = f"tiempo de espera agotado ({type(exc).__name__})"
            except httpx.TransportError as exc:
                reason = f"error de red ({type(exc).__name__})"
            else:
                if 200 <= status < 300:
                    return body
                if status >= 500:
                    reason = f"HTTP {status}"
                else:
                    raise SourceUnavailable(SOURCE_KEY, f"HTTP {status}", retryable=False)
            finally:
                self._last_done = self._clock()
            if attempt < attempts - 1:
                self._sleep(self._retry_waits[attempt])
        raise SourceUnavailable(SOURCE_KEY, f"{reason} tras {attempts} intentos", retryable=True)

    def search(self, term: str, date_from: date, date_to: date, start: int = 0, length: int = 100,
               *, mode: str = "Y") -> SearchPage:
        body = self._request("POST", SEARCH_PATH, search_form(term, date_from, date_to, start, length, mode))
        return parse_search_response(_json(body, "búsqueda"))

    def get_note(self, cod_nota: str) -> NoteDetail:
        cod_nota = str(cod_nota).strip()
        if not _COD_NOTA.match(cod_nota):
            raise ValueError(f"Código de nota inválido: {cod_nota!r}")
        body = self._request("GET", f"/dof/sidof/notas/nota/{cod_nota}")
        return parse_note_response(_json(body, "nota"), cod_nota, datetime.now(timezone.utc))


# ── Parser de notas ──────────────────────────────────────────────────────────

# Número de procedimiento de Compras MX: LA-50-GYR-050GYR010-T-104-2026, LA-64-072-905038959-N-57-2026…
PROCEDURE_RE = re.compile(r"\b(?:L|I|A)[AOS]-\d{2,3}-[0-9A-Z]{2,4}-[0-9A-Z]{4,12}-[A-Z]-\d{1,5}-(?:19|20)\d{2}\b")
_EXPEDIENTE_RE = re.compile(r"\bE-(?:19|20)\d{2}-\d{6,10}\b")
_PROCEDURE_TYPES = {"L": "licitacion_publica", "I": "invitacion_3", "A": "adjudicacion_directa"}
_CHARACTER_CODES = {"N": "nacional", "T": "internacional_tlc", "I": "internacional_abierta"}

# Siglas oficiales de los convocantes más frecuentes (se muestran tal cual las usan las propias instituciones).
_BUYER_ACRONYMS = [
    ("seguro social para el bienestar", "IMSS-Bienestar"),
    ("instituto mexicano del seguro social", "IMSS"),
    ("instituto de seguridad y servicios sociales de los trabajadores del estado", "ISSSTE"),
]

# Entidades federativas con los mismos nombres que usa la UI (labels.ts · MX_STATES).
_STATES = [
    ("baja california sur", "Baja California Sur"), ("baja california", "Baja California"),
    ("estado de mexico", "Estado de México"), ("edo. mex", "Estado de México"), ("edo. de mex", "Estado de México"),
    ("ciudad de mexico", "Ciudad de México"), ("cdmx", "Ciudad de México"),
    ("aguascalientes", "Aguascalientes"), ("campeche", "Campeche"), ("chiapas", "Chiapas"),
    ("chihuahua", "Chihuahua"), ("coahuila", "Coahuila"), ("colima", "Colima"), ("durango", "Durango"),
    ("guanajuato", "Guanajuato"), ("jalisco", "Jalisco"), ("michoacan", "Michoacán"), ("nayarit", "Nayarit"),
    ("nuevo leon", "Nuevo León"), ("oaxaca", "Oaxaca"), ("puebla", "Puebla"), ("queretaro", "Querétaro"),
    ("quintana roo", "Quintana Roo"), ("san luis potosi", "San Luis Potosí"), ("sinaloa", "Sinaloa"),
    ("sonora", "Sonora"), ("tabasco", "Tabasco"), ("tamaulipas", "Tamaulipas"), ("tlaxcala", "Tlaxcala"),
    ("veracruz", "Veracruz"), ("yucatan", "Yucatán"), ("zacatecas", "Zacatecas"),
]
# Nombres que también son apellidos o calles: solo cuentan con contexto («ESTATAL GUERRERO», «ESTADO DE HIDALGO»).
_STATES_WITH_CONTEXT = [("guerrero", "Guerrero"), ("hidalgo", "Hidalgo"), ("morelos", "Morelos")]
_STATE_CONTEXT = r"(?:estatal|regional|estado de|salud de|salud en|gobierno de|delegacion|ooad)\s+"

_EMPTY_VALUES = {"", "-", "--", "n/a", "na", "no aplica", "no", "ninguno", "ninguna"}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _strip_quotes(text: str) -> str:
    return text.strip(" \"'“”«»").strip()


class _NoteHTML(HTMLParser):
    """Recorre el HTML tolerando etiquetas sin cerrar y entidades rotas.

    Produce, en orden, párrafos fuera de tablas (`("p", align, texto)`) y tablas (`("table", filas)`), donde cada
    fila es una lista de textos de celda.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[tuple] = []
        self._tables: list[dict] = []
        self._p: dict | None = None

    # párrafos
    def _flush_p(self):
        if self._p is not None:
            text = _clean("".join(self._p["buf"]))
            if text:
                self.items.append(("p", self._p["align"], text))
            self._p = None

    # tablas
    def _close_cell(self, t):
        if t["cell"] is not None:
            if t["row"] is None:
                t["row"] = []
            t["row"].append(_clean("".join(t["cell"])))
            t["cell"] = None

    def _close_row(self, t):
        self._close_cell(t)
        if t["row"]:
            if any(t["row"]):
                t["rows"].append(t["row"])
        t["row"] = None

    def _close_table(self):
        t = self._tables.pop()
        self._close_row(t)
        if t["rows"]:
            self.items.append(("table", t["rows"]))

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self._flush_p()
            self._tables.append({"rows": [], "row": None, "cell": None})
            return
        if self._tables:
            t = self._tables[-1]
            if tag == "tr":
                self._close_row(t)
                t["row"] = []
            elif tag in ("td", "th"):
                self._close_cell(t)
                if t["row"] is None:
                    t["row"] = []
                t["cell"] = []
            elif tag in ("p", "br", "div", "li") and t["cell"] is not None:
                t["cell"].append(" ")
            return
        if tag == "p":
            self._flush_p()
            self._p = {"align": (dict(attrs).get("align") or "").lower(), "buf": []}
        elif tag in ("br", "div", "li") and self._p is not None:
            self._p["buf"].append(" ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "table":
            if self._tables:
                self._close_table()
            return
        if self._tables:
            t = self._tables[-1]
            if tag == "tr":
                self._close_row(t)
            elif tag in ("td", "th"):
                self._close_cell(t)
            return
        if tag == "p":
            self._flush_p()

    def handle_data(self, data):
        if self._tables:
            t = self._tables[-1]
            if t["cell"] is not None:
                t["cell"].append(data)
            return
        if self._p is None:
            self._p = {"align": "", "buf": []}
        self._p["buf"].append(data)

    def finish(self) -> list[tuple]:
        self.close()
        while self._tables:
            self._close_table()
        self._flush_p()
        return self.items


def _read_html(html: str) -> list[tuple]:
    parser = _NoteHTML()
    try:
        parser.feed(html or "")
    except Exception:                      # HTMLParser es tolerante; esto es solo una red de seguridad
        pass
    try:
        return parser.finish()
    except Exception:
        return parser.items


def _field_for(label: str) -> str | None:
    """Campo al que corresponde una etiqueta de la tabla (variantes de la investigación §1.4)."""
    n = normalize_text(PROCEDURE_RE.sub(" ", label.upper()))
    n = _clean(n)
    if not n:
        return None
    if "ganador" in n:
        return "winner"
    if "adjudicad" in n:
        return "awarded"
    if "fallo" in n:
        return "ruling"
    if "aclaraciones" in n:
        return "questions"
    if "presentacion" in n or "apertura" in n:
        return "submission"
    if "publicacion" in n:
        return "published"
    if "visita" in n:
        return "visit"
    if "volumen" in n or n.startswith("monto") or "monto minimo" in n or "monto maximo" in n:
        return "volume"
    if "descripcion" in n or "objeto" in n:
        return "title"
    if re.match(r"^(no\.?|num\.?|numero|nro\.?)\s*(de\s+)?(la\s+)?(licitacion|procedimiento)", n):
        return "number"
    if "caracter" in n or n == "tipo" or n.startswith("tipo "):
        return "character"
    return None


def _character(text: str | None) -> str | None:
    if not text:
        return None
    n = normalize_text(text)
    if "tratado" in n:
        return "internacional_tlc"
    if "internacional" in n and "abierta" in n:
        return "internacional_abierta"
    if re.search(r"(?<!inter)nacional", n):
        return "nacional"
    return None


def _value(text: str | None) -> str | None:
    if text is None:
        return None
    text = _clean(text)
    return None if normalize_text(text).strip(" .") in _EMPTY_VALUES else text


class _Block:
    def __init__(self, number: str):
        self.number = number
        self.fields: dict[str, str] = {}
        self.lines: list[str] = []

    def add(self, field: str | None, label: str, value: str | None):
        value = _value(value)
        if field and value and field not in self.fields:
            self.fields[field] = value
        line = f"{label}: {value}" if label and value and label != value else (value or label or "")
        if line:
            self.lines.append(line)


def _table_blocks(rows: list[list[str]]) -> tuple[list[_Block], list[str]]:
    """Procedimientos de una tabla y, si no trae ninguno, sus líneas sueltas (p. ej. la tabla del ganador)."""
    header = rows[0]
    header_fields = [_field_for(c) for c in header]
    has_numbers = any(PROCEDURE_RE.search(" ".join(r)) for r in rows)
    # Tabla en columnas: la primera fila son etiquetas cortas y los procedimientos van en filas (avisos de fallo).
    columnar = (len(rows) >= 2 and len(header) >= 2 and not PROCEDURE_RE.search(" ".join(header))
                and sum(f is not None for f in header_fields) >= 2 and all(len(c) <= 80 for c in header)
                and ("number" in header_fields or not has_numbers))
    blocks: list[_Block] = []
    loose: list[str] = []
    if columnar:
        for row in rows[1:]:
            numbers = PROCEDURE_RE.findall(" ".join(row))
            if not numbers:
                loose.append(" · ".join(c for c in row if c))
                continue
            block = _Block(numbers[0])
            for i, cell in enumerate(row):
                label = header[i] if i < len(header) else ""
                block.add(header_fields[i] if i < len(header_fields) else None, label, cell)
            blocks.append(block)
        if not blocks:
            loose = [" · ".join(f"{h}: {c}" for h, c in zip(header, row) if c) for row in rows[1:]]
        return blocks, [line for line in loose if line]

    current: _Block | None = None
    pending: list[tuple[str | None, str, str | None]] = []
    for row in rows:
        if len(row) >= 2:
            label, value = row[0], " ".join(c for c in row[1:] if c)
        else:
            text = row[0]
            m = re.match(r"^([^:\d]{2,80}):\s*(.+)$", text)
            label, value = (m.group(1), m.group(2)) if m else (text, text)
        numbers = PROCEDURE_RE.findall(f"{label} {value}")
        if numbers and (current is None or numbers[0] != current.number):
            current = _Block(numbers[0])
            blocks.append(current)
            for item in pending:              # filas antes del número: pertenecen al primer procedimiento
                current.add(*item)
            pending = []
        field = _field_for(label)
        if field == "number":
            value_for_field = None            # el número ya es el identificador del bloque
        else:
            value_for_field = PROCEDURE_RE.sub("", value).strip() if numbers and field else value
        line_label = _clean(PROCEDURE_RE.sub("", label)) if numbers else label
        item = (field, line_label, value_for_field if field != "number" else value)
        if current is None:
            pending.append(item)
        else:
            current.add(*item)
        if numbers and current is not None:
            exp = _EXPEDIENTE_RE.search(f"{label} {value}")
            if exp:
                current.fields.setdefault("expediente", exp.group(0))
            char = _character(label) if "caracter" in normalize_text(label) else None
            if char:
                current.fields.setdefault("character_text", label)
    if not blocks:
        loose = [f"{lbl}: {val}" if lbl and val and lbl != val else (val or lbl or "") for _f, lbl, val in pending]
    return blocks, [line for line in loose if line]


def _header(items: list[tuple]) -> tuple[list[str], str]:
    """Líneas centradas del encabezado (convocante y unidad) y el tipo de aviso."""
    lines: list[str] = []
    notice = "aviso"
    for item in items:
        if item[0] == "table":
            break
        _, align, text = item
        n = normalize_text(text)
        heading = align == "center" or len(n) <= 120      # un párrafo largo puede mencionar «fallo» de pasada
        if heading and re.search(r"\bfallos?\b", n):
            notice = "fallo"
            continue
        if heading and "convocatoria" in n:
            notice = "convocatoria" if notice == "aviso" else notice
            continue
        if align == "center" and len(text) <= 200:
            lines.append(text)
    return lines, notice


def _buyer(lines: list[str]) -> tuple[str | None, str | None]:
    if not lines:
        return None, None
    first = lines[0]
    n = normalize_text(first)
    buyer = next((acr for key, acr in _BUYER_ACRONYMS if key in n), first)
    unit = " · ".join(lines[1:]) or None
    return buyer[:255], (unit[:255] if unit else None)


def _state(lines: list[str]) -> str | None:
    text = " " + normalize_text(" ".join(lines)) + " "
    for key, name in _STATES:
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", text):
            return name
    for key, name in _STATES_WITH_CONTEXT:
        if re.search(rf"{_STATE_CONTEXT}{key}(?![a-z])", text):
            return name
    return None


def _build(block: _Block, buyer: str | None, unit: str | None, state: str | None, notice: str) -> ProcedureParsed:
    f = block.fields
    dates: dict[str, tuple[datetime | None, str]] = {}
    for key in ("published", "questions", "submission", "ruling"):
        dates[key] = parse_spanish_datetime(f.get(key) or "")
    any_date = any(dt is not None for dt, _ in dates.values())
    explicit = any(has_explicit_mx_timezone(f.get(k) or "") for k in dates)
    code = block.number.split("-")
    character = _character(f.get("character")) or _character(f.get("character_text")) \
        or _CHARACTER_CODES.get(code[-3] if len(code) >= 3 else "")
    submission_at, submission_precision = dates["submission"]
    title = _value(_strip_quotes(f["title"])) if f.get("title") else None
    return ProcedureParsed(
        external_id=block.number,
        buyer=buyer,
        title=title[:500] if title else None,
        state=state,
        volume=f.get("volume"),
        published_at=dates["published"][0],
        questions_at=dates["questions"][0],
        submission_at=submission_at,
        ruling_at=dates["ruling"][0],
        submission_precision=submission_precision if submission_at else "datetime",
        timezone_assumed=any_date and not explicit,
        excerpt=" | ".join(block.lines),
        buying_unit=unit,
        procedure_type=_PROCEDURE_TYPES.get(block.number[0]),
        character=character,
        notice=notice,
        expediente=f.get("expediente"),
    )


def parse_procedures(html: str) -> list[ProcedureParsed]:
    """Procedimientos de una nota, uno por número encontrado en sus tablas.

    Nunca lanza excepción ni inventa: si un campo no aparece queda en None. Los números que solo aparecen en la
    prosa no crean procedimientos (en las notas reales a veces repiten el número con una letra distinta).
    """
    items = _read_html(html)
    lines, notice = _header(items)
    buyer, unit = _buyer(lines)
    state = _state(lines)
    blocks: list[_Block] = []
    for item in items:
        if item[0] != "table":
            continue
        found, loose = _table_blocks(item[1])
        if found:
            blocks.extend(found)
        elif blocks and loose:              # p. ej. la tabla del ganador que sigue a su procedimiento
            blocks[-1].lines.extend(loose)
    if any("winner" in b.fields for b in blocks):
        notice = "fallo"
    elif notice == "aviso" and any("submission" in b.fields for b in blocks):
        notice = "convocatoria"
    merged: dict[str, _Block] = {}
    for b in blocks:
        key = re.sub(r"[^0-9A-Z]", "", b.number)
        if key in merged:                   # el mismo número dos veces: se completan los campos que falten
            for k, v in b.fields.items():
                merged[key].fields.setdefault(k, v)
            merged[key].lines.extend(b.lines)
        else:
            merged[key] = b
    return [_build(b, buyer, unit, state, notice) for b in merged.values()]
