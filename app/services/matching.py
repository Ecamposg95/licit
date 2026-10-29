"""Motor determinista de correspondencia (task pack §10, etapa 2).

Compara un requisito de las bases (atributo, operador, valor esperado y unidad) con lo que el catálogo declara
para la variante propuesta. Reglas:

- Solo lee `attributes` (y la existencia simulada de la variante). Nunca lee el nombre comercial: un atributo
  ausente, nulo o «por validar» es `desconocido`.
- Una lista de medidas (`{"values": [...]}`) coincide si la medida exigida está en la lista; si no, incumple y la
  explicación enumera las medidas disponibles. No se asume equivalencia clínica ni tolerancia.
- Los números se comparan en `Decimal`. Las longitudes se convierten a la unidad exigida (cm→mm ×10, m→mm ×1000);
  una unidad que no se puede convertir da `no_comparable`.
- La explicación siempre cita el texto de la fuente (`source_text`) cuando existe.

El resultado es una correspondencia técnica preliminar: nunca concede cumplimiento ni cambia el estado del requisito.
"""
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

ENGINE_VERSION = "1.0"

Operator = Literal["eq", "contains", "gte", "lte", "in"]
Result = Literal["coincide", "incumple", "desconocido", "no_comparable"]
# Etiquetas en español de cada resultado (las usan los borradores DOCX/CSV/XLSX; la interfaz tiene las mismas).
RESULT_LABELS: dict[str, str] = {"coincide": "Coincide", "incumple": "Incumple", "desconocido": "Desconocido",
                                 "no_comparable": "No comparable"}

UNKNOWN_TEXT = "No declarado en el catálogo; no se infiere del nombre."
_PRELIMINARY = "Correspondencia técnica preliminar; el cumplimiento documental sigue sujeto a evidencia."
_NO_EQUIVALENCE = "No se asume equivalencia clínica ni tolerancia no documentada."
_SIMULATED = "Dato simulado (SYNTHETIC): no confirma ni descarta disponibilidad real."

# Valores que el catálogo usa para decir «no sé»: cuentan como no declarados.
_PLACEHOLDERS = {"", "por validar", "por verificar", "no declarado", "desconocido", "n/d", "nd", "-"}

_UNIT_ALIASES = {
    "mm": "mm", "milimetro": "mm", "milimetros": "mm",
    "cm": "cm", "centimetro": "cm", "centimetros": "cm",
    "m": "m", "metro": "m", "metros": "m",
    "orificio": "orificios", "orificios": "orificios",
    "pieza": "pieza", "piezas": "pieza", "pza": "pieza", "pzas": "pieza",
}
_TO_MM = {"mm": Decimal(1), "cm": Decimal(10), "m": Decimal(1000)}

_ATTRIBUTE_LABELS = {
    "material": "material", "holes": "orificios", "length_mm": "longitud", "diameter_mm": "diámetro",
    "width_mm": "ancho", "stock_demo": "existencia (simulada)", "size_demo": "talla (demo)",
}
_OPERATOR_SYMBOL = {"eq": "=", "contains": "contiene", "gte": "≥", "lte": "≤", "in": "en"}
_NUMBER_RE = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")


@dataclass
class RequirementSpec:
    attribute: str
    operator: Operator
    expected: str
    unit: str | None


@dataclass
class RuleResult:
    result: Result
    explanation: str
    rule: str
    catalog_value: str | None
    source_text: str | None


@dataclass
class _Declared:
    values: list[Any]
    unit: str | None
    source_text: str | None
    is_list: bool
    simulated: bool


# ── Utilidades ───────────────────────────────────────────────────────────────

def fold(text: Any) -> str:
    """Texto sin acentos, sin mayúsculas y con espacios normalizados."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(plain.casefold().split())


def _is_placeholder(value: Any) -> bool:
    return value is None or (isinstance(value, str) and fold(value) in _PLACEHOLDERS)


def _num(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str) and _NUMBER_RE.match(value.strip()):
        try:
            return Decimal(value.strip().replace(",", "."))
        except InvalidOperation:  # pragma: no cover - la expresión regular ya lo descarta
            return None
    return None


def _norm_unit(unit: str | None) -> str | None:
    if unit is None or not str(unit).strip():
        return None
    key = fold(unit).rstrip(".")
    return _UNIT_ALIASES.get(key, key)


def _show(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, Decimal):
        return format(value.normalize(), "f") if value == value.to_integral_value() else str(value)
    return str(value)


def spanish_join(items: list[str]) -> str:
    """«5, 6 y 7»."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def _with_unit(text: str, unit: str | None) -> str:
    return f"{text} {unit}" if unit else text


def _declared(raw: Any) -> _Declared | None:
    """Lo que el catálogo declara para un atributo, o `None` si no declara nada utilizable."""
    if raw is None:
        return None
    unit = source = None
    simulated = False
    if isinstance(raw, dict):
        unit, source = raw.get("unit"), raw.get("source_text")
        simulated = raw.get("data_kind") == "SYNTHETIC"
        if "values" in raw:
            payload = raw["values"]
        elif "value" in raw:
            payload = raw["value"]
        else:
            return None
    else:
        payload = raw
    is_list = isinstance(payload, (list, tuple))
    values = [v for v in (payload if is_list else [payload]) if not _is_placeholder(v)]
    if not values:
        return None
    return _Declared(values=values, unit=unit, source_text=source or None, is_list=is_list, simulated=simulated)


def _catalog_value(d: _Declared) -> str:
    return _with_unit(spanish_join([_show(v) for v in d.values]), d.unit)


def _required_text(spec: RequirementSpec, label: str) -> str:
    """«Exigido: orificios = 6», «Exigido: material contiene «titanio»», «Exigido: longitud = 96 mm»."""
    unit = spec.unit if spec.unit and fold(spec.unit) != fold(label) else None
    if spec.operator == "contains":
        expr = f"{label} contiene «{spec.expected}»"
    elif spec.operator == "in":
        expr = f"{label} en {{{_with_unit(spec.expected, unit)}}}"
    else:
        expr = f"{label} {_OPERATOR_SYMBOL.get(spec.operator, spec.operator)} {_with_unit(spec.expected, unit)}"
    return f"Exigido: {expr}."


def _catalog_text(d: _Declared) -> str:
    shown = [_show(v) if _num(v) is not None else f"«{_show(v)}»" for v in d.values]
    return f"Catálogo: {_with_unit(spanish_join(shown), d.unit)}."


def _cite(text: str, d: _Declared | None) -> str:
    if d is not None and d.simulated:
        text = f"{text} {_SIMULATED}"
    if d is not None and d.source_text:
        text = f"{text} Cita del catálogo: «{d.source_text}»"
    return text


# ── Comparación ──────────────────────────────────────────────────────────────

def _compare_one(spec: RequirementSpec, value: Any, factor: Decimal) -> bool | None:
    """True/False si se puede decidir para este valor; None si no es comparable."""
    if isinstance(value, (dict, list, tuple)):
        return None
    op = spec.operator
    if op == "contains":
        return fold(spec.expected) in fold(value)
    if op == "in":
        options = [o for o in re.split(r"[,;|]", spec.expected) if o.strip()]
        outcomes = [_compare_one(RequirementSpec(spec.attribute, "eq", o.strip(), spec.unit), value, factor)
                    for o in options]
        if any(o is True for o in outcomes):
            return True
        return None if all(o is None for o in outcomes) else False
    expected_n, value_n = _num(spec.expected), _num(value)
    if op in ("gte", "lte"):
        if expected_n is None or value_n is None:
            return None
        value_n *= factor
        return value_n >= expected_n if op == "gte" else value_n <= expected_n
    if op == "eq":
        if expected_n is not None and value_n is not None:
            return value_n * factor == expected_n
        if expected_n is None and value_n is None:
            return fold(spec.expected) == fold(value)
        return None
    return None


def evaluate(spec: RequirementSpec, attributes: dict) -> RuleResult:
    """Evalúa un requisito contra los atributos declarados de una variante (nunca contra su nombre)."""
    raw = (attributes or {}).get(spec.attribute)
    declared = _declared(raw)
    label = _ATTRIBUTE_LABELS.get(spec.attribute, spec.attribute)
    required = _required_text(spec, label)
    if declared is None:
        return RuleResult("desconocido", f"{UNKNOWN_TEXT} {required}", "atributo_no_declarado", None, None)

    catalog_value = _catalog_value(declared)
    found = f"{required} {_catalog_text(declared)}"
    if spec.operator not in _OPERATOR_SYMBOL:
        return RuleResult("no_comparable", _cite(f"Operador «{spec.operator}» no reconocido por el motor.", declared),
                          "operador_desconocido", catalog_value, declared.source_text)

    factor = Decimal(1)
    if spec.operator != "contains":
        su, du = _norm_unit(spec.unit), _norm_unit(declared.unit)
        if su and du and su != du:
            if su in _TO_MM and du in _TO_MM:
                factor = _TO_MM[du] / _TO_MM[su]
            else:
                text = f"{found} Las unidades ({spec.unit} y {declared.unit}) no se pueden convertir entre sí."
                return RuleResult("no_comparable", _cite(text, declared), "unidad_no_convertible",
                                  catalog_value, declared.source_text)

    outcomes = [_compare_one(spec, v, factor) for v in declared.values]
    rule = f"{spec.operator}_{'lista' if declared.is_list else 'valor'}"
    if any(o is True for o in outcomes):
        return RuleResult("coincide", _cite(f"{found} {_PRELIMINARY}", declared), rule, catalog_value,
                          declared.source_text)
    if all(o is None for o in outcomes):
        text = f"{found} El valor declarado no se puede comparar con lo exigido."
        return RuleResult("no_comparable", _cite(text, declared), "tipo_no_comparable",
                          catalog_value, declared.source_text)
    if declared.is_list:
        available = spanish_join([_show(v) for v in declared.values])
        text = f"{required} Medidas disponibles: {available}."
    else:
        text = found
    if not declared.simulated:
        text = f"{text} {_NO_EQUIVALENCE}"
    return RuleResult("incumple", _cite(text, declared), rule, catalog_value, declared.source_text)


def variant_attributes(variant) -> dict:
    """Atributos comparables de una variante: los declarados más su existencia simulada.

    No toma nada del nombre. La existencia (`stock_demo`) siempre es un dato simulado y va marcada así.
    """
    attrs = dict(getattr(variant, "attributes", None) or {})
    stock = getattr(variant, "stock_demo", None)
    if stock is not None and "stock_demo" not in attrs:
        attrs["stock_demo"] = {"value": stock, "unit": getattr(variant, "unit", None) or None,
                               "source_text": None, "data_kind": "SYNTHETIC"}
    return attrs


def spec_from_requirement(requirement) -> RequirementSpec | None:
    """El requisito como especificación comparable; `None` si no declara un atributo."""
    if not getattr(requirement, "attribute", None):
        return None
    return RequirementSpec(attribute=requirement.attribute, operator=requirement.operator or "eq",
                           expected=requirement.expected_value or "", unit=requirement.unit)
