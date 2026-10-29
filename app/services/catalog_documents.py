"""Ingesta de los PDFs del catálogo de Dipromedic y Traufix como evidencia REAL (frente D5).

Los PDFs propios (técnicas quirúrgicas, folletos y catálogos de Dipromedic/Traufix) de hasta 25 MB se guardan con
su SHA-256 para poder citarlos por página; los más grandes se crean como enlace a su sitio de origen. Los de otras
marcas (Corentec, Biotechni, Anton-Hipp, IOT, Caleb…) solo se enlazan, aunque el archivo viva en dipromedic.com:
su reutilización no está cubierta por el aviso de Dipromedic.
Ningún nombre de archivo se toma como validación: nunca se produce `ficha_tecnica` ni `certificado`.
"""
import hashlib
import json
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Document, Product
from app.services import audit, uploads
from app.services.storage import get_storage

OWN_HOSTS = {"dipromedic.com", "www.dipromedic.com", "traufix.com", "www.traufix.com"}
# Tope por archivo, tanto para copias locales como para descargas. Los PDFs propios más grandes se crean como
# documento de enlace (sin archivo) y se cuentan en `skipped_large`.
CATALOG_DOC_MAX_BYTES = 25 * 1024 * 1024
FETCH_TIMEOUT = 60.0
MAX_REDIRECTS = 3
USER_AGENT = "LicitDemo/1.0 (+contacto Atlas Technologies)"
LOCAL_PREFIX = "docs/research/dipromedic/pdfs/"
FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "catalogo_dipromedic.json"


# ── Descarga (validación mínima de dominio) ──────────────────────────────────

class FetchError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _require_own_https(url: str) -> None:
    try:
        parts = urlparse(url)
        host, port = (parts.hostname or "").lower(), parts.port       # `.port` lanza ValueError con «:abc» o «:99999»
    except ValueError:
        raise FetchError("dominio_no_permitido") from None
    if parts.scheme != "https" or host not in OWN_HOSTS or parts.username or parts.password \
            or port not in (None, 443):
        raise FetchError("dominio_no_permitido")


def _download(url: str, *, max_bytes: int | None = None, timeout: float = FETCH_TIMEOUT,
              transport: httpx.BaseTransport | None = None) -> bytes:
    """GET de un PDF en un host propio (solo https; las redirecciones también deben quedar en hosts propios).
    TODO(integración): usar netguard.safe_get (frente C4) en lugar de esta validación mínima."""
    limit = CATALOG_DOC_MAX_BYTES if max_bytes is None else max_bytes
    current = url
    try:
        with httpx.Client(transport=transport, follow_redirects=False, headers={"User-Agent": USER_AGENT},
                          timeout=httpx.Timeout(timeout, connect=10.0)) as client:
            for _ in range(MAX_REDIRECTS + 1):
                _require_own_https(current)
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        try:
                            current = urljoin(current, response.headers.get("location", ""))
                        except ValueError:
                            raise FetchError("dominio_no_permitido") from None
                        continue
                    if response.status_code != 200:
                        raise FetchError(f"http_{response.status_code}")
                    declared = response.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > limit:
                        raise FetchError("archivo_demasiado_grande")
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise FetchError("archivo_demasiado_grande")
                        chunks.append(chunk)
                    return b"".join(chunks)
    except (httpx.HTTPError, httpx.InvalidURL):
        raise FetchError("descarga_fallida") from None
    raise FetchError("demasiadas_redirecciones")


# ── Inventario a partir del fixture ──────────────────────────────────────────

def _plain(text: str | None) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower().strip()


def _short_title(title: str, limit: int = 200) -> str:
    """Los catálogos compartidos traen el título de cada ficha pegado con «; » (más de 600 caracteres), y
    `documents.title` es VARCHAR(500). Se deja el primero y se cuenta el resto."""
    if len(title) <= limit:
        return title
    first, *rest = title.split("; ")
    suffix = f" y {len(rest)} más" if rest else ""
    room = limit - len(suffix)
    if len(first) > room:
        first = first[:room - 1].rstrip() + "…"
    return first + suffix


def doc_type_from_label(label: str | None) -> str:
    """Etiqueta del sitio → tipo de documento. Nunca `ficha_tecnica` ni `certificado`: eso lo decide una persona."""
    text = _plain(label)
    if text.startswith("tecnica"):
        return "tecnica_quirurgica"
    if "brochure" in text or "folleto" in text:
        return "folleto"
    if "catalogo" in text:
        return "catalogo"
    return "otro"


@dataclass
class Entry:
    url: str
    title: str
    doc_type: str
    third_party: bool
    local_path: str | None = None
    http_status: int | None = None
    size_bytes: int | None = None
    product_refs: list[str] = field(default_factory=list)


def load_catalog() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _is_third_party_line(owner: str | None) -> bool:
    return _plain(owner).startswith("tercero")


def build_inventory(catalog: dict) -> list[Entry]:
    """Un `Entry` por URL (primero el orden de `pdfs[]`, luego las que solo aparecen en fichas de producto)."""
    refs: dict[str, dict] = {}
    for line in catalog.get("lines", []):
        third = _is_third_party_line(line.get("owner"))
        for product in line.get("products", []):
            for doc in product.get("documents", []):
                ref = refs.setdefault(doc["url"], {"labels": [], "products": [], "third": []})
                ref["labels"].append(doc.get("label"))
                ref["products"].append(product["id"])
                ref["third"].append(third)
    # Archivos que ninguna ficha referencia: se clasifican por la carpeta donde viven sus hermanos.
    by_dir: dict[str, list[bool]] = {}
    for url, ref in refs.items():
        by_dir.setdefault(url.rsplit("/", 1)[0], []).extend(ref["third"])

    pdfs = {p["url"]: p for p in catalog.get("pdfs", [])}
    entries = []
    for url in [*pdfs, *[u for u in refs if u not in pdfs]]:
        pdf, ref = pdfs.get(url, {}), refs.get(url)
        parts = urlparse(url)
        if ref:
            third_line = any(ref["third"])
        else:
            third_line = any(by_dir.get(url.rsplit("/", 1)[0], []))
        label = next((lab for lab in (ref["labels"] if ref else []) if lab), None)
        doc_type = doc_type_from_label(label) if label else doc_type_from_label(pdf.get("title"))
        name = unquote(PurePosixPath(parts.path).name)
        entries.append(Entry(
            url=url, title=_short_title(pdf.get("title") or (f"{label} · {name}" if label else name)),
            doc_type=doc_type,
            third_party=parts.scheme != "https" or (parts.hostname or "").lower() not in OWN_HOSTS or third_line,
            local_path=pdf.get("local_path"), http_status=pdf.get("http_status"), size_bytes=pdf.get("size_bytes"),
            product_refs=list(dict.fromkeys(ref["products"])) if ref else [],
        ))
    return entries


def _local_file(local_root: Path | None, entry: Entry) -> Path | None:
    if local_root is None or not entry.local_path:
        return None
    relative = entry.local_path.removeprefix(LOCAL_PREFIX)
    root = Path(local_root).resolve()
    path = (root / relative).resolve()
    return path if path.is_relative_to(root) and path.is_file() else None


# ── Ingesta ──────────────────────────────────────────────────────────────────

def _code(url: str) -> str:
    return "CAT-" + hashlib.sha1(url.encode()).hexdigest()[:10].upper()


class _TooLarge(Exception):
    """El archivo propio supera `CATALOG_DOC_MAX_BYTES`: se enlaza en vez de guardarse."""


class _NoSource(Exception):
    """No hay copia local ni se pidió descargar."""


def _read_own_pdf(entry: Entry, local_root: Path | None, fetch: bool, state: dict) -> bytes:
    """Bytes de un PDF propio, de la copia local o de una descarga. Lanza `_TooLarge`, `_NoSource` o `FetchError`."""
    local = _local_file(local_root, entry)
    if local is not None:
        if local.stat().st_size > CATALOG_DOC_MAX_BYTES:
            raise _TooLarge
        return local.read_bytes()
    if entry.size_bytes is not None and entry.size_bytes > CATALOG_DOC_MAX_BYTES:
        raise _TooLarge                       # el propio catálogo dice cuánto pesa: ni siquiera se descarga
    if not fetch:
        raise _NoSource
    if state["fetched"]:
        time.sleep(1.0)                       # cortesía con el sitio: una descarga a la vez, con pausa
    state["fetched"] = True
    try:
        return _download(entry.url, max_bytes=CATALOG_DOC_MAX_BYTES)
    except FetchError as err:
        if err.reason == "archivo_demasiado_grande":
            raise _TooLarge from None
        raise


def ingest_catalog_documents(db: Session, org_id: str, local_root: Path | None, fetch: bool,
                             catalog: dict | None = None) -> dict:
    """Crea los `Document` REAL del catálogo. Idempotente por `external_url`. Hace commit por documento.

    - Hosts y marcas propios: el PDF se lee de `local_root` (carpeta espejo de `docs/research/dipromedic/pdfs`)
      o, con `fetch=True`, se descarga (máx. 25 MB, 60 s). Se guarda con SHA-256 como versión 1. Si pesa más de
      25 MB se crea como documento de enlace (sin archivo, `third_party=False`) y se cuenta en `skipped_large`.
    - Otras marcas o dominios: documento de tercero, solo con enlace y sin archivo.
    - Se vincula al `Product` por `external_ref` cuando la ficha lo referencia una sola; un PDF compartido por
      varias fichas (un catálogo) queda sin producto. Si el producto no está importado, el documento se crea sin
      vínculo y se reporta `producto_no_importado`; la siguiente corrida completa el vínculo.
    - Si un documento propio ya existe pero su objeto desapareció del almacenamiento (disco efímero), se vuelve a
      subir desde la misma fuente siempre que el contenido sea idéntico (mismo SHA-256); si cambió, se reporta
      `hash_distinto` y no se sobrescribe.

    Devuelve `{uploaded, linked_external, skipped, skipped_large, relinked, repaired, errors: [{url, reason}],
    large_files: [{url, reason: "archivo_grande", size_bytes}]}`."""
    entries = build_inventory(catalog if catalog is not None else load_catalog())
    products = {ref: pid for pid, ref in db.execute(select(Product.id, Product.external_ref).where(
        Product.organization_id == org_id, Product.external_ref.is_not(None)))}
    result: dict = {"uploaded": 0, "linked_external": 0, "skipped": 0, "skipped_large": 0, "relinked": 0,
                    "repaired": 0, "errors": [], "large_files": []}
    state = {"fetched": False}
    storage = get_storage()

    def error(entry: Entry, reason: str) -> None:
        result["errors"].append({"url": entry.url, "reason": reason})

    for entry in entries:
        product_id, missing_product = None, False
        if len(entry.product_refs) == 1:
            product_id = products.get(entry.product_refs[0])
            missing_product = product_id is None

        existing = db.scalars(select(Document).where(
            Document.organization_id == org_id, Document.external_url == entry.url)).first()
        if existing is not None:
            if existing.product_id is None and product_id:
                existing.product_id = product_id
                audit.record(db, organization_id=org_id, actor_id=None, action="document.link_product",
                             resource_type="document", resource_id=existing.id,
                             before={"product_id": None}, after={"product_id": product_id})
                db.commit()
                result["relinked"] += 1
            if missing_product:
                error(entry, "producto_no_importado")
            version = existing.versions[-1] if existing.versions else None
            if not existing.third_party and version is not None and version.storage_key \
                    and not storage.exists(version.storage_key):
                _repair(db, entry, existing, version, local_root, fetch, state, storage, result)
            else:
                result["skipped"] += 1
            continue

        data = None
        too_large = False
        if not entry.third_party:
            if entry.http_status not in (None, 200):
                error(entry, f"enlace_roto_http_{entry.http_status}")
                continue
            try:
                data = _read_own_pdf(entry, local_root, fetch, state)
            except _TooLarge:
                too_large = True
            except _NoSource:
                result["skipped"] += 1        # sin copia local y sin --fetch
                continue
            except FetchError as err:
                error(entry, err.reason)
                continue
            if data is not None:
                filename = unquote(PurePosixPath(urlparse(entry.url).path).name)
                try:
                    content_type, _ = uploads.validate_upload(data, filename, CATALOG_DOC_MAX_BYTES)
                    if content_type != uploads.PDF:
                        raise AppError(422, "unsupported_file", "No es un PDF")
                except AppError as err:
                    error(entry, "archivo_demasiado_grande" if err.status == 413 else "archivo_no_valido")
                    continue

        host = (urlparse(entry.url).hostname or "").removeprefix("www.")
        doc = uploads.create_document(
            db, None, organization_id=org_id, title=entry.title, scope="producto", doc_type=entry.doc_type,
            data_kind="REAL", product_id=product_id, code=_code(entry.url), third_party=entry.third_party,
            external_url=entry.url, issuer_declared=f"Sitio público {host}" if host else None)
        if data is not None:
            uploads.store_version(db, None, doc, data, unquote(PurePosixPath(urlparse(entry.url).path).name),
                                  "Descargado del sitio público de Dipromedic/Traufix.",
                                  max_bytes=CATALOG_DOC_MAX_BYTES)
            result["uploaded"] += 1
        elif too_large:
            result["skipped_large"] += 1
            result["large_files"].append({"url": entry.url, "reason": "archivo_grande", "size_bytes": entry.size_bytes})
        else:
            result["linked_external"] += 1
        db.commit()
        if missing_product:
            error(entry, "producto_no_importado")
    return result


def _repair(db: Session, entry: Entry, doc: Document, version, local_root: Path | None, fetch: bool, state: dict,
            storage, result: dict) -> None:
    """Repone el objeto perdido de un documento propio si la fuente da exactamente el mismo contenido."""
    try:
        data = _read_own_pdf(entry, local_root, fetch, state)
    except (_TooLarge, _NoSource):
        result["errors"].append({"url": entry.url, "reason": "archivo_perdido"})
        return
    except FetchError as err:
        result["errors"].append({"url": entry.url, "reason": err.reason})
        return
    if hashlib.sha256(data).hexdigest() != version.sha256:
        # El origen cambió: sobrescribir invalidaría las citas por hash y página. Lo decide una persona.
        result["errors"].append({"url": entry.url, "reason": "hash_distinto"})
        return
    storage.put(version.storage_key, data, version.content_type or uploads.PDF)
    audit.record(db, organization_id=doc.organization_id, actor_id=None, action="document.file_repaired",
                 resource_type="document", resource_id=doc.id,
                 after={"version": version.version, "sha256": version.sha256})
    db.commit()
    result["repaired"] += 1
