from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import Perm, require_permission
from app.core.tenant import get_owned
from app.models import Job, User
from app.schemas.jobs import JobOut

router = APIRouter(prefix="/api/v1/jobs", tags=["trabajos"])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db),
            user: User = Depends(require_permission(Perm.OPPORTUNITY_READ))):
    return JobOut.model_validate(get_owned(db, Job, job_id, user, "Trabajo"))
