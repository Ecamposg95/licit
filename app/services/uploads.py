"""Validación y almacenamiento de archivos cargados (frente D2).

Lo que decide el tipo es el contenido (firma), nunca el nombre ni el `Content-Type` que declara el cliente.
El nombre se sanea, el contenido se hashea con SHA-256 y cada carga nueva crea una versión; las anteriores
se conservan. Todo cambio se audita en la misma transacción.
"""
import hashlib
import io
import re
import unicodedata
import zipfile
import zlib
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import config
from app.core.errors import AppError
from app.models import Document, DocumentVersion
from app.services import audit
from app.services.storage import get_storage

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PNG = "image/png"
JPEG = "image/jpeg"

# Extensiones aceptadas por tipo detectado (en minúsculas; el nombre puede venir en mayúsculas).
EXTENSIONS = {PDF: (".pdf",), DOCX: (".docx",), PNG: (".png",), JPEG: (".jpg", ".jpeg")}
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_FILENAME = 120

SCOPES = ("empresa", "producto", "expediente")


def _unsupported(message: str) -> AppError:
    return AppError(422, "unsupported_file", message)


# Todo lo que puede salir al leer un ZIP mal formado: CRC, método de compresión no soportado, deflate corrupto, etc.
_ZIP_ERRORS = (zipfile.BadZipFile, NotImplementedError, zlib.error, OSError, ValueError, RuntimeError, EOFError,
               OverflowError)


def _sniff_docx(data: bytes) -> str:
    try:
        return _inspect_docx(data)
    except _ZIP_ERRORS:
        raise _unsupported("El archivo no es un documento válido (el ZIP está dañado o usa un formato no admitido).") \
            from None


def _inspect_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED_BYTES:
            raise AppError(422, "archive_too_large",
                           "El contenido descomprimido del archivo supera 50 MB; no se acepta.")
        names = {i.filename.lower() for i in infos}
        if "[content_types].xml" not in names or "word/document.xml" not in names:
            raise _unsupported("Solo se aceptan PDF, DOCX, PNG y JPEG; este archivo no es un DOCX.")
        content_types = next(i for i in infos if i.filename.lower() == "[content_types].xml")
        declared = archive.read(content_types).decode("utf-8", errors="ignore").lower()
        if any(n.endswith("vbaproject.bin") or n.endswith("vbadata.xml") for n in names) \
                or "macroenabled" in declared:
            raise _unsupported("Los documentos con macros no se aceptan.")
    return DOCX


def sniff_content_type(data: bytes, filename: str) -> str:
    """Tipo real por firma: PDF, DOCX sin macros, PNG o JPEG. Si no, `AppError(422, "unsupported_file")`.
    La extensión del nombre debe corresponder al contenido (se compara en minúsculas)."""
    if not data:
        raise AppError(422, "empty_file", "El archivo está vacío (0 bytes).")
    if data.startswith(b"%PDF-"):
        kind = PDF
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = PNG
    elif data.startswith(b"\xff\xd8\xff"):
        kind = JPEG
    elif data.startswith(b"PK\x03\x04"):
        kind = _sniff_docx(data)
    else:
        raise _unsupported("Solo se aceptan PDF, DOCX (sin macros), PNG y JPEG.")
    ext = _extension(filename)
    if ext and ext not in EXTENSIONS[kind]:
        raise _unsupported(f"La extensión «{ext}» no corresponde al contenido del archivo ({EXTENSIONS[kind][0]}).")
    return kind


def _extension(filename: str) -> str:
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    dot = base.rfind(".")
    return base[dot:].lower() if dot > 0 else ""


def sanitize_filename(name: str) -> str:
    """Solo el nombre base, sin `..` ni separadores ni caracteres de control. Conserva acentos.
    Se limita a 120 caracteres respetando la extensión. Un nombre vacío queda como «documento»."""
    base = unicodedata.normalize("NFC", name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C")
    base = re.sub(r'[<>:"|?*]', "", base).replace("..", "")
    base = re.sub(r"\s+", " ", base).strip(" .")
    if not base:
        return "documento"
    if len(base) > MAX_FILENAME:
        dot = base.rfind(".")
        ext = base[dot:] if 0 < dot and len(base) - dot <= 10 else ""
        base = base[:MAX_FILENAME - len(ext)].rstrip(" .") + ext
    return base


def validate_upload(data: bytes, filename: str, max_bytes: int | None = None) -> tuple[str, str]:
    """Devuelve `(content_type, nombre saneado)` o lanza `AppError` (422 vacío/tipo, 413 tamaño)."""
    limit = config.DOCUMENT_MAX_BYTES if max_bytes is None else max_bytes
    if not data:
        raise AppError(422, "empty_file", "El archivo está vacío (0 bytes).")
    if len(data) > limit:
        raise AppError(413, "file_too_large", f"El archivo supera el máximo de {limit // (1024 * 1024)} MB.",
                       {"max_bytes": limit})
    safe = sanitize_filename(filename)
    content_type = sniff_content_type(data, safe)
    if not _extension(safe):
        safe += EXTENSIONS[content_type][0]
    return content_type, safe


_PAGES_MARK = re.compile(rb"/Type\s*/Pages\b")
_MAX_PAGES_NODES = 100          # un PDF con más nodos /Pages que esto no se inspecciona: se devuelve None
_WINDOW_BEFORE = 512            # cuánto se mira hacia atrás para encontrar «N G obj»
_WINDOW_AFTER = 4096            # cuánto se mira hacia adelante para encontrar «endobj»


def pdf_page_count(data: bytes) -> int | None:
    """Páginas leídas del `/Count` del nodo raíz de páginas. `None` si no se puede determinar con certeza
    (PDF con objetos comprimidos, nodos demasiado grandes o más de 100 nodos `/Pages`): es mejor no saberlo que
    inventarlo. Las ventanas de búsqueda están acotadas, así que el costo es lineal incluso con PDFs hostiles."""
    count = None
    for inspected, mark in enumerate(_PAGES_MARK.finditer(data)):
        if inspected >= _MAX_PAGES_NODES:
            return None
        start = data.rfind(b"obj", max(0, mark.start() - _WINDOW_BEFORE), mark.start())
        end = data.find(b"endobj", mark.end(), mark.end() + _WINDOW_AFTER)
        if start < 0 or end < 0:
            continue
        body = data[start:end]
        if re.search(rb"/Parent\b", body):
            continue
        found = re.search(rb"/Count\s+(\d+)", body)
        if found:
            count = int(found.group(1))
    return count if count and count > 0 else None


def create_document(db: Session, user, *, title: str, scope: str, doc_type: str | None, data_kind: str,
                    product_id: str | None = None, opportunity_id: str | None = None,
                    valid_until: date | None = None, organization_id: str | None = None, **extra) -> Document:
    """Crea el registro del documento (sin versiones) y lo audita. `user` puede ser None (ingesta por CLI)."""
    org_id = organization_id or user.organization_id
    doc = Document(
        organization_id=org_id, title=title.strip(), scope=scope, doc_type=doc_type, data_kind=data_kind,
        valid_until=valid_until, product_id=product_id, opportunity_id=opportunity_id,
        review_status="pendiente", current_version=0,
        watermark=config.WATERMARK if data_kind == "SYNTHETIC" else None,
        owner_id=user.id if user else None, **extra,
    )
    db.add(doc)
    db.flush()
    doc.code = doc.code or f"DOC-{doc.id[:8].upper()}"
    audit.record(db, organization_id=org_id, actor_id=user.id if user else None, action="document.create",
                 resource_type="document", resource_id=doc.id,
                 after=audit.snapshot(doc, ["code", "title", "scope", "doc_type", "data_kind", "valid_until",
                                            "product_id", "opportunity_id", "third_party", "external_url"]))
    return doc


def store_version(db: Session, user, document: Document, data: bytes, filename: str, note: str | None,
                  *, max_bytes: int | None = None) -> DocumentVersion:
    """Valida, hashea, guarda el archivo y crea la versión siguiente (las anteriores se conservan).

    Clave: `org/{org_id}/documents/{doc_id}/v{n}/{filename}`. Audita `document.version_upload` en la misma
    transacción; quien llama hace el commit. Una versión nueva anula la revisión previa del documento: la
    validación de un humano aplica al contenido que revisó, no al que lo reemplaza."""
    content_type, safe_name = validate_upload(data, filename, max_bytes)
    # Serializa cargas simultáneas del mismo documento (en SQLite no hace nada).
    db.scalar(select(Document.id).where(Document.id == document.id).with_for_update())
    previous = db.scalar(select(func.max(DocumentVersion.version)).where(DocumentVersion.document_id == document.id)) or 0
    number = previous + 1
    sha256 = hashlib.sha256(data).hexdigest()
    key = f"org/{document.organization_id}/documents/{document.id}/v{number}/{safe_name}"
    get_storage().put(key, data, content_type)
    version = DocumentVersion(
        organization_id=document.organization_id, document_id=document.id, version=number, filename=safe_name,
        content_type=content_type, size_bytes=len(data), sha256=sha256, storage_key=key,
        uploaded_by_id=user.id if user else None, note=(note or "").strip() or None,
    )
    document.versions.append(version)
    before = {"current_version": document.current_version, "review_status": document.review_status}
    document.current_version = number
    if number > 1:
        document.review_status = "pendiente"
    if content_type == PDF:
        document.page_count = pdf_page_count(data)
    db.flush()
    audit.record(db, organization_id=document.organization_id, actor_id=user.id if user else None,
                 action="document.version_upload", resource_type="document", resource_id=document.id,
                 before=before,
                 after={"current_version": number, "review_status": document.review_status, "version": number,
                        "filename": safe_name, "content_type": content_type, "size_bytes": len(data),
                        "sha256": sha256, "note": version.note})
    return version
