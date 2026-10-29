"""Bootstrap de organización, fuentes y usuarios, y reinicio determinista del demo.

`reset_demo` borra y vuelve a crear sólo datos SYNTHETIC e HISTORICAL de la
organización. Nunca toca registros REAL ni la bitácora: cada reinicio abre una
corrida demo nueva (`DemoRun`). Los IDs se derivan con uuid5 del código del
fixture, así que un reinicio produce exactamente los mismos IDs.
"""
import json
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import config
from app.core.permissions import Role
from app.core.security import get_password_hash
from app.models import (
    DataKind, DemoRun, Document, DocumentVersion, EvidenceLink, Lot, Opportunity, Organization,
    Product, Requirement, Source, SourceStatus, Task, User, UserRole, Variant,
)
from app.services import audit, demo_documents

log = logging.getLogger(__name__)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
MX = ZoneInfo("America/Mexico_City")
_NS = uuid.UUID("5b3f8a3e-6f0e-4c64-9d0a-6a1b2c3d4e5f")

_DEMO_KINDS = (DataKind.SYNTHETIC.value, DataKind.HISTORICAL.value)


def stable_id(org_id: str, code: str) -> str:
    return str(uuid.uuid5(_NS, f"{org_id}:{code}"))


def normalize_external_id(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch.isalnum())


def current_demo_run_id(db: Session, org_id: str) -> str | None:
    return db.scalar(select(DemoRun.id).where(DemoRun.organization_id == org_id)
                     .order_by(DemoRun.started_at.desc(), DemoRun.id.desc()).limit(1))


# ── Bootstrap ────────────────────────────────────────────────────────────────

SOURCES = [
    {"key": "dof_sidof", "name": "DOF vía SIDOF", "base_url": "https://sidof.segob.gob.mx/",
     "allowed_domains": ["sidof.segob.gob.mx"], "method": "scraper",
     "notes": "Resúmenes oficiales de convocatorias. Adaptador del servidor (E2)."},
    {"key": "comprasmx", "name": "Compras MX · difusión", "base_url": "https://comprasmx.buengobierno.gob.mx/sitiopublico/",
     "allowed_domains": ["comprasmx.buengobierno.gob.mx"], "method": "manual",
     "notes": "Sitio dinámico; no se ha verificado una API pública. Importación manual mientras se investiga."},
    {"key": "imss", "name": "IMSS · licitaciones públicas", "base_url": "https://www.imss.gob.mx/licitaciones-publicas",
     "allowed_domains": ["www.imss.gob.mx", "imss.gob.mx"], "method": "manual",
     "notes": "Publicaciones institucionales; no representa cobertura exhaustiva."},
    {"key": "escenarios_demo", "name": "Escenarios de demostración", "base_url": None,
     "allowed_domains": [], "method": "fixture", "status": SourceStatus.ACTIVA.value,
     "notes": "Datos ficticios (SYNTHETIC). Nunca se presentan como resultado de una consulta en vivo."},
]

DEMO_USERS = [
    ("direccion@dipromedic.example", "Dirección (demo)", [Role.DIRECCION]),
    ("analista1@dipromedic.example", "Analista comercial 1 (demo)", [Role.ANALISTA_COMERCIAL]),
    ("analista2@dipromedic.example", "Analista comercial 2 (demo)", [Role.ANALISTA_COMERCIAL]),
    ("analista3@dipromedic.example", "Analista comercial 3 (demo)", [Role.ANALISTA_COMERCIAL]),
    ("revisor@dipromedic.example", "Revisor técnico documental (demo)", [Role.REVISOR_TECNICO]),
    ("responsable@dipromedic.example", "Responsable comercial (demo)", [Role.RESPONSABLE_COMERCIAL]),
    ("ti@dipromedic.example", "Administrador TI (demo)", [Role.ADMIN_TI]),
    ("presentador@dipromedic.example", "Presentador (todos los roles)", list(Role)),
]


def ensure_organization(db: Session) -> Organization:
    org = db.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name=config.ORGANIZATION_NAME, demo_mode=config.DEMO_MODE,
                           branding={"label": "Dipromedic · Demo", "white_label": True})
        db.add(org)
        db.flush()
    return org


def ensure_sources(db: Session, org: Organization) -> None:
    existing = set(db.scalars(select(Source.key).where(Source.organization_id == org.id)))
    for s in SOURCES:
        if s["key"] in existing:
            continue
        db.add(Source(id=stable_id(org.id, f"source:{s['key']}"), organization_id=org.id,
                      status=s.get("status", SourceStatus.NO_PROBADA.value),
                      **{k: v for k, v in s.items() if k != "status"}))
    db.flush()


def _ensure_user(db: Session, org: Organization, email: str, name: str, roles: list[Role], password: str) -> None:
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is not None:
        return
    user = User(organization_id=org.id, email=email, full_name=name,
                hashed_password=get_password_hash(password))
    user.roles = [UserRole(role=r.value) for r in roles]
    db.add(user)


def ensure_users(db: Session, org: Organization) -> None:
    if config.DEMO_USER_PASSWORD:
        for email, name, roles in DEMO_USERS:
            _ensure_user(db, org, email, name, roles, config.DEMO_USER_PASSWORD)
    if config.ADMIN_EMAIL and config.ADMIN_PASSWORD:
        _ensure_user(db, org, config.ADMIN_EMAIL.lower(), "Administrador TI", [Role.ADMIN_TI], config.ADMIN_PASSWORD)
    db.flush()


def bootstrap(db: Session) -> Organization:
    org = ensure_organization(db)
    ensure_sources(db, org)
    ensure_users(db, org)
    # El catálogo real va antes que la semilla: DEMO-LIC-001 propone variantes REAL (DPM-…) de Traufix.
    if config.IMPORT_CATALOG and db.scalar(select(Product.id).where(
            Product.organization_id == org.id, Product.data_kind == DataKind.REAL.value).limit(1)) is None:
        from app.services import catalog_import  # catalog_import importa este módulo
        catalog_import.log_summary(catalog_import.import_catalog(db, org.id, catalog_import.CATALOG_PATH))
    if db.scalar(select(Opportunity.id).where(Opportunity.organization_id == org.id).limit(1)) is None:
        reset_demo(db, org, actor_id=None)
    try:
        # Con disco efímero (sin bucket) los archivos semilla desaparecen en cada despliegue; se reponen.
        demo_documents.ensure_demo_files(db, org.id)
    except Exception:  # noqa: BLE001 - el almacenamiento no debe impedir el arranque
        log.warning("No se pudieron reponer los archivos semilla", exc_info=True)
    db.commit()
    return org


# ── Reinicio determinista ────────────────────────────────────────────────────

def _load() -> tuple[dict, dict]:
    base = json.loads((FIXTURES / "datos_demo.json").read_text(encoding="utf-8"))
    extra = json.loads((FIXTURES / "escenarios_demo.json").read_text(encoding="utf-8"))
    return base, extra


def _at(d: date | None, hour: int = 10) -> datetime | None:
    """Hora local de Ciudad de México convertida a UTC: todo se persiste en UTC."""
    if d is None:
        return None
    return datetime.combine(d, time(hour, 0), tzinfo=MX).astimezone(timezone.utc)


def _offset(days: int | None) -> date | None:
    return None if days is None else config.DEMO_BASE_DATE + timedelta(days=days)


def _purge(db: Session, org_id: str) -> list[str]:
    """Borra los datos SYNTHETIC e HISTORICAL. Devuelve las claves de almacenamiento de sus archivos."""
    opp_ids = list(db.scalars(select(Opportunity.id).where(
        Opportunity.organization_id == org_id, Opportunity.data_kind.in_(_DEMO_KINDS))))
    doc_ids = list(db.scalars(select(Document.id).where(
        Document.organization_id == org_id, Document.data_kind.in_(_DEMO_KINDS))))
    prod_ids = list(db.scalars(select(Product.id).where(
        Product.organization_id == org_id, Product.data_kind.in_(_DEMO_KINDS))))
    req_ids = list(db.scalars(select(Requirement.id).where(Requirement.opportunity_id.in_(opp_ids))))
    lot_ids = list(db.scalars(select(Lot.id).where(Lot.opportunity_id.in_(opp_ids))))
    task_ids = list(db.scalars(select(Task.id).where(
        Task.organization_id == org_id, Task.data_kind.in_(_DEMO_KINDS))))
    var_ids = list(db.scalars(select(Variant.id).where(Variant.product_id.in_(prod_ids))))
    stored_keys = list(db.scalars(select(DocumentVersion.storage_key).where(
        DocumentVersion.document_id.in_(doc_ids), DocumentVersion.storage_key.is_not(None))))

    db.execute(delete(EvidenceLink).where(EvidenceLink.requirement_id.in_(req_ids)))
    db.execute(delete(EvidenceLink).where(EvidenceLink.document_id.in_(doc_ids)))
    db.execute(delete(Task).where(Task.id.in_(task_ids)))
    db.execute(delete(Task).where(Task.opportunity_id.in_(opp_ids)))
    db.execute(delete(Requirement).where(Requirement.id.in_(req_ids)))
    db.execute(delete(DocumentVersion).where(DocumentVersion.document_id.in_(doc_ids)))
    db.execute(delete(Document).where(Document.id.in_(doc_ids)))
    db.execute(delete(Lot).where(Lot.id.in_(lot_ids)))
    db.execute(delete(Opportunity).where(Opportunity.id.in_(opp_ids)))
    db.execute(delete(Variant).where(Variant.id.in_(var_ids)))
    db.execute(delete(Product).where(Product.id.in_(prod_ids)))
    db.flush()
    return stored_keys


def _product_base_name(name: str) -> str:
    return name.split(" variante ")[0]


def _seed_catalog(db: Session, org_id: str, products: list[dict]) -> dict[str, Variant]:
    by_sku: dict[str, Variant] = {}
    groups: dict[str, Product] = {}
    for p in products:
        base_name = _product_base_name(p["name"])
        product = groups.get(base_name)
        if product is None:
            product = Product(id=stable_id(org_id, f"product:{base_name}"), organization_id=org_id,
                              name=base_name, family=p["family"], brand=p.get("brand"),
                              manufacturer=p.get("manufacturer"), data_kind=p["data_kind"])
            db.add(product)
            groups[base_name] = product
        variant = Variant(id=stable_id(org_id, p["id"]), organization_id=org_id, product=product,
                          sku=p["id"], name=p["name"], attributes=p.get("attributes") or {},
                          unit=p["unit"], price=Decimal(p["price_demo_mxn"]), currency="MXN",
                          stock_demo=p.get("stock_demo"), regulatory_reference=p.get("regulatory_reference"),
                          data_kind=p["data_kind"])
        db.add(variant)
        by_sku[p["id"]] = variant
    db.flush()
    return by_sku


# El fixture usa "unknown"; la UI y los textos derivados son en español.
_RESULTS = {None: "desconocido", "unknown": "desconocido"}

# Convocante y entidad sólo cuando el resumen oficial los declara (task pack §6); el resto queda por verificar.
_HISTORICAL_BUYERS = {
    "LA-50-GYR-050GYR075-I-134-2026": ("IMSS", "Querétaro"),
    "LA-56-AYO-056AYO954-N-88-2026": ("IMSS Bienestar", "Estado de México"),
}


def _seed_historical(db: Session, org_id: str, refs: list[dict], sources: dict[str, Source]) -> None:
    sidof = sources.get("dof_sidof")
    for h in refs:
        checked = date.fromisoformat(h["checked_on"])
        buyer, state = _HISTORICAL_BUYERS.get(h["id"], ("Por verificar", None))
        db.add(Opportunity(
            id=stable_id(org_id, h["id"]), organization_id=org_id,
            external_id=h["id"], normalized_id=normalize_external_id(h["id"]),
            title=h["title"], buyer=buyer, state=state,
            procedure_type="licitacion_publica", families=["Osteosíntesis", "Endoprótesis"],
            data_kind=DataKind.HISTORICAL.value, source_id=sidof.id if sidof else None,
            source_url=h["url"], last_checked_at=_at(checked, 0),
            reported_status=h.get("status"), verification_status="verificada",
            verification_scope=h.get("verification_scope"), result=_RESULTS.get(h.get("result"), "desconocido"),
            submission_at=_at(date.fromisoformat(h["opening_date"]), 0), submission_precision="date",
            source_timezone="America/Mexico_City", timezone_assumed=True,
            requires_human_review=True,
            notes="Metadatos tomados del resumen oficial; no del expediente completo. "
                  "La hora no se consultó y la zona horaria es supuesta.",
        ))
    db.flush()


def _real_variants(db: Session, org_id: str, extra: dict, synthetic: dict[str, Variant]) -> dict[str, Variant]:
    """Variantes REAL del catálogo importado que proponen las partidas (las DEMO-… son las de la semilla)."""
    wanted = {lot["proposed_variant"] for e in extra["scenarios"].values() for lot in e.get("lots", [])
              if lot.get("proposed_variant") and lot["proposed_variant"] not in synthetic}
    if not wanted:
        return {}
    return {v.sku: v for v in db.scalars(select(Variant).where(
        Variant.organization_id == org_id, Variant.sku.in_(wanted), Variant.data_kind == DataKind.REAL.value))}


def _proposed_variant(scenario_id: str, lot: dict, synthetic: dict[str, Variant],
                      real: dict[str, Variant]) -> Variant | None:
    """La variante propuesta de una partida: ficticia (DEMO-…) o real (DPM-…); si la real no está importada,
    la ficticia de respaldo, con un aviso (en pruebas el catálogo no se importa)."""
    sku = lot.get("proposed_variant")
    if not sku:
        return None
    variant = synthetic.get(sku) or real.get(sku)
    if variant is not None:
        return variant
    fallback = synthetic.get(lot.get("fallback_variant") or "")
    if fallback is not None:
        log.warning("%s partida %s: la variante REAL %s no está en el catálogo importado; se usa la variante "
                    "ficticia %s.", scenario_id, lot["number"], sku, fallback.sku)
    else:
        log.warning("%s partida %s: la variante %s no existe; la partida queda sin variante propuesta.",
                    scenario_id, lot["number"], sku)
    return fallback


def _lot_price(lot: dict) -> dict:
    """Precio unitario de la partida. En los escenarios siempre es ficticio, con su procedencia y moneda."""
    if not lot.get("unit_price"):
        return {"unit_price": None, "currency": None, "price_data_kind": None}
    return {"unit_price": Decimal(lot["unit_price"]), "currency": lot.get("currency") or "MXN",
            "price_data_kind": lot.get("price_data_kind") or DataKind.SYNTHETIC.value}


def _seed_scenarios(db: Session, org_id: str, scenarios: list[dict], extra: dict,
                    variants: dict[str, Variant], sources: dict[str, Source]) -> dict[str, Opportunity]:
    fixture_source = sources.get("escenarios_demo")
    real = _real_variants(db, org_id, extra, variants)
    opps: dict[str, Opportunity] = {}
    for s in scenarios:
        e = extra["scenarios"].get(s["id"], {})
        submission = _offset(s.get("deadline_offset_days"))
        has_dates = submission is not None
        opp = Opportunity(
            id=stable_id(org_id, s["id"]), organization_id=org_id,
            external_id=s["id"], normalized_id=normalize_external_id(s["id"]),
            title=s["title"], buyer=s["buyer"], state=e.get("state"),
            procedure_type=e.get("procedure_type"), character=e.get("character"),
            families=e.get("families", []), data_kind=DataKind.SYNTHETIC.value,
            source_id=fixture_source.id if fixture_source else None, source_url=s.get("official_url"),
            last_checked_at=None, reported_status=s.get("scenario_status"),
            verification_status=e.get("verification_status", "simulada"),
            verification_scope=e.get("source_error"),
            questions_at=_at(_offset(e.get("questions_offset_days"))) if has_dates else None,
            submission_at=_at(submission),
            ruling_at=_at(_offset(e.get("ruling_offset_days"))) if has_dates else None,
            source_timezone="America/Mexico_City" if has_dates else None,
            requires_human_review=s.get("requires_human_review", True),
            currency="MXN",
            notes=f"Escenario ficticio. Fechas relativas a DEMO_BASE_DATE ({config.DEMO_BASE_DATE.isoformat()}).",
        )
        for lot in e.get("lots", []):
            variant = _proposed_variant(s["id"], lot, variants, real)
            opp.lots.append(Lot(
                id=stable_id(org_id, f"{s['id']}:lot:{lot['number']}"), organization_id=org_id,
                number=lot["number"], description=lot["description"], family=lot.get("family"),
                quantity=Decimal(lot["quantity"]) if lot.get("quantity") else None, unit=lot.get("unit"),
                specs=lot.get("specs", {}), proposed_variant_id=variant.id if variant else None,
                **_lot_price(lot),
            ))
        db.add(opp)
        opps[s["id"]] = opp
    db.flush()
    return opps


def _seed_documents(db: Session, org_id: str, docs: list[dict], extra: dict,
                    variants: dict[str, Variant], opps: dict[str, Opportunity]) -> dict[str, Document]:
    out: dict[str, Document] = {}
    for d in docs:
        meta = extra["documents"].get(d["id"], {})
        variant = variants.get(meta.get("product_sku") or "")
        opp = opps.get(meta.get("opportunity") or "")
        doc = Document(
            id=stable_id(org_id, d["id"]), organization_id=org_id, code=d["id"],
            title=f"{d['title']} · {meta['label']}" if meta.get("label") else d["title"],
            scope=meta.get("scope", "empresa"), doc_type=meta.get("doc_type"),
            issuer_declared="Emisor ficticio", valid_until=_offset(d.get("valid_until_offset_days")),
            review_status=d.get("review_status", "pendiente"), data_kind=d["data_kind"],
            watermark=d.get("watermark") or config.WATERMARK,
            product_id=variant.product_id if variant else None, opportunity_id=opp.id if opp else None,
            current_version=d.get("version", 1),
        )
        doc.versions.append(DocumentVersion(
            id=stable_id(org_id, f"{d['id']}:v{doc.current_version}"), organization_id=org_id,
            version=doc.current_version, note="Versión semilla sin archivo adjunto.",
        ))
        db.add(doc)
        out[d["id"]] = doc
    # Cada documento SYNTHETIC lleva su PDF de prueba con la marca DEMO (D4); el hash queda en la versión.
    demo_documents.attach_demo_files(org_id, out, extra, {sku: v.attributes for sku, v in variants.items()})
    db.flush()
    return out


def _seed_requirements(db: Session, org_id: str, extra: dict, opps: dict[str, Opportunity],
                       docs: dict[str, Document]) -> dict[str, Requirement]:
    reqs: dict[str, Requirement] = {}
    for r in extra["requirements"]:
        opp = opps[r["opportunity_id"]]
        lot = next((l for l in opp.lots if l.number == r.get("lot")), None)
        req = Requirement(
            id=stable_id(org_id, r["id"]), organization_id=org_id, code=r["id"],
            opportunity_id=opp.id, lot_id=lot.id if lot else None, text=r["text"],
            req_type=r.get("req_type"), mandatory=r.get("mandatory", True), scope=r.get("scope"),
            attribute=r.get("attribute"), operator=r.get("operator"),
            expected_value=r.get("expected_value"), unit=r.get("unit"),
            page=r.get("page"), source_label="Bases ficticias del escenario", bases_version="v1",
            status=r["status"], status_reason=r.get("status_reason"),
            required_valid_until=_offset(r.get("required_valid_until_offset_days")),
            next_action=r.get("next_action"), data_kind=DataKind.SYNTHETIC.value,
        )
        db.add(req)
        reqs[r["id"]] = req
    db.flush()
    for ev in extra.get("evidence", []):
        doc = docs[ev["document"]]
        db.add(EvidenceLink(
            id=stable_id(org_id, f"evidence:{ev['requirement']}:{ev['document']}"), organization_id=org_id,
            requirement_id=reqs[ev["requirement"]].id, document_id=doc.id,
            document_version_id=doc.versions[-1].id if doc.versions else None,
            page=ev.get("page"), fragment=ev.get("fragment"), decision="propuesta",
        ))
    db.flush()
    return reqs


def _seed_tasks(db: Session, org_id: str, tasks: list[dict], extra: dict, reqs: dict[str, Requirement]) -> None:
    users = {u.email: u for u in db.scalars(select(User).where(User.organization_id == org_id))}
    mapping = extra.get("task_requirements", {})
    for t in tasks:
        req = reqs.get(mapping.get(t["id"], t["requirement_id"]))
        if req is None:
            continue
        assignee = users.get(t["assignee"])
        db.add(Task(
            id=stable_id(org_id, t["id"]), organization_id=org_id, code=t["id"],
            title=f"Atender requisito {req.code}: {req.text}", status=t.get("status", "pendiente"),
            assignee_id=assignee.id if assignee else None, due_date=_offset(t.get("due_offset_days")),
            opportunity_id=req.opportunity_id, requirement_id=req.id,
            data_kind=DataKind.SYNTHETIC.value,
            notes=None if assignee else f"Responsable de fixture no encontrado: {t['assignee']}",
        ))
    db.flush()


def reset_demo(db: Session, org: Organization, actor_id: str | None) -> dict:
    base, extra = _load()
    sources = {s.key: s for s in db.scalars(select(Source).where(Source.organization_id == org.id))}
    run = DemoRun(organization_id=org.id, actor_id=actor_id)
    db.add(run)
    db.flush()
    old_keys = _purge(db, org.id)
    variants = _seed_catalog(db, org.id, base["products"])
    _seed_historical(db, org.id, base["historical_references"], sources)
    opps = _seed_scenarios(db, org.id, base["scenarios"], extra, variants, sources)
    docs = _seed_documents(db, org.id, base["document_metadata"], extra, variants, opps)
    reqs = _seed_requirements(db, org.id, extra, opps, docs)
    _seed_tasks(db, org.id, base["tasks"], extra, reqs)
    # Los archivos SYNTHETIC anteriores (semilla y cargas de prueba) se borran al confirmar el reinicio.
    kept = {v.storage_key for d in docs.values() for v in d.versions if v.storage_key}
    demo_documents.delete_after_commit(db, [k for k in old_keys if k not in kept])
    summary = {
        "demo_base_date": config.DEMO_BASE_DATE.isoformat(),
        "variants": len(variants), "historical": len(base["historical_references"]),
        "scenarios": len(opps), "documents": len(docs), "requirements": len(reqs),
        "tasks": len(base["tasks"]),
    }
    run.summary = summary
    audit.record(db, organization_id=org.id, actor_id=actor_id, action="demo.reset",
                 resource_type="organization", resource_id=org.id, after=summary)
    db.flush()
    return summary
