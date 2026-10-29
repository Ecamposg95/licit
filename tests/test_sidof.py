"""Adaptador SIDOF (C2): peticiones, respuestas reales capturadas en C1, parser de notas y fechas en español.

Ninguna prueba toca la red: el cliente HTTP lleva un `httpx.MockTransport` que sirve los fixtures.
"""
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.sources.base import SourceUnavailable
from app.sources.dates_es import parse_spanish_datetime
from app.sources.sidof import USER_AGENT, SidofClient, parse_procedures

FIX = Path(__file__).parent / "fixtures" / "sidof"
MX = ZoneInfo("America/Mexico_City")


def fixture(name: str) -> bytes:
    return (FIX / name).read_bytes()


def note_html(name: str) -> str:
    return json.loads(fixture(name))["Nota"]["cadenaContenido"]


class FakeTime:
    """Reloj simulado: solo avanza cuando el cliente «duerme»."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def fixture_transport(seen: list | None = None, search: str = "search_osteosintesis_2026.json"):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/busqueda/CargaNotasAvanzadas/":
            return httpx.Response(200, content=fixture(search), headers={"Content-Type": "text/html"})
        if request.method == "GET" and path.startswith("/dof/sidof/notas/nota/"):
            name = f"nota_{path.rsplit('/', 1)[-1]}.json"
            if (FIX / name).exists():
                return httpx.Response(200, content=fixture(name))
        return httpx.Response(404, text="no encontrado")

    return httpx.MockTransport(handler)


def make_client(transport, fake: FakeTime | None = None) -> SidofClient:
    fake = fake or FakeTime()
    return SidofClient(httpx.Client(transport=transport), clock=fake.clock, sleep=fake.sleep)


def by_id(procs, external_id):
    return next(p for p in procs if p.external_id == external_id)


# ── Búsqueda ─────────────────────────────────────────────────────────────────

def test_search_posts_expected_form():
    seen: list[httpx.Request] = []
    client = make_client(fixture_transport(seen))
    client.search("osteosintesis", date(2026, 1, 1), date(2026, 10, 29))

    assert len(seen) == 1
    req = seen[0]
    assert str(req.url) == "https://sidof.segob.gob.mx/busqueda/CargaNotasAvanzadas/"
    form = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
    assert form["tipoBus"] == "C"
    assert form["idOrg"] == "TODOS"
    assert form["textoBus"] == "osteosintesis"
    assert form["fechaIni"] == "01-01-2026" and form["fechaFin"] == "29-10-2026"
    assert form["columns[0][data]"] == "fecha" and form["columns[3][data]"] == "codOrgaDos"
    assert form["start"] == "0" and form["length"] == "100"
    assert req.headers["User-Agent"] == USER_AGENT == "LicitDemo/1.0 (+contacto Atlas Technologies)"


def test_search_parses_hits():
    expected = json.loads(fixture("search_osteosintesis_2026.json"))["Notas"]
    page = make_client(fixture_transport()).search("osteosintesis", date(2026, 1, 1), date(2026, 10, 29))

    assert page.confirmed is True
    assert page.total == 79
    assert len(page.hits) == len(expected) == 79
    first = page.hits[0]
    assert first.cod_nota == "5801639"
    assert first.published_on == date(2026, 10, 20)
    assert first.title == "INSTITUTO MEXICANO DEL SEGURO SOCIAL - REF:581420"
    assert first.organism.startswith("CONVOCATORIAS PARA CONCURSOS DE ADQUISICIONES")
    assert first.url == "https://sidof.segob.gob.mx/notas/docFuente/5801639"


def test_zero_without_messagecode_is_unconfirmed():
    page = make_client(fixture_transport(search="search_zero.json")).search(
        "zzzxqv", date(2026, 1, 1), date(2026, 10, 29))
    assert page.hits == []
    assert page.confirmed is False
    assert page.total is None


def test_messagecode_other_than_200_is_source_unavailable():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"messageCode": 500, "response": "ERROR"}))
    with pytest.raises(SourceUnavailable) as exc:
        make_client(transport).search("osteosintesis", date(2026, 1, 1), date(2026, 10, 29))
    assert exc.value.source == "dof_sidof"


def test_non_json_response_is_source_unavailable():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, text="<html>Mantenimiento</html>"))
    with pytest.raises(SourceUnavailable) as exc:
        make_client(transport).search("osteosintesis", date(2026, 1, 1), date(2026, 10, 29))
    assert "JSON" in exc.value.reason


# ── Notas ────────────────────────────────────────────────────────────────────

def test_parse_note_5801639():
    note = make_client(fixture_transport()).get_note("5801639")
    assert note.cod_nota == "5801639"
    assert note.url == "https://sidof.segob.gob.mx/notas/docFuente/5801639"
    assert len(note.sha256) == 64 and note.fetched_at.tzinfo is not None
    assert "LA-50-GYR-050GYR010-T-104-2026" in note.html

    procs = parse_procedures(note.html)
    proc = by_id(procs, "LA-50-GYR-050GYR010-T-104-2026")
    assert proc.submission_at.astimezone(MX).date() == date(2026, 10, 21)
    assert proc.submission_at.astimezone(MX).hour == 9
    assert proc.submission_precision == "datetime"
    assert proc.timezone_assumed is True
    assert "IMSS" in proc.buyer
    assert proc.questions_at.astimezone(MX) == datetime(2026, 10, 14, 9, 0, tzinfo=MX)
    assert proc.published_at.astimezone(MX).date() == date(2026, 10, 8)
    assert proc.ruling_at is None                       # la nota no lo indica: no se inventa
    assert proc.title.startswith("ADQUISICION DE MATERIAL DE OSTEOSINTESIS Y ENDOPROTESIS")
    assert proc.state == "Durango"
    assert proc.character == "internacional_tlc"
    assert proc.procedure_type == "licitacion_publica"
    assert proc.volume == "MAXIMO: 3,146 BIENES MINIMO: 1,259 BIENES"
    assert proc.notice == "convocatoria"
    assert "LA-50-GYR-050GYR010-T-104-2026" in proc.excerpt
    assert len(procs) == 1


def test_parse_note_5797331_repeated_number_in_prose_is_one_procedure():
    procs = parse_procedures(note_html("nota_5797331.json"))
    assert [p.external_id for p in procs] == ["LA-50-GYR-050GYR075-I-134-2026"]
    proc = procs[0]
    assert proc.submission_at == datetime(2026, 9, 2, 16, 0, tzinfo=timezone.utc)   # 10:00 en CDMX
    assert proc.state == "Querétaro"
    assert proc.character == "internacional_abierta"


def test_parse_tolerates_mangled_note():
    html = note_html("nota_mangled.json")
    procs = parse_procedures(html)                       # no lanza excepción
    assert len(procs) == 1
    proc = procs[0]
    assert proc.external_id == "LA-50-GYR-050GYR010-T-104-2026"
    assert proc.published_at is None and proc.questions_at is None
    assert proc.submission_at is None and proc.ruling_at is None
    assert proc.timezone_assumed is False                # sin fechas no se supuso ninguna zona
    assert "IMSS" in proc.buyer


def test_parse_garbage_returns_empty_list():
    assert parse_procedures("") == []
    assert parse_procedures("<table><tr><td>&#xZZ; sin número</td></tr>") == []
    assert parse_procedures("<<<>>>&&&;;; <td></tr></table></p>") == []


def test_multi_procedure_note_splits_by_table_and_ignores_prose_numbers():
    procs = parse_procedures(note_html("nota_5800141.json"))
    ids = [p.external_id for p in procs]
    assert len(ids) == 15 == len(set(ids))
    # La prosa repite «LA-50-GYR-050GYR028-N-102-2026» con otra letra; solo cuenta la tabla.
    assert "LA-50-GYR-050GYR028-T-102-2026" in ids and "LA-50-GYR-050GYR028-N-102-2026" not in ids
    osteo = by_id(procs, "LA-50-GYR-050GYR028-T-111-2026")
    assert "OSTEOSINTESIS" in osteo.title
    assert osteo.state == "Estado de México"            # del encabezado, no del lugar de firma (CDMX)
    assert sum("OSTEOSINTESIS" in (p.title or "") for p in procs) == 1


def test_number_inside_label_cell_and_numeric_dates():
    proc = parse_procedures(note_html("nota_5800121.json"))[0]
    assert proc.external_id == "LA-64-072-905038959-N-57-2026"
    assert proc.title.startswith("SERVICIO INTEGRAL DE OSTEOSINTESIS Y ENDOPROTESIS")  # sin comillas decorativas
    assert proc.submission_at.astimezone(MX) == datetime(2026, 10, 16, 14, 0, tzinfo=MX)
    assert proc.ruling_at.astimezone(MX) == datetime(2026, 10, 22, 14, 15, tzinfo=MX)
    assert proc.questions_at.astimezone(MX) == datetime(2026, 10, 9, 13, 0, tzinfo=MX)
    assert proc.character == "nacional"
    assert proc.expediente == "E-2026-00097699"
    assert "COAHUILA" in proc.buyer and proc.state == "Coahuila"


def test_fallo_note_with_column_tables():
    procs = parse_procedures(note_html("nota_5799326.json"))
    assert [p.external_id for p in procs] == ["LA-50-GYR-050GYR069-T-82-2026", "LA-50-GYR-050GYR069-T-92-2026"]
    fallo = procs[0]
    assert fallo.notice == "fallo"
    assert fallo.submission_at is None
    assert fallo.ruling_at.astimezone(MX) == datetime(2026, 7, 7, 0, 0, tzinfo=MX)
    assert "OSTEOSINTESIS" in fallo.title
    assert "EXORTA" in fallo.excerpt                    # la tabla del ganador acompaña su procedimiento
    assert fallo.state == "Campeche"


def test_header_variants_seen_in_live_run():
    """Casos de la corrida real: «Distrito Federal» en el encabezado y comillas tipográficas dobles."""
    html = ('<p align="center">INSTITUTO MEXICANO DEL SEGURO SOCIAL</p>'
            '<p align="center">ORGANO DE OPERACION ADMINISTRATIVA DESCONCENTRADA NORTE DEL DISTRITO FEDERAL</p>'
            '<table><tr><td>Licitación</td><td>Licitación Pública Número LA-51-GYN-051GYN030-I-75-2026</td></tr>'
            '<tr><td>Objeto de la Licitación</td><td>‘‘Adquisición de material de osteosíntesis”</td></tr>'
            '<tr><td>Apertura de proposiciones</td><td>20/julio /2026, 10:00 horas</td></tr></table>')
    proc = parse_procedures(html)[0]
    assert proc.state == "Ciudad de México"
    assert proc.title == "Adquisición de material de osteosíntesis"
    assert proc.submission_at.astimezone(MX) == datetime(2026, 7, 20, 10, 0, tzinfo=MX)


def test_unicode_dashes_and_nbsp_in_number_parse():
    """Guiones tipográficos (U+2010–U+2015, U+2212) y espacios duros no esconden el número."""
    html = ('<p align="center">INSTITUTO MEXICANO DEL SEGURO SOCIAL</p>'
            '<table><tr><td>No.\u00a0Licitación</td><td>LA\u201150\u2011GYR\u2011050GYR010\u2011T\u2011104\u20112026</td></tr>'
            '<tr><td>Descripción de la licitación</td><td>MATERIAL DE OSTEOSINTESIS</td></tr></table>'
            '<table><tr><td>No. Licitación</td><td>LA\u221250\u2013GYR\u2014050GYR010\u2012T\u2010105\u20152026</td></tr></table>')
    assert [p.external_id for p in parse_procedures(html)] == ["LA-50-GYR-050GYR010-T-104-2026",
                                                                "LA-50-GYR-050GYR010-T-105-2026"]


def _notice(heading: str, rows: str = "") -> str:
    table = rows or ('<tr><td>No. Licitación</td><td>LA-50-GYR-050GYR001-T-9-2026</td></tr>'
                     '<tr><td>Descripción de la licitación</td><td>MATERIAL DE OSTEOSINTESIS</td></tr>'
                     '<tr><td>Fecha del fallo</td><td>30 DE NOVIEMBRE DE 2026</td></tr>')
    return (f'<p align="center">INSTITUTO MEXICANO DEL SEGURO SOCIAL</p><p align="center">{heading}</p>'
            f'<table>{table}</table>')


def test_diferimiento_del_fallo_is_not_a_fallo():
    proc = parse_procedures(_notice("AVISO DE DIFERIMIENTO DEL FALLO"))[0]
    assert proc.notice == "modificacion"


def test_fallo_needs_a_positive_pattern():
    assert parse_procedures(_notice("PUBLICACION DE FALLO DE LICITACION PUBLICA"))[0].notice == "fallo"
    assert parse_procedures(_notice("SE DA A CONOCER EL FALLO DE LA LICITACION"))[0].notice == "fallo"
    # «fallo» de pasada en un encabezado no basta.
    assert parse_procedures(_notice("CALENDARIO: JUNTA, APERTURA Y FALLO"))[0].notice != "fallo"
    assert parse_procedures(_notice("MODIFICACION A LA FECHA DE FALLO"))[0].notice == "modificacion"


def test_cancellation_notice_is_classified():
    proc = parse_procedures(_notice("AVISO DE CANCELACION DE LA LICITACION PUBLICA"))[0]
    assert proc.notice == "cancelacion"
    winner = ('<tr><td>No. licitación</td><td>Descripción</td><td>Licitante ganador</td></tr>'
              '<tr><td>LA-50-GYR-050GYR001-T-9-2026</td><td>OSTEOSINTESIS</td><td>EMPRESA X</td></tr>')
    assert parse_procedures(_notice("AVISO DE CANCELACION", winner))[0].notice == "cancelacion"


def test_get_note_rejects_non_numeric_code():
    with pytest.raises(ValueError):
        make_client(fixture_transport()).get_note("../../etc/passwd")


# ── Fechas en español ───────────────────────────────────────────────────────

def test_date_only_is_midnight_mexico_city():
    dt, precision = parse_spanish_datetime("2 de septiembre de 2026")
    assert dt == datetime(2026, 9, 2, 6, 0, tzinfo=timezone.utc)
    assert dt.isoformat().replace("+00:00", "Z") == "2026-09-02T06:00:00Z"
    assert precision == "date"


@pytest.mark.parametrize("text, expected, precision", [
    ("21 de octubre de 2026, 10:00 horas", datetime(2026, 10, 21, 10, 0), "datetime"),
    ("21/10/2026", datetime(2026, 10, 21, 0, 0), "date"),
    ("14 OCTUBRE DE 2026; 09:00 HORAS", datetime(2026, 10, 14, 9, 0), "datetime"),
    ("25 DE AGOSTO DE 2026 10:00 HRS.", datetime(2026, 8, 25, 10, 0), "datetime"),
    ("29/09/2026, 10:00 horas", datetime(2026, 9, 29, 10, 0), "datetime"),
    ("1 de sep tiembre de 2026 a las 09:0 0 horas", datetime(2026, 9, 1, 9, 0), "datetime"),
    ("7 DE JULIO DEL 2026", datetime(2026, 7, 7, 0, 0), "date"),
    ("16/10/2026 14:00 hrs.", datetime(2026, 10, 16, 14, 0), "datetime"),
    ("22/10/2026 1:30 p.m.", datetime(2026, 10, 22, 13, 30), "datetime"),
    ("MARTES 3 DE NOVIEMBRE DE 2026\n 12:00 HORAS", datetime(2026, 11, 3, 12, 0), "datetime"),
    ("21 de octubre de 2026 a las 25:00 horas", datetime(2026, 10, 21, 0, 0), "date"),
    # Visto en la corrida real del 2026-10-29 (nota 5793828, ISSSTE): día/mes en letra/año.
    ("07/julio /2026, 12:00 horas", datetime(2026, 7, 7, 12, 0), "datetime"),
    ("20-JULIO-2026", datetime(2026, 7, 20, 0, 0), "date"),
])
def test_spanish_formats(text, expected, precision):
    dt, got = parse_spanish_datetime(text)
    assert dt == expected.replace(tzinfo=MX).astimezone(timezone.utc)
    assert got == precision


@pytest.mark.parametrize("text", ["NO APLICA", "", "31 de febrero de 2026", "Se detalla en la convocatoria",
                                  "LA-50-GYR-050GYR010-T-104-2026", "&#xZZ; 99/99/9999"])
def test_unparseable_dates_are_none(text):
    assert parse_spanish_datetime(text) == (None, "date")


# ── Red: reintentos, errores y ritmo ─────────────────────────────────────────

def test_timeout_raises_source_unavailable():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectTimeout("tiempo agotado", request=request)

    fake = FakeTime()
    with pytest.raises(SourceUnavailable) as exc:
        make_client(httpx.MockTransport(handler), fake).search("osteosintesis", date(2026, 1, 1), date(2026, 10, 29))
    assert exc.value.retryable is True
    assert exc.value.source == "dof_sidof"
    assert len(calls) == 3                               # 1 intento + 2 reintentos
    assert fake.sleeps[:2] == [1.0, 3.0]


def test_http_4xx_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    with pytest.raises(SourceUnavailable) as exc:
        make_client(httpx.MockTransport(handler)).get_note("5801639")
    assert exc.value.retryable is False
    assert len(calls) == 1


def test_http_5xx_is_retried_then_succeeds():
    responses = [httpx.Response(503), httpx.Response(200, content=fixture("nota_5801639.json"))]
    note = make_client(httpx.MockTransport(lambda r: responses.pop(0))).get_note("5801639")
    assert note.cod_nota == "5801639"


def test_decoding_error_is_source_unavailable():
    """Un cuerpo gzip corrupto (httpx.DecodingError) es un fallo de la fuente, no un error interno."""
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=b"esto no es gzip"))
    with pytest.raises(SourceUnavailable) as exc:
        make_client(transport).get_note("5801639")
    assert exc.value.source == "dof_sidof"


def test_oversized_response_is_rejected():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 2048))
    client = SidofClient(httpx.Client(transport=transport), clock=FakeTime().clock, sleep=FakeTime().sleep,
                         max_bytes=1024)
    with pytest.raises(SourceUnavailable) as exc:
        client.get_note("5801639")
    assert exc.value.retryable is False


def test_rate_limit_sleeps_between_calls(monkeypatch):
    fake = FakeTime()
    monkeypatch.setattr(time, "sleep", fake.sleep)
    starts: list[float] = []

    def handler(request):
        starts.append(fake.now)
        return httpx.Response(200, content=fixture("nota_5801639.json"))

    client = SidofClient(httpx.Client(transport=httpx.MockTransport(handler)), clock=fake.clock)
    client.get_note("5801639")
    client.get_note("5801639")
    assert len(starts) == 2
    assert starts[1] - starts[0] >= 1.0
    assert any(s >= 1.0 for s in fake.sleeps)


def test_note_service_gets_accept_any():
    """SIDOF responde 406 a `Accept: application/json, ...` en el servicio de notas (observado el 2026-10-29)."""
    def handler(request):
        if request.headers.get("Accept") != "*/*":
            return httpx.Response(406, text="Not Acceptable")
        if request.url.path.startswith("/dof/sidof/notas/nota/"):
            return httpx.Response(200, content=fixture("nota_5801639.json"))
        return httpx.Response(200, content=fixture("search_osteosintesis_2026.json"))

    client = make_client(httpx.MockTransport(handler))
    assert client.get_note("5801639").cod_nota == "5801639"
    assert len(client.search("osteosintesis", date(2026, 1, 1), date(2026, 10, 29)).hits) == 79


def test_clients_do_not_share_rate_limit_state():
    fake = FakeTime()
    transport = fixture_transport()
    SidofClient(httpx.Client(transport=transport), clock=fake.clock, sleep=fake.sleep).get_note("5801639")
    SidofClient(httpx.Client(transport=transport), clock=fake.clock, sleep=fake.sleep).get_note("5801639")
    assert fake.sleeps == []
