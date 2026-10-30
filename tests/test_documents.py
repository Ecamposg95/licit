"""Frente D · documentos: carga validada, versiones, descarga autorizada, archivos DEMO e ingesta del catálogo."""
import hashlib
import io
import os
import zipfile

import pytest
from sqlalchemy import select

from app.core import config
from app.core.database import SessionLocal
from app.models import AuditEvent, Document, DocumentVersion, Organization
from app.services.storage import get_storage
from tests.conftest import login

DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def pdf_bytes(tag: str = "a") -> bytes:
    return (b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%% " + tag.encode() + b"\n%%EOF\n")


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def docx_bytes() -> bytes:
    return make_zip({
        "[Content_Types].xml": b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "word/document.xml": b"<w:document/>",
    })


def org_id() -> str:
    with SessionLocal() as db:
        return db.scalars(select(Organization.id)).first()


FORM = {"title": "Ficha técnica de prueba", "scope": "empresa", "doc_type": "ficha_tecnica", "data_kind": "SYNTHETIC"}


def upload(client, headers, data: bytes, filename: str = "ficha.pdf", content_type: str = "application/pdf", **form):
    return client.post("/api/v1/documents", headers=headers, data={**FORM, **form},
                       files={"file": (filename, data, content_type)})


def upload_version(client, headers, doc_id: str, data: bytes, filename: str = "ficha_v2.pdf", note: str | None = None):
    return client.post(f"/api/v1/documents/{doc_id}/versions", headers=headers,
                       data={"note": note} if note else {}, files={"file": (filename, data, "application/pdf")})


# ── D2 · carga y versiones ───────────────────────────────────────────────────

def test_upload_pdf_creates_version_with_hash(client, analista):
    data = pdf_bytes("hash")
    r = upload(client, analista, data)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["current_version"] == 1
    assert doc["data_kind"] == "SYNTHETIC"
    assert doc["watermark"] == config.WATERMARK
    assert doc["code"] and doc["third_party"] is False and doc["external_url"] is None
    [version] = doc["versions"]
    assert version["version"] == 1
    assert version["sha256"] == hashlib.sha256(data).hexdigest()
    assert version["size_bytes"] == len(data)
    assert version["content_type"] == "application/pdf"
    assert version["filename"] == "ficha.pdf"
    assert "storage_key" not in version
    key = f"org/{org_id()}/documents/{doc['id']}/v1/ficha.pdf"
    assert get_storage().get(key) == data
    with SessionLocal() as db:
        actions = [e.action for e in db.scalars(select(AuditEvent).where(AuditEvent.resource_id == doc["id"]))]
    assert "document.create" in actions and "document.version_upload" in actions


def test_real_upload_has_no_demo_watermark(client, analista):
    r = upload(client, analista, pdf_bytes("real"), data_kind="REAL")
    assert r.status_code == 201, r.text
    assert r.json()["watermark"] is None and r.json()["data_kind"] == "REAL"


def test_rejects_oversize(client, analista):
    r = upload(client, analista, b"%PDF-" + b"\0" * config.DOCUMENT_MAX_BYTES)
    assert r.status_code == 413
    assert r.json()["code"] == "file_too_large"
    # El límite exacto sí pasa.
    ok = upload(client, analista, b"%PDF-" + b"\0" * (config.DOCUMENT_MAX_BYTES - 5))
    assert ok.status_code == 201, ok.text


def test_rejects_disguised_exe(client, analista):
    r = upload(client, analista, b"MZ\x90\x00\x03\x00\x00\x00" + b"\0" * 64, filename="x.pdf")
    assert r.status_code == 422
    assert r.json()["code"] == "unsupported_file"


def test_rejects_docm_macro(client, analista):
    macro = make_zip({
        "[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w:document/>",
        "word/vbaProject.bin": b"\xd0\xcf\x11\xe0 vba",
    })
    for name in ("x.docx", "x.docm"):
        r = upload(client, analista, macro, filename=name, content_type=DOCX_CT)
        assert r.status_code == 422, r.text
        assert r.json()["code"] == "unsupported_file"
    # Un DOCX sin macros sí se acepta.
    ok = upload(client, analista, docx_bytes(), filename="Carta.DOCX", content_type=DOCX_CT)
    assert ok.status_code == 201, ok.text
    assert ok.json()["versions"][0]["content_type"] == DOCX_CT


def test_rejects_zip_bomb_and_other_office_files(client, analista):
    bomb = make_zip({"[Content_Types].xml": b"<Types/>", "word/document.xml": b"\0" * (51 * 1024 * 1024)})
    assert len(bomb) < config.DOCUMENT_MAX_BYTES
    r = upload(client, analista, bomb, filename="bomba.docx", content_type=DOCX_CT)
    assert r.status_code == 422
    assert r.json()["code"] == "archive_too_large"
    xlsx = make_zip({"[Content_Types].xml": b"<Types/>", "xl/workbook.xml": b"<workbook/>"})
    r = upload(client, analista, xlsx, filename="hoja.docx", content_type=DOCX_CT)
    assert r.status_code == 422 and r.json()["code"] == "unsupported_file"
    r = upload(client, analista, b"PK\x03\x04 no es un zip", filename="roto.docx", content_type=DOCX_CT)
    assert r.status_code == 422 and r.json()["code"] == "unsupported_file"


def test_extension_must_match_content(client, analista):
    r = upload(client, analista, pdf_bytes("ext"), filename="ficha.exe")
    assert r.status_code == 422 and r.json()["code"] == "unsupported_file"
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
    assert upload(client, analista, png, filename="sello.PNG", content_type="image/png").status_code == 201
    jpg = b"\xff\xd8\xff\xe0" + b"\0" * 32
    assert upload(client, analista, jpg, filename="foto.jpeg", content_type="image/jpeg").status_code == 201
    assert upload(client, analista, jpg, filename="foto.png", content_type="image/png").status_code == 422


def test_new_version_keeps_previous(client, analista):
    v1, v2 = pdf_bytes("uno"), pdf_bytes("dos")
    doc = upload(client, analista, v1).json()
    r = upload_version(client, analista, doc["id"], v2, note="Corrige el material")
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2 and r.json()["note"] == "Corrige el material"
    assert r.json()["sha256"] == hashlib.sha256(v2).hexdigest()
    detail = client.get(f"/api/v1/documents/{doc['id']}", headers=analista).json()
    assert [v["version"] for v in detail["versions"]] == [1, 2]
    assert detail["current_version"] == 2
    org = org_id()
    storage = get_storage()
    assert storage.get(f"org/{org}/documents/{doc['id']}/v1/ficha.pdf") == v1
    # La versión 1 sigue descargable por la API después de subir la 2 (D3).
    assert client.get(f"/api/v1/documents/{doc['id']}/versions/1/download", headers=analista).content == v1
    assert client.get(f"/api/v1/documents/{doc['id']}/versions/2/download", headers=analista).content == v2
    assert storage.get(f"org/{org}/documents/{doc['id']}/v2/ficha_v2.pdf") == v2


def test_new_version_resets_review_status(client, analista):
    doc = upload(client, analista, pdf_bytes("rev")).json()
    with SessionLocal() as db:
        db.get(Document, doc["id"]).review_status = "validado"
        db.commit()
    upload_version(client, analista, doc["id"], pdf_bytes("rev2"))
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=analista).json()["review_status"] == "pendiente"


def test_direccion_cannot_upload(client, direccion, analista):
    r = upload(client, direccion, pdf_bytes("dir"))
    assert r.status_code == 403
    doc = upload(client, analista, pdf_bytes("ok")).json()
    assert upload_version(client, direccion, doc["id"], pdf_bytes("v2")).status_code == 403
    assert client.post("/api/v1/documents", data=FORM, files={"file": ("a.pdf", pdf_bytes(), "application/pdf")}).status_code == 401


def test_filename_sanitized_and_empty_rejected(client, analista):
    data = pdf_bytes("san")
    r = upload(client, analista, data, filename="../../ficha.PDF")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["versions"][0]["filename"] == "ficha.PDF"
    assert get_storage().exists(f"org/{org_id()}/documents/{doc['id']}/v1/ficha.PDF")
    # Acentos y extensión en mayúsculas se conservan; las barras invertidas de Windows también se quitan.
    r = upload(client, analista, pdf_bytes("acentos"), filename="C:\\temp\\Técnica quirúrgica Ñandú.PDF")
    assert r.status_code == 201 and r.json()["versions"][0]["filename"] == "Técnica quirúrgica Ñandú.PDF"
    # Nombre larguísimo: se limita a 120 caracteres y conserva la extensión.
    r = upload(client, analista, pdf_bytes("largo"), filename="a" * 300 + ".pdf")
    assert r.status_code == 201
    name = r.json()["versions"][0]["filename"]
    assert len(name) <= 120 and name.endswith(".pdf")
    # 0 bytes se rechaza.
    r = upload(client, analista, b"", filename="vacio.pdf")
    assert r.status_code == 422
    assert r.json()["code"] == "empty_file"
    with SessionLocal() as db:
        assert not db.scalars(select(DocumentVersion).where(DocumentVersion.filename == "vacio.pdf")).all()


def test_upload_validates_form_and_links(client, analista):
    assert upload(client, analista, pdf_bytes(), scope="otro").status_code == 422
    assert upload(client, analista, pdf_bytes(), data_kind="FAKE").status_code == 422
    assert upload(client, analista, pdf_bytes(), title="   ").status_code == 422
    assert upload(client, analista, pdf_bytes(), valid_until="no-es-fecha").status_code == 422
    # Una oportunidad o un producto de otra organización (o inexistente) responde 404.
    assert upload(client, analista, pdf_bytes(), opportunity_id="no-existe").status_code == 404
    assert upload(client, analista, pdf_bytes(), product_id="no-existe").status_code == 404
    ok = upload(client, analista, pdf_bytes("vig"), valid_until="2027-03-31")
    assert ok.status_code == 201 and ok.json()["valid_until"] == "2027-03-31"


# ── D3 · descarga autorizada ─────────────────────────────────────────────────

def download(client, headers, doc_id: str, version: int = 1):
    return client.get(f"/api/v1/documents/{doc_id}/versions/{version}/download", headers=headers)


def test_download_returns_inline_file_with_headers(client, analista):
    data = pdf_bytes("dl")
    doc = upload(client, analista, data, filename="Técnica quirúrgica.PDF").json()
    r = download(client, analista, doc["id"])
    assert r.status_code == 200
    assert r.content == data
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-length"] == str(len(data))
    disposition = r.headers["content-disposition"]
    assert disposition.startswith("inline;")
    assert "filename*=UTF-8''T%C3%A9cnica%20quir%C3%BArgica.PDF" in disposition
    assert r.headers["x-content-type-options"] == "nosniff"
    assert download(client, analista, doc["id"], 7).status_code == 404       # versión inexistente
    assert client.get(f"/api/v1/documents/{doc['id']}/versions/1/download").status_code == 401


def test_download_other_org_404(client, analista):
    with SessionLocal() as db:
        other = Organization(name="Otra organización")
        db.add(other)
        db.flush()
        foreign = Document(organization_id=other.id, code="AJENO-1", title="Documento ajeno", scope="empresa",
                           data_kind="REAL", current_version=1)
        foreign.versions.append(DocumentVersion(organization_id=other.id, version=1, filename="ajeno.pdf",
                                                content_type="application/pdf", size_bytes=9, sha256="0" * 64,
                                                storage_key=f"org/{other.id}/documents/x/v1/ajeno.pdf"))
        db.add(foreign)
        db.commit()
        foreign_id = foreign.id
        get_storage().put(f"org/{other.id}/documents/x/v1/ajeno.pdf", pdf_bytes("ajeno"), "application/pdf")
    assert download(client, analista, foreign_id).status_code == 404
    assert client.get(f"/api/v1/documents/{foreign_id}", headers=analista).status_code == 404
    assert upload_version(client, analista, foreign_id, pdf_bytes("x")).status_code == 404
    assert foreign_id not in {d["id"] for d in client.get("/api/v1/documents", headers=analista).json()}
    with SessionLocal() as db:
        assert not db.scalars(select(AuditEvent).where(AuditEvent.action == "document.download")).all()


def test_download_audited(client, analista):
    doc = upload(client, analista, pdf_bytes("aud")).json()
    assert download(client, analista, doc["id"]).status_code == 200
    with SessionLocal() as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.action == "document.download")).all()
        assert len(events) == 1
        event = events[0]
        assert event.resource_type == "document" and event.resource_id == doc["id"]
        assert event.after["version"] == 1 and event.after["sha256"] == doc["versions"][0]["sha256"]
        assert event.actor_id is not None


def test_third_party_returns_external_url(client, analista):
    url = "https://www.fabricante-externo.example/ficha.pdf"
    with SessionLocal() as db:
        doc = Document(organization_id=org_id(), code="EXT-1", title="Ficha del fabricante (tercero)",
                       scope="producto", doc_type="ficha_tecnica", data_kind="REAL", current_version=0,
                       third_party=True, external_url=url)
        db.add(doc)
        db.commit()
        doc_id = doc.id
    r = download(client, analista, doc_id)
    assert r.status_code == 409
    assert r.json()["code"] == "external_document"
    assert r.json()["details"] == {"external_url": url}
    listed = {d["id"]: d for d in client.get("/api/v1/documents", headers=analista).json()}
    assert listed[doc_id]["third_party"] is True and listed[doc_id]["external_url"] == url


def test_download_without_file_or_lost_file_is_404(client, analista):
    # Versión semilla sin archivo adjunto (documento propio, no de tercero).
    with SessionLocal() as db:
        doc = Document(organization_id=org_id(), code="SIN-1", title="Sin archivo", scope="empresa",
                       data_kind="SYNTHETIC", current_version=1)
        doc.versions.append(DocumentVersion(organization_id=org_id(), version=1, note="Versión semilla sin archivo"))
        db.add(doc)
        db.commit()
        doc_id = doc.id
    r = download(client, analista, doc_id)
    assert r.status_code == 404 and r.json()["code"] == "file_missing"
    # El registro existe pero el objeto desapareció del almacenamiento.
    up = upload(client, analista, pdf_bytes("perdido")).json()
    get_storage().delete(f"org/{org_id()}/documents/{up['id']}/v1/ficha.pdf")
    r = download(client, analista, up["id"])
    assert r.status_code == 404 and r.json()["code"] == "file_missing"


# ── D4 · documentos de prueba con marca DEMO ─────────────────────────────────

from app.services import demo_documents  # noqa: E402
from app.services.demo_seed import reset_demo  # noqa: E402


def test_demo_pdf_contains_watermark():
    data = demo_documents.render_demo_pdf("Ficha técnica de prueba", [
        "Producto: Placa bloqueada demostración variante 1", "Registro sanitario: DEMO-SIN-VALIDEZ",
        demo_documents.PAGE_BREAK, "Segunda página con más texto",
    ])
    assert data.startswith(b"%PDF-")
    assert b"/Filter" not in data                                   # sin compresión: el texto se puede buscar
    # Marca exacta en los metadatos (UTF-8) y en el contenido de cada página (diagonal + pie, en latin-1).
    assert config.WATERMARK.encode("utf-8") in data
    assert data.count(config.WATERMARK.encode("latin-1")) == 2 * 2
    assert config.FICTITIOUS_REGISTRY.encode() in data
    assert demo_documents.has_demo_watermark(data)
    assert not demo_documents.has_demo_watermark(pdf_bytes("sin marca"))
    assert uploads_page_count(data) == 2
    # Determinista: mismos datos, mismos bytes (el reinicio del demo no cambia los hashes).
    assert data == demo_documents.render_demo_pdf("Ficha técnica de prueba", [
        "Producto: Placa bloqueada demostración variante 1", "Registro sanitario: DEMO-SIN-VALIDEZ",
        demo_documents.PAGE_BREAK, "Segunda página con más texto",
    ])


def uploads_page_count(data: bytes):
    from app.services.uploads import pdf_page_count
    return pdf_page_count(data)


def test_demo_pdf_tolerates_characters_outside_latin1():
    data = demo_documents.render_demo_pdf("Vigencia ≥ 90 días — “ficticia” ✓", ["Vigencia: fecha base −10 días"])
    assert data.startswith(b"%PDF-") and demo_documents.has_demo_watermark(data)


def _synthetic_versions(db):
    return db.execute(select(DocumentVersion, Document).join(Document, Document.id == DocumentVersion.document_id)
                      .where(Document.data_kind == "SYNTHETIC").order_by(Document.code)).all()


def test_reset_attaches_demo_files():
    storage = get_storage()
    with SessionLocal() as db:
        rows = _synthetic_versions(db)
        assert len(rows) == 12
        org = db.get(Organization, org_id())
        for version, doc in rows:
            assert version.storage_key == f"demo/{org.id}/{doc.code}.pdf"
            data = storage.get(version.storage_key)
            assert version.sha256 == hashlib.sha256(data).hexdigest()
            assert version.size_bytes == len(data) and version.content_type == "application/pdf"
            assert version.filename == f"{doc.code}.pdf"
            assert demo_documents.has_demo_watermark(data)
            assert doc.page_count and doc.page_count >= 1
        hashes = {doc.code: v.sha256 for v, doc in rows}
    # El PDF cita el fragmento que la evidencia de la semilla señala (DEMO-DOC-007: «Material: no declarado»).
    doc7 = storage.get(f"demo/{org_id()}/DEMO-DOC-007.pdf")
    assert b"Material: no declarado" in doc7

    # Una carga SYNTHETIC del presentador y un reinicio: el reinicio borra los archivos anteriores (y la carga),
    # vuelve a guardar los 12 y los hashes no cambian.
    uploaded = upload(client_for_tests(), login(client_for_tests(), "analista1@dipromedic.example"), pdf_bytes("presentador"))
    assert uploaded.status_code == 201
    uploaded_key = f"org/{org_id()}/documents/{uploaded.json()['id']}/v1/ficha.pdf"
    assert storage.exists(uploaded_key)
    with SessionLocal() as db:
        org = db.get(Organization, org_id())
        reset_demo(db, org, actor_id=None)
        db.commit()
    assert not storage.exists(uploaded_key)
    with SessionLocal() as db:
        rows = _synthetic_versions(db)
        assert len(rows) == 12
        assert {doc.code: v.sha256 for v, doc in rows} == hashes
        assert all(storage.exists(v.storage_key) for v, _ in rows)


def client_for_tests():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_reset_rollback_keeps_files():
    storage = get_storage()
    with SessionLocal() as db:
        keys = [v.storage_key for v, _ in _synthetic_versions(db)]
        org = db.get(Organization, org_id())
        stale = f"demo/{org.id}/viejo.pdf"
        storage.put(stale, pdf_bytes("viejo"), "application/pdf")
        demo_documents.delete_after_commit(db, [stale])
        db.rollback()                                  # el reinicio se revirtió: nada se borra
        db.commit()
    assert storage.exists(stale) and all(storage.exists(k) for k in keys)
    with SessionLocal() as db:
        demo_documents.delete_after_commit(db, [stale])
        db.commit()
    assert not storage.exists(stale)


def test_ensure_demo_files_restores_lost_objects():
    storage = get_storage()
    with SessionLocal() as db:
        rows = _synthetic_versions(db)
        lost = [v.storage_key for v, _ in rows][:3]
    for key in lost:
        storage.delete(key)
    with SessionLocal() as db:
        assert demo_documents.ensure_demo_files(db, org_id()) == 3
        assert demo_documents.ensure_demo_files(db, org_id()) == 0
    assert all(storage.exists(k) for k in lost)


def test_demo_documents_are_downloadable(client, analista):
    with SessionLocal() as db:
        doc = db.scalars(select(Document).where(Document.code == "DEMO-DOC-002")).one()
        doc_id = doc.id
    r = download(client, analista, doc_id)
    assert r.status_code == 200 and demo_documents.has_demo_watermark(r.content)
    assert r.headers["content-disposition"].startswith("inline;")


def test_upload_sample_script_and_upload(client, analista, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_sample", "scripts/make_demo_upload_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = module.main(tmp_path / "ficha.pdf")
    data = out.read_bytes()
    assert demo_documents.has_demo_watermark(data) and b"DEMO-PLA-001" in data
    assert data == demo_documents.render_upload_sample()
    # El presentador lo sube como documento SYNTHETIC y queda con marca DEMO.
    r = upload(client, analista, data, filename=demo_documents.UPLOAD_SAMPLE_NAME)
    assert r.status_code == 201, r.text
    assert r.json()["data_kind"] == "SYNTHETIC" and r.json()["watermark"] == config.WATERMARK
    assert r.json()["page_count"] == 1


# ── D5 · ingesta de PDFs del catálogo ────────────────────────────────────────

import httpx  # noqa: E402

from app.core import netguard  # noqa: E402
from app.models import Product  # noqa: E402
from app.services import catalog_documents as cd  # noqa: E402

OWN_OWNER = "Marca propia de Dipromedic (creada en 2009 según la línea de tiempo de /nosotros)"
THIRD_OWNER = "Tercero (Corentec, Corea)"
TQ_URL = "https://traufix.com/wp-content/uploads/2026/02/TITAN-Humero-Proximal-TQ-048.pdf"
BROCHURE_URL = "https://www.dipromedic.com/assets/docs/brochure/caleb/E-7-brochure.pdf"
CATALOG_URL = "https://www.dipromedic.com/assets/docs/catalogos/traufix/Catalogo-Traufix-ES.pdf"
COREN_URL = "https://www.dipromedic.com/assets/docs/brochure/corentec/Bencox-M-Stem.pdf"
LOCAL_PREFIX = "docs/research/dipromedic/pdfs/"


def mini_catalog() -> dict:
    def pdf(title, url, local):
        return {"title": title, "url": url, "http_status": 200, "size_bytes": 100, "size_mb": 0.0,
                "host": url.split("/")[2].removeprefix("www."), "local_path": LOCAL_PREFIX + local if local else None}
    return {
        "source": "https://www.dipromedic.com", "checked_on": "2026-10-28",
        "lines": [
            {"line": "Traufix", "owner": OWN_OWNER, "products": [
                {"id": "traufix_extremidad-superior_titan", "name": "TITAN", "documents": [
                    {"type": "tecnica_quirurgica", "label": "Técnica Quirúrgica", "url": TQ_URL},
                    {"type": "catalogo", "label": "Ver catálogo completo (página de categoría)", "url": CATALOG_URL}]},
                {"id": "traufix_extremidad-superior_telios", "name": "TELIOS", "documents": [
                    {"type": "catalogo", "label": "Ver catálogo completo (página de categoría)", "url": CATALOG_URL}]},
            ]},
            {"line": "Corentec", "owner": THIRD_OWNER, "products": [
                {"id": "corentec_cadera_m-stem", "name": "M-Stem", "documents": [
                    {"type": "brochure", "label": "Brochure", "url": COREN_URL}]}]},
            {"line": "Caleb", "owner": "Tercero (Corea)", "products": []},
        ],
        "pdfs": [
            pdf("Técnica Quirúrgica – TITAN Húmero Proximal", TQ_URL, "traufix.com/TITAN-Humero-Proximal-TQ-048.pdf"),
            pdf("Catálogo Traufix", CATALOG_URL, "dipromedic/catalogos/traufix/Catalogo-Traufix-ES.pdf"),
            pdf("Brochure – Vástago M-Stem", COREN_URL, "dipromedic/brochure/corentec/Bencox-M-Stem.pdf"),
            pdf("Brochure – Lavador Pulsátil E7", BROCHURE_URL, "dipromedic/brochure/caleb/E-7-brochure.pdf"),
            pdf("Ficha de un fabricante externo", "https://www.fabricante-externo.example/ficha.pdf", None),
        ],
    }


def write_local(root, rel: str, data: bytes):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def add_product(db, ref: str, name: str = "Producto real") -> Product:
    product = Product(organization_id=org_id(), name=name, family="Osteosíntesis", data_kind="REAL", external_ref=ref)
    db.add(product)
    db.commit()
    return product


def test_doc_type_from_label():
    assert cd.doc_type_from_label("Técnica Quirúrgica") == "tecnica_quirurgica"
    assert cd.doc_type_from_label("Técnica Qurúrgica") == "tecnica_quirurgica"      # la errata del sitio
    assert cd.doc_type_from_label("Técnica TIDIS II") == "tecnica_quirurgica"
    assert cd.doc_type_from_label("Brochure") == "folleto"
    assert cd.doc_type_from_label("Folleto no cementado") == "folleto"
    assert cd.doc_type_from_label("Ver catálogo de anclas") == "catalogo"
    assert cd.doc_type_from_label("Checklist") == "otro"
    assert cd.doc_type_from_label(None) == "otro"
    # Un nombre de archivo no es una validación: nunca se produce ficha_tecnica ni certificado.
    assert cd.doc_type_from_label("Ficha técnica certificado") not in {"ficha_tecnica", "certificado"}


def test_ingest_own_pdf_from_local(tmp_path):
    data = pdf_bytes("tq048") + b"\n% " + b"x" * 500
    write_local(tmp_path, "traufix.com/TITAN-Humero-Proximal-TQ-048.pdf", data)
    with SessionLocal() as db:
        product = add_product(db, "traufix_extremidad-superior_titan", "TITAN Placa bloqueada ALP")
        product_id = product.id
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        assert result["uploaded"] == 1
        doc = db.scalars(select(Document).where(Document.external_url == TQ_URL)).one()
        assert doc.data_kind == "REAL" and doc.scope == "producto" and doc.doc_type == "tecnica_quirurgica"
        assert doc.third_party is False and doc.review_status == "pendiente"
        assert doc.product_id == product_id
        assert doc.title == "Técnica Quirúrgica – TITAN Húmero Proximal"
        assert doc.watermark is None and doc.issuer_declared == "Sitio público traufix.com"
        [version] = doc.versions
        assert version.sha256 == hashlib.sha256(data).hexdigest()
        assert version.size_bytes == len(data) and version.content_type == "application/pdf"
        assert version.filename == "TITAN-Humero-Proximal-TQ-048.pdf"
        assert get_storage().get(version.storage_key) == data
        assert version.storage_key == f"org/{org_id()}/documents/{doc.id}/v1/TITAN-Humero-Proximal-TQ-048.pdf"
        actions = {e.action for e in db.scalars(select(AuditEvent).where(AuditEvent.resource_id == doc.id))}
        assert {"document.create", "document.version_upload"} <= actions
        # Idempotente por external_url: una segunda corrida no duplica nada.
        again = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        assert again["uploaded"] == 0 and again["skipped"] >= 1
        assert len(db.scalars(select(Document).where(Document.external_url == TQ_URL)).all()) == 1
        assert len(db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id)).all()) == 1


def test_ingested_pdf_is_downloadable_by_page_viewer(client, analista, tmp_path):
    write_local(tmp_path, "traufix.com/TITAN-Humero-Proximal-TQ-048.pdf", pdf_bytes("visor"))
    with SessionLocal() as db:
        cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        doc_id = db.scalars(select(Document.id).where(Document.external_url == TQ_URL)).one()
    r = download(client, analista, doc_id)
    assert r.status_code == 200 and r.content == pdf_bytes("visor")


def test_third_party_link_only(tmp_path, monkeypatch):
    downloaded = []
    monkeypatch.setattr(cd, "_download", lambda url, **k: downloaded.append(url) or pdf_bytes("propio"))
    monkeypatch.setattr(cd.time, "sleep", lambda s: None)
    # Aunque exista copia local y aunque el archivo viva en dipromedic.com, el de otra marca solo se enlaza.
    write_local(tmp_path, "dipromedic/brochure/corentec/Bencox-M-Stem.pdf", pdf_bytes("corentec"))
    with SessionLocal() as db:
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=True, catalog=mini_catalog())
        assert result["linked_external"] == 2          # Corentec en dipromedic.com + el dominio externo
        assert COREN_URL not in downloaded and not any("fabricante-externo" in u for u in downloaded)
        for url in (COREN_URL, "https://www.fabricante-externo.example/ficha.pdf"):
            doc = db.scalars(select(Document).where(Document.external_url == url)).one()
            assert doc.third_party is True and doc.data_kind == "REAL" and doc.versions == []
            assert doc.review_status == "pendiente"
        assert not [d for d in db.scalars(select(Document)).all() if d.third_party and d.versions]
        again = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=True, catalog=mini_catalog())
        assert again["linked_external"] == 0
        assert len(db.scalars(select(Document).where(Document.third_party.is_(True))).all()) == 2


def test_missing_product_creates_unlinked_document_and_reports(tmp_path):
    write_local(tmp_path, "traufix.com/TITAN-Humero-Proximal-TQ-048.pdf", pdf_bytes("sinproducto"))
    with SessionLocal() as db:
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        doc = db.scalars(select(Document).where(Document.external_url == TQ_URL)).one()
        assert doc.product_id is None and doc.versions
        assert {"url": TQ_URL, "reason": "producto_no_importado"} in result["errors"]
        # Al importar el producto, la siguiente corrida solo completa el vínculo.
        product = add_product(db, "traufix_extremidad-superior_titan")
        again = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        db.refresh(doc)
        assert doc.product_id == product.id and again["relinked"] == 1
        assert TQ_URL not in [e["url"] for e in again["errors"]]


def test_shared_catalog_is_not_linked_to_one_product(tmp_path):
    write_local(tmp_path, "dipromedic/catalogos/traufix/Catalogo-Traufix-ES.pdf", pdf_bytes("catalogo"))
    with SessionLocal() as db:
        add_product(db, "traufix_extremidad-superior_titan")
        add_product(db, "traufix_extremidad-superior_telios")
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        doc = db.scalars(select(Document).where(Document.external_url == CATALOG_URL)).one()
        assert doc.doc_type == "catalogo" and doc.product_id is None
        assert CATALOG_URL not in [e["url"] for e in result["errors"]]


def test_missing_local_copy_is_skipped_or_fetched(tmp_path, monkeypatch):
    with SessionLocal() as db:
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        assert result["uploaded"] == 0 and result["skipped"] == 3      # TQ, catálogo y folleto: sin copia local
        assert not db.scalars(select(Document).where(Document.external_url.is_not(None),
                                                     Document.third_party.is_(False))).all()
        calls = []

        def fake_download(url, **kwargs):
            calls.append(url)
            if url == BROCHURE_URL:
                raise cd.FetchError("http_404")
            return pdf_bytes("descargado")

        monkeypatch.setattr(cd, "_download", fake_download)
        monkeypatch.setattr(cd.time, "sleep", lambda s: None)
        result = cd.ingest_catalog_documents(db, org_id(), None, fetch=True, catalog=mini_catalog())
        assert result["uploaded"] == 2 and sorted(calls) == sorted([TQ_URL, CATALOG_URL, BROCHURE_URL])
        assert {"url": BROCHURE_URL, "reason": "http_404"} in result["errors"]
        assert not db.scalars(select(Document).where(Document.external_url == BROCHURE_URL)).all()


def test_known_broken_link_is_an_error_not_a_skip(tmp_path):
    catalog = mini_catalog()
    for pdf in catalog["pdfs"]:
        if pdf["url"] == TQ_URL:
            pdf.update(http_status=404, size_bytes=None, local_path=None)
    with SessionLocal() as db:
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=catalog)
        assert {"url": TQ_URL, "reason": "enlace_roto_http_404"} in result["errors"]
        assert result["skipped"] == 2                                       # catálogo y folleto: sin copia local
        assert not db.scalars(select(Document).where(Document.external_url == TQ_URL)).all()


def test_non_pdf_content_is_reported_not_stored(tmp_path):
    write_local(tmp_path, "traufix.com/TITAN-Humero-Proximal-TQ-048.pdf", b"<html>404 Not Found</html>")
    with SessionLocal() as db:
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        assert {"url": TQ_URL, "reason": "archivo_no_valido"} in result["errors"]
        assert not db.scalars(select(Document).where(Document.external_url == TQ_URL)).all()


def test_download_guard_allows_only_own_https_hosts(monkeypatch):
    monkeypatch.setattr(netguard, "resolve_host", lambda host: ["8.8.8.8"])       # sin red: IP pública fija
    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if path == "/ok.pdf":
            return httpx.Response(200, content=pdf_bytes("red"), headers={"content-type": "application/pdf"})
        if path == "/to-own.pdf":
            return httpx.Response(302, headers={"location": "https://www.dipromedic.com/ok.pdf"})
        if path == "/to-evil.pdf":
            return httpx.Response(302, headers={"location": "https://evil.example/ok.pdf"})
        if path == "/to-http.pdf":
            return httpx.Response(302, headers={"location": "http://traufix.com/ok.pdf"})
        if path == "/loop.pdf":
            return httpx.Response(302, headers={"location": f"https://{host}/loop.pdf"})
        if path == "/to-badport.pdf":
            return httpx.Response(302, headers={"location": "https://traufix.com:abc/ok.pdf"})
        if path == "/to-hugeport.pdf":
            return httpx.Response(302, headers={"location": "https://traufix.com:99999/ok.pdf"})
        if path == "/to-brokenhost.pdf":
            return httpx.Response(302, headers={"location": "https://[::1/ok.pdf"})
        if path == "/big.pdf":
            return httpx.Response(200, content=b"%PDF-" + b"0" * 2048)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    get = lambda url, **kw: cd._download(url, transport=transport, **kw)      # noqa: E731
    assert get("https://traufix.com/ok.pdf") == pdf_bytes("red")
    assert get("https://traufix.com/to-own.pdf") == pdf_bytes("red")           # redirección dentro de los hosts propios
    for url, reason in [("http://traufix.com/ok.pdf", "dominio_no_permitido"),
                        ("https://evil.example/ok.pdf", "dominio_no_permitido"),
                        ("https://traufix.com.evil.example/ok.pdf", "dominio_no_permitido"),
                        ("https://traufix.com/to-evil.pdf", "dominio_no_permitido"),
                        ("https://traufix.com/to-http.pdf", "dominio_no_permitido"),
                        ("https://traufix.com:abc/ok.pdf", "dominio_no_permitido"),
                        ("https://traufix.com:99999/ok.pdf", "dominio_no_permitido"),
                        ("https://[::1/ok.pdf", "dominio_no_permitido"),
                        ("https://traufix.com/loop.pdf", "demasiadas_redirecciones"),
                        ("https://traufix.com/missing.pdf", "http_404")]:
        with pytest.raises(cd.FetchError) as err:
            get(url)
        assert err.value.reason == reason, url
    # Un Location hostil (puerto no numérico o fuera de rango, host que urlparse rechaza) nunca escapa como ValueError:
    # httpx ya lo rechaza al construir la redirección (descarga_fallida) o lo detiene la validación propia.
    for path in ("to-badport.pdf", "to-hugeport.pdf", "to-brokenhost.pdf"):
        with pytest.raises(cd.FetchError) as err:
            get(f"https://traufix.com/{path}")
        assert err.value.reason in {"dominio_no_permitido", "descarga_fallida"}, path
    for url in ("https://traufix.com:abc/x.pdf", "https://traufix.com:99999/x.pdf", "https://[::1/x.pdf"):
        with pytest.raises(cd.FetchError) as err:
            get(url)
        assert err.value.reason == "dominio_no_permitido", url
    with pytest.raises(cd.FetchError) as err:
        get("https://traufix.com/big.pdf", max_bytes=1024)
    assert err.value.reason == "archivo_demasiado_grande"
    # netguard: un host propio que resuelve a una IP interna tampoco se consulta
    monkeypatch.setattr(netguard, "resolve_host", lambda host: ["10.0.0.5"])
    with pytest.raises(cd.FetchError) as err:
        get("https://traufix.com/ok.pdf")
    assert err.value.reason == "dominio_no_permitido"


def test_real_catalog_fixture_classification():
    """El fixture real: nada de otra marca se sube, aunque su archivo viva en dipromedic.com."""
    catalog = cd.load_catalog()
    inventory = cd.build_inventory(catalog)
    assert len(inventory) == 76
    third = [i for i in inventory if i.third_party]
    own = [i for i in inventory if not i.third_party]
    assert len(third) == 27 and len(own) == 49
    assert all(i.url.startswith("https://") for i in inventory)
    assert {i.doc_type for i in inventory} <= {"tecnica_quirurgica", "folleto", "catalogo", "otro"}
    # Las 4 rutas de Corentec, Biotechni, Anton-Hipp e IOT bajo dipromedic.com quedan como enlaces.
    assert all(i.third_party for i in inventory if any(m in i.url for m in
                                                      ("/corentec/", "/biotechni/", "/anton-hipp/", "/iot/", "/caleb/")))
    # Las de Traufix sí son propias, incluida la que ningún producto referencia (catálogo de medicina deportiva).
    assert not any(i.third_party for i in inventory if "traufix" in i.url or "sports_medicine" in i.url)
    with SessionLocal() as db:
        result = cd.ingest_catalog_documents(db, org_id(), None, fetch=False)
        assert result["linked_external"] == 27 and result["uploaded"] == 0
        assert len(db.scalars(select(Document).where(Document.third_party.is_(True))).all()) == 27
        # Los PDFs propios de más de 25 MB se crean como enlace (sin archivo) y no son de tercero.
        large = [i for i in own if (i.size_bytes or 0) > cd.CATALOG_DOC_MAX_BYTES]
        assert large and result["skipped_large"] == len(large)
        assert all(i.url in {e["url"] for e in result["large_files"]} for i in large)
        link_only = db.scalars(select(Document).where(Document.external_url.in_([i.url for i in large]))).unique().all()
        assert len(link_only) == len(large) and all(not d.third_party and not d.versions for d in link_only)


# ── Ronda de correcciones 1 ──────────────────────────────────────────────────

import time  # noqa: E402
import struct  # noqa: E402

from app.services import uploads  # noqa: E402


# I1 · pdf_page_count acotado ante PDFs hostiles

def test_pdf_page_count_is_bounded_on_hostile_input():
    hostile = b"%PDF-1.4\n" + b"/Type/Pages " * 175_000                 # ~2 MB, 175k coincidencias
    assert len(hostile) > 2_000_000
    started = time.perf_counter()
    assert uploads.pdf_page_count(hostile) is None                      # no se puede determinar: nunca se adivina
    assert time.perf_counter() - started < 1.0
    # También sin ningún "obj"/"endobj" cerca y con un diccionario enorme sin cerrar.
    started = time.perf_counter()
    assert uploads.pdf_page_count(b"%PDF-1.4\n1 0 obj\n<< /Type /Pages " + b"x" * 3_000_000) is None
    assert time.perf_counter() - started < 1.0
    # Un PDF normal sigue contándose.
    assert uploads.pdf_page_count(demo_documents.render_demo_pdf("Dos páginas", ["a", demo_documents.PAGE_BREAK, "b"])) == 2


# I2 · DOCX mal formados responden 422, no 500

def patch_zip_method(data: bytes, name: str, method: int) -> bytes:
    """Cambia el método de compresión declarado de una entrada (en la cabecera local y en el directorio central)."""
    out = bytearray(data)
    encoded = name.encode()
    for signature, offset in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
        start = 0
        while (start := out.find(signature, start)) != -1:
            name_len_at = start + (26 if signature == b"PK\x03\x04" else 28)
            name_len = struct.unpack_from("<H", out, name_len_at)[0]
            name_at = start + (30 if signature == b"PK\x03\x04" else 46)
            if bytes(out[name_at:name_at + name_len]) == encoded:
                struct.pack_into("<H", out, start + offset, method)
            start += 4
    return bytes(out)


def stored_docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types>0123456789</Types>")
        zf.writestr("word/document.xml", b"<w:document/>")
    return buf.getvalue()


def test_malformed_docx_is_422_not_500(client, analista):
    good = stored_docx()
    # CRC incorrecto en [Content_Types].xml (se altera un byte del contenido sin actualizar el CRC).
    bad_crc = good.replace(b"0123456789", b"0123456780", 1)
    assert bad_crc != good
    # Método de compresión no soportado (99 = AES) en [Content_Types].xml.
    unsupported = patch_zip_method(good, "[Content_Types].xml", 99)
    # Deflate corrupto.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types>" + b"abcdefghij" * 400 + b"</Types>")
        zf.writestr("word/document.xml", b"<w:document/>")
    raw = bytearray(buf.getvalue())
    start = raw.find(b"PK\x03\x04") + 30 + len(b"[Content_Types].xml")
    for i in range(start + 4, start + 14):
        raw[i] ^= 0xFF
    for label, blob in (("crc", bad_crc), ("compresion", unsupported), ("deflate", bytes(raw))):
        r = upload(client, analista, blob, filename="roto.docx", content_type=DOCX_CT)
        assert r.status_code == 422, (label, r.status_code, r.text)
        assert r.json()["code"] == "unsupported_file", label
    # Un DOCX sin macros, sin comprimir, sí pasa.
    assert upload(client, analista, good, filename="bueno.docx", content_type=DOCX_CT).status_code == 201


def test_malformed_docx_in_ingest_does_not_abort(tmp_path):
    # Un archivo de catálogo que no es PDF (ni DOCX válido) se reporta y la ingesta sigue con los demás.
    write_local(tmp_path, "traufix.com/TITAN-Humero-Proximal-TQ-048.pdf", patch_zip_method(stored_docx(), "[Content_Types].xml", 99))
    write_local(tmp_path, "dipromedic/catalogos/traufix/Catalogo-Traufix-ES.pdf", pdf_bytes("bueno"))
    with SessionLocal() as db:
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        assert {"url": TQ_URL, "reason": "archivo_no_valido"} in result["errors"]
        assert result["uploaded"] == 1


# M4 · un documento de tercero solo se enlaza

def test_cannot_upload_version_to_third_party_document(client, analista):
    url = "https://www.fabricante-externo.example/ficha.pdf"
    with SessionLocal() as db:
        doc = Document(organization_id=org_id(), code="EXT-2", title="Ficha del fabricante (tercero)", scope="producto",
                       data_kind="REAL", current_version=0, third_party=True, external_url=url)
        db.add(doc)
        db.commit()
        doc_id = doc.id
    r = upload_version(client, analista, doc_id, pdf_bytes("copia"))
    assert r.status_code == 409
    assert r.json()["code"] == "external_document"
    assert r.json()["details"] == {"external_url": url}
    with SessionLocal() as db:
        assert not db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc_id)).all()
        assert not [e for e in db.scalars(select(AuditEvent).where(AuditEvent.resource_id == doc_id))
                    if e.action == "document.version_upload"]
    assert get_storage().exists(f"org/{org_id()}/documents/{doc_id}/v1/ficha_v2.pdf") is False


# M1 · tope de ingesta: los PDFs propios grandes solo se enlazan

def test_large_own_pdf_is_link_only_not_third_party(client, analista, tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "CATALOG_DOC_MAX_BYTES", 1000)
    monkeypatch.setattr(cd.time, "sleep", lambda s: None)
    big_local = pdf_bytes("grande") + b"0" * 2000
    write_local(tmp_path, "traufix.com/TITAN-Humero-Proximal-TQ-048.pdf", big_local)              # local: 2 KB > tope
    catalog = mini_catalog()
    for pdf in catalog["pdfs"]:
        if pdf["url"] == CATALOG_URL:
            pdf["size_bytes"] = 5000                                                                # el fixture ya dice que pesa
    downloads = []
    with SessionLocal() as db:
        add_product(db, "traufix_extremidad-superior_titan")

    def fake_download(url, **kwargs):
        downloads.append((url, kwargs.get("max_bytes")))
        raise cd.FetchError("archivo_demasiado_grande")                                            # tamaño desconocido, excede al bajar

    monkeypatch.setattr(cd, "_download", fake_download)
    with SessionLocal() as db:
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=True, catalog=catalog)
        assert result["skipped_large"] == 3 and result["uploaded"] == 0
        assert {e["reason"] for e in result["large_files"]} == {"archivo_grande"}
        assert {e["url"] for e in result["large_files"]} == {TQ_URL, CATALOG_URL, BROCHURE_URL}
        assert not [e for e in result["errors"] if e["url"] in {TQ_URL, CATALOG_URL, BROCHURE_URL}]
        assert downloads == [(BROCHURE_URL, 1000)]                    # solo el de tamaño desconocido llegó a descargarse
        doc = db.scalars(select(Document).where(Document.external_url == TQ_URL)).one()
        assert doc.third_party is False and doc.versions == [] and doc.data_kind == "REAL" and doc.doc_type == "tecnica_quirurgica"
        doc_id = doc.id
        again = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=True, catalog=catalog)
        assert again["skipped_large"] == 0 and len(db.scalars(select(Document).where(Document.external_url == TQ_URL)).all()) == 1
    # La descarga de un documento propio sin archivo responde 409 con su URL de origen.
    r = download(client, analista, doc_id)
    assert r.status_code == 409 and r.json()["code"] == "external_document"
    assert r.json()["details"] == {"external_url": TQ_URL}


def test_ingest_cap_default_is_25_mb():
    assert cd.CATALOG_DOC_MAX_BYTES == 25 * 1024 * 1024


# M7 · reparación de objetos perdidos del almacenamiento

def test_ingest_repairs_lost_object(tmp_path):
    data = pdf_bytes("reparar") + b"0" * 300
    local = write_local(tmp_path, "traufix.com/TITAN-Humero-Proximal-TQ-048.pdf", data)
    storage = get_storage()
    with SessionLocal() as db:
        cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        doc = db.scalars(select(Document).where(Document.external_url == TQ_URL)).one()
        key = doc.versions[0].storage_key
        assert storage.exists(key)
        # Sin pérdida, la segunda corrida no sube nada ni repara nada.
        again = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        assert again["repaired"] == 0 and again["uploaded"] == 0
        # El objeto se pierde (disco efímero) y la siguiente corrida lo repone con el mismo contenido.
        storage.delete(key)
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        assert result["repaired"] == 1 and result["uploaded"] == 0
        assert storage.get(key) == data
        assert len(db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id)).all()) == 1
        # Si el origen cambió (hash distinto), no se sobrescribe: se reporta.
        storage.delete(key)
        local.write_bytes(data + b"cambio")
        result = cd.ingest_catalog_documents(db, org_id(), tmp_path, fetch=False, catalog=mini_catalog())
        assert {"url": TQ_URL, "reason": "hash_distinto"} in result["errors"] and result["repaired"] == 0
        assert not storage.exists(key)
        # Sin origen disponible tampoco se puede reparar: se reporta.
        result = cd.ingest_catalog_documents(db, org_id(), None, fetch=False, catalog=mini_catalog())
        assert {"url": TQ_URL, "reason": "archivo_perdido"} in result["errors"]


def test_inventory_titles_fit_the_title_column():
    """Los catálogos compartidos traen el título de cada ficha pegado con «; » (hasta 600+ caracteres) y
    `documents.title` es VARCHAR(500): en Postgres el INSERT fallaba (SQLite no lo hace cumplir)."""
    inventory = cd.build_inventory(cd.load_catalog())
    assert max(len(i.title) for i in inventory) <= 200
    long_title = "; ".join(f"Ver catálogo de misceláneos – Pieza {n} " + "x" * 40 for n in range(15))
    catalog = mini_catalog()
    catalog["pdfs"][0]["title"] = long_title
    short = cd.build_inventory(catalog)[0].title
    assert len(short) <= 200 and short.startswith("Ver catálogo de misceláneos – Pieza 0") and short.endswith("y 14 más")
    assert cd.build_inventory(mini_catalog())[0].title == "Técnica Quirúrgica – TITAN Húmero Proximal"
