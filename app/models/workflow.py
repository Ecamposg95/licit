"""Corridas demo, trabajos, búsquedas con evidencia, evaluación y expediente de licitación."""
import enum

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base
from app.models.base import OrgScoped, new_id, utcnow


class DemoRun(Base):
    """Cada reinicio del demo abre una corrida; los eventos de la bitácora la llevan en demo_run_id."""
    __tablename__ = "demo_runs"

    id = Column(String(36), primary_key=True, default=new_id)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    actor_id = Column(String(36), ForeignKey("users.id"))
    summary = Column(JSON)


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job(OrgScoped, Base):
    __tablename__ = "jobs"

    kind = Column(String(60), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default=JobStatus.QUEUED.value, index=True)
    progress = Column(Integer, nullable=False, default=0)          # 0–100
    message = Column(Text)
    result = Column(JSON)
    error = Column(Text)
    attempts = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String(120), unique=True)
    created_by_id = Column(String(36), ForeignKey("users.id"))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


class SearchRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    PARTIAL = "partial"              # algún término falló después de algún éxito
    FAILED = "failed"


class SweepStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"


class Sweep(OrgScoped, Base):
    """Barrido diario (o manual) del DOF: agrupa las corridas de búsqueda de un día."""
    __tablename__ = "sweeps"

    day = Column(Date, nullable=False, index=True)
    attempt = Column(Integer, nullable=False, default=1)
    trigger = Column(String(10), nullable=False, default="daily")          # daily | manual
    status = Column(String(20), nullable=False, default=SweepStatus.QUEUED.value)
    terms = Column(JSON, nullable=False, default=list)
    dropped_terms = Column(JSON, nullable=False, default=list)
    counts = Column(JSON, nullable=False, default=dict)    # notes, procedures, new, updated, unchanged
    errors = Column(JSON, nullable=False, default=list)    # [{batch, code, message}]
    job_id = Column(String(36), ForeignKey("jobs.id"))
    created_by_id = Column(String(36), ForeignKey("users.id"))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


class SearchRun(OrgScoped, Base):
    __tablename__ = "search_runs"

    created_by_id = Column(String(36), ForeignKey("users.id"))
    query = Column(JSON, nullable=False, default=dict)             # términos y rango de fechas
    status = Column(String(20), nullable=False, default=SearchRunStatus.QUEUED.value)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    counts = Column(JSON, nullable=False, default=dict)
    errors = Column(JSON, nullable=False, default=list)
    job_id = Column(String(36), ForeignKey("jobs.id"))
    sweep_id = Column(String(36), ForeignKey("sweeps.id"), index=True)


class OpportunityEvidence(OrgScoped, Base):
    """Nota oficial consultada: URL, hora, hash y extracto que respaldan un procedimiento."""
    __tablename__ = "opportunity_evidence"

    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("sources.id"), nullable=False)
    search_run_id = Column(String(36), ForeignKey("search_runs.id"))
    url = Column(String(1000), nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    sha256 = Column(String(64), nullable=False)
    http_status = Column(Integer)
    excerpt = Column(Text)


class MatchAssessment(OrgScoped, Base):
    __tablename__ = "match_assessments"

    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    lot_id = Column(String(36), ForeignKey("lots.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(String(36), ForeignKey("variants.id", ondelete="CASCADE"))
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"))
    result = Column(String(30), nullable=False)
    explanation = Column(Text, nullable=False)
    rule = Column(String(80), nullable=False)
    engine_version = Column(String(20), nullable=False)
    catalog_value = Column(Text)      # lo que dice el catálogo, citado en la evaluación
    source_text = Column(Text)        # texto de la fuente (ficha o bases) del que sale ese valor


class BidWorkspace(OrgScoped, Base):
    __tablename__ = "bid_workspaces"

    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"),
                            nullable=False, unique=True)
    decision = Column(String(20), nullable=False, default="pendiente")   # pendiente | participar | no_participar
    decision_by_id = Column(String(36), ForeignKey("users.id"))
    decision_at = Column(DateTime(timezone=True))
    decision_reason = Column(Text)
    technical_approval_by_id = Column(String(36), ForeignKey("users.id"))
    technical_approval_at = Column(DateTime(timezone=True))
    commercial_approval_by_id = Column(String(36), ForeignKey("users.id"))
    commercial_approval_at = Column(DateTime(timezone=True))
    approvals_stale = Column(Boolean, nullable=False, default=False)
    affinity = Column(JSON)                                        # null = sin evaluar
    phase = Column(String(30), nullable=False, default="analisis")
    version = Column(Integer, nullable=False, default=1)


class GeneratedArtifact(OrgScoped, Base):
    __tablename__ = "generated_artifacts"

    workspace_id = Column(String(36), ForeignKey("bid_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    template_version = Column(String(20), nullable=False)
    snapshot = Column(JSON, nullable=False)
    data_version = Column(String(64), nullable=False)
    warnings = Column(JSON, nullable=False, default=list)
    storage_key = Column(String(500), nullable=False)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="borrador")
    created_by_id = Column(String(36), ForeignKey("users.id"))
