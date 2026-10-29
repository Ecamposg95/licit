"""Documentos de prueba con marca DEMO (frente D4).

`render_demo_pdf` produce PDFs ficticios sin comprimir (el texto de la marca se puede buscar en los bytes).
`attach_demo_files` los genera para los documentos SYNTHETIC de la semilla y los guarda por la abstracción
de almacenamiento en `demo/{org}/{code}.pdf`. Nada de esto es un documento oficial ni tiene validez.
"""
import hashlib
import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from fpdf import FPDF
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core import config
from app.models import Document, DocumentVersion
from app.services.storage import get_storage
from app.services.uploads import pdf_page_count

log = logging.getLogger(__name__)

PAGE_BREAK = "\f"                        # en `lines`: empieza una página nueva
_REPLACEMENTS = {"−": "-", "–": "-", "—": "-", "≥": ">=", "≤": "<=", "“": '"',
                 "”": '"', "‘": "'", "’": "'", "…": "...", "→": "->", " ": " "}


def _latin1(text: str) -> str:
    """Las fuentes base de PDF solo cubren latin-1 (suficiente para español); lo demás se aproxima."""
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _DemoPDF(FPDF):
    def header(self) -> None:
        # Marca diagonal en cada página, translúcida para no tapar el contenido.
        self.set_font("Helvetica", "B", 21)
        text = _latin1(config.WATERMARK)
        with self.local_context(fill_opacity=0.16):
            self.set_text_color(185, 28, 28)
            with self.rotation(angle=45, x=self.w / 2, y=self.h / 2):
                self.text(self.w / 2 - self.get_string_width(text) / 2, self.h / 2, text)
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_y(-18)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(185, 28, 28)
        self.cell(0, 4, _latin1(config.WATERMARK), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 7)
        self.set_text_color(90, 90, 90)
        self.cell(0, 4, _latin1(f"Registro: {config.FICTITIOUS_REGISTRY} - Página {self.page_no()} de {{nb}}"),
                  align="C")


def _xmp(title: str) -> str:
    mark = escape(config.WATERMARK)
    return (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{escape(title)}</rdf:li></rdf:Alt></dc:title>'
        f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{mark}</rdf:li></rdf:Alt></dc:description>'
        f'<dc:rights><rdf:Alt><rdf:li xml:lang="x-default">{mark}</rdf:li></rdf:Alt></dc:rights>'
        '</rdf:Description></rdf:RDF></x:xmpmeta>'
    )


def render_demo_pdf(title: str, lines: list[str]) -> bytes:
    """PDF ficticio A4 sin comprimir: título, líneas, marca DEMO en diagonal y en el pie de cada página.

    Un `PAGE_BREAK` en `lines` abre una página nueva. Es determinista: misma entrada, mismos bytes
    (la fecha de creación se fija a la fecha base del demo). La marca va, además, en los metadatos XMP
    con su texto exacto en UTF-8."""
    pdf = _DemoPDF(format="A4")
    pdf.set_compression(False)
    pdf.set_creation_date(datetime.combine(config.DEMO_BASE_DATE, datetime.min.time(), tzinfo=timezone.utc))
    pdf.set_title(_latin1(title))
    pdf.set_author("Atlas Technologies - Demo")
    pdf.set_creator("Licit - Dipromedic Demo")
    pdf.set_subject(_latin1(config.WATERMARK))
    pdf.set_xmp_metadata(_xmp(title))
    pdf.alias_nb_pages("{nb}")
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.set_margins(left=20, top=22, right=20)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 17)
    pdf.multi_cell(0, 8, _latin1(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    for line in lines:
        if line == PAGE_BREAK:
            pdf.add_page()
            pdf.set_font("Helvetica", "", 11)
            continue
        pdf.multi_cell(0, 6.5, _latin1(line), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def has_demo_watermark(data: bytes) -> bool:
    """La marca literal aparece en el contenido de la página (latin-1) o en los metadatos (UTF-8)."""
    return config.WATERMARK.encode("latin-1", errors="replace") in data or config.WATERMARK.encode() in data


# ── Archivos de la semilla ───────────────────────────────────────────────────

def _content_lines(code: str, doc: Document, meta: dict, fragments: list[dict], attributes: dict) -> list[str]:
    lines = [
        f"Código: {code}",
        f"Tipo de documento: {doc.doc_type or 'no declarado'}",
        f"Ámbito: {doc.scope}",
        "Emisor declarado: Emisor ficticio",
    ]
    if meta.get("product_sku"):
        lines.append(f"Producto (SKU de demostración): {meta['product_sku']}")
    for key, value in sorted(attributes.items()):
        if key != "size_demo" and value not in (None, "por validar"):
            lines.append(f"{key}: {value}")
    if meta.get("opportunity"):
        lines.append(f"Procedimiento ficticio: {meta['opportunity']}")
    if doc.valid_until:
        lines.append(f"Vigencia declarada: {doc.valid_until.isoformat()}")
    if doc.scope == "producto" or doc.doc_type in {"certificado", "ficha_tecnica", "constancia"}:
        lines.append(f"Registro sanitario: {config.FICTITIOUS_REGISTRY}")
    by_page: dict[int, list[str]] = {}
    for ev in fragments:
        by_page.setdefault(ev.get("page") or 1, []).append(ev["fragment"])
    last = max(by_page, default=1)
    for page in range(1, last + 1):
        if page > 1:
            lines.append(PAGE_BREAK)
            lines.append(f"Continuación del documento ficticio {code} (página {page})")
        for fragment in by_page.get(page, []):
            lines.append("")
            lines.append(fragment)
    lines += ["", "Este documento es ficticio, se generó para la demostración y no sustituye a ningún "
                  "documento oficial. Nada de lo que contiene es un registro, certificado o garantía real."]
    return lines


def demo_key(org_id: str, code: str) -> str:
    return f"demo/{org_id}/{code}.pdf"


def render_seed_pdf(doc: Document, meta: dict, evidence: list[dict], attributes: dict) -> bytes:
    code = doc.code
    fragments = [e for e in evidence if e["document"] == code and e.get("fragment")]
    return render_demo_pdf(doc.title, _content_lines(code, doc, meta, fragments, attributes))


def attach_demo_files(org_id: str, docs: dict[str, Document], extra: dict, attributes_by_sku: dict[str, dict]) -> set[str]:
    """Genera y guarda el PDF de cada documento SYNTHETIC y completa su versión semilla. Devuelve las claves."""
    storage = get_storage()
    keys: set[str] = set()
    for code, doc in docs.items():
        if doc.data_kind != "SYNTHETIC":
            continue
        meta = extra["documents"].get(code, {})
        data = render_seed_pdf(doc, meta, extra.get("evidence", []), attributes_by_sku.get(meta.get("product_sku") or "", {}))
        key = demo_key(org_id, code)
        storage.put(key, data, "application/pdf")
        keys.add(key)
        version = doc.versions[-1]
        version.filename = f"{code}.pdf"
        version.content_type = "application/pdf"
        version.size_bytes = len(data)
        version.sha256 = hashlib.sha256(data).hexdigest()
        version.storage_key = key
        version.note = "Versión semilla con archivo de prueba y marca DEMO."
        doc.page_count = pdf_page_count(data)
    return keys


def ensure_demo_files(db: Session, org_id: str) -> int:
    """Regenera los archivos semilla que falten en el almacenamiento (por ejemplo, tras un redeploy con
    disco efímero). Los bytes son deterministas, así que el hash guardado sigue siendo válido.
    Devuelve cuántos repuso. Pensado para llamarse desde `bootstrap()`."""
    from app.services.demo_seed import _load  # demo_seed importa este módulo

    storage = get_storage()
    base, extra = _load()
    attributes = {p["id"]: p.get("attributes") or {} for p in base["products"]}
    rows = db.execute(select(DocumentVersion, Document).join(Document, Document.id == DocumentVersion.document_id)
                      .where(Document.organization_id == org_id, Document.data_kind == "SYNTHETIC",
                             DocumentVersion.storage_key.like(f"demo/{org_id}/%"))).all()
    restored = 0
    for version, doc in rows:
        if storage.exists(version.storage_key):
            continue
        meta = extra["documents"].get(doc.code, {})
        data = render_seed_pdf(doc, meta, extra.get("evidence", []), attributes.get(meta.get("product_sku") or "", {}))
        if hashlib.sha256(data).hexdigest() == version.sha256:
            storage.put(version.storage_key, data, "application/pdf")
            restored += 1
    return restored


def delete_after_commit(db: Session, keys: Iterable[str]) -> None:
    """Borra objetos del almacenamiento cuando la transacción se confirma (si se revierte, no se borra nada)."""
    pending = [k for k in keys if k]
    if not pending:
        return
    state = {"done": False}      # los oyentes quedan inertes tras el primer commit o rollback (la sesión es corta)

    def on_commit(_session) -> None:
        if state["done"]:
            return
        state["done"] = True
        storage = get_storage()
        for key in pending:
            try:
                storage.delete(key)
            except Exception:  # noqa: BLE001 - un objeto huérfano no debe tumbar el reinicio
                log.warning("No se pudo borrar el objeto %s", key, exc_info=True)

    def on_rollback(_session) -> None:
        state["done"] = True

    event.listen(db, "after_commit", on_commit)
    event.listen(db, "after_rollback", on_rollback)


# ── Archivo que el presentador sube en la reunión (paso 7 del guion) ─────────

UPLOAD_SAMPLE_NAME = "Ficha_tecnica_DEMO_para_carga.pdf"


def render_upload_sample() -> bytes:
    """Ficha técnica ficticia de la placa de la partida 1 (DEMO-PLA-001) para subir en vivo y resolver el
    requisito «Ficha técnica del producto propuesto». Los atributos son los del catálogo ficticio."""
    return render_demo_pdf("Ficha técnica de prueba · Placa bloqueada demostración variante 1", [
        "Ficha técnica ficticia para la demostración. No describe un producto real.",
        "",
        "Producto (SKU de demostración): DEMO-PLA-001",
        "Material: titanio",
        "Orificios: 6",
        "Fabricante declarado: Fabricante ficticio",
        f"Registro sanitario: {config.FICTITIOUS_REGISTRY}",
        "",
        "Uso en la demostración: sube este archivo como evidencia del requisito «Ficha técnica del producto "
        "propuesto». El requisito pasa a «En revisión»; solo una persona con permiso de revisión puede "
        "marcarlo como cumplido.",
    ])
