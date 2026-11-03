"""Búsquedas guardadas: cada persona administra solo las suyas."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import SavedSearch, User
from app.schemas.saved_search import SavedSearchIn, SavedSearchOut
from app.services import audit, saved_searches

router = APIRouter(prefix="/api/v1/saved-searches", tags=["búsquedas guardadas"])
_FIELDS = ["name", "terms", "states", "families", "buyers"]


def _audit(db: Session, user: User, action: str, saved: SavedSearch, before=None, after=None) -> None:
    audit.record(db, organization_id=user.organization_id, actor_id=user.id, action=action,
                 resource_type="saved_search", resource_id=saved.id, before=before, after=after)


@router.get("", response_model=list[SavedSearchOut])
def list_saved(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id)
                           .order_by(SavedSearch.created_at, SavedSearch.name)))


@router.post("", response_model=SavedSearchOut, status_code=201)
def create_saved(payload: SavedSearchIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = saved_searches.clean(payload)
    saved_searches.check_name_and_limit(db, user, data["name"])
    saved = SavedSearch(organization_id=user.organization_id, user_id=user.id, **data)
    db.add(saved)
    db.flush()
    _audit(db, user, "saved_search.create", saved, after=data)
    db.commit()
    return saved


@router.put("/{saved_id}", response_model=SavedSearchOut)
def update_saved(saved_id: str, payload: SavedSearchIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    saved = saved_searches.get_own(db, saved_id, user)
    data = saved_searches.clean(payload)
    saved_searches.check_name_and_limit(db, user, data["name"], exclude_id=saved.id)
    before = audit.snapshot(saved, _FIELDS)
    for k, v in data.items():
        setattr(saved, k, v)
    _audit(db, user, "saved_search.update", saved, before=before, after=data)
    db.commit()
    return saved


@router.delete("/{saved_id}", status_code=204)
def delete_saved(saved_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    saved = saved_searches.get_own(db, saved_id, user)
    before = audit.snapshot(saved, _FIELDS)
    _audit(db, user, "saved_search.delete", saved, before=before)
    db.delete(saved)
    db.commit()
    return Response(status_code=204)
