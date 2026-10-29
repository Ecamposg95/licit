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
