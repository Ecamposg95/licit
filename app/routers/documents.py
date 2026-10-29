"""Centro documental: listado, carga con versiones y descarga autorizada (frente D)."""
import io
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import Perm, require_permission
from app.core.tenant import get_owned
from app.models import DataKind, Document, Opportunity, Product, User
from app.schemas.documents import DocumentOut, DocumentVersionOut
from app.schemas.v1 import UserRef
from app.services import audit, uploads
from app.services.storage import get_storage

router = APIRouter(prefix="/api/v1/documents", tags=["documentos"])

DOC_TYPES = {"certificado", "ficha_tecnica", "carta", "constancia", "catalogo", "bases", "registro",
             "tecnica_quirurgica", "folleto", "otro"}


# ── Serialización ────────────────────────────────────────────────────────────

def _documents_out(db: Session, docs: list[Document]) -> list[DocumentOut]:
    """Agrega lo que el ORM no resuelve solo: quién subió cada versión y el nombre del producto."""
    user_ids = {v.uploaded_by_id for d in docs for v in d.versions if v.uploaded_by_id}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    product_ids = {d.product_id for d in docs if d.product_id}
    products = {p.id: p.name for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))} \
        if product_ids else {}
    out = []
    for d in docs:
        item = DocumentOut.model_validate(d)
        item.product_name = products.get(d.product_id)
        for v_out, v in zip(item.versions, d.versions):
            v_out.has_file = bool(v.storage_key)
            if v.uploaded_by_id in users:
                v_out.uploaded_by = UserRef.model_validate(users[v.uploaded_by_id])
        out.append(item)
    return out


def _version_out(db: Session, document: Document, version) -> DocumentVersionOut:
    return next(v for v in _documents_out(db, [document])[0].versions if v.version == version.version)


def _read_upload(file: UploadFile) -> bytes:
    # Se lee un byte más del máximo: basta para rechazar sin cargar en memoria un cuerpo enorme.
    return file.file.read(config.DOCUMENT_MAX_BYTES + 1)


# ── Consulta ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DocumentOut])
def list_documents(scope: str | None = None, data_kind: list[str] = Query(default=[]),
                   doc_type: str | None = None, q: str | None = None, product_id: str | None = None,
                   opportunity_id: str | None = None, db: Session = Depends(get_db),
                   user: User = Depends(require_permission(Perm.DOCUMENT_READ))):
    stmt = select(Document).where(Document.organization_id == user.organization_id)
    if scope:
        stmt = stmt.where(Document.scope == scope)
    if data_kind:
        stmt = stmt.where(Document.data_kind.in_(data_kind))
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if product_id:
        stmt = stmt.where(Document.product_id == product_id)
    if opportunity_id:
        stmt = stmt.where(Document.opportunity_id == opportunity_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Document.title.ilike(like), Document.code.ilike(like)))
    docs = list(db.scalars(stmt.order_by(Document.code, Document.title)).unique())
    return _documents_out(db, docs)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db),
                 user: User = Depends(require_permission(Perm.DOCUMENT_READ))):
    return _documents_out(db, [get_owned(db, Document, document_id, user, "Documento")])[0]


# ── Carga ────────────────────────────────────────────────────────────────────

def _invalid(field: str, message: str) -> AppError:
    return AppError(422, "validation_error", "Datos inválidos", [{"field": field, "message": message}])


@router.post("", response_model=DocumentOut, status_code=201)
def create_document(file: UploadFile = File(...), title: str = Form(...), scope: str = Form(...),
                    doc_type: str | None = Form(None), data_kind: str = Form("REAL"),
                    product_id: str | None = Form(None), opportunity_id: str | None = Form(None),
                    valid_until: str | None = Form(None), db: Session = Depends(get_db),
                    user: User = Depends(require_permission(Perm.DOCUMENT_UPLOAD))):
    title = " ".join(title.split())
    if not title or len(title) > 500:
        raise _invalid("title", "El título es obligatorio y admite hasta 500 caracteres.")
    if scope not in uploads.SCOPES:
        raise _invalid("scope", "El ámbito debe ser empresa, producto o expediente.")
    if data_kind not in {k.value for k in DataKind}:
        raise _invalid("data_kind", "El tipo de dato debe ser REAL, HISTORICAL o SYNTHETIC.")
    doc_type = (doc_type or "").strip() or None
    if doc_type and doc_type not in DOC_TYPES:
        raise _invalid("doc_type", "Tipo de documento no reconocido.")
    expires = None
    if valid_until and valid_until.strip():
        try:
            expires = date.fromisoformat(valid_until.strip())
        except ValueError:
            raise _invalid("valid_until", "La vigencia debe tener el formato AAAA-MM-DD.") from None
    if product_id:
        get_owned(db, Product, product_id, user, "Producto")
    if opportunity_id:
        get_owned(db, Opportunity, opportunity_id, user, "Procedimiento")

    data = _read_upload(file)
    # Se valida antes de crear nada: un archivo rechazado no deja un documento vacío.
    uploads.validate_upload(data, file.filename or "")
    doc = uploads.create_document(db, user, title=title, scope=scope, doc_type=doc_type, data_kind=data_kind,
                                  product_id=product_id or None, opportunity_id=opportunity_id or None,
                                  valid_until=expires)
    uploads.store_version(db, user, doc, data, file.filename or "", None)
    db.commit()
    db.refresh(doc)
    return _documents_out(db, [doc])[0]


@router.post("/{document_id}/versions", response_model=DocumentVersionOut, status_code=201)
def upload_version(document_id: str, file: UploadFile = File(...), note: str | None = Form(None),
                   db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.DOCUMENT_UPLOAD))):
    doc = get_owned(db, Document, document_id, user, "Documento")
    data = _read_upload(file)
    version = uploads.store_version(db, user, doc, data, file.filename or "", note)
    db.commit()
    db.refresh(doc)
    return _version_out(db, doc, version)


# ── Descarga ─────────────────────────────────────────────────────────────────

def _content_disposition(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "").strip() or "documento"
    return f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _chunks(data: bytes, size: int = 64 * 1024):
    view = io.BytesIO(data)
    while chunk := view.read(size):
        yield chunk


@router.get("/{document_id}/versions/{version}/download")
def download_version(document_id: str, version: int, db: Session = Depends(get_db),
                     user: User = Depends(require_permission(Perm.DOCUMENT_READ))):
    """Entrega el archivo de una versión (`inline`, para el visor). Cada descarga queda en la bitácora."""
    doc = get_owned(db, Document, document_id, user, "Documento")
    row = next((v for v in doc.versions if v.version == version), None)
    if row is None or not row.storage_key:
        if doc.third_party and doc.external_url:
            raise AppError(409, "external_document",
                           "Es un documento de tercero: solo se enlaza, no se almacena en esta plataforma.",
                           {"external_url": doc.external_url})
        if row is None:
            raise AppError(404, "not_found", "Versión no encontrada")
        raise AppError(404, "file_missing", "Esta versión no tiene un archivo adjunto.")
    try:
        data = get_storage().get(row.storage_key)
    except FileNotFoundError:
        raise AppError(404, "file_missing",
                       "El archivo de esta versión ya no está en el almacenamiento.") from None
    audit.record(db, organization_id=doc.organization_id, actor_id=user.id, action="document.download",
                 resource_type="document", resource_id=doc.id,
                 after={"version": row.version, "filename": row.filename, "sha256": row.sha256})
    db.commit()    # libera el bloqueo de la bitácora antes de transmitir
    return StreamingResponse(_chunks(data), media_type=row.content_type or "application/octet-stream", headers={
        "Content-Length": str(len(data)),
        "Content-Disposition": _content_disposition(row.filename or "documento"),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    })
