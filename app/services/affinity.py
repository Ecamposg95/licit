"""Afinidad orientativa por componente y vigencia documental a la fecha exigida (task pack §10).

La afinidad no es probabilidad de ganar ni dictamen de elegibilidad. Cada componente muestra su cobertura
(`known` de `total`); si un componente no tiene datos (`total == 0`), su puntuación es `None` y el total también
(«cobertura incompleta»), para no presentar un número engañoso. Los requisitos bloqueantes se listan siempre,
aunque la puntuación sea alta.
"""
import copy
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Literal

from app.services.matching import fold

WEIGHTS = {"familia": 40, "atributos": 30, "documental": 20, "capacidad": 10}

BLOCKING_STATUSES = ("incumple", "faltante", "vencido")
# Estados en los que se sabe si el requisito está cubierto o no (el resto es desconocido para la cobertura).
_DETERMINATE = {"cumple_validado", "incumple", "faltante", "vencido"}
_NOT_APPLICABLE = "no_aplica_justificado"

Validity = Literal["vigente", "vence_antes", "vencido", "sin_vigencia"]


@dataclass
class Affinity:
    components: dict[str, dict]
    total: int | None
    coverage_complete: bool
    blocking: list[str] = field(default_factory=list)


def check_validity(valid_until: date | None, required_by: date | None, today: date) -> Validity:
    """Vigencia de un documento hoy y a la fecha exigida (un documento vigente hoy puede vencer antes)."""
    if valid_until is None:
        return "sin_vigencia"
    if valid_until < today:
        return "vencido"
    if required_by is not None and valid_until < required_by:
        return "vence_antes"
    return "vigente"


def _component(name: str, positive: int, known: int, total: int) -> dict:
    score = None if total == 0 else round(positive / total, 4)
    return {"weight": WEIGHTS[name], "score": score, "known": known, "total": total}


def _requirement_outcome(requirement, assessment) -> tuple[bool, bool]:
    """(se sabe, es positivo). El resultado objetivo del motor va antes que el estado capturado."""
    result = getattr(assessment, "result", None)
    if result in ("coincide", "incumple"):
        return True, result == "coincide"
    status = requirement.status
    return status in _DETERMINATE, status == "cumple_validado"


def compute_affinity(opportunity, requirements, assessments) -> Affinity:
    """Afinidad 40/30/20/10 con cobertura por componente y lista de bloqueantes."""
    by_requirement = {a.requirement_id: a for a in assessments if getattr(a, "requirement_id", None)}
    applicable = [r for r in requirements if r.status != _NOT_APPLICABLE]

    # Familia: partidas cuya familia es la del producto propuesto.
    lots = list(getattr(opportunity, "lots", None) or [])
    fam_known = fam_positive = 0
    for lot in lots:
        if not lot.family:
            continue
        fam_known += 1
        variant = lot.proposed_variant
        product = getattr(variant, "product", None) if variant is not None else None
        if product is not None and product.family and fold(product.family) == fold(lot.family):
            fam_positive += 1

    def tally(items) -> tuple[int, int, int]:
        known = positive = 0
        for r in items:
            k, p = _requirement_outcome(r, by_requirement.get(r.id))
            known += k
            positive += p
        return positive, known, len(items)

    technical = [r for r in applicable if r.req_type == "tecnico"]
    capacity = [r for r in applicable if r.req_type == "capacidad"]
    documentary = [r for r in applicable if r.req_type == "documental" and r.mandatory is True]
    doc_known = sum(1 for r in documentary if r.status in _DETERMINATE)
    doc_positive = sum(1 for r in documentary if r.status == "cumple_validado")

    counts = {
        "familia": (fam_positive, fam_known, len(lots)),
        "atributos": tally(technical),
        "documental": (doc_positive, doc_known, len(documentary)),
        "capacidad": tally(capacity),
    }
    components = {name: _component(name, *c) for name, c in counts.items()}

    if any(c["score"] is None for c in components.values()):
        total = None
    else:
        # Aritmética exacta con las cuentas (no con las puntuaciones redondeadas) y redondeo comercial.
        exact = sum((Fraction(WEIGHTS[name] * positive, n) for name, (positive, _known, n) in counts.items()),
                    Fraction(0))
        total = int((Decimal(exact.numerator) / Decimal(exact.denominator)).quantize(Decimal(1), ROUND_HALF_UP))
    coverage_complete = all(c["total"] > 0 and c["known"] == c["total"] for c in components.values())

    blocking = sorted(
        r.code for r in requirements
        if r.mandatory is True and r.code and (
            r.status in BLOCKING_STATUSES or getattr(by_requirement.get(r.id), "result", None) == "incumple"))
    return Affinity(components=components, total=total, coverage_complete=coverage_complete, blocking=blocking)


def serialize_affinity(a: Affinity) -> dict:
    """Forma que se guarda en `bid_workspaces.affinity` (la generación de borradores la lee tal cual)."""
    return {"components": copy.deepcopy(a.components), "total": a.total,
            "coverage_complete": a.coverage_complete, "blocking": list(a.blocking)}
