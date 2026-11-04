"""API del tablero «Hoy» y del contador de nuevas del menú (T17)."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import Perm, require_permission
from app.models import User
from app.schemas.hoy import HoyBadge, HoyOut
from app.services import hoy

router = APIRouter(tags=["hoy"])


@router.get("/api/v1/hoy", response_model=HoyOut)
def get_hoy(scope: Literal["mine", "team"] | None = Query(None),
            touch: bool = Query(True, description="false en el polling: no recorre la marca de visita"),
            db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    scope = scope or ("team" if "direccion" in user.role_names else "mine")
    now = datetime.now(timezone.utc)
    if touch:
        hoy.touch_visit(user, now)
    data = hoy.dashboard(db, user, now, scope)
    db.commit()    # solo las dos marcas de visita del usuario; sin auditoría
    return data


@router.get("/api/v1/hoy/badge", response_model=HoyBadge)
def get_badge(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    return HoyBadge(new=hoy.badge_count(db, user))
