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
