"""Búsquedas guardadas por persona: limpieza, coincidencia con oportunidades y territorio (T17).

Una búsqueda coincide cuando se cumplen TODAS sus condiciones definidas (las vacías no restringen):
términos (título o algún extracto de evidencia), entidad federativa (igualdad), familias (intersección) e
institución (contiene). Todas las comparaciones ignoran acentos y mayúsculas.
"""
from collections import defaultdict
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Opportunity, OpportunityEvidence, SavedSearch, User
from app.services import search_runs
from app.sources.dates_es import normalize_text

MAX_PER_USER = 20
MAX_TERMS = 10
_LISTS = ("terms", "states", "families", "buyers")


def _key(text: str) -> str:
    return " ".join(normalize_text(text or "").split())


def _dedupe(values: Sequence[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        v = " ".join((raw or "").split())
        k = _key(v)
        if k and k not in seen:
            seen.add(k)
            out.append(v)
    return out


def clean(payload) -> dict:
    """Campos limpios (nombre recortado; listas sin vacíos ni repetidos). Sin nombre o sin condiciones → 422."""
    data = payload if isinstance(payload, dict) else payload.model_dump()
    out = {"name": (data.get("name") or "").strip()}
    if not out["name"]:
        raise AppError(422, "validation_error", "Escribe un nombre para la búsqueda guardada")
    out["terms"] = search_runs.normalize_terms(data.get("terms"), default=False)
    for f in _LISTS[1:]:
        out[f] = _dedupe(data.get(f))
    if len(out["terms"]) > MAX_TERMS:
        raise AppError(422, "validation_error", f"Usa como máximo {MAX_TERMS} términos")
    if not any(out[f] for f in _LISTS):
        raise AppError(422, "saved_search_empty", "Define al menos una condición de búsqueda")
    return out


def get_own(db: Session, saved_id: str, user: User) -> SavedSearch:
    """Búsqueda propia; la de otra persona o de otra organización responde 404 igual que una inexistente."""
    from app.core.tenant import get_owned

    saved = get_owned(db, SavedSearch, saved_id, user, "Búsqueda guardada")
    if saved.user_id != user.id:
        raise AppError(404, "not_found", "Búsqueda guardada no encontrada")
    return saved


def check_name_and_limit(db: Session, user: User, name: str, exclude_id: str | None = None) -> None:
    mine = list(db.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id)))
    if any(s.id != exclude_id and _key(s.name) == _key(name) for s in mine):
        raise AppError(409, "saved_search_duplicate", "Ya tienes una búsqueda guardada con ese nombre")
    if exclude_id is None and len(mine) >= MAX_PER_USER:
        raise AppError(422, "saved_search_limit", f"Máximo {MAX_PER_USER} búsquedas guardadas por persona")


def matches(ss: SavedSearch, opp: Opportunity, excerpts: Sequence[str]) -> bool:
    if ss.terms:
        texts = [opp.title, *excerpts]
        if not any(search_runs.matches_term(t, term) for term in ss.terms for t in texts):
            return False
    if ss.states and _key(opp.state or "") not in {_key(s) for s in ss.states}:
        return False
    if ss.families and not ({_key(f) for f in ss.families} & {_key(f) for f in (opp.families or [])}):
        return False
    if ss.buyers:
        buyer = _key(opp.buyer or "")
        if not any(_key(b) in buyer for b in ss.buyers):
            return False
    return True


def excerpts_by_opportunity(db: Session, opp_ids: list[str]) -> dict[str, list[str]]:
    if not opp_ids:
        return {}
    out: dict[str, list[str]] = defaultdict(list)
    for opp_id, excerpt in db.execute(select(OpportunityEvidence.opportunity_id, OpportunityEvidence.excerpt)
                                      .where(OpportunityEvidence.opportunity_id.in_(opp_ids))):
        if excerpt:
            out[opp_id].append(excerpt)
    return dict(out)


def territory(db: Session, org_id: str, opps: list[Opportunity]) -> dict[str, list[SavedSearch]]:
    """Por oportunidad, las búsquedas guardadas de cualquier persona de la organización que coinciden."""
    searches = list(db.scalars(select(SavedSearch).where(SavedSearch.organization_id == org_id)
                               .order_by(SavedSearch.created_at, SavedSearch.name)))
    excerpts = excerpts_by_opportunity(db, [o.id for o in opps]) if searches else {}
    return {o.id: [s for s in searches if matches(s, o, excerpts.get(o.id, []))] for o in opps}
