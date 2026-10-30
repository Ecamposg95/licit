"""C4: protección SSRF (netguard), API de corridas de búsqueda e importación manual.

Sin red: la resolución DNS y el cliente HTTP de netguard se sustituyen en cada prueba.
"""
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.core import netguard
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import AuditEvent, Job, Opportunity, OpportunityEvidence, SearchRun
from tests.conftest import login

FIX = Path(__file__).parent / "fixtures" / "sidof"
SIDOF = ["sidof.segob.gob.mx"]
COMPRAS = ["comprasmx.buengobierno.gob.mx"]
PUBLIC_IP = "8.8.8.8"


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Todos los nombres resuelven a una IP pública salvo los que la prueba sobrescriba."""
    table: dict[str, list[str]] = {}

    def resolve(host: str) -> list[str]:
        if host in table:
            return table[host]
        return [PUBLIC_IP]

    monkeypatch.setattr(netguard, "resolve_host", resolve)
    return table


def use_transport(monkeypatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def wrapped(request):
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(netguard, "_new_client", lambda timeout: httpx.Client(transport=httpx.MockTransport(wrapped)))
    return seen


def expect_rejected(url: str, allowed: list[str]) -> AppError:
    with pytest.raises(AppError) as exc:
        netguard.validate_public_url(url, allowed)
    assert exc.value.status == 422 and exc.value.code == "url_not_allowed"
    return exc.value


# ── validate_public_url ─────────────────────────────────────────────────────

def test_rejects_metadata_ip(client):
    expect_rejected("https://169.254.169.254/", COMPRAS)
    expect_rejected("https://169.254.169.254/latest/meta-data/", ["169.254.169.254"])   # ni aunque se permita
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/opportunities/import", json={"url": "https://169.254.169.254/latest/meta-data/"},
                    headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "url_not_allowed"


def test_rejects_other_domain():
    expect_rejected("https://evil.example.com/notas/docFuente/1", SIDOF)
    expect_rejected("https://sidof.segob.gob.mx.evil.com/", SIDOF)
    expect_rejected("https://evilsidof.segob.gob.mx/", SIDOF)
    expect_rejected("https://sidof.segob.gob.mx@evil.com/", SIDOF)           # credenciales en la URL
    expect_rejected("https://user:pw@sidof.segob.gob.mx/", SIDOF)
    expect_rejected("https://sidof.segob.gob.mx:8443/", SIDOF)                 # puerto no estándar
    expect_rejected("not a url", SIDOF)
    expect_rejected("", SIDOF)


def test_http_scheme_rejected():
    expect_rejected("http://sidof.segob.gob.mx/notas/docFuente/5801639", SIDOF)
    expect_rejected("ftp://sidof.segob.gob.mx/", SIDOF)
    expect_rejected("file:///etc/passwd", SIDOF)


@pytest.mark.parametrize("ip", ["10.0.0.5", "127.0.0.1", "192.168.1.10", "172.16.0.1", "169.254.169.254",
                                "100.64.0.1", "0.0.0.0", "224.0.0.1", "::1", "fd00::1", "fe80::1",
                                "::ffff:10.0.0.5", "192.0.2.10"])
def test_rejects_allowed_domain_resolving_to_internal_ip(fake_dns, ip):
    fake_dns["sidof.segob.gob.mx"] = [PUBLIC_IP, ip]          # basta con una IP interna
    expect_rejected("https://sidof.segob.gob.mx/notas/docFuente/5801639", SIDOF)


def test_unresolvable_host_rejected(fake_dns):
    fake_dns["sidof.segob.gob.mx"] = []
    err = expect_rejected("https://sidof.segob.gob.mx/", SIDOF)
    assert "resolver" in err.message


def test_accepts_domain_and_subdomain_and_keeps_fragment():
    assert netguard.validate_public_url("https://SIDOF.segob.gob.mx/notas/docFuente/5801639", SIDOF) == \
        "https://sidof.segob.gob.mx/notas/docFuente/5801639"
    url = "https://comprasmx.buengobierno.gob.mx/sitiopublico/#/sitiopublico/detalle/abc/1"
    assert netguard.validate_public_url(url, COMPRAS) == url
    assert netguard.validate_public_url("https://www.dipromedic.com/x.pdf", ["dipromedic.com"]) == \
        "https://www.dipromedic.com/x.pdf"


# ── safe_get ─────────────────────────────────────────────────────────────────

def test_rejects_redirect_to_private(monkeypatch):
    def handler(request):
        return httpx.Response(302, headers={"Location": "https://10.0.0.5/"})

    seen = use_transport(monkeypatch, handler)
    with pytest.raises(AppError) as exc:
        netguard.safe_get("https://sidof.segob.gob.mx/notas/docFuente/5801639", SIDOF)
    assert exc.value.status == 422 and exc.value.code == "url_not_allowed"
    assert [r.url.host for r in seen] == ["sidof.segob.gob.mx"]          # nunca se contactó 10.0.0.5


def test_redirect_within_allowed_domain_is_followed_and_validated(monkeypatch, fake_dns):
    def handler(request):
        if request.url.path == "/a":
            return httpx.Response(301, headers={"Location": "/b"})
        if request.url.path == "/b":
            return httpx.Response(302, headers={"Location": "https://internal.sidof.segob.gob.mx/c"})
        return httpx.Response(200, text="ok")

    fake_dns["internal.sidof.segob.gob.mx"] = ["10.1.2.3"]
    seen = use_transport(monkeypatch, handler)
    with pytest.raises(AppError):
        netguard.safe_get("https://sidof.segob.gob.mx/a", SIDOF)
    assert [r.url.path for r in seen] == ["/a", "/b"]


def test_too_many_redirects(monkeypatch):
    use_transport(monkeypatch, lambda r: httpx.Response(302, headers={"Location": "/loop"}))
    with pytest.raises(AppError) as exc:
        netguard.safe_get("https://sidof.segob.gob.mx/loop", SIDOF, max_redirects=3)
    assert exc.value.code == "url_not_allowed" and "redirecciones" in exc.value.message


def test_safe_get_caps_size_and_sends_user_agent(monkeypatch):
    seen = use_transport(monkeypatch, lambda r: httpx.Response(200, content=b"x" * 2000))
    r = netguard.safe_get("https://sidof.segob.gob.mx/ok", SIDOF, max_bytes=5000)
    assert r.status_code == 200 and r.content == b"x" * 2000
    assert seen[0].headers["User-Agent"] == "LicitDemo/1.0 (+contacto Atlas Technologies)"
    with pytest.raises(AppError) as exc:
        netguard.safe_get("https://sidof.segob.gob.mx/ok", SIDOF, max_bytes=1000)
    assert exc.value.code == "response_too_large"


def test_safe_get_decoding_error_is_502(monkeypatch):
    use_transport(monkeypatch, lambda r: httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=b"roto"))
    with pytest.raises(AppError) as exc:
        netguard.safe_get("https://sidof.segob.gob.mx/ok", SIDOF)
    assert exc.value.status == 502 and exc.value.code == "source_unavailable"


def test_safe_get_bad_redirect_location_is_a_clean_error(monkeypatch):
    """httpx rechaza la cabecera Location inválida (RemoteProtocolError): error de la fuente, nunca un 500."""
    use_transport(monkeypatch, lambda r: httpx.Response(302, headers={"Location": "https://[::1"}))
    with pytest.raises(AppError) as exc:
        netguard.safe_get("https://sidof.segob.gob.mx/ok", SIDOF)
    assert (exc.value.status, exc.value.code) == (502, "source_unavailable")


def test_safe_get_network_error_is_502(monkeypatch):
    def handler(request):
        raise httpx.ConnectTimeout("sin respuesta", request=request)

    use_transport(monkeypatch, handler)
    with pytest.raises(AppError) as exc:
        netguard.safe_get("https://sidof.segob.gob.mx/ok", SIDOF)
    assert exc.value.status == 502 and exc.value.code == "source_unavailable"


# ── API de corridas ──────────────────────────────────────────────────────────

def test_search_run_requires_permission(client):
    headers = login(client, "revisor@dipromedic.example")
    r = client.post("/api/v1/search-runs", json={}, headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SearchRun)) == 0


def test_post_search_run_returns_202_and_job(client):
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/search-runs", json={}, headers=headers)
    assert r.status_code == 202, r.text
    body = r.json()
    assert set(body) == {"search_run_id", "job_id"}

    job = client.get(f"/api/v1/jobs/{body['job_id']}", headers=headers).json()
    assert job["kind"] == "search_run" and job["status"] == "queued"
    run = client.get(f"/api/v1/search-runs/{body['search_run_id']}", headers=headers).json()
    assert run["status"] == "queued" and run["job_id"] == body["job_id"]
    assert run["query"]["terms"] == ["osteosintesis", "endoprotesis", "implantes ortopedicos",
                                     "material de osteosintesis"]
    assert run["query"]["date_from"].endswith("-01-01")
    assert run["counts"] == {"notes": 0, "procedures": 0, "new": 0, "updated": 0, "unchanged": 0}
    assert [t["term"] for t in run["terms"]] == run["query"]["terms"]
    assert run["created_by"]["email"] == "analista1@dipromedic.example"
    listing = client.get("/api/v1/search-runs", headers=headers).json()
    assert [x["id"] for x in listing] == [body["search_run_id"]]


def test_search_run_same_idempotency_key_same_run(client):
    headers = {**login(client, "analista1@dipromedic.example"), "Idempotency-Key": "clic-abc"}
    payload = {"terms": ["osteosíntesis", "Osteosintesis", "endoprotesis"], "date_from": "2026-09-01",
               "date_to": "2026-10-29"}
    first = client.post("/api/v1/search-runs", json=payload, headers=headers)
    second = client.post("/api/v1/search-runs", json=payload, headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    run = client.get(f"/api/v1/search-runs/{first.json()['search_run_id']}", headers=headers).json()
    assert run["query"] == {"terms": ["osteosíntesis", "endoprotesis"], "date_from": "2026-09-01",
                            "date_to": "2026-10-29"}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SearchRun)) == 1
        assert db.scalar(select(func.count()).select_from(Job)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)
                         .where(AuditEvent.action == "search.start")) == 1


@pytest.mark.parametrize("payload", [
    {"date_from": "2026-10-29", "date_to": "2026-01-01"},
    {"date_from": "2024-01-01", "date_to": "2026-10-29"},
    {"terms": ["x" * 81]},
    {"terms": [f"t{i}" for i in range(11)]},
])
def test_search_run_validation(client, payload):
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/search-runs", json=payload, headers=headers)
    assert r.status_code == 422


def test_search_run_rejects_dates_before_2021(client):
    """El robots.txt de SIDOF prohíbe notas de 2011–2020: la búsqueda empieza el 01-01-2021 como mínimo."""
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/search-runs", json={"date_from": "2020-12-31", "date_to": "2021-06-30"}, headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "date_out_of_range"
    ok = client.post("/api/v1/search-runs", json={"date_from": "2021-01-01", "date_to": "2021-06-30"}, headers=headers)
    assert ok.status_code == 202


def test_search_run_detail_is_org_scoped(client):
    headers = login(client, "analista1@dipromedic.example")
    r = client.get("/api/v1/search-runs/no-existe", headers=headers)
    assert r.status_code == 404


# ── Importación manual ───────────────────────────────────────────────────────

def test_manual_import_comprasmx_por_verificar(client):
    headers = login(client, "analista1@dipromedic.example")
    meta = {"external_id": "LA-12-ABC-012ABC001-N-9-2026", "title": "Material de osteosíntesis para hospital",
            "buyer": "Hospital General (captura)", "submission_at": "2026-11-20T10:00:00",
            "source_url": "https://comprasmx.buengobierno.gob.mx/sitiopublico/#/sitiopublico/detalle/abc/1",
            "notes": "Revisado en el navegador por el analista"}
    r = client.post("/api/v1/opportunities/import", json={"metadata": meta}, headers=headers)
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["data_kind"] == "REAL"
    assert row["verification_status"] == "por_verificar"
    assert row["derived"]["code"] == "por_verificar"
    assert row["source"]["key"] == "comprasmx"
    assert row["source_url"] == meta["source_url"]
    assert row["submission_at"].startswith("2026-11-20T16:00:00")          # 10:00 de CDMX en UTC
    assert row["families"] == ["Osteosíntesis"]
    detail = client.get(f"/api/v1/opportunities/{row['id']}", headers=headers).json()
    assert detail["reported_status"] == "importada manualmente"
    assert detail["timezone_assumed"] is True
    with SessionLocal() as db:
        ev = db.scalars(select(AuditEvent).where(AuditEvent.action == "opportunity.import")).one()
        assert ev.resource_id == row["id"] and ev.after["method"] == "captura_comprasmx"

    again = client.post("/api/v1/opportunities/import", json={"metadata": meta}, headers=headers)
    assert again.status_code == 409 and again.json()["details"]["opportunity_id"] == row["id"]


def test_manual_import_rejects_non_comprasmx_url(client):
    headers = login(client, "analista1@dipromedic.example")
    meta = {"external_id": "LA-1", "title": "Algo", "buyer": "Alguien", "source_url": "https://evil.example.com/"}
    r = client.post("/api/v1/opportunities/import", json={"metadata": meta}, headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "url_not_allowed"


def test_import_requires_permission(client):
    headers = login(client, "direccion@dipromedic.example")
    r = client.post("/api/v1/opportunities/import",
                    json={"url": "https://sidof.segob.gob.mx/notas/docFuente/5801639"}, headers=headers)
    assert r.status_code == 403


def test_import_needs_exactly_one_form(client):
    headers = login(client, "analista1@dipromedic.example")
    assert client.post("/api/v1/opportunities/import", json={}, headers=headers).status_code == 422
    both = {"url": "https://sidof.segob.gob.mx/notas/docFuente/1",
            "metadata": {"external_id": "X", "title": "Tít", "buyer": "Yo", "source_url": "https://x"}}
    assert client.post("/api/v1/opportunities/import", json=both, headers=headers).status_code == 422


def sidof_notes_transport(notes: dict[str, bytes]):
    def handler(request):
        cod = request.url.path.rsplit("/", 1)[-1]
        if request.url.path.startswith("/dof/sidof/notas/nota/") and cod in notes:
            return httpx.Response(200, content=notes[cod])
        return httpx.Response(404)
    return handler


def test_import_sidof_note_url(client, monkeypatch):
    seen = use_transport(monkeypatch, sidof_notes_transport({"5801639": (FIX / "nota_5801639.json").read_bytes()}))
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/opportunities/import",
                    json={"url": "https://sidof.segob.gob.mx/notas/docFuente/5801639"}, headers=headers)
    assert r.status_code == 201, r.text
    assert r.headers["X-Import-Outcome"] == "new"
    row = r.json()
    assert row["external_id"] == "LA-50-GYR-050GYR010-T-104-2026" and row["data_kind"] == "REAL"
    assert row["source"]["key"] == "dof_sidof"
    assert row["source_url"] == "https://sidof.segob.gob.mx/notas/docFuente/5801639"
    assert str(seen[0].url) == "https://sidof.segob.gob.mx/dof/sidof/notas/nota/5801639"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OpportunityEvidence)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)
                         .where(AuditEvent.action == "opportunity.import")) == 1

    again = client.post("/api/v1/opportunities/import",
                        json={"url": "https://sidof.segob.gob.mx/notas/docFuente/5801639"}, headers=headers)
    assert again.status_code == 200 and again.headers["X-Import-Outcome"] == "unchanged"
    assert again.json()["id"] == row["id"]


def test_import_multi_procedure_note_picks_matching_object(client, monkeypatch):
    use_transport(monkeypatch, sidof_notes_transport({"5800141": (FIX / "nota_5800141.json").read_bytes()}))
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/opportunities/import",
                    json={"url": "https://sidof.segob.gob.mx/notas/5800141"}, headers=headers)
    assert r.status_code == 201 and r.json()["external_id"] == "LA-50-GYR-050GYR028-T-111-2026"
    chosen = client.post("/api/v1/opportunities/import",
                         json={"url": "https://sidof.segob.gob.mx/notas/5800141",
                               "external_id": "LA-50-GYR-050GYR028-N-103-2026"}, headers=headers)
    assert chosen.status_code == 201 and chosen.json()["external_id"] == "LA-50-GYR-050GYR028-N-103-2026"


def test_import_ambiguous_note_asks_which_procedure(client, monkeypatch):
    table = ('<table><tr><td>No. Licitación</td><td>{n}</td></tr><tr><td>Descripción de la licitación</td>'
             '<td>MATERIAL DE OSTEOSINTESIS {i}</td></tr></table>')
    html = table.format(n="LA-50-GYR-050GYR001-T-1-2026", i=1) + table.format(n="LA-50-GYR-050GYR001-T-2-2026", i=2)
    note = json.dumps({"messageCode": 200, "Nota": {"codNota": 9, "cadenaContenido": html}}).encode()
    use_transport(monkeypatch, sidof_notes_transport({"9": note}))
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/opportunities/import",
                    json={"url": "https://sidof.segob.gob.mx/notas/docFuente/9"}, headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "procedure_choice_required"
    assert [d["external_id"] for d in r.json()["details"]] == ["LA-50-GYR-050GYR001-T-1-2026",
                                                              "LA-50-GYR-050GYR001-T-2-2026"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.data_kind == "REAL")) == 0


def test_import_fallo_note_is_not_created(client, monkeypatch):
    use_transport(monkeypatch, sidof_notes_transport({"5799326": (FIX / "nota_5799326.json").read_bytes()}))
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/opportunities/import",
                    json={"url": "https://sidof.segob.gob.mx/notas/docFuente/5799326"}, headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "notice_not_convocatoria"
    assert "fallo" in r.json()["message"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.data_kind == "REAL")) == 0


def test_import_comprasmx_url_points_to_manual_capture(client):
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/opportunities/import",
                    json={"url": "https://comprasmx.buengobierno.gob.mx/sitiopublico/#/"}, headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "use_manual_capture"


def test_import_sidof_down_creates_nothing(client, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("sin red", request=request)

    use_transport(monkeypatch, handler)
    headers = login(client, "analista1@dipromedic.example")
    r = client.post("/api/v1/opportunities/import",
                    json={"url": "https://sidof.segob.gob.mx/notas/docFuente/5801639"}, headers=headers)
    assert r.status_code == 502 and r.json()["code"] == "source_unavailable"
    assert "no significa" in r.json()["message"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.data_kind == "REAL")) == 0


def test_default_window_is_current_year(client):
    headers = login(client, "analista1@dipromedic.example")
    body = client.post("/api/v1/search-runs", json={"terms": ["osteosintesis"]}, headers=headers).json()
    run = client.get(f"/api/v1/search-runs/{body['search_run_id']}", headers=headers).json()
    today = date.fromisoformat(run["query"]["date_to"])
    assert run["query"]["date_from"] == f"{today.year}-01-01"
