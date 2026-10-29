"""Borradores del expediente: generación asíncrona, historial, manifiesto y descarga autorizada (frente F)."""
import hashlib
import io
import json
import zipfile
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import Perm, require_permission
from app.core.tenant import get_owned
from app.models import GeneratedArtifact, Opportunity, User
from app.schemas.artifacts import (
    ArtifactOut, GenerateIn, GenerateOut, GenerationPreview, OpenRequirement, TemplateInfo,
)
from app.schemas.v1 import UserRef
from app.services import audit, jobs, workspace
from app.services.generation import JOB_KIND, normalize_templates
from app.services.generation.docx_templates import TEMPLATE_FILES
from app.services.generation.snapshot import build_snapshot
from app.services.storage import get_storage

router = APIRouter(prefix="/api/v1", tags=["borradores"])

MAX_KEY_LENGTH = 200


def _invalid(field: str, message: str) -> AppError:
    return AppError(422, "validation_error", "Datos inválidos", [{"field": field, "message": message}])


def _templates_info() -> list[TemplateInfo]:
    return [TemplateInfo(key=k, label=title, filename=name) for k, (name, title) in TEMPLATE_FILES.items()]


def _artifact_out(db: Session, rows: list[GeneratedArtifact]) -> list[ArtifactOut]:
    user_ids = {a.created_by_id for a in rows if a.created_by_id}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    out = []
    for a in rows:
        item = ArtifactOut.model_validate(a)
        item.created_by = UserRef.model_validate(users[a.created_by_id]) if a.created_by_id in users else None
        out.append(item)
    return out


# ── Vista previa y generación ────────────────────────────────────────────────

@router.get("/workspaces/{opportunity_id}/generation-preview", response_model=GenerationPreview)
def generation_preview(opportunity_id: str, db: Session = Depends(get_db),
                       user: User = Depends(require_permission(Perm.ARTIFACT_DOWNLOAD))):
    """Lo que se generaría con los datos de hoy: versión de datos, advertencias y pendientes. No crea nada."""
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    snap = build_snapshot(db, opp)
    last = db.scalars(select(GeneratedArtifact).where(
        GeneratedArtifact.organization_id == user.organization_id, GeneratedArtifact.opportunity_id == opp.id
    ).order_by(GeneratedArtifact.created_at.desc(), GeneratedArtifact.id.desc()).limit(1)).first()
    return GenerationPreview(
        data_version=snap["data_version"], generated_at=snap["generated_at"], notice=snap["notice"],
        templates=_templates_info(), warnings=snap["warnings"],
        open_requirements=[OpenRequirement(code=r["code"], text=r["text"], status=r["status"],
                                           mandatory=r["mandatory"], lot=r["lot"])
                           for r in snap["requirements"] if r["open"]],
        totals_text=snap["totals"]["text"], fiscal_text=snap["fiscal"]["text"],
        affinity_state=snap["affinity"]["state"],
        last_data_version=last.data_version if last else None,
        changed_since_last=bool(last and last.data_version != snap["data_version"]),
    )


@router.post("/workspaces/{opportunity_id}/generate", response_model=GenerateOut, status_code=202)
def generate(opportunity_id: str, payload: GenerateIn | None = None,
             idempotency_key: str | None = Header(default=None), db: Session = Depends(get_db),
             user: User = Depends(require_permission(Perm.PROPOSAL_GENERATE))):
    """Encola la generación del borrador. La misma `Idempotency-Key` devuelve el mismo trabajo (doble clic)."""
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    workspace.ensure_not_historical(opp)      # 409 historical_opportunity, igual que el expediente
    try:
        templates = normalize_templates(payload.templates if payload else None)
    except ValueError as exc:
        raise _invalid("templates", str(exc)) from None
    key = None
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > MAX_KEY_LENGTH:
            raise _invalid("Idempotency-Key", f"La clave debe tener entre 1 y {MAX_KEY_LENGTH} caracteres.")
        # La clave de la cola es global: se amarra a la organización y al procedimiento para que no choque con otras.
        key = "gen:" + hashlib.sha256(f"{user.organization_id}|{opp.id}|{idempotency_key}".encode()).hexdigest()
    job = jobs.enqueue(db, organization_id=user.organization_id, kind=JOB_KIND,
                       payload={"opportunity_id": opp.id, "templates": templates, "requested_by": user.id},
                       created_by_id=user.id, idempotency_key=key)
    db.commit()
    return GenerateOut(job_id=job.id, status=job.status)


# ── Historial ────────────────────────────────────────────────────────────────

@router.get("/workspaces/{opportunity_id}/artifacts", response_model=list[ArtifactOut])
def list_artifacts(opportunity_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_permission(Perm.ARTIFACT_DOWNLOAD))):
    opp = get_owned(db, Opportunity, opportunity_id, user, "Oportunidad")
    rows = list(db.scalars(select(GeneratedArtifact).where(
        GeneratedArtifact.organization_id == user.organization_id, GeneratedArtifact.opportunity_id == opp.id
    ).order_by(GeneratedArtifact.created_at.desc(), GeneratedArtifact.id.desc())))
    return _artifact_out(db, rows)


# ── Descarga y manifiesto ────────────────────────────────────────────────────

def _read_verified(artifact: GeneratedArtifact) -> bytes:
    try:
        data = get_storage().get(artifact.storage_key)
    except FileNotFoundError:
        raise AppError(404, "file_missing", "El paquete ya no está en el almacenamiento.") from None
    if hashlib.sha256(data).hexdigest() != artifact.sha256:
        # Nunca se entrega un paquete que no coincide con la huella registrada al generarlo.
        raise AppError(409, "integrity_error",
                       "El paquete almacenado no coincide con su huella SHA-256; no se entrega.")
    return data


def _chunks(data: bytes, size: int = 64 * 1024):
    view = io.BytesIO(data)
    while chunk := view.read(size):
        yield chunk


def _content_disposition(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "").strip() or "borrador.zip"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, db: Session = Depends(get_db),
                      user: User = Depends(require_permission(Perm.ARTIFACT_DOWNLOAD))):
    artifact = get_owned(db, GeneratedArtifact, artifact_id, user, "Borrador")
    data = _read_verified(artifact)
    audit.record(db, organization_id=artifact.organization_id, actor_id=user.id, action="artifact.download",
                 resource_type="generated_artifact", resource_id=artifact.id,
                 after={"opportunity_id": artifact.opportunity_id, "filename": artifact.filename,
                        "sha256": artifact.sha256, "size_bytes": artifact.size_bytes,
                        "data_version": artifact.data_version})
    db.commit()           # libera el bloqueo de la bitácora antes de transmitir
    return StreamingResponse(_chunks(data), media_type="application/zip", headers={
        "Content-Length": str(len(data)),
        "Content-Disposition": _content_disposition(artifact.filename),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    })


@router.get("/artifacts/{artifact_id}/manifest")
def artifact_manifest(artifact_id: str, db: Session = Depends(get_db),
                      user: User = Depends(require_permission(Perm.ARTIFACT_DOWNLOAD))):
    """El `manifest.json` del paquete, para verlo sin descargarlo."""
    artifact = get_owned(db, GeneratedArtifact, artifact_id, user, "Borrador")
    data = _read_verified(artifact)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return json.loads(zf.read("manifest.json").decode("utf-8"))
    except (KeyError, zipfile.BadZipFile, ValueError):
        raise AppError(409, "integrity_error", "El paquete no contiene un manifiesto legible.") from None
