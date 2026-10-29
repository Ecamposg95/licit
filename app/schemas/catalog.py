"""Contratos de la API del catálogo (`/api/v1/catalog`)."""
from datetime import date
from typing import Any

from pydantic import BaseModel

from app.schemas.v1 import DocumentOut, ORM, VariantOut


class LineOut(BaseModel):
    line: str
    product_count: int
    families: list[str]


class ProductCard(ORM):
    """Ficha resumida. Las fichas importadas traen origen, fecha de consulta y crédito."""
    id: str
    name: str
    family: str
    brand: str | None
    manufacturer: str | None
    data_kind: str
    review_status: str
    description: str | None
    line: str | None
    subfamily: str | None
    source_url: str | None
    checked_on: date | None
    attribution: str | None
    images: list[str]
    variant_count: int = 0


class VariantDetail(VariantOut):
    side: str | None
    source_text: str | None
    field_provenance: dict[str, Any]


class ProductDetail(ProductCard):
    features: list[str]
    data_quality_notes: list[str]
    # Atributos de la ficha, cada uno con su cita; los de cada fila (orificios, diámetro, longitud) viajan
    # sólo dentro de la variante. En datos ficticios (sin ficha) son los que comparten todas las variantes.
    attributes: dict[str, Any]
    variants: list[VariantDetail]
    documents: list[DocumentOut]
