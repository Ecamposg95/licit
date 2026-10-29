"""Catálogo: líneas, productos y detalle con la cita textual de cada atributo."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, lazyload

from app.core.database import get_db
from app.core.permissions import Perm, require_permission
from app.core.tenant import get_owned
from app.models import Document, Product, User, Variant
from app.schemas.catalog import LineOut, ProductCard, ProductDetail, VariantDetail
from app.schemas.v1 import DocumentOut
from app.services.catalog_import import ROW_ATTRIBUTES, normalize_code

router = APIRouter(prefix="/api/v1/catalog", tags=["catálogo"])


def _like(text: str) -> str:
    """Patrón LIKE que trata `%`, `_` y `\\` del texto como caracteres normales."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _card(p: Product, variant_count: int) -> ProductCard:
    card = ProductCard.model_validate(p)
    card.variant_count = variant_count
    return card


def _common_attributes(variants: list[Variant]) -> dict:
    """Atributos que comparten todas las variantes con el mismo valor y la misma cita."""
    if not variants:
        return {}
    first = variants[0].attributes or {}
    return {
        key: value for key, value in first.items()
        if key not in ROW_ATTRIBUTES and all((v.attributes or {}).get(key) == value for v in variants[1:])
    }


@router.get("/lines", response_model=list[LineOut])
def list_lines(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_READ))):
    rows = db.execute(
        select(Product.line, Product.family, func.count(Product.id))
        .where(Product.organization_id == user.organization_id, Product.line.is_not(None))
        .group_by(Product.line, Product.family)).all()
    lines: dict[str, LineOut] = {}
    for line, family, n in rows:
        out = lines.setdefault(line, LineOut(line=line, product_count=0, families=[]))
        out.product_count += n
        out.families.append(family)
    for out in lines.values():
        out.families.sort(key=str.casefold)
    return sorted(lines.values(), key=lambda x: (-x.product_count, x.line.casefold()))


@router.get("/products", response_model=list[ProductCard])
def list_products(line: str | None = None, family: str | None = None, data_kind: list[str] = Query(default=[]),
                  q: str | None = None, db: Session = Depends(get_db),
                  user: User = Depends(require_permission(Perm.CATALOG_READ))):
    stmt = (select(Product).options(lazyload(Product.variants))
            .where(Product.organization_id == user.organization_id))
    if line:
        stmt = stmt.where(Product.line == line)
    if family:
        stmt = stmt.where(Product.family == family)
    if data_kind:
        stmt = stmt.where(Product.data_kind.in_(data_kind))
    if q and q.strip():
        match = Product.name.ilike(_like(q.strip()), escape="\\")
        code = normalize_code(q)  # los SKU se guardan normalizados (sin cirílico ni espacios)
        if code:
            match = match | exists().where(Variant.product_id == Product.id,
                                           Variant.sku.ilike(_like(code), escape="\\"))
        stmt = stmt.where(match)
    products = list(db.scalars(stmt.order_by(Product.family, Product.name, Product.id)))
    counts = dict(db.execute(
        select(Variant.product_id, func.count(Variant.id))
        .where(Variant.organization_id == user.organization_id).group_by(Variant.product_id)).all())
    return [_card(p, counts.get(p.id, 0)) for p in products]


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str, db: Session = Depends(get_db),
                user: User = Depends(require_permission(Perm.CATALOG_READ))):
    product = get_owned(db, Product, product_id, user, "Producto")
    variants = list(product.variants)
    documents = db.scalars(select(Document).where(
        Document.organization_id == user.organization_id, Document.product_id == product.id)
        .order_by(Document.code, Document.title)).unique()
    card = _card(product, len(variants))
    return ProductDetail(
        **card.model_dump(), features=list(product.features or []),
        data_quality_notes=list(product.data_quality_notes or []),
        attributes=_common_attributes(variants),
        variants=[VariantDetail.model_validate(v) for v in variants],
        documents=[DocumentOut.model_validate(d) for d in documents])
