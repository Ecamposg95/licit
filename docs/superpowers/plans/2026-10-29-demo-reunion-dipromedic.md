# Demo de reunión Dipromedic · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir E1 en la demo de reunión: identidad Dipromedic, catálogo real de dipromedic.com, búsqueda en vivo en SIDOF,
evidencia documental, motor de correspondencia, flujo de expediente con separación de funciones, DOCX/ZIP y vistas por asistente.

**Architecture:** Monolito modular sobre E1 (FastAPI + SQLAlchemy 2 + Postgres + Alembic; React/Vite/TS/Tailwind). La Fase 0 fija
un esquema común y dos servicios compartidos (almacenamiento y trabajos). Después, siete frentes trabajan en paralelo en worktrees,
en dos oleadas, cada uno dueño de sus archivos. Un integrador une las ramas, conecta rutas y menú, y despliega en cada hito.

**Tech Stack:** Python 3.11, FastAPI 0.127, SQLAlchemy 2.0.45, Alembic 1.14, httpx, python-docx, openpyxl, fpdf2, boto3,
moto (pruebas); React 18, Vite 5, TypeScript estricto, Tailwind 3, zustand, lucide-react 1.50.0.

**Spec:** `docs/superpowers/specs/2026-10-28-demo-dipromedic-design.md` (y el pack `docs/spec/Task_Pack_Maestro_Dipromedic.md`).
Hallazgos que el plan usa: `docs/research/dipromedic-web.md`, `docs/research/dipromedic-catalogo.json`, `docs/research/fuentes-licitaciones.md`.

## Global Constraints

- Las 8 reglas no negociables de `CLAUDE.md` aplican a cada tarea: data_kind separado del estado, ausencia de evidencia ≠ cumplimiento, nunca rellenar búsquedas con fixtures, no inventar APIs/fechas/registros, Decimal + moneda, permisos en backend + `get_owned()`, auditoría en la misma transacción, y la marca DEMO en todo lo ficticio.
- Marca DEMO literal: `DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN` (`app.core.config.WATERMARK`). Registro ficticio: `DEMO-SIN-VALIDEZ`.
- Crédito literal en el pie y en cada ficha importada: `Contenido de catálogo: DIPROMEDIC S.A. DE C.V. · www.dipromedic.com · consultado el {checked_on}`.
- Colores de marca: azul `#0F75BC`, verde Fixi `#47AD36`, degradado `#63F24B→#47AD36`, navy `#001D4C`, azul Traufix `#004991`. Tipografía Inter. Sobre `#47AD36` nunca va texto blanco pequeño (contraste < 4.5:1); el botón primario es azul `#0F75BC` con texto blanco.
- El rayado ámbar `.hatch-synthetic` sigue siendo la marca exclusiva de lo SYNTHETIC; ningún color de marca lo sustituye.
- SIDOF: una petición/s y una a la vez; timeout de 10 s para conectar y 20 s para leer; 2 reintentos con espera de 1 s y luego 3 s. User-Agent `LicitDemo/1.0 (+contacto Atlas Technologies)`.
- Documentos: máximo 15 MB (`DOCUMENT_MAX_BYTES=15728640`); tipos permitidos por firma: PDF, DOCX sin macros, PNG, JPEG.
- Pesos de afinidad: familia 40, atributos 30, documental 20, capacidad 10. Si un componente no tiene datos, el total es `null` («cobertura incompleta»).
- Estados de requisito (8): `pendiente, desconocido, faltante, vencido, incumple, en_revision, cumple_validado, no_aplica_justificado`. Una evidencia nueva lleva el requisito a `en_revision`. Solo un humano con permiso marca `cumple_validado`.
- SKU de variante real: `DPM-` + `normalize_code(código del sitio)`. Las variantes ficticias conservan `DEMO-…`.
- Todo lo nuevo se escribe en español de México; las fechas se muestran en `America/Mexico_City` y se guardan en UTC.
- Cada tarea termina con `.venv/bin/python -m pytest -q` en verde (y `cd frontend && npm run build` si tocó el frontend), más un commit en la rama de su frente. Nadie hace push ni despliega salvo el integrador, y solo con autorización de Emmanuel.
- Los subagentes trabajan dentro de su worktree, nunca ejecutan `railway` y nunca tocan archivos de otro frente (ver «Propiedad de archivos»).

## Review Focus

1. **Notas de SIDOF con formato irregular** (varios procedimientos en una nota, fechas en prosa, campos ausentes, entidades HTML): el parser devuelve `null` en cada campo que no encuentra y nunca truena ni inventa. Prueba en C2: `test_parse_tolerates_mangled_note`.
2. **Fechas que solo traen el día** (sin hora): se muestran como fecha, sin correrse de día en la zona de México. Prueba en C2: `test_date_only_is_midnight_mexico_city`.
3. **Doble clic en Generar o Buscar ahora**: la misma `Idempotency-Key` devuelve el mismo trabajo. Pruebas en P0.2 (`test_enqueue_idempotent`) y F4 (`test_generate_idempotent`).
4. **Nombres de archivo hostiles o raros** (`../../x.pdf`, acentos, extensión en mayúsculas, 0 bytes): el nombre se sanea, el archivo de 0 bytes se rechaza y la extensión en mayúsculas se acepta. Prueba en D2: `test_filename_sanitized_and_empty_rejected`.
5. **Cambio de cuenta a mitad del recorrido o cuenta demo vencida**: el backend rechaza tokens de cuentas vencidas y la UI vuelve a cargar los permisos tras cambiar de cuenta. Prueba en G2: `test_expired_account_token_rejected`.

---

## Organización de la ejecución

| Oleada | Frentes (en paralelo, cada uno en su worktree) | Al cerrar |
|---|---|---|
| 0 | **Fase 0** (integrador, en secuencia) | Rama `feat/demo-reunion` con esquema común |
| 1 | **A** Marca · **B** Catálogo real · **C** Búsqueda en vivo · **D** Documentos | Integración 1 → **hito 1: deploy** (con autorización) |
| 2 | **E** Motor y expediente · **F** Generación · **G** Vistas y gobierno | Integración 2 → QA (**H**) → **hito 2: deploy y ensayo** |

Worktrees: `git worktree add ../licit-ws-<x> -b ws/<x> feat/demo-reunion` (la oleada 2 sale de `feat/demo-reunion`
después de la integración 1). Cada worktree crea su `.venv` con `uv venv .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt`
y su `frontend/node_modules` con `npm ci`.

### Propiedad de archivos

| Frente | Es dueño de | No toca |
|---|---|---|
| A | `frontend/tailwind.config.js`, `frontend/index.html`, `frontend/src/index.css`, `frontend/src/components/Layout.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/components/brand/*`, `frontend/public/brand/*`, `docs/adr/ADR-003-identidad.md` | backend, otras páginas |
| B | `app/services/catalog_import.py`, `app/fixtures/catalogo_dipromedic.json`, `app/routers/catalog.py`, `frontend/src/pages/Catalog.tsx`, `frontend/src/pages/catalog/*`, `frontend/src/lib/api-catalog.ts`, `tests/test_catalog_import.py` | `demo_seed.py` salvo la llamada en `bootstrap()` |
| C | `app/sources/*`, `app/core/netguard.py`, `app/services/search_runs.py`, `app/routers/search.py`, `tests/fixtures/sidof/*`, `scripts/capture_sidof_fixtures.py`, `frontend/src/pages/radar/*`, `frontend/src/lib/api-search.ts`, `tests/test_sidof.py`, `tests/test_search_runs.py`, `tests/test_netguard.py` | `Radar.tsx` solo para montar `radar/SearchDialog` e `ImportDialog` |
| D | `app/services/storage.py` (solo la parte S3), `app/services/uploads.py`, `app/services/demo_documents.py`, `app/routers/documents.py`, `scripts/ingest_catalog_documents.py`, `frontend/src/pages/Documents.tsx`, `frontend/src/pages/documents/*`, `frontend/src/lib/api-documents.ts`, `tests/test_documents.py` | |
| E | `app/services/matching.py`, `app/services/affinity.py`, `app/services/review.py`, `app/services/workspace.py`, `app/routers/workspaces.py`, `app/fixtures/escenarios_demo.json`, `frontend/src/pages/opportunity/*`, `frontend/src/lib/api-workspace.ts`, `tests/test_matching.py`, `tests/test_review.py`, `tests/test_workspace.py` | |
| F | `app/services/generation/*`, `app/routers/artifacts.py`, `frontend/src/pages/opportunity/ExpedienteTab.tsx`, `frontend/src/lib/api-artifacts.ts`, `tests/test_generation.py` | |
| G | `app/routers/governance.py`, `app/services/dashboard.py`, `frontend/src/pages/Panel.tsx`, `frontend/src/pages/Gobierno.tsx`, `frontend/src/components/AccountSwitcher.tsx`, `frontend/src/lib/api-governance.ts`, `tests/test_governance.py` | `Layout.tsx` (A monta el switcher en la integración) |
| Integrador | `app/main.py` (registro de routers), `frontend/src/App.tsx`, el arreglo `NAV` de `Layout.tsx`, `alembic/versions/*`, `app/models/*`, `requirements.txt`, `CLAUDE.md`, `docs/*.md` | |

Regla: si un frente necesita una columna o tabla nueva, **no** escribe migraciones. La pide al integrador, que la agrega en
una migración de integración.

---

## Fase 0 · Esquema común y servicios compartidos (integrador)

### Task P0.1: Esquema común, bitácora encadenada y corridas demo

**Files:**
- Modify: `app/models/identity.py`, `app/models/opportunity.py`, `app/models/catalog.py`, `app/models/expediente.py`, `app/models/__init__.py`
- Create: `app/models/workflow.py`, `alembic/versions/<rev>_esquema_demo_reunion.py`
- Modify: `app/services/audit.py`, `app/services/demo_seed.py`
- Test: `tests/test_schema_p0.py`

**Interfaces:**
- Produces (columnas y tablas nuevas, todas con `OrgScoped` salvo que se indique otra cosa):
  - `users.expires_at` DateTime tz null.
  - `audit_events.demo_run_id` String(36) null idx, `prev_hash` String(64) null, `hash` String(64) not null.
  - `demo_runs(id, organization_id, started_at, actor_id, summary JSON)` (sin `OrgScoped.updated_at`).
  - `products`: `line` String(80), `subfamily` String(200), `external_ref` String(200) idx, `source_url` String(1000), `checked_on` Date, `attribution` String(255), `images` JSON default [], `features` JSON default [], `data_quality_notes` JSON default [].
  - `variants`: `side` String(20) null, `source_text` Text, `field_provenance` JSON default {}.
  - `documents`: `external_url` String(1000), `third_party` Boolean default False, `page_count` Integer.
  - `evidence_links.created_by_id` FK users.
  - `lots`: `unit_price` Numeric(14,2), `currency` String(3), `price_data_kind` String(12).
  - `opportunity_evidence(opportunity_id FK cascade, source_id FK, search_run_id FK null, url, fetched_at, sha256 String(64), http_status Integer, excerpt Text)`.
  - `search_runs(created_by_id, query JSON, status, started_at, finished_at, counts JSON, errors JSON, job_id)`, con estados `queued|running|done|partial|failed`.
  - `jobs(kind, payload JSON, status queued|running|done|failed, progress Integer 0–100, message, result JSON, error Text, attempts Integer, idempotency_key String(120) unique null, created_by_id, started_at, finished_at)`.
  - `match_assessments(opportunity_id, lot_id, variant_id null, requirement_id null, result, explanation, rule, engine_version)`.
  - `bid_workspaces(opportunity_id unique, decision default "pendiente", decision_by_id, decision_at, decision_reason, technical_approval_by_id, technical_approval_at, commercial_approval_by_id, commercial_approval_at, approvals_stale Boolean default False, affinity JSON, phase default "analisis", version Integer default 1)`.
  - `generated_artifacts(workspace_id, opportunity_id, template_version, snapshot JSON, data_version String(64), warnings JSON, storage_key, filename, sha256, size_bytes, status default "borrador", created_by_id)`.
  - En Postgres, la migración crea la función `audit_events_immutable()` y el trigger `BEFORE UPDATE OR DELETE ON audit_events`, que lanza la excepción `audit_events es de solo inserción`.
  - `services.audit.record(...)`: misma firma que en E1. Ahora rellena `demo_run_id` con `current_demo_run_id(db, org)`, `prev_hash` con el `hash` del último evento de la organización y `hash` con `compute_event_hash(prev_hash, payload)`. En Postgres toma antes `pg_advisory_xact_lock(hashtext(organization_id))`.
  - `services.audit.compute_event_hash(prev_hash: str | None, payload: dict) -> str`: SHA-256 hex de `(prev_hash or "") + json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)`. El payload incluye organization_id, actor_id, action, resource_type, resource_id, before, after, correlation_id, demo_run_id y created_at en ISO.
  - `services.audit.verify_chain(db, organization_id) -> tuple[bool, int, str | None]`: devuelve si la cadena es válida, cuántos eventos revisó y el id del primer evento roto.
  - `services.demo_seed.current_demo_run_id(db, org_id) -> str | None`.
  - `reset_demo(...)`: crea un `DemoRun` **antes** de sembrar y deja de borrar `audit_events`.

- [ ] **Step 1: Write failing tests** en `tests/test_schema_p0.py`:
  - `test_audit_chain_links_events`: dos `record()` seguidos → `e2.prev_hash == e1.hash` y `verify_chain(...) == (True, n, None)`.
  - `test_verify_detects_tamper`: (solo SQLite) se cambia `after` de un evento con `UPDATE` y SQL directo → `verify_chain` devuelve `False` con el id de ese evento.
  - `test_audit_immutable_in_postgres`: se salta si el dialecto no es Postgres. Un `UPDATE audit_events SET action='x'` lanza `sqlalchemy.exc.DBAPIError` y el mensaje contiene `solo inserción`.
  - `test_reset_keeps_audit_and_opens_new_run`: tras dos reinicios, `count(demo_runs) == 3` (bootstrap + 2) y los eventos anteriores siguen ahí.
  - `test_history_shows_only_current_run`: se edita LIC-001, se reinicia y `GET /opportunities/{id}/history` no trae el `opportunity.update` anterior.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_schema_p0.py -q`. Expected: FAIL (faltan columnas y funciones).
- [ ] **Step 3: Implement** modelos, `audit.py` y `demo_seed.py`. En `_purge`, quitar el `delete(AuditEvent)`. En `routers/opportunities.py::opportunity_history`, agregar el filtro `AuditEvent.demo_run_id == current_demo_run_id(...)`.
- [ ] **Step 4: Generate migration** `DATABASE_URL=sqlite:///./gen.db .venv/bin/alembic upgrade head && DATABASE_URL=sqlite:///./gen.db .venv/bin/alembic revision --autogenerate -m "esquema demo reunion"`. Agregar a mano el trigger con `if op.get_bind().dialect.name == "postgresql":` en `upgrade()` y `downgrade()`. Borrar `gen.db`.
- [ ] **Step 5: Run** la suite completa en SQLite y en Postgres (`docker start licit-pg-test`, `TEST_DATABASE_URL=postgresql://postgres:toor@localhost:5433/licit`), más `alembic check` contra Postgres. Expected: todo PASS y «No new upgrade operations detected».
- [ ] **Step 6: Commit** `feat(p0): esquema común, bitácora encadenada e inmutable, corridas demo`.

### Task P0.2: Almacenamiento local y cola de trabajos

**Files:**
- Create: `app/services/storage.py`, `app/services/jobs.py`, `app/routers/jobs.py`
- Modify: `app/main.py` (lifespan: arrancar y detener el worker), `app/core/config.py`
- Test: `tests/test_jobs.py`, `tests/test_storage.py`

**Interfaces:**
- Produces:
  - `class Storage(Protocol)`: `put(key: str, data: bytes, content_type: str) -> None`, `get(key: str) -> bytes`, `delete(key: str) -> None`, `exists(key: str) -> bool`.
  - `class LocalStorage(Storage)`: raíz en `STORAGE_DIR` (default `./.storage`); rechaza claves con `..` o absolutas (lanza `ValueError`).
  - `get_storage() -> Storage`: devuelve `S3Storage` si `OBJECT_STORAGE_BUCKET` está definido (lo implementa D1) y `LocalStorage` si no.
  - `jobs.register(kind: str, handler: Callable[[Session, Job], dict | None]) -> None`.
  - `jobs.enqueue(db, *, organization_id, kind, payload: dict, created_by_id: str | None, idempotency_key: str | None = None) -> Job`: si la clave ya existe, devuelve el trabajo existente.
  - `jobs.set_progress(db, job, progress: int, message: str) -> None`: hace commit inmediato para que el polling lo vea.
  - `jobs.run_pending_once(db) -> Job | None`: toma uno con `with_for_update(skip_locked=True)`, ejecuta su handler, guarda `done` o `failed` con `error`; `attempts += 1`.
  - `jobs.start_worker(poll_seconds: float = 1.0) -> threading.Thread` y `jobs.stop_worker()`. Se activan con `JOBS_WORKER=1` (default 1; las pruebas lo ponen en 0).
  - Endpoint `GET /api/v1/jobs/{job_id}` → `{id, kind, status, progress, message, result, error, created_at, started_at, finished_at}`. Usa `get_owned` y requiere `opportunity.read`.

- [ ] **Step 1: Write failing tests:**
  - `test_enqueue_idempotent`: dos `enqueue` con la misma clave → mismo `id`.
  - `test_run_pending_executes_handler`: un handler registrado que devuelve `{"ok": 1}` → status `done` y `result == {"ok": 1}`.
  - `test_failing_handler_marks_failed`: un handler que lanza `RuntimeError("x")` → `failed` y `error` contiene `x`.
  - `test_job_endpoint_scoped`: un trabajo de otra organización responde 404.
  - `test_local_storage_roundtrip_and_rejects_traversal`: `put/get` funcionan y `put("../x")` lanza `ValueError`.
- [ ] **Step 2: Run** y verificar que FALLAN.
- [ ] **Step 3: Implement.** Agregar `JOBS_WORKER=0` en `tests/conftest.py`, y `STORAGE_DIR=<tmp>` vía `os.environ` en el mismo archivo.
- [ ] **Step 4: Run** la suite completa. Expected: PASS.
- [ ] **Step 5: Commit** `feat(p0): almacenamiento local y cola de trabajos en Postgres`.

### Task P0.3: Rama de integración y worktrees

- [ ] **Step 1:** `git checkout -b feat/demo-reunion` desde `feat/e1-base` (con P0.1 y P0.2 ya commiteados). Copiar `docs/research/dipromedic-catalogo.json` → `app/fixtures/catalogo_dipromedic.json` (el contenedor solo copia `app/`) y `docs/research/dipromedic/brand/*` → `frontend/public/brand/`.
- [ ] **Step 2:** agregar a `requirements.txt`: `httpx` (ya transitivo; fijar `httpx==0.28.1`), `python-docx==1.1.2`, `openpyxl==3.1.5`, `fpdf2==2.8.3`, `boto3==1.35.90`, `moto[s3]==5.0.26`. Instalar y correr la suite.
- [ ] **Step 3:** crear los 4 worktrees de la oleada 1 (`ws/a-marca`, `ws/b-catalogo`, `ws/c-busqueda`, `ws/d-documentos`).
- [ ] **Step 4: Commit** `chore(p0): dependencias, recursos de marca y catálogo en fixtures`.

---

## Frente A · Identidad Dipromedic (oleada 1, solo frontend)

### Task A1: Tokens de marca, tipografía y recursos

**Files:** Modify `frontend/tailwind.config.js`, `frontend/index.html`, `frontend/src/index.css`. Create `frontend/src/components/brand/Logo.tsx`.

**Interfaces:**
- Produces:
  - La paleta Tailwind `dpm`: `blue #0F75BC` (más una escala 50–900), `green #47AD36`, `navy #001D4C`, `traufix #004991`.
  - Las clases `.btn-primary` (azul) y `.btn-accent` (degradado verde con texto `navy`).
  - Los mismos nombres de clase que E1 (`.btn-*`, `.card`, `.table-base`, `.hatch-synthetic`). Las demás páginas no cambian.
  - `<Logo variant="color" | "white" className? />`, que usa `/brand/logo-dipromedic-color.png` y `/brand/logo-dipromedic-blanco.svg`.

- [ ] **Step 1:** sustituir la paleta `petrol` por `dpm` en `tailwind.config.js`, manteniendo un alias `petrol` → `dpm.blue` para no romper clases de E1. Inter en `fontFamily.sans`; `<link>` de Google Fonts a Inter 400/500/600/700 en `index.html`; favicon `/brand/favicon.png`; `<title>Dipromedic · Licitaciones (Demo)</title>`.
- [ ] **Step 2:** `npm run build`. Expected: compila sin errores.
- [ ] **Step 3: Commit** `feat(marca): tokens Dipromedic, Inter y logotipos`.

### Task A2: Shell, login y pie con crédito

**Files:** Modify `frontend/src/components/Layout.tsx`, `frontend/src/pages/Login.tsx`. Create `frontend/src/components/brand/Footer.tsx`.

**Interfaces:**
- Consumes: `<Logo/>` (A1) y `meta.demo_base_date` (E1).
- Produces:
  - Barra superior navy `#001D4C` con logo blanco, la etiqueta `Licitaciones` y una píldora `Demo`. Se conservan las píldoras de fecha base y de zona.
  - Un hueco `<div id="account-switcher-slot" />` donde G monta su componente en la integración.
  - El menú lateral con el activo en azul y una barra verde de 3 px.
  - `<Footer checkedOn="2026-10-28" />` con el crédito literal de Global Constraints.
  - Login a pantalla dividida: un panel navy con el logo blanco, el texto «Plataforma de licitaciones públicas · Demostración» y la mascota `fixi-color.png` como acento discreto; a la derecha, el formulario.

- [ ] **Step 1:** implementar y `npm run build`.
- [ ] **Step 2: Verify visually.** Levantar el backend como en CLAUDE.md, servir `frontend/dist` y tomar capturas de `/login` y `/radar` en 1440×900 y 1024×768 con Playwright desde el caché de npx (como en E1). Revisar: nada se desborda horizontalmente, el logo es nítido y el contraste de los textos en la barra cumple AA.
- [ ] **Step 3: Commit** `feat(marca): shell, login y crédito Dipromedic`.

### Task A3: ADR-003

- [ ] **Step 1:** escribir `docs/adr/ADR-003-identidad.md`: la identidad Dipromedic sustituye al white label (decisión de Emmanuel, 2026-10-28). Incluye la fuente de colores y logos, la regla de contraste, que los logos de terceros solo se muestran como texto y el crédito que pide el aviso de propiedad intelectual.
- [ ] **Step 2: Commit** `docs(marca): ADR-003 identidad Dipromedic`.

---

## Frente B · Catálogo real (oleada 1)

### Task B1: Importador del catálogo público

**Files:** Create `app/services/catalog_import.py`, `tests/test_catalog_import.py`. Modify `app/services/demo_seed.py::bootstrap` (una llamada).

**Interfaces:**
- Consumes: las columnas de P0.1 en `products` y `variants`, y `app/fixtures/catalogo_dipromedic.json`.
- Produces:
  - `normalize_code(raw: str) -> str`: convierte las letras cirílicas parecidas (А→A, В→B, С→C, Е→E, Н→H, К→K, М→M, О→O, Р→P, Т→T, Х→X, y sus minúsculas), quita espacios y pasa a mayúsculas.
  - `@dataclass ImportSummary(products: int, variants: int, updated: int, warnings: list[str])`.
  - `import_catalog(db, organization_id: str, path: Path) -> ImportSummary`: idempotente. Un `Product` por producto del JSON (`external_ref=id`, `line`, `family`, `subfamily`, `name`, `description`, `features`, `images`, `source_url=page_url`, `checked_on`, `attribution`, `data_kind=REAL`; `review_status="por_revisar"` si `data_quality_notes` no está vacío).
  - Variantes:
    - Cada fila de `variants[]` genera un `Variant` por cada código en `codes`. Con `izquierda`/`derecha`, `side` toma ese valor; con `unica`, `side=None`.
    - `sku = "DPM-" + normalize_code(code)` y `name = fila.name + (" · izquierda" | " · derecha" | "")`.
    - `attributes` = los `attributes` del producto (con su `source_text`) más `{"holes": {"values": fila.orificios, "unit": "orificios", "source_text": fila.source_text}}` cuando la fila trae `orificios`. Las tablas de diámetro × longitud se cargan como `{"diameter_mm": {"values": [...]}, "length_mm": {"values": [...]}}` solo si vienen en la fila.
    - `price`, `stock_demo` y `regulatory_reference` = `None`, y `field_provenance = {}`.
    - Un producto sin `variants` pero con `codes` genera un `Variant` por código con los atributos del producto; sin códigos, no genera variantes.
  - Nunca se deriva un atributo del nombre.
  - `bootstrap()` llama a `import_catalog` si no hay productos `REAL`. `reset_demo` no los toca, porque ya solo purga SYNTHETIC/HISTORICAL.

- [ ] **Step 1: Write failing tests:**
  - `test_import_counts`: los productos importados son tantos como la suma de `products` en el JSON (116) y `variants >= 200`.
  - `test_titan_large_left`: el variant `DPM-570` tiene `side == "izquierda"`, `attributes["holes"]["values"] == [4, 6, 8, 10]` y `attributes["material"]["value"] == "Aleación de titanio Ti6Al4V ELI"`, con `source_text` no vacío.
  - `test_alp35_single_code`: `DPM-198` tiene `side is None` y `holes.values == [5, 6, 7, 8, 9, 10, 12]`.
  - `test_import_idempotent`: dos importaciones dejan los mismos conteos.
  - `test_cyrillic_code_normalized`: `normalize_code("СL-1")` (C cirílica) `== "CL-1"`.
  - `test_real_variants_have_no_commercial_data`: todos los `Variant` REAL tienen `price is None and stock_demo is None and regulatory_reference is None`.
  - `test_reset_keeps_real_catalog`: después de `reset_demo`, el conteo de REAL no cambia.
- [ ] **Step 2: Run** y verificar que FALLAN.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** la suite completa (SQLite). Expected: PASS.
- [ ] **Step 5: Commit** `feat(catalogo): importador del catálogo público de Dipromedic`.

### Task B2: API del catálogo

**Files:** Create `app/routers/catalog.py`. Mover `list_products` desde `app/routers/resources.py` (el integrador borra la ruta vieja en la integración). Modify `app/schemas/v1.py` (agregar solo clases nuevas al final).

**Interfaces:**
- Produces:
  - `GET /api/v1/catalog/products?line&family&data_kind(repetible)&q` → `list[ProductCard]`. `ProductCard` = campos de `ProductOut` + `line, subfamily, source_url, checked_on, attribution, images, review_status, variant_count`. `q` busca en el nombre y en los SKU normalizados.
  - `GET /api/v1/catalog/products/{id}` → `ProductDetail` = `ProductCard` + `features`, `data_quality_notes`, `variants: list[VariantOut + side, source_text, field_provenance]` y `documents: list[DocumentOut]` (`product_id == id`).
  - `GET /api/v1/catalog/lines` → `[{line, product_count, families: [..]}]`.

- [ ] **Step 1: Write failing tests** `test_catalog_api_filters_line_and_code_search` (`q="198"` encuentra la placa ALP 3.5) y `test_product_detail_has_citations` (todos los atributos tienen `source_text`).
- [ ] **Step 2:** FAIL → implementar → PASS (la suite completa).
- [ ] **Step 3: Commit** `feat(catalogo): API de líneas, productos y detalle con citas`.

### Task B3: Catálogo en la interfaz

**Files:** Modify `frontend/src/pages/Catalog.tsx`. Create `frontend/src/pages/catalog/ProductDetail.tsx`, `frontend/src/pages/catalog/AttributeTable.tsx`, `frontend/src/lib/api-catalog.ts`.

**Interfaces:**
- Consumes: los endpoints de B2.
- Produces:
  - La ruta `/catalogo/:productId`, que el integrador registra en `App.tsx`.
  - `<AttributeTable attributes={...} />`: muestra valor y unidad, con la cita textual en un tooltip y el aviso «Fuente: página del producto».
  - En la tarjeta de producto, la imagen remota con `loading="lazy"`, un ícono de respaldo si falla y el crédito al pie.
  - Pestañas «Catálogo Dipromedic (REAL)» y «Variantes ficticias de escenarios (SIMULADO)»; la segunda con `.hatch-synthetic`.
  - En la ficha, los campos comerciales se muestran como «No publicado en el sitio», nunca como 0.
  - Las fichas con `review_status === "por_revisar"` muestran sus `data_quality_notes`.

- [ ] **Step 1:** implementar y `npm run build`.
- [ ] **Step 2: Verify** con curl o Playwright: la ficha TITAN muestra la tabla de orificios por lado y el enlace «Ver en dipromedic.com».
- [ ] **Step 3: Commit** `feat(catalogo): fichas reales con citas y variantes por lado`.

---

## Frente C · Búsqueda en vivo SIDOF (oleada 1)

### Task C1: Respuestas reales de SIDOF como fixtures

**Files:** Create `scripts/capture_sidof_fixtures.py`, `tests/fixtures/sidof/`.

- [ ] **Step 1:** escribir el script. Hace las peticiones exactas documentadas en `docs/research/fuentes-licitaciones.md`: `POST https://sidof.segob.gob.mx/busqueda/CargaNotasAvanzadas/` con `tipoBus=C`, `idOrg=TODOS`, los campos DataTables `columns[*][data]` y la palabra `osteosintesis` para 2026; `GET /dof/sidof/notas/nota/{codNota}` para 5801639 y 5797331; y una búsqueda sin resultados (`palabra=zzzxqv`). Guarda cada respuesta tal cual (`search_osteosintesis_2026.json`, `nota_5801639.json`, `nota_5797331.json`, `search_zero.json`) y un `README.md` con la fecha de captura.
- [ ] **Step 2: Run** el script una vez (es la única tarea que toca la red). Revisar que los 4 archivos existan y no estén vacíos.
- [ ] **Step 3: Commit** `test(busqueda): respuestas reales de SIDOF como fixtures`.

### Task C2: Adaptador SIDOF

**Files:** Create `app/sources/__init__.py`, `app/sources/base.py`, `app/sources/sidof.py`, `app/sources/dates_es.py`, `tests/test_sidof.py`.

**Interfaces:**
- Produces:
  - `class SourceUnavailable(Exception)` con `source: str`, `reason: str`, `retryable: bool`.
  - `@dataclass NoteHit(cod_nota: str, title: str, published_on: date | None, organism: str | None, url: str)`.
  - `@dataclass SearchPage(hits: list[NoteHit], total: int | None, confirmed: bool)`: `confirmed=False` cuando la respuesta no trae `messageCode`.
  - `@dataclass NoteDetail(cod_nota: str, html: str, sha256: str, fetched_at: datetime, url: str)`.
  - `@dataclass ProcedureParsed(external_id: str, buyer: str | None, title: str | None, state: str | None, volume: str | None, published_at: datetime | None, questions_at: datetime | None, submission_at: datetime | None, ruling_at: datetime | None, submission_precision: str, timezone_assumed: bool, excerpt: str)`.
  - `class SidofClient(http: httpx.Client | None = None, *, rate_limit_s: float = 1.0)`, con los métodos `search(term: str, date_from: date, date_to: date, start: int = 0, length: int = 100) -> SearchPage` y `get_note(cod_nota: str) -> NoteDetail`.
  - `parse_procedures(html: str) -> list[ProcedureParsed]`.
  - `dates_es.parse_spanish_datetime(text: str) -> tuple[datetime | None, str]`: devuelve la fecha y la precisión, `"datetime"` o `"date"`. Entiende formatos como «21 de octubre de 2026, 10:00 horas» y «21/10/2026». Sin hora → 00:00 en America/Mexico_City convertida a UTC, con `"date"`. Sin zona explícita → `timezone_assumed=True`.
  - Las URL públicas de nota son `https://sidof.segob.gob.mx/notas/docFuente/{cod_nota}` (y también `/notas/{cod_nota}` si así viene en el JSON).

- [ ] **Step 1: Write failing tests** (con `httpx.MockTransport` sirviendo los fixtures de C1):
  - `test_search_posts_expected_form`: el cuerpo enviado contiene `tipoBus=C` e `idOrg=TODOS`.
  - `test_search_parses_hits`: el número de hits coincide con el fixture y `confirmed is True`.
  - `test_zero_without_messagecode_is_unconfirmed`: el fixture `search_zero.json` da `hits == []` y `confirmed is False`.
  - `test_parse_note_5801639`: hay un procedimiento con `external_id == "LA-50-GYR-050GYR010-T-104-2026"`, `submission_at` en el día 2026-10-21 (hora local) y `buyer` que contiene «IMSS».
  - `test_parse_tolerates_mangled_note`: el HTML del fixture sin fechas y con entidades rotas da un procedimiento con fechas `None` y no lanza excepción.
  - `test_date_only_is_midnight_mexico_city`: `parse_spanish_datetime("2 de septiembre de 2026")` → `2026-09-02T06:00:00Z` con `"date"`.
  - `test_timeout_raises_source_unavailable`: un transporte que lanza `httpx.ConnectTimeout` tres veces → `SourceUnavailable(retryable=True)`.
  - `test_rate_limit_sleeps_between_calls`: se parchea `time.sleep` y se verifica una espera ≥ 1.0 s entre dos llamadas.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(busqueda): adaptador SIDOF con parser de notas y fechas en español`.

### Task C3: Corridas de búsqueda

**Files:** Create `app/services/search_runs.py`, `tests/test_search_runs.py`.

**Interfaces:**
- Consumes: `jobs.enqueue/register/set_progress` (P0.2), `SidofClient`, `parse_procedures` (C2), `normalize_external_id` (`demo_seed`) y `audit.record`.
- Produces:
  - `DEFAULT_TERMS = ["osteosintesis", "endoprotesis", "implantes ortopedicos", "material de osteosintesis"]`.
  - `start_search(db, user, terms: list[str], date_from: date, date_to: date, idempotency_key: str | None) -> SearchRun`: crea el `SearchRun` en `queued`, encola el trabajo `search_run` y audita `search.start`.
  - `run_search_job(db, job, client_factory=SidofClient) -> dict`: el handler registrado. Para cada término busca, y para cada hit nuevo trae la nota, la parsea y llama a `upsert_procedure`. Actualiza `Source(dof_sidof).status / last_checked_at / last_error` y fija `SearchRun.status`: `done` sin errores, `partial` con errores después de algún éxito, `failed` si todo falló. Los `counts` son `{notes, procedures, new, updated, unchanged}` y los `errors` `[{source, term, code, message}]`.
  - `upsert_procedure(db, org_id, proc: ProcedureParsed, note: NoteDetail, run: SearchRun) -> Literal["new", "updated", "unchanged"]`: deduplica por `normalized_id`. Si es nuevo, crea una `Opportunity` `REAL` con `source=dof_sidof`, `source_url=note.url`, `last_checked_at=note.fetched_at`, `verification_status = "verificada"` si `submission_at` no es nulo (o `"por_verificar"` si lo es) y `families` según el término. Siempre agrega `OpportunityEvidence(sha256=note.sha256, url=note.url, excerpt=proc.excerpt[:500])`. Si el `sha256` cambió respecto de la última evidencia, el resultado es `updated`; si no, `unchanged`.
  - Nunca crea oportunidades cuando el cliente lanzó `SourceUnavailable`.

- [ ] **Step 1: Write failing tests** (con un cliente falso que devuelve los fixtures de C1):
  - `test_search_creates_real_opportunities_with_evidence`: el procedimiento LA-50-GYR-050GYR010-T-104-2026 existe con `data_kind == "REAL"` y una evidencia.
  - `test_same_note_twice_is_unchanged`: la segunda corrida tiene `counts["unchanged"] >= 1` y no duplica.
  - `test_source_failure_partial_and_no_records`: el segundo término lanza `SourceUnavailable` → `status == "partial"` y `errors[0]["code"] == "source_unavailable"`. Si el primero también falla → `failed` y 0 oportunidades nuevas.
  - `test_past_dates_never_open`: el radar devuelve `derived.code == "fecha_transcurrida"` para el procedimiento del 21-10.
  - `test_unconfirmed_zero_is_reported`: si `confirmed=False` y no hay hits, `errors` contiene `code == "zero_unconfirmed"` y el estado es `partial`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(busqueda): corridas asíncronas con deduplicación y evidencia`.

### Task C4: API de búsqueda e importación manual protegida contra SSRF

**Files:** Create `app/core/netguard.py`, `app/routers/search.py`, `tests/test_netguard.py`. Modify `app/schemas/v1.py` (clases nuevas al final).

**Interfaces:**
- Produces:
  - `netguard.validate_public_url(url: str, allowed_domains: list[str]) -> str`. Solo `https`; el host debe ser exactamente un dominio permitido o un subdominio suyo; las IP resueltas deben ser públicas (bloquea privadas, loopback, link-local, `169.254.169.254`, multicast, IPv6 ULA). Si no, lanza `AppError(422, "url_not_allowed", ...)`.
  - `netguard.safe_get(url, allowed_domains, max_bytes=5_000_000, max_redirects=3, timeout=(10, 20)) -> httpx.Response`: valida cada salto.
  - `POST /api/v1/search-runs`: body `{terms?: list[str], date_from?: date, date_to?: date}` y cabecera opcional `Idempotency-Key`. Requiere `search.run`. Responde `202 {search_run_id, job_id}`. Default: `DEFAULT_TERMS` del 1 de enero del año en curso a hoy.
  - `GET /api/v1/search-runs` (las últimas 20) y `GET /api/v1/search-runs/{id}`.
  - `POST /api/v1/opportunities/import`: requiere `opportunity.import` y acepta una de dos formas.
    - `{url}`: si el host es SIDOF, trae la nota con `safe_get`, la parsea y pasa por `upsert_procedure`.
    - `{metadata: {external_id, title, buyer, source_url, submission_at?, notes?}}`: para Compras MX, donde no se descarga nada. Crea una `REAL` con `verification_status="por_verificar"`, `reported_status="importada manualmente"` y la URL validada con `validate_public_url` para `comprasmx.buengobierno.gob.mx`.
    - Audita `opportunity.import` y responde `201 OpportunityRow`.

- [ ] **Step 1: Write failing tests:**
  - `test_rejects_metadata_ip` (`https://169.254.169.254/` → 422).
  - `test_rejects_redirect_to_private`: un transporte simulado redirige a `https://10.0.0.5/` y da 422.
  - `test_rejects_other_domain`.
  - `test_http_scheme_rejected`.
  - `test_manual_import_comprasmx_por_verificar`.
  - `test_search_run_requires_permission`: la cuenta revisor recibe 403.
  - `test_post_search_run_returns_202_and_job`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(busqueda): API de corridas e importación manual con protección SSRF`.

### Task C5: «Buscar ahora» e «Importar» en el radar

**Files:** Create `frontend/src/pages/radar/SearchDialog.tsx`, `frontend/src/pages/radar/ImportDialog.tsx`, `frontend/src/pages/radar/SearchRunsPanel.tsx`, `frontend/src/lib/api-search.ts`. Modify `frontend/src/pages/Radar.tsx` (habilitar los botones y montar los diálogos; nada más).

**Interfaces:**
- Consumes: los endpoints de C4 y `GET /api/v1/jobs/{id}` (P0.2).
- Produces:
  - **SearchDialog.** Términos precargados (editables) desde `DEFAULT_TERMS`, y un rango de fechas. Al lanzar, consulta `/jobs/{id}` cada 1 s y muestra una línea por término, por ejemplo `SIDOF · 12:04 · «osteosintesis» · 79 notas · 3 nuevas`, más una barra de avance.
  - Mensajes del SearchDialog:
    - `zero_unconfirmed`: «Sin resultados confirmados (la fuente no confirmó la respuesta)».
    - Error: «SIDOF no respondió: {mensaje}. Esto no significa que no haya licitaciones. Puedes importar manualmente».
    - Vacío real: «La búsqueda terminó sin procedimientos nuevos».
    - Al terminar, el radar se refresca con el filtro REAL activo.
  - **ImportDialog.** Una pestaña «URL de nota DOF (SIDOF)» y otra «Procedimiento de Compras MX (captura)», esta con el aviso «Compras MX bloquea la consulta automatizada; se registra como por verificar».
  - **SearchRunsPanel.** Historial plegable de corridas: hora, términos, estado y conteos.

- [ ] **Step 1:** implementar y `npm run build`.
- [ ] **Step 2: Verify** con el backend local y `JOBS_WORKER=1`: una búsqueda real desde la UI crea filas REAL en el radar con «Ver nota oficial». Anotar el resultado (conteos y hora) en el reporte del frente.
- [ ] **Step 3: Commit** `feat(busqueda): búsqueda en vivo e importación manual en el radar`.

---

## Frente D · Documentos y almacenamiento (oleada 1)

### Task D1: Backend S3

**Files:** Modify `app/services/storage.py` (agregar `S3Storage`). Test: `tests/test_storage.py`.

**Interfaces:**
- Produces: `S3Storage(endpoint: str, bucket: str, access_key: str, secret_key: str, region: str = "auto")` sobre boto3, que implementa `Storage`. Lo elige `get_storage()` cuando están definidas `OBJECT_STORAGE_ENDPOINT`, `OBJECT_STORAGE_BUCKET`, `OBJECT_STORAGE_ACCESS_KEY` y `OBJECT_STORAGE_SECRET_KEY`.

- [ ] **Step 1:** test `test_s3_storage_roundtrip` con `moto.mock_aws` (put/get/exists/delete) → FAIL → implementar → PASS.
- [ ] **Step 2: Commit** `feat(documentos): almacenamiento S3 compatible`.

### Task D2: Carga de documentos y versiones

**Files:** Create `app/services/uploads.py`, `app/routers/documents.py`, `tests/test_documents.py`.

**Interfaces:**
- Produces:
  - `sniff_content_type(data: bytes, filename: str) -> str`: reconoce `application/pdf` (`%PDF-`), `docx` (ZIP con `[Content_Types].xml` y sin `word/vbaProject.bin`), `image/png` e `image/jpeg`. Si no, lanza `AppError(422, "unsupported_file")`. Un DOCX cuyo contenido descomprimido supera 50 MB lanza `AppError(422, "archive_too_large")`.
  - `sanitize_filename(name: str) -> str`: conserva solo el nombre base, quita `..` y separadores, conserva acentos y limita a 120 caracteres.
  - `store_version(db, user, document: Document, data: bytes, filename: str, note: str | None) -> DocumentVersion`: calcula `sha256`, usa la clave `org/{org_id}/documents/{doc_id}/v{n}/{filename}`, incrementa `current_version` y audita `document.version_upload`.
  - `POST /api/v1/documents` (multipart: `file`, `title`, `scope`, `doc_type`, `data_kind`, `product_id?`, `opportunity_id?`, `valid_until?`): requiere `document.upload` y responde 201 `DocumentOut`.
  - `POST /api/v1/documents/{id}/versions` (multipart: `file`, `note?`) → 201 `DocumentVersionOut`. La versión anterior se conserva.
  - Un `data_kind` igual a `SYNTHETIC` hace que la UI muestre la marca DEMO.

- [ ] **Step 1: Write failing tests:**
  - `test_upload_pdf_creates_version_with_hash`: `sha256` igual a `hashlib.sha256(data).hexdigest()`.
  - `test_rejects_oversize`: 15 MB + 1 → 413 con `code == "file_too_large"`.
  - `test_rejects_disguised_exe`: contenido `MZ...` llamado `x.pdf` → 422.
  - `test_rejects_docm_macro`.
  - `test_new_version_keeps_previous`: versiones `[1, 2]` y la 1 sigue descargable.
  - `test_direccion_cannot_upload`: 403.
  - `test_filename_sanitized_and_empty_rejected`: `../../ficha.PDF` se guarda como `ficha.PDF` y 0 bytes → 422 `empty_file`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(documentos): carga con validación de tipo, tamaño y versiones`.

### Task D3: Descarga autorizada

**Files:** Modify `app/routers/documents.py`. Test: `tests/test_documents.py`.

**Interfaces:**
- Produces:
  - `GET /api/v1/documents/{id}/versions/{version}/download`: requiere `document.read` y `get_owned`. Responde con `StreamingResponse`, `Content-Disposition: inline; filename*=UTF-8''…` y audita `document.download`.
  - Un documento `third_party` sin archivo → `409 {code: "external_document", details: {external_url}}`.

- [ ] **Step 1: Write failing tests** `test_download_other_org_404`, `test_download_audited` y `test_third_party_returns_external_url` → FAIL → implementar → PASS.
- [ ] **Step 2: Commit** `feat(documentos): descarga autorizada y auditada`.

### Task D4: Documentos de prueba con marca DEMO

**Files:** Create `app/services/demo_documents.py`. Modify `app/services/demo_seed.py::_seed_documents` (adjuntar el archivo generado a la versión semilla). Create `scripts/make_demo_upload_sample.py`.

**Interfaces:**
- Produces:
  - `render_demo_pdf(title: str, lines: list[str]) -> bytes` con fpdf2 y compresión desactivada: título, líneas, la marca DEMO literal en diagonal en cada página y en el pie, y `DEMO-SIN-VALIDEZ` donde corresponda un registro.
  - `reset_demo` guarda los 12 archivos en `demo/{org}/{code}.pdf`, rellena `sha256`/`size_bytes`/`content_type`/`storage_key` en sus versiones y borra los archivos SYNTHETIC anteriores.
  - El script genera `docs/demo/Ficha_tecnica_DEMO_para_carga.pdf`, que el presentador sube en el paso 7 del guion.

- [ ] **Step 1: Write failing tests** `test_demo_pdf_contains_watermark` (la marca DEMO literal aparece en los bytes) y `test_reset_attaches_demo_files` (las 12 versiones tienen `sha256` y el archivo existe en el almacenamiento) → FAIL → implementar → PASS.
- [ ] **Step 2: Commit** `feat(documentos): documentos de prueba con marca DEMO`.

### Task D5: Ingesta de PDFs del catálogo

**Files:** Create `scripts/ingest_catalog_documents.py`, `app/services/catalog_documents.py`. Test: `tests/test_documents.py`.

**Interfaces:**
- Consumes: `app/fixtures/catalogo_dipromedic.json` (`pdfs[]` y `products[].documents`), `netguard.safe_get` (de C4; si D termina antes que C, se usa un `httpx` directo con validación de dominio y se cambia en la integración) y `get_storage()`.
- Produces:
  - `OWN_HOSTS = {"dipromedic.com", "www.dipromedic.com", "traufix.com", "www.traufix.com"}`.
  - `ingest_catalog_documents(db, org_id, local_root: Path | None, fetch: bool) -> dict`:
    - Hosts propios: si el PDF existe en `local_root` se lee de ahí; si no y `fetch=True`, se descarga (máx. 90 MB, timeout 60 s). Se sube y se crea un `Document(REAL, scope="producto", doc_type` según la etiqueta`, third_party=False, external_url=url)` con su versión 1 y `sha256`. Se vincula al `Product` por `external_ref`.
    - Hosts de terceros: `Document(REAL, third_party=True, external_url=url)` sin archivo.
    - Idempotente por `external_url`. Devuelve `{uploaded, linked_external, skipped, errors}`.
  - CLI: `python scripts/ingest_catalog_documents.py [--local docs/research/dipromedic/pdfs] [--fetch]`.

- [ ] **Step 1: Write failing tests** `test_ingest_own_pdf_from_local` (crea un PDF temporal en `local_root` → documento con `sha256`) y `test_third_party_link_only` → FAIL → implementar → PASS.
- [ ] **Step 2: Commit** `feat(documentos): ingesta de técnicas quirúrgicas y folletos como evidencia real`.

### Task D6: Centro documental en la interfaz

**Files:** Modify `frontend/src/pages/Documents.tsx`. Create `frontend/src/pages/documents/UploadDialog.tsx`, `frontend/src/pages/documents/DocumentViewer.tsx`, `frontend/src/lib/api-documents.ts`.

**Interfaces:**
- Produces:
  - `<UploadDialog onUploaded(doc) documentId? />`: si recibe `documentId`, sube una versión nueva. E lo reutiliza.
  - `<DocumentViewer documentId version page? />`: `<iframe>` del blob descargado con `#page=N`, cabecera con hash, versión y vigencia, y la marca DEMO si es SYNTHETIC. Un tercero muestra «Documento de tercero · enlace externo» con un botón que abre la URL.
  - La ruta `/documentos/:id` muestra el historial de versiones.

- [ ] **Step 1:** implementar y `npm run build`, más una verificación manual de carga, visor y versión 2.
- [ ] **Step 2: Commit** `feat(documentos): carga, visor por página y versiones en la interfaz`.

---

## Integración 1 · Hito 1 (integrador)

### Task I1: Unir la oleada 1 y desplegar

- [ ] **Step 1:** fusionar `ws/a-marca`, `ws/b-catalogo`, `ws/c-busqueda` y `ws/d-documentos` en `feat/demo-reunion`, en ese orden. Registrar los routers nuevos en `app/main.py` (catalog, search, documents, jobs), borrar `list_products` de `resources.py`, agregar a `App.tsx` las rutas `/catalogo/:productId` y `/documentos/:id`, y cambiar `safe_get` en D5.
- [ ] **Step 2:** suite completa en SQLite y Postgres, `npm run build` y `alembic check`.
- [ ] **Step 3: Infra Railway** (con autorización de Emmanuel):
  1. Crear el bucket (`railway bucket create`) y fijar en `web` las variables `OBJECT_STORAGE_*`.
  2. Borrar `users` y `licitaciones` de la base de producción (contenido ya revisado: 1 usuario admin y 0 licitaciones).
  3. Borrar `SECRET_KEY`, `ADMIN_EMAIL` y `ADMIN_PASSWORD`.
  4. Desplegar con la receta de CLAUDE.md.
  5. `railway ssh … python scripts/ingest_catalog_documents.py --fetch`.
  6. Lanzar una búsqueda real desde la UI de producción y anotar el resultado (o el bloqueo de la IP de Railway) en `docs/LIMITACIONES.md`.
- [ ] **Step 4:** push de `feat/demo-reunion` (con autorización). Commit `chore: integración 1`.

---

## Frente E · Motor de correspondencia y expediente (oleada 2)

### Task E1: Motor determinista

**Files:** Create `app/services/matching.py`, `tests/test_matching.py`.

**Interfaces:**
- Produces:
  - `@dataclass RequirementSpec(attribute: str, operator: Literal["eq", "contains", "gte", "lte", "in"], expected: str, unit: str | None)`.
  - `@dataclass RuleResult(result: Literal["coincide", "incumple", "desconocido", "no_comparable"], explanation: str, rule: str, catalog_value: str | None, source_text: str | None)`.
  - `ENGINE_VERSION = "1.0"`.
  - `evaluate(spec: RequirementSpec, attributes: dict) -> RuleResult`. Reglas:
    - Atributo ausente, o con valor `None` o «por validar» → `desconocido` («No declarado en el catálogo; no se infiere del nombre»).
    - `{"values": [...]}`: `eq` coincide si el valor esperado está en la lista; si no, `incumple` («Medidas disponibles: …»).
    - `contains`: compara textos sin acentos ni mayúsculas.
    - `gte`/`lte`: comparación numérica en `Decimal`.
    - Unidades: `cm→mm ×10` y `m→mm ×1000`; si la unidad no es convertible → `no_comparable`.
    - La explicación siempre cita `source_text` cuando existe.

- [ ] **Step 1: Write failing tests:**
  - `test_case_a_match`: `holes eq 6` contra `{"holes": {"values": [5, 6, 7, 8, 9, 10, 12]}}` → `coincide`.
  - `test_case_b_mismatch`: `holes eq 6` contra `{"holes": {"value": 8}}` → `incumple`.
  - `test_case_c_unknown`: `material contains titanio` contra `{"material": {"value": "por validar"}}` → `desconocido`.
  - `test_material_contains_real_value`: «titanio» contra «Aleación de titanio Ti6Al4V ELI» → `coincide`.
  - `test_unit_conversion_cm`: `diameter_mm eq 10 mm` contra `{"value": 1, "unit": "cm"}` → `coincide`.
  - `test_capacity_gte`: `stock_demo gte 200` contra `{"stock_demo": {"value": 25}}` → `incumple`.
  - `test_never_reads_name`: con `attributes={}` y `name="Placa titanio 6 orificios"` → `desconocido`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(motor): reglas deterministas de correspondencia con citas`.

### Task E2: Afinidad y vigencia documental

**Files:** Create `app/services/affinity.py`. Test: `tests/test_matching.py`.

**Interfaces:**
- Produces:
  - `WEIGHTS = {"familia": 40, "atributos": 30, "documental": 20, "capacidad": 10}`.
  - `@dataclass Affinity(components: dict[str, dict], total: int | None, coverage_complete: bool, blocking: list[str])`, donde cada componente es `{weight, score: float | None, known: int, total: int}`.
  - `compute_affinity(opportunity, requirements, assessments) -> Affinity`.
    - Familia: la proporción de partidas cuya familia está en las familias del catálogo propuesto.
    - Atributos: coincidencias sobre requisitos técnicos evaluados.
    - Documental: `cumple_validado` sobre requisitos documentales obligatorios.
    - Capacidad: requisitos de capacidad que coinciden.
    - Un componente con `total == 0` tiene `score=None`. Si alguno es `None`, el total es `None`.
    - `blocking` lista los códigos de los requisitos obligatorios en `incumple`, `faltante` o `vencido`.
  - `check_validity(valid_until: date | None, required_by: date | None, today: date) -> Literal["vigente", "vence_antes", "vencido", "sin_vigencia"]`.
  - `serialize_affinity(a: Affinity) -> dict`, que se guarda en `bid_workspaces.affinity`.

- [ ] **Step 1: Write failing tests:**
  - `test_weights_exact`.
  - `test_incomplete_coverage_total_none`.
  - `test_blocking_listed_even_with_high_score`.
  - `test_valid_today_expires_before_required`: `valid_until = today + 90` y `required_by = today + 120` → `vence_antes`.
  - `test_expired`.
  - `test_no_valid_until_is_sin_vigencia`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(motor): afinidad por componente con cobertura y vigencia a fecha exigida`.

### Task E3: Escenario principal con productos reales de Traufix

**Files:** Modify `app/fixtures/escenarios_demo.json`, `app/services/demo_seed.py` (`_seed_scenarios` resuelve `proposed_variant` contra variantes REAL o SYNTHETIC y guarda `unit_price` y `price_data_kind` de la partida). Modify `docs/adr/ADR-002-fixtures.md`.

**Interfaces:**
- Consumes: el catálogo importado (B1), con variantes `DPM-…`.
- Produces: en DEMO-LIC-001, partidas que usan variantes REAL elegidas del JSON para que los tres casos sean ciertos con los datos citados.
  - Partida 1: placa bloqueada de titanio 3.5 mm de 6 orificios → `DPM-198` (orificios `[5…10, 12]`, material citado). Resultado: coincide.
  - Partida 2: la misma placa con 11 orificios → `DPM-198`. Resultado: incumple, porque «Medidas disponibles: 5, 6, 7, 8, 9, 10 y 12».
  - Partida 3: un atributo exigido que la página no declara, por ejemplo `length_mm eq 96` en la misma familia, verificando en el JSON que no esté declarado. Resultado: desconocido.
  - Cada partida lleva `unit_price` ficticio con `price_data_kind: "SYNTHETIC"` y `currency: "MXN"`.
  - Los requisitos DEMO-REQ-001…004 usan `operator` `contains` para material y `eq` para orificios.
  - Si el catálogo REAL no se importó (por ejemplo, en pruebas sin el JSON), el seed se queda con `DEMO-PLA-*` y registra un warning.

- [ ] **Step 1: Write failing test** `test_lic001_uses_real_traufix` en `tests/test_e1.py`: las variantes propuestas de LIC-001 tienen `data_kind == "REAL"` y SKU `DPM-…`; `lot.price_data_kind == "SYNTHETIC"`.
- [ ] **Step 2:** FAIL → implementar → PASS (y ajustar `test_matrix_for_main_scenario` a los nuevos SKU).
- [ ] **Step 3: Commit** `feat(escenarios): DEMO-LIC-001 sobre productos reales Traufix con precios ficticios marcados`.

### Task E4: Revisión de requisitos, evidencia y tareas

**Files:** Create `app/services/review.py`, `app/routers/workspaces.py` (la parte de requisitos), `tests/test_review.py`.

**Interfaces:**
- Consumes: `get_owned`, `audit.record`, `check_validity` (E2) y `store_version` (D2).
- Produces:
  - `link_evidence(db, user, requirement, document_version, page: int | None, fragment: str | None) -> EvidenceLink`: requiere `document.upload`. Guarda `created_by_id=user.id` y lleva el requisito a `en_revision` (salvo que ya esté en `cumple_validado`; en ese caso también vuelve a `en_revision`). Incrementa `version`, marca `approvals_stale=True` en el workspace y audita `requirement.evidence_linked`.
  - `review_requirement(db, user, requirement, decision: str, reason: str, expected_version: int) -> Requirement`: requiere `requirement.review`. Rechazos:
    - `reason` vacío → 422 `reason_required`.
    - `expected_version != version` → 409 `version_conflict`.
    - `decision == "cumple_validado"` sin evidencia → 422 `evidence_required`.
    - El revisor subió o vinculó alguna evidencia del requisito → 403 `self_approval`.
    - Alguna evidencia con `check_validity(...)` igual a `vencido` o `vence_antes` (contra `required_valid_until` o la fecha de presentación) → 422 `evidence_expired`.
    - Al aprobar, las evidencias pasan a `decision="aceptada"`; se fija `reviewer_id`, se incrementa `version`, se marca `approvals_stale=True` y se audita `requirement.review` con antes y después.
  - `assign_task(db, user, requirement, assignee_id: str, due_date: date | None, title: str | None) -> Task`: requiere `task.assign` y audita `task.assign`.
  - Endpoints:
    - `POST /api/v1/requirements/{id}/evidence` (`{document_id, version, page?, fragment?}`).
    - `PATCH /api/v1/requirements/{id}/review` (`{decision, reason, expected_version}`).
    - `POST /api/v1/requirements/{id}/tasks` (`{assignee_id, due_date?, title?}`).
    - `PATCH /api/v1/tasks/{id}` (`{status}`, requiere `task.update`).

- [ ] **Step 1: Write failing tests:**
  - `test_new_evidence_goes_to_review_not_valid` (US04).
  - `test_self_approval_blocked_even_for_presentador`.
  - `test_reviewer_can_validate_others_evidence`: analista vincula y revisor valida → `cumple_validado`.
  - `test_stale_version_409`.
  - `test_expired_evidence_blocks_validation`: el DOC-002 de LIC-005 da 422 `evidence_expired`.
  - `test_reason_required`.
  - `test_analista_cannot_review`: 403.
  - `test_assign_task_audited`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(expediente): evidencia a revisión, validación sin autoaprobación y tareas`.

### Task E5: Workspace, decisión y aprobaciones

**Files:** Create `app/services/workspace.py`. Modify `app/routers/workspaces.py`. Test: `tests/test_workspace.py`.

**Interfaces:**
- Produces:
  - `get_or_create_workspace(db, opportunity) -> BidWorkspace`.
  - `assess(db, user, opportunity) -> Affinity`: requiere `opportunity.write` o `requirement.review`. Evalúa cada requisito con `attribute` contra la variante propuesta de su partida, reemplaza los `MatchAssessment` de la oportunidad (con `engine_version`), guarda la afinidad y audita `workspace.assess`. **No cambia `Requirement.status`.**
  - `decide(db, user, ws, decision: Literal["participar", "no_participar"], reason: str)`: requiere `bid.decide`.
  - `approve(db, user, ws, kind: Literal["tecnica", "comercial"])`: `tecnica` requiere `requirement.review` y `comercial` requiere `pricing.approve`. Si el mismo usuario ya dio la otra aprobación → 403 `segregation`. Tras aprobar, `approvals_stale=False`.
  - `mark_ready(db, user, ws) -> BidWorkspace`: requiere `bid.decide`. Exige decisión `participar`, todos los obligatorios aplicables en `cumple_validado` o `no_aplica_justificado`, ambas aprobaciones y `approvals_stale is False`. Si falla → 409 `not_ready` con `details={"blockers": [...]}` (códigos de requisito y aprobaciones faltantes). Si pasa, `phase="listo_revision_final"`.
  - Cualquier `link_evidence` o `review_requirement` (E4) borra ambas aprobaciones, marca `approvals_stale=True` y regresa `phase` a `preparacion`.
  - Endpoints:
    - `GET /api/v1/workspaces/{opportunity_id}` → `{workspace, affinity, assessments: [{lot_id, requirement_id, variant_sku, result, explanation, catalog_value, source_text}]}`.
    - `POST …/assess`, `POST …/decision`, `POST …/approvals` (`{kind}`), `POST …/ready`.
  - `RequirementRow` (E1) gana el campo `assessment: dict | None`.

- [ ] **Step 1: Write failing tests:**
  - `test_assess_lic001_three_cases`: con el seed de E3, los resultados son `coincide`, `incumple` y `desconocido` para las partidas 1, 2 y 3.
  - `test_assess_does_not_change_status`.
  - `test_segregation_same_user_both_approvals_403`.
  - `test_ready_blocked_with_missing_mandatory` (US06): `blockers` contiene `DEMO-REQ-005`.
  - `test_change_after_approval_marks_stale`.
  - `test_ready_succeeds_when_all_validated`: escenario construido en la prueba.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(expediente): decisión, aprobaciones segregadas y compuerta de revisión final`.

### Task E6: Expediente interactivo en la interfaz

**Files:** Modify `frontend/src/pages/opportunity/LotsTab.tsx`, `frontend/src/pages/opportunity/RequirementsTab.tsx`, `frontend/src/pages/opportunity/SummaryTab.tsx`. Create `frontend/src/pages/opportunity/WorkspacePanel.tsx`, `frontend/src/pages/opportunity/ReviewDialog.tsx`, `frontend/src/pages/opportunity/EvidenceDialog.tsx`, `frontend/src/lib/api-workspace.ts`.

**Interfaces:**
- Consumes: los endpoints de E4 y E5, y `<UploadDialog/>` y `<DocumentViewer/>` de D6.
- Produces:
  - **Comparador** en Partidas: por requisito, una fila «Exigido | Catálogo (cita) | Resultado» con chip de texto e ícono, y el enlace a la ficha del producto (`/catalogo/:id`).
  - **Matriz** con acciones según permisos: «Asignar», «Vincular evidencia» (documento existente o carga nueva) y «Revisar» (decisión, motivo obligatorio y `expected_version`). Mensajes en español para `self_approval` («No puedes aprobar evidencia que tú cargaste. Cambia a la cuenta del revisor»), `evidence_expired`, `version_conflict` y `segregation`.
  - **WorkspacePanel** en el encabezado del detalle:
    - Barras de afinidad por componente con «conocidos / total»; si el total es `null`, «Cobertura incompleta».
    - Lista de bloqueantes, decisión, aprobaciones técnica y comercial con quién y cuándo, y el botón «Listo para revisión final», que muestra los bloqueantes del 409.
    - Leyenda fija: «La afinidad no es probabilidad de ganar ni dictamen de elegibilidad».

- [ ] **Step 1:** implementar y `npm run build`, más el recorrido manual de los pasos 5–7 del guion con cambio de cuenta.
- [ ] **Step 2: Commit** `feat(expediente): comparador, matriz interactiva y panel de decisión`.

---

## Frente F · Generación de borradores (oleada 2)

### Task F1: Instantánea y aritmética

**Files:** Create `app/services/generation/__init__.py`, `app/services/generation/snapshot.py`, `tests/test_generation.py`.

**Interfaces:**
- Consumes: los modelos de P0.1. La afinidad se lee de `bid_workspaces.affinity`; no se importa E.
- Produces:
  - `build_snapshot(db, opportunity) -> dict`, con las claves `opportunity`, `lots` (con `variant`, `unit_price`, `price_data_kind`, `subtotal`), `requirements` (estado, evidencias y tarea abierta), `workspace`, `affinity`, `totals`, `fiscal`, `generated_at`, `data_version`, `notice`.
  - `line_subtotal(quantity: Decimal | None, unit_price: Decimal | None) -> Decimal | None`: `(q * p).quantize(Decimal("0.01"), ROUND_HALF_UP)`, o `None` si falta alguno.
  - `fiscal = {"status": "pendiente", "text": "Tratamiento fiscal pendiente de configurar; no se aplicaron impuestos."}`.
  - `data_version`: SHA-256 del JSON canónico sin `generated_at`.
  - Los precios faltantes generan el warning «Partida {n}: precio pendiente»; el total suma solo los subtotales conocidos y lo indica.

- [ ] **Step 1: Write failing tests:**
  - `test_subtotal_exact`: `Decimal("40") * Decimal("1500.00")` → `60000.00`.
  - `test_missing_price_warning_and_partial_total`.
  - `test_data_version_stable`: dos instantáneas seguidas sin cambios dan el mismo `data_version`.
  - `test_synthetic_prices_flagged`: cada línea lleva `price_data_kind`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(generacion): instantánea versionada y aritmética exacta`.

### Task F2: Plantillas DOCX P0

**Files:** Create `app/services/generation/docx_templates.py`. Test: `tests/test_generation.py`.

**Interfaces:**
- Produces:
  - `TEMPLATE_VERSION = "1.0"`.
  - `TEMPLATES = {"resumen": render_resumen, "matriz": render_matriz, "faltantes": render_faltantes, "indice": render_indice, "propuesta_tecnica": render_propuesta_tecnica, "propuesta_economica": render_propuesta_economica}`.
  - Cada `render_*(snapshot: dict) -> bytes` genera un DOCX con encabezado «Dipromedic · Borrador de expediente · DEMO» y un pie con la marca DEMO literal, `data_version` y la fecha.
  - Cada dato faltante aparece como `[PENDIENTE: …]`. Nunca hay espacios de firma, sellos ni «presentado».
  - La propuesta económica lleva una tabla con cantidad, unidad, precio, moneda, subtotal y origen del precio (`SIMULADO`), más el texto fiscal de F1.

- [ ] **Step 1: Write failing tests** (abriendo cada DOCX con `python-docx`):
  - `test_all_templates_have_watermark`: la marca DEMO aparece en el pie de las 6 plantillas.
  - `test_economic_totals_text`: aparece `60,000.00`.
  - `test_pending_markers_for_open_requirements`: el número de `[PENDIENTE` es mayor o igual al de requisitos abiertos obligatorios.
  - `test_no_signature_words`: no aparecen «firma», «sello» ni «presentado» fuera de la marca.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(generacion): seis plantillas DOCX con marca DEMO y pendientes visibles`.

### Task F3: Paquete ZIP con manifiesto

**Files:** Create `app/services/generation/package.py`. Test: `tests/test_generation.py`.

**Interfaces:**
- Produces:
  - `build_package(snapshot: dict, rendered: dict[str, bytes]) -> tuple[bytes, dict]`. El ZIP contiene `docx/*.docx`, `matriz.csv` (UTF-8 con BOM), `matriz.xlsx`, `README_PENDIENTES.md` y `manifest.json`.
  - El manifiesto: `{files: [{name, sha256, size_bytes}], template_version, generated_at, data_version, opportunity: {external_id, data_kind}, provenance: {REAL: n, SYNTHETIC: n, HISTORICAL: n}, warnings, notice: WATERMARK, excluded_documents: [...]}`.
  - No incluye archivos de documentos de terceros ni privados; solo los lista en `excluded_documents` con su motivo.

- [ ] **Step 1: Write failing tests** `test_manifest_hashes_match`, `test_readme_lists_pending` y `test_third_party_excluded` → FAIL → implementar → PASS.
- [ ] **Step 2: Commit** `feat(generacion): ZIP con manifiesto, matriz CSV/XLSX y README de pendientes`.

### Task F4: Trabajo y endpoints

**Files:** Create `app/routers/artifacts.py`. Modify `app/services/generation/__init__.py` (registra el handler `generate_artifact`). Test: `tests/test_generation.py`.

**Interfaces:**
- Produces:
  - `POST /api/v1/workspaces/{opportunity_id}/generate` (`{templates?: list[str]}`, cabecera `Idempotency-Key`): requiere `proposal.generate` y responde 202 `{job_id}`.
  - El handler construye la instantánea, renderiza, empaqueta, guarda en `artifacts/{org}/{opp}/{artifact_id}.zip`, crea el `GeneratedArtifact(status="borrador")` y audita `artifact.generate`.
  - `GET /api/v1/workspaces/{opportunity_id}/artifacts` → la lista con `{id, created_at, created_by, data_version, warnings, sha256, size_bytes, status}`.
  - `GET /api/v1/artifacts/{id}/download`: requiere `artifact.download` y `get_owned`, y audita `artifact.download`.
  - El estado nunca pasa de `borrador`.

- [ ] **Step 1: Write failing tests:**
  - `test_generate_idempotent`: la misma clave da el mismo `job_id`.
  - `test_download_other_org_404`.
  - `test_admin_ti_cannot_download`: 403, porque `admin_ti` no tiene `artifact.download`.
  - `test_regenerate_keeps_previous_hash`: el ZIP anterior sigue con su `sha256`.
  - `test_download_audited`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(generacion): generación asíncrona versionada y descarga autorizada`.

### Task F5: Pestaña Expediente

**Files:** Create `frontend/src/pages/opportunity/ExpedienteTab.tsx`, `frontend/src/lib/api-artifacts.ts`.

**Interfaces:**
- Produces: la pestaña «Expediente», que el integrador agrega a `OpportunityDetail`. Incluye checkboxes de plantillas (todas marcadas), `data_version`, warnings y pendientes abiertos antes de generar, avance del trabajo, historial de generaciones con descarga y una vista previa del `manifest.json`. Aviso fijo: «Borrador · no apto para presentación».

- [ ] **Step 1:** implementar, `npm run build` y verificación manual: generar, descargar y abrir el ZIP.
- [ ] **Step 2: Commit** `feat(generacion): pestaña Expediente con historial y manifiesto`.

---

## Frente G · Vistas por asistente y gobierno (oleada 2)

### Task G1: Integridad y matriz de permisos

**Files:** Create `app/routers/governance.py`, `tests/test_governance.py`.

**Interfaces:**
- Consumes: `audit.verify_chain` (P0.1) y `ROLE_PERMISSIONS`/`ROLE_LABELS`.
- Produces:
  - `GET /api/v1/governance/audit/verify` (requiere `audit.read`) → `{ok, checked, first_broken_id, verified_at}`. Audita `audit.verify`.
  - `GET /api/v1/governance/permissions` (requiere `audit.read`) → `{roles: [{role, label, permissions: [..]}], permissions: [{code, label_es}]}`.
  - `GET /api/v1/governance/approvals` (requiere `audit.read`) → los eventos `requirement.review`, `workspace.decision`, `workspace.approval`, `workspace.ready` y `artifact.download` de la corrida actual, con actor y rol.
  - `GET /api/v1/governance/runs` → las corridas demo con su resumen.

- [ ] **Step 1: Write failing tests** `test_verify_ok`, `test_verify_detects_tamper_sqlite`, `test_permissions_matrix_matches_code` y `test_analista_forbidden` → FAIL → implementar → PASS.
- [ ] **Step 2: Commit** `feat(gobierno): verificación de integridad, matriz de permisos y aprobaciones`.

### Task G2: Cambio de cuenta demo y cuentas con vencimiento

**Files:** Modify `app/routers/governance.py`, `app/routers/auth.py`, `app/core/security.py`. Test: `tests/test_governance.py`.

**Interfaces:**
- Produces:
  - `GET /api/v1/demo/accounts` (sin autenticación, solo con `DEMO_MODE`; si no, 404) → `[{email, full_name, roles: [label]}]`, solo de usuarios `@dipromedic.example` activos. Nunca devuelve contraseñas.
  - El login rechaza cuentas con `expires_at < now` (401 `account_expired`), y `get_current_user` también.

- [ ] **Step 1: Write failing tests:**
  - `test_demo_accounts_listed_without_secrets`: ninguna clave contiene «pass».
  - `test_demo_accounts_404_when_not_demo`: con monkeypatch de `config.DEMO_MODE=False`.
  - `test_expired_account_login_401`.
  - `test_expired_account_token_rejected`: token emitido y luego `expires_at` en el pasado → 401.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(gobierno): cambio de cuenta demo y vencimiento de cuentas`.

### Task G3: Datos para dirección

**Files:** Create `app/services/dashboard.py`. Modify `app/routers/governance.py`. Test: `tests/test_governance.py`.

**Interfaces:**
- Produces:
  - `GET /api/v1/dashboard/direccion` (requiere `opportunity.read`) → `{by_data_kind: {REAL: {total, por_estado: {...}}, HISTORICAL: {...}, SYNTHETIC: {...}}, upcoming_real: [OpportunityRow] (abierta_verificada, ordenadas por fecha), last_search: SearchRun | None, scenarios_at_risk: [{external_id, blocking: [...], data_kind: "SYNTHETIC"}]}`. Los conteos nunca se suman entre tipos de dato.

- [ ] **Step 1: Write failing tests:**
  - `test_dashboard_never_mixes_kinds`: no existe ninguna clave `total` en la raíz y `SYNTHETIC` va separado.
  - `test_upcoming_real_excludes_synthetic_future`.
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3: Commit** `feat(vistas): datos del panel de dirección`.

### Task G4: Páginas Panel, Gobierno y selector de cuenta

**Files:** Create `frontend/src/pages/Panel.tsx`, `frontend/src/pages/Gobierno.tsx`, `frontend/src/components/AccountSwitcher.tsx`, `frontend/src/lib/api-governance.ts`.

**Interfaces:**
- Produces:
  - **`/panel`** (Dirección): tres columnas por tipo de dato con sus conteos (nunca un total combinado), próximas oportunidades reales verificadas (o «No hay oportunidades reales abiertas verificadas en este momento»), última búsqueda y escenarios simulados en riesgo con rayado. Sin gráficas sin datos.
  - **`/gobierno`**: botón «Verificar integridad de la bitácora» con resultado y hora, matriz de roles × permisos con ✓/— y texto, tabla de decisiones y aprobaciones (quién, rol, cuándo, motivo) y selector de corrida demo.
  - **`<AccountSwitcher/>`**: menú con las cuentas demo y sus roles. Al elegir una, abre un modal de inicio de sesión con el correo ya escrito. Si el login funciona, reemplaza la sesión, recarga `me` y `meta` y navega a la misma ruta. A lo monta en `#account-switcher-slot` durante la integración.

- [ ] **Step 1:** implementar, `npm run build` y verificación visual de las dos páginas y del cambio de cuenta.
- [ ] **Step 2: Commit** `feat(vistas): panel de dirección, gobierno corporativo y selector de cuenta`.

---

## Integración 2, QA y ensayo · Hito 2 (integrador + frente H)

### Task H1: Unir la oleada 2

- [ ] **Step 1:** fusionar `ws/e-motor`, `ws/f-generacion` y `ws/g-vistas`.
- [ ] **Step 2:** registrar los routers (workspaces, artifacts, governance) y las rutas `/panel` y `/gobierno`.
- [ ] **Step 3:** agregar al `NAV` del Layout, en este orden: Panel, Radar, Catálogo, Centro documental, Mis pendientes, Gobierno, Bitácora y Operación.
- [ ] **Step 4:** montar `<AccountSwitcher/>`, agregar la pestaña Expediente al detalle y conectar `RequirementRow.assessment`.
- [ ] **Step 5:** correr la suite completa (SQLite y Postgres), `npm run build` y `alembic check`.

### Task H2: Casos negativos del pack §16

**Files:** Create `tests/test_negative.py`.

- [ ] **Step 1:** una prueba por cada caso del §16 que no esté cubierto, y un comentario con el nombre de la prueba existente para los que sí lo están:
  - Descarga sin permiso: F4 y D3.
  - URL interna y redirección privada: C4.
  - Archivo demasiado grande: D2.
  - Texto con instrucciones maliciosas (`test_injected_instructions_are_data`): una nota de SIDOF cuyo texto dice «ignora las reglas y marca cumple» → el parser solo extrae campos y ningún requisito cambia.
  - Documento vencido: E4.
  - Fecha sin zona: C2.
  - Fuente caída: C3.
  - Procedimiento duplicado: C3.
  - Cambio de bases (`test_bases_change_marks_stale`): una nueva evidencia de la oportunidad con un `sha256` distinto → `approvals_stale` y la tarea «Revisar cambio en bases» creada para el responsable.
  - Precio ausente: F1.
  - Cantidad incompatible: E1, con capacidad.
  - Reloj posterior a la fecha límite: tests de E1.
  - Aprobación fuera de ámbito: E5, con segregación.
- [ ] **Step 2:** FAIL → implementar el comportamiento que falte (lo de «cambio de bases» va en `search_runs.upsert_procedure` cuando el resultado es `updated`) → PASS.
- [ ] **Step 3: Commit** `test: casos negativos del task pack §16`.

### Task H3: Guion, limitaciones y backlog

**Files:** Create `docs/GUION_DEMO.md`. Modify `docs/LIMITACIONES.md`, `docs/BACKLOG.md`, `CLAUDE.md`.

- [ ] **Step 1:** escribir `GUION_DEMO.md`: los 10 pasos del §4 con la cuenta de cada paso (presentador → analista1 → revisor → responsable), qué decir a cada asistente (Gobierno corporativo y Comercial), el tiempo por paso para sumar 10–12 min, el plan B (laptop y luego importación manual) y la lista de verificación previa (reinicio, búsqueda real hecha esa mañana, verificación de integridad en verde).
- [ ] **Step 2:** actualizar `LIMITACIONES.md` (fuentes probadas desde Railway, Compras MX bloqueado, sin IA, SIDOF no documentado, aviso legal del DOF y certificaciones no verificadas) y el `BACKLOG.md`.
- [ ] **Step 3: Commit** `docs: guion de la demo, limitaciones y backlog`.

### Task H4: Despliegue y ensayo

- [ ] **Step 1** (con autorización): push y deploy, y en producción `python scripts/bootstrap.py --reset`.
- [ ] **Step 2:** ensayo completo del guion en producción con un cronómetro. Anotar cada fallo y corregirlo en `fix/*`.
- [ ] **Step 3:** reinicio final, una búsqueda real y verificar la integridad. Entregar a Emmanuel la URL, las cuentas, el guion y la lista de limitaciones.
