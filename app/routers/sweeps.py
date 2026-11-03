"""API del barrido en SIDOF: «Volver a barrer» y el historial de barridos (T17)."""
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import Perm, require_permission
from app.models import Sweep, User
from app.schemas.sweep import SweepAccepted, SweepOut
from app.services import sweeps  # también registra el handler `daily_sweep` y el gancho del worker

router = APIRouter(tags=["barrido"])


@router.post("/api/v1/sweeps", status_code=202, response_model=SweepAccepted)
def create_sweep(idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=64),
                 db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.SEARCH_RUN))):
    sweep = sweeps.start_manual(db, user, idempotency_key)
    db.commit()
    return SweepAccepted(sweep_id=sweep.id, job_id=sweep.job_id)


@router.get("/api/v1/sweeps", response_model=list[SweepOut])
def list_sweeps(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db),
                user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    rows = db.scalars(select(Sweep).where(Sweep.organization_id == user.organization_id)
                      .order_by(Sweep.created_at.desc(), Sweep.id.desc()).limit(limit))
    return [sweeps.serialize(db, s) for s in rows]
