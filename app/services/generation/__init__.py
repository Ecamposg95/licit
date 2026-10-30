"""Generación de borradores del expediente (frente F).

Importar este paquete registra el handler `generate_artifact` en la cola de trabajos.
"""
import hashlib
import logging
import uuid

from sqlalchemy.orm import Session

from app.models import GeneratedArtifact, Job, Opportunity
from app.services import audit, jobs, workspace
from app.services.generation.docx_templates import (
    TEMPLATE_FILES, TEMPLATE_VERSION, TEMPLATES, render_indice,
)
from app.services.generation.package import build_package
from app.services.generation.snapshot import build_snapshot
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

JOB_KIND = "generate_artifact"
TEMPLATE_KEYS = list(TEMPLATES)
_NS = uuid.UUID("9b0c6c5e-31f4-4a57-8a2f-3d1f5b6a7c10")


def normalize_templates(requested: list[str] | None) -> list[str]:
    """Claves en el orden del expediente y sin repetir. Lanza ValueError si alguna no existe o la lista queda vacía."""
    if requested is None:
        return list(TEMPLATE_KEYS)
    unknown = [k for k in requested if k not in TEMPLATES]
    if unknown:
        raise ValueError("Plantilla desconocida: " + ", ".join(sorted(set(unknown))))
    keys = [k for k in TEMPLATE_KEYS if k in requested]
    if not keys:
        raise ValueError("Selecciona al menos una plantilla")
    return keys


def artifact_id_for(job_id: str) -> str:
    """Identificador determinista: un trabajo repetido encuentra su artefacto en vez de crear otro."""
    return str(uuid.uuid5(_NS, job_id))


def storage_key(organization_id: str, opportunity_id: str, artifact_id: str) -> str:
    return f"artifacts/{organization_id}/{opportunity_id}/{artifact_id}.zip"


def _result(artifact: GeneratedArtifact) -> dict:
    return {"artifact_id": artifact.id, "data_version": artifact.data_version, "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes, "warnings": len(artifact.warnings or [])}


def generate_artifact(db: Session, job: Job) -> dict:
    """Handler del trabajo: instantánea, plantillas, ZIP, almacenamiento, fila `borrador` y auditoría."""
    payload = job.payload or {}
    artifact_id = artifact_id_for(job.id)
    existing = db.get(GeneratedArtifact, artifact_id)
    if existing is not None:
        return _result(existing)
    opp = db.get(Opportunity, payload.get("opportunity_id") or "")
    if opp is None or opp.organization_id != job.organization_id:
        raise LookupError("Oportunidad no encontrada")
    keys = normalize_templates(payload.get("templates"))
    workspace.ensure_not_historical(opp)      # una referencia histórica no se prepara como expediente

    jobs.set_progress(db, job, 5, "Preparando el espacio de trabajo")
    # El artefacto cuelga del expediente: se crea si falta, con la misma función (y auditoría) que usa E.
    ws = workspace.get_or_create_workspace(db, opp, job.created_by_id, workspace.ORIGIN_GENERATION)
    jobs.set_progress(db, job, 15, "Congelando la instantánea de datos")     # commit: nada de la bitácora queda abierto
    snapshot = build_snapshot(db, opp)
    rendered: dict[str, bytes] = {}
    for i, key in enumerate(keys):
        jobs.set_progress(db, job, 25 + int(45 * i / len(keys)), f"Generando «{TEMPLATE_FILES[key][1]}»")
        rendered[key] = render_indice(snapshot, keys) if key == "indice" else TEMPLATES[key](snapshot)
    jobs.set_progress(db, job, 75, "Empaquetando archivos y calculando huellas")
    data, manifest = build_package(snapshot, rendered)

    jobs.set_progress(db, job, 90, "Guardando el paquete")
    skey = storage_key(opp.organization_id, opp.id, artifact_id)
    sha256 = hashlib.sha256(data).hexdigest()
    stamp = snapshot["generated_at"][:16].replace("-", "").replace(":", "")
    filename = f"borrador_expediente_{_safe(opp.external_id)}_{stamp}Z.zip"
    storage = get_storage()
    storage.put(skey, data, "application/zip")
    try:
        artifact = GeneratedArtifact(
            id=artifact_id, organization_id=opp.organization_id, workspace_id=ws.id, opportunity_id=opp.id,
            template_version=TEMPLATE_VERSION, snapshot=snapshot, data_version=snapshot["data_version"],
            warnings=snapshot["warnings"], storage_key=skey, filename=filename, sha256=sha256,
            size_bytes=len(data), status="borrador", created_by_id=job.created_by_id)
        db.add(artifact)
        db.flush()
        audit.record(db, organization_id=opp.organization_id, actor_id=job.created_by_id, action="artifact.generate",
                     resource_type="generated_artifact", resource_id=artifact.id,
                     after={"opportunity_id": opp.id, "filename": filename, "sha256": sha256,
                            "size_bytes": len(data), "data_version": snapshot["data_version"],
                            "template_version": TEMPLATE_VERSION, "templates": keys,
                            "warnings": len(snapshot["warnings"]), "files": len(manifest["files"]) + 1,
                            "status": "borrador"})
    except Exception:
        storage.delete(skey)          # no deja un ZIP huérfano si la fila o la bitácora fallan
        raise
    job.message = "Borrador listo"        # sin commit propio: lo confirma el ejecutor junto con el resultado
    return _result(artifact)


def _safe(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in text)[:60] or "oportunidad"


jobs.register(JOB_KIND, generate_artifact)
