"""Roles del task pack (§3) y matriz de permisos efectivos.

Una persona puede acumular roles; sus permisos son la unión. La autorización se
evalúa siempre en backend con `require_permission`.
"""
import enum

from fastapi import Depends

from app.core.errors import AppError


class Role(str, enum.Enum):
    DIRECCION = "direccion"
    ANALISTA_COMERCIAL = "analista_comercial"
    REVISOR_TECNICO = "revisor_tecnico"
    RESPONSABLE_COMERCIAL = "responsable_comercial"
    ADMIN_TI = "admin_ti"


ROLE_LABELS = {
    Role.DIRECCION: "Dirección",
    Role.ANALISTA_COMERCIAL: "Analista comercial",
    Role.REVISOR_TECNICO: "Revisor técnico documental",
    Role.RESPONSABLE_COMERCIAL: "Responsable comercial",
    Role.ADMIN_TI: "Administrador TI",
}


class Perm(str, enum.Enum):
    OPPORTUNITY_READ = "opportunity.read"
    OPPORTUNITY_WRITE = "opportunity.write"        # clasificar, editar metadatos
    OPPORTUNITY_IMPORT = "opportunity.import"
    SEARCH_RUN = "search.run"
    CATALOG_READ = "catalog.read"
    CATALOG_IMPORT = "catalog.import"
    CATALOG_EDIT = "catalog.edit"                  # fichas técnicas
    DOCUMENT_READ = "document.read"
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_VALIDATE = "document.validate"
    REQUIREMENT_READ = "requirement.read"
    REQUIREMENT_REVIEW = "requirement.review"      # validar cumplimiento técnico/documental
    TASK_READ = "task.read"
    TASK_ASSIGN = "task.assign"
    TASK_UPDATE = "task.update"
    BID_DECIDE = "bid.decide"                      # decidir participar
    PRICING_APPROVE = "pricing.approve"
    PROPOSAL_GENERATE = "proposal.generate"
    ARTIFACT_DOWNLOAD = "artifact.download"
    AUDIT_READ = "audit.read"
    USER_MANAGE = "user.manage"
    SOURCE_MANAGE = "source.manage"
    DEMO_RESET = "demo.reset"


_READ = {
    Perm.OPPORTUNITY_READ, Perm.CATALOG_READ, Perm.DOCUMENT_READ,
    Perm.REQUIREMENT_READ, Perm.TASK_READ,
}

ROLE_PERMISSIONS: dict[Role, set[Perm]] = {
    # Consulta cartera, riesgos, avance y decisiones. No modifica fichas técnicas.
    Role.DIRECCION: _READ | {Perm.ARTIFACT_DOWNLOAD, Perm.AUDIT_READ},
    # Busca, clasifica, importa, asigna y prepara borradores. No aprueba evidencias ni permisos.
    Role.ANALISTA_COMERCIAL: _READ | {
        Perm.OPPORTUNITY_WRITE, Perm.OPPORTUNITY_IMPORT, Perm.SEARCH_RUN,
        Perm.CATALOG_IMPORT, Perm.DOCUMENT_UPLOAD, Perm.TASK_ASSIGN, Perm.TASK_UPDATE,
        Perm.PROPOSAL_GENERATE, Perm.ARTIFACT_DOWNLOAD,
    },
    # Valida requisitos y documentos de su ámbito. No aprueba precios.
    Role.REVISOR_TECNICO: _READ | {
        Perm.REQUIREMENT_REVIEW, Perm.DOCUMENT_VALIDATE, Perm.DOCUMENT_UPLOAD,
        Perm.CATALOG_EDIT, Perm.TASK_UPDATE, Perm.ARTIFACT_DOWNLOAD,
    },
    # Decide participar y aprueba propuesta económica. No certifica documentos de terceros.
    Role.RESPONSABLE_COMERCIAL: _READ | {
        Perm.BID_DECIDE, Perm.PRICING_APPROVE, Perm.PROPOSAL_GENERATE,
        Perm.TASK_ASSIGN, Perm.TASK_UPDATE, Perm.ARTIFACT_DOWNLOAD,
    },
    # Usuarios, fuentes y operación técnica. Sin aprobación de negocio implícita.
    Role.ADMIN_TI: _READ | {
        Perm.USER_MANAGE, Perm.SOURCE_MANAGE, Perm.DEMO_RESET, Perm.AUDIT_READ,
    },
}


def permissions_for(roles: list[str]) -> set[Perm]:
    perms: set[Perm] = set()
    for r in roles:
        try:
            perms |= ROLE_PERMISSIONS[Role(r)]
        except ValueError:
            continue
    return perms


def require_permission(perm: Perm):
    from app.core.security import get_current_user

    def checker(user=Depends(get_current_user)):
        if perm not in permissions_for(user.role_names):
            raise AppError(403, "forbidden", f"Tu rol no tiene el permiso {perm.value}")
        return user

    return checker
