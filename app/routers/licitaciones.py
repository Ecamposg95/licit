from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.licitacion import EstatusLicitacion, Licitacion
from app.models.user import Role, User
from app.schemas.licitacion import LicitacionCreate, LicitacionOut, LicitacionUpdate

router = APIRouter(prefix="/api/licitaciones", tags=["licitaciones"])

_EDITORES = (Role.ADMIN.value, Role.GERENTE.value, Role.ANALISTA.value)


def _get_or_404(db: Session, licitacion_id: str) -> Licitacion:
    obj = db.get(Licitacion, licitacion_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Licitación no encontrada")
    return obj


@router.get("", response_model=list[LicitacionOut])
def list_licitaciones(
    q: str | None = None,
    estatus: EstatusLicitacion | None = None,
    dependencia: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(Licitacion)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Licitacion.titulo.ilike(like), Licitacion.numero_procedimiento.ilike(like)))
    if estatus:
        query = query.filter(Licitacion.estatus == estatus.value)
    if dependencia:
        query = query.filter(Licitacion.dependencia.ilike(f"%{dependencia}%"))
    return query.order_by(Licitacion.fecha_apertura.desc().nullslast()).offset(offset).limit(limit).all()


@router.post("", response_model=LicitacionOut, status_code=201)
def create_licitacion(
    payload: LicitacionCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*_EDITORES)),
):
    if db.query(Licitacion).filter(Licitacion.numero_procedimiento == payload.numero_procedimiento).first():
        raise HTTPException(status_code=409, detail="Ese número de procedimiento ya existe")
    obj = Licitacion(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{licitacion_id}", response_model=LicitacionOut)
def get_licitacion(licitacion_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return _get_or_404(db, licitacion_id)


@router.patch("/{licitacion_id}", response_model=LicitacionOut)
def update_licitacion(
    licitacion_id: str,
    payload: LicitacionUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*_EDITORES)),
):
    obj = _get_or_404(db, licitacion_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{licitacion_id}", status_code=204)
def delete_licitacion(
    licitacion_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMIN.value, Role.GERENTE.value)),
):
    db.delete(_get_or_404(db, licitacion_id))
    db.commit()

