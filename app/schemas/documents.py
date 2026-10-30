"""Contratos del centro documental (frente D). Extienden los de la API v1 sin modificarlos."""
from app.schemas import v1


class DocumentVersionOut(v1.DocumentVersionOut):
    has_file: bool = False                      # false: versión semilla sin archivo, o documento de tercero
    uploaded_by: v1.UserRef | None = None


class DocumentOut(v1.DocumentOut):
    external_url: str | None
    third_party: bool
    page_count: int | None
    product_name: str | None = None
    versions: list[DocumentVersionOut]          # type: ignore[assignment]
