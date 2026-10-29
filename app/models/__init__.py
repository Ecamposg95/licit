# Registrar aquí cada modelo para que Alembic (autogenerate) y los tests lo vean.
from app.models.base import DataKind  # noqa: F401
from app.models.identity import Organization, User, UserRole  # noqa: F401
from app.models.opportunity import (  # noqa: F401
    Lot, Opportunity, Source, SourceStatus, VerificationStatus,
)
from app.models.catalog import Product, Variant  # noqa: F401
from app.models.expediente import (  # noqa: F401
    AuditEvent, Document, DocumentVersion, EvidenceLink, Requirement, RequirementStatus, Task,
)
