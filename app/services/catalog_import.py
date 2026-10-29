"""Importador del catálogo público de Dipromedic (dipromedic.com), siempre como datos REAL.

Fuente: `app/fixtures/catalogo_dipromedic.json`, consultado el día que dice `checked_on`. Reglas:

- Cada atributo técnico conserva el texto literal de la página (`source_text`). Un atributo sin cita no se carga.
- Nunca se deriva un atributo del nombre de la variante ni de su código.
- Precio, existencias y registro sanitario no vienen del sitio: las variantes REAL los dejan en `None`.
- Lo ambiguo no se adivina: se omite y queda en `ImportSummary.warnings`.
- La importación es idempotente (ids estables por producto y por SKU) y no borra nada.
"""
import copy
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, lazyload

from app.models import DataKind, Product, Variant
from app.services import audit
from app.services.demo_seed import FIXTURES, stable_id

CATALOG_PATH = FIXTURES / "catalogo_dipromedic.json"
ATTRIBUTION = "DIPROMEDIC S.A. DE C.V. · www.dipromedic.com"
SKU_PREFIX = "DPM-"
SIDES = ("izquierda", "derecha")
# Atributos que salen de la fila de la tabla (no de la ficha): cambian de una variante a otra.
ROW_ATTRIBUTES = ("holes", "diameter_mm", "length_mm")

# Letras cirílicas que se ven igual que las latinas (el sitio trae tres códigos con ellas).
_CYRILLIC_TO_LATIN = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K",
    "М": "M", "О": "O", "Р": "P", "Т": "T", "Х": "X",
})
# Un código de producto real: ASCII, con al menos un dígito (descarta "igo", "-", "Type III", "φ2.5mm").
_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]*$")

# Columnas de fila que se cargan como atributos o que son metadatos; el resto de columnas
# (Diámetro, Sutura, Medidas…) no se interpretan: la fila completa queda citada en `Variant.source_text`.
_ROW_KEYS_HANDLED = {
    "name", "Descripción", "table_label", "source_text", "codes", "code", "Código", "Código_normalizado_ascii",
    "orificios", "diametro_mm", "diametros_mm", "longitud_mm", "longitudes_mm",
}


@dataclass
class ImportSummary:
    products: int          # fichas del catálogo presentes tras la importación
    variants: int          # variantes (códigos) presentes tras la importación
    updated: int           # filas ya existentes (productos y variantes) que cambiaron
    warnings: list[str] = field(default_factory=list)


def normalize_code(raw: str) -> str:
    """Cirílico parecido → latino, sin espacios y en mayúsculas."""
    return "".join(raw.split()).upper().translate(_CYRILLIC_TO_LATIN)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _row_codes(ref: str, row: dict, warnings: list[str]) -> list[tuple[str, str | None]]:
    """(código tal como lo publica el sitio, lado) de una fila de `variants`."""
    out: list[tuple[str, str | None]] = []
    codes = row.get("codes")
    if isinstance(codes, dict):
        for key, value in codes.items():
            if key in SIDES:
                out.extend((c, key) for c in _as_list(value))
            elif key == "unica":
                out.extend((c, None) for c in _as_list(value))
            else:
                warnings.append(f"{ref}: la fila «{row.get('name')}» trae códigos con un lado desconocido "
                                f"({key!r}); se omitieron.")
    for key in ("code", "Código"):
        if row.get(key) is not None:
            out.append((row[key], None))
    return out


def _row_attributes(row: dict, attrs: dict) -> list[str]:
    """Agrega a `attrs` lo que la fila declara (orificios, diámetros, longitudes), siempre con su cita.

    Devuelve los atributos que la fila declara pero no puede citar (no se cargan).
    """
    quote = row.get("source_text")
    pending = dict(zip(ROW_ATTRIBUTES, (
        (_as_list(row.get("orificios")), "orificios"),
        (_as_list(row.get("diametros_mm", row.get("diametro_mm"))), "mm"),
        (_as_list(row.get("longitudes_mm", row.get("longitud_mm"))), "mm"),
    )))
    uncited = []
    for key, (values, unit) in pending.items():
        if not values:
            continue
        if quote:
            attrs[key] = {"values": values, "unit": unit, "source_text": quote}
        else:
            uncited.append(key)
    return uncited


def _clean_code(ref: str, raw: Any, warnings: list[str]) -> str | None:
    """Código normalizado, o `None` (con aviso) si lo que trae el sitio no es un código usable."""
    text = raw if isinstance(raw, str) else str(raw)
    norm = normalize_code(text)
    if not _CODE_RE.match(norm) or not any(ch.isdigit() for ch in norm):
        warnings.append(f"{ref}: el valor {text!r} no es un código de producto usable (revisar la página); "
                        "se omitió esa variante.")
        return None
    if norm != text.strip():
        warnings.append(f"{ref}: el código {text!r} se normalizó a {norm!r} (letras cirílicas o espacios); "
                        "el original queda en la cita de la variante.")
    return norm


def _variant_specs(ref: str, raw: dict, warnings: list[str], unmapped: set[str]) -> list[dict]:
    """Variantes que describe un producto del JSON, sin tocar la base."""
    specs: list[dict] = []
    uncited_rows: list[str] = []
    product_attrs = raw.get("attributes") or {}
    rows = raw.get("variants") or []
    if rows:
        for row in rows:
            unmapped.update(k for k in row if k not in _ROW_KEYS_HANDLED)
            codes = _row_codes(ref, row, warnings)
            if not codes:
                warnings.append(f"{ref}: la fila «{row.get('name') or row.get('Descripción')}» no trae códigos; "
                                "no genera variantes.")
                continue
            if len(codes) > 1 and row.get("orificios") and not any(side for _c, side in codes):
                warnings.append(f"{ref}: una sola fila ({row.get('source_text')!r}) declara orificios para "
                                f"{len(codes)} códigos; la lista se asignó completa a cada uno.")
            attrs = copy.deepcopy(product_attrs)
            if _row_attributes(row, attrs):
                uncited_rows.append(str(row.get("code") or row.get("name")))
            base_name = row.get("name") or row.get("Descripción") or raw["name"]
            for code, side in codes:
                specs.append({
                    "raw_code": code if isinstance(code, str) else str(code), "side": side,
                    "name": base_name + (f" · {side}" if side else ""),
                    "attributes": copy.deepcopy(attrs), "source_text": row.get("source_text"),
                })
        if uncited_rows:
            warnings.append(f"{ref}: {len(uncited_rows)} filas declaran orificios, diámetros o longitudes sin texto "
                            f"original que los cite; esas medidas no se cargaron ({', '.join(uncited_rows)}).")
    else:
        for code in raw.get("codes") or []:
            specs.append({
                "raw_code": code if isinstance(code, str) else str(code), "side": None, "name": raw["name"],
                "attributes": copy.deepcopy(product_attrs), "source_text": None,
            })
    return specs


def _apply(obj: Any, values: dict) -> bool:
    """Asigna sólo lo que cambió. Devuelve si hubo cambios."""
    changed = False
    for key, value in values.items():
        if getattr(obj, key) != value:
            setattr(obj, key, value)
            changed = True
    return changed


def import_catalog(db: Session, organization_id: str, path: Path) -> ImportSummary:
    """Importa (o actualiza) el catálogo público como productos y variantes REAL. No hace commit."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    checked_on = date.fromisoformat(data["checked_on"])
    warnings: list[str] = []
    unmapped: set[str] = set()

    products = {p.external_ref: p for p in db.scalars(
        select(Product).options(lazyload(Product.variants)).where(
            Product.organization_id == organization_id, Product.data_kind == DataKind.REAL.value,
            Product.external_ref.is_not(None)))}
    variants = {v.sku: v for v in db.scalars(select(Variant).where(Variant.organization_id == organization_id))}

    claimed: dict[str, str] = {}     # sku → ficha que lo reclamó en esta importación
    n_products = n_variants = updated = created = 0

    for line in data["lines"]:
        for raw in line["products"]:
            ref = raw["id"]
            notes = list(raw.get("data_quality_notes") or [])
            status = "por_revisar" if notes else "pendiente"
            fields = {
                "name": raw["name"], "family": raw["family"], "subfamily": raw.get("subfamily"),
                "line": line["line"], "description": raw.get("description"),
                "features": list(raw.get("features") or []), "images": list(raw.get("images") or []),
                "source_url": raw.get("page_url"), "checked_on": checked_on, "attribution": ATTRIBUTION,
                "data_quality_notes": notes, "data_kind": DataKind.REAL.value,
            }
            product = products.get(ref)
            if product is None:
                product = Product(id=stable_id(organization_id, f"catalog:product:{ref}"),
                                  organization_id=organization_id, external_ref=ref,
                                  review_status=status, **fields)
                db.add(product)
                products[ref] = product
                created += 1
            else:
                changed = _apply(product, fields)
                # Un estado ya revisado por una persona no se pisa; sólo se alterna entre los dos automáticos.
                if product.review_status in ("pendiente", "por_revisar"):
                    changed = _apply(product, {"review_status": status}) or changed
                updated += changed
            n_products += 1

            for spec in _variant_specs(ref, raw, warnings, unmapped):
                norm = _clean_code(ref, spec["raw_code"], warnings)
                if norm is None:
                    continue
                sku = SKU_PREFIX + norm
                owner = claimed.get(sku)
                if owner is None and sku in variants and variants[sku].data_kind != DataKind.REAL.value:
                    owner = "una variante no REAL"
                if owner is not None:
                    warnings.append(f"{ref}: el SKU {sku} ya lo usa {owner}; se omitió la variante duplicada "
                                    f"(la página trae el mismo código en ambas fichas).")
                    continue
                claimed[sku] = ref
                source_text = spec["source_text"]
                if norm != spec["raw_code"].strip():
                    note = f"código original: {spec['raw_code']}"
                    source_text = f"{source_text} · {note}" if source_text else note
                vfields = {
                    "product_id": product.id, "name": spec["name"], "attributes": spec["attributes"],
                    "side": spec["side"], "source_text": source_text, "unit": "",
                    "data_kind": DataKind.REAL.value,
                }
                variant = variants.get(sku)
                if variant is None:
                    variant = Variant(id=stable_id(organization_id, f"catalog:variant:{sku}"),
                                      organization_id=organization_id, sku=sku, review_status=status,
                                      price=None, currency=None, stock_demo=None, regulatory_reference=None,
                                      field_provenance={}, **vfields)
                    db.add(variant)
                    variants[sku] = variant
                    created += 1
                else:
                    changed = _apply(variant, vfields)
                    if variant.review_status in ("pendiente", "por_revisar"):
                        changed = _apply(variant, {"review_status": status}) or changed
                    updated += changed
                n_variants += 1

    if unmapped:
        warnings.append("Columnas de las tablas del sitio que no se cargan como atributos (la fila completa queda "
                        "citada en la variante): " + ", ".join(sorted(unmapped)) + ".")
    db.flush()
    summary = ImportSummary(products=n_products, variants=n_variants, updated=updated, warnings=warnings)
    if created or updated:
        audit.record(
            db, organization_id=organization_id, actor_id=None, action="catalog.import",
            resource_type="organization", resource_id=organization_id,
            after={"source": data["source"], "checked_on": data["checked_on"], "products": n_products,
                   "variants": n_variants, "created": created, "updated": updated, "warnings": len(warnings)})
        db.flush()
    return summary
