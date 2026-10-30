# CLAUDE.md — Licit (demo comercial de licitaciones · Dipromedic)

Demo white label («Dipromedic · Demo») para descubrir procedimientos de compra pública de trauma y ortopedia,
contrastar partidas con un catálogo ficticio, administrar evidencia y faltantes, y generar borradores.
**La especificación manda:** `docs/spec/Task_Pack_Maestro_Dipromedic.md` (léela antes de cada feature).
Decisiones en `docs/adr/`, avance en `docs/BACKLOG.md`, límites honestos en `docs/LIMITACIONES.md`.

Stack: FastAPI + SQLAlchemy 2 + PostgreSQL + **Alembic** (`app/`, `alembic/`) · React + Vite + TS + Tailwind + zustand
(`frontend/`), servida por el backend. Deploy en Railway con Dockerfile.

## Reglas no negociables (task pack §2)
1. `data_kind` (REAL / HISTORICAL / SYNTHETIC) está separado del estado. Un registro SYNTHETIC con fecha futura nunca es una oportunidad real.
2. Ausencia de evidencia = `desconocido` o `pendiente`, **nunca** cumplimiento. Una evidencia nueva lleva el requisito a `en_revision`, no a `cumple_validado`.
3. Nunca rellenar con fixtures una búsqueda vacía o fallida. Una fuente caída no significa que no haya licitaciones.
4. No inventar APIs de Compras MX, fechas, registros sanitarios, firmas ni precios. Los campos desconocidos quedan en null.
5. El dinero se maneja con `Decimal` y moneda explícita; la aritmética se hace en el backend.
6. Los permisos se evalúan en el backend (`require_permission(Perm.X)`) y el acceso a un recurso pasa por `get_owned()` (aislamiento por organización).
7. Cada cambio sensible se registra con `services.audit.record(...)` en la misma transacción.
8. Lo ficticio lleva la marca `DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN`; un registro ficticio usa `DEMO-SIN-VALIDEZ`.

## Reglas de repo
- Commit y push solo cuando el usuario lo pida; trabajar en `feat/*` o `fix/*`.
- Esquema: modifica el modelo, corre `alembic revision --autogenerate -m "..."`, revisa el archivo y prueba `upgrade`/`downgrade`.
- PKs y FKs son UUID `String(36)`. Los datos demo usan `stable_id()` (uuid5) para que el reinicio sea determinista.
- Fixtures: `app/fixtures/datos_demo.json` (original, no se edita) + `escenarios_demo.json` (complemento, ver ADR-002).

## Comandos
```bash
uv venv .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt   # WSL: python3 no trae venv/pip, usar uv
export DEMO_USER_PASSWORD=demo-pass SESSION_SECRET=dev
.venv/bin/alembic upgrade head                 # esquema
.venv/bin/python scripts/bootstrap.py          # org, fuentes, usuarios demo y semilla (si está vacía)
.venv/bin/python scripts/bootstrap.py --reset  # reinicio determinista del demo (no toca datos REAL)
.venv/bin/python scripts/ingest_catalog_documents.py --fetch   # PDFs de Traufix hacia el almacenamiento (OBJECT_STORAGE_* o STORAGE_DIR); idempotente
.venv/bin/uvicorn app.main:app --reload        # :8000 · Swagger en /docs
.venv/bin/python -m pytest -q                  # SQLite
TEST_DATABASE_URL=postgresql://postgres:toor@localhost:5433/licit .venv/bin/python -m pytest -q   # contra Postgres
cd frontend && npm install && npm run dev      # :5173 (proxy /api → :8000)
cd frontend && npm run build                   # tsc && vite build
docker compose up -d                           # postgres:17 local
```
`IMPORT_CATALOG=1` (el valor por defecto) hace que `bootstrap.py` importe el catálogo real de Dipromedic/Traufix en el primer
arranque; con `IMPORT_CATALOG=0` se omite. `JOBS_WORKER=1` corre el worker de la búsqueda en vivo dentro del servicio web.
Usuarios demo (`@dipromedic.example`): direccion, analista1..3, revisor, responsable y presentador (todos los roles).
`ti` (admin_ti) existe solo para operar el demo; TI y planta están fuera del alcance (solo comercial).

## Módulos de la demo de reunión (plan `docs/superpowers/plans/2026-10-29-demo-reunion-dipromedic.md`)
- **Fuentes y búsqueda:** `app/sources/sidof.py` (adaptador SIDOF), `app/core/netguard.py` (SSRF), `app/services/search_runs.py`
  (corridas, deduplicación, evidencia y cambio de bases), `app/routers/search.py`; radar en `frontend/src/pages/radar/*`.
- **Catálogo y documentos:** `app/services/catalog_import.py`, `catalog_documents.py`, `uploads.py`, `storage.py` (S3 o disco),
  `app/routers/{catalog,documents}.py`.
- **Expediente:** `app/services/matching.py` (motor determinista), `affinity.py`, `review.py` (evidencia, revisión, tareas),
  `workspace.py` (único get-or-create del expediente, decisión, aprobaciones segregadas, compuerta), `app/routers/workspaces.py`;
  interfaz en `frontend/src/pages/opportunity/*`.
- **Borradores:** `app/services/generation/*` (instantánea, seis DOCX, ZIP con manifiesto) y `app/routers/artifacts.py`.
- **Gobierno y vistas:** `app/routers/governance.py` (integridad, permisos, aprobaciones, panel),
  `app/services/dashboard.py`; páginas `Panel`, `Gobierno` y `components/AccountSwitcher.tsx`.
- Trabajos asíncronos: `app/services/jobs.py` (cola en Postgres; `JOBS_WORKER=1` la atiende dentro del servicio web).
- Etiquetas en español de la interfaz: `frontend/src/lib/labels.ts` (resultados del motor, fases, decisiones, acciones de bitácora).
- Casos negativos del pack §16: `tests/test_negative.py`. Guion de la reunión: `docs/GUION_DEMO.md`.

```bash
.venv/bin/python scripts/bootstrap.py --reset                    # reinicio del demo (o Operación → «Reiniciar demo», o POST /api/v1/demo/reset)
.venv/bin/python scripts/ingest_catalog_documents.py --fetch     # ingesta de PDFs del catálogo (>25 MB solo enlace)
JOBS_WORKER=1 IMPORT_CATALOG=1 .venv/bin/uvicorn app.main:app    # servidor con worker (búsqueda en vivo y borradores)
```

## Deploy (Railway)
Proyecto `licit-dipromedic` (workspace Atlas Tech) · servicios `web` + `Postgres` · https://web-production-9afcc.up.railway.app
El contenedor corre `alembic upgrade head && python scripts/bootstrap.py && uvicorn …`.

**No corras `railway up` desde `/mnt/c`**: el CLI sube los archivos como bytes nulos al leerlos desde el FS de Windows.
Copia los archivos versionados a un directorio del FS de Linux y despliega desde ahí:
```bash
D=$(mktemp -d) && git ls-files -z | xargs -0 -I{} cp --parents {} $D/ && cd $D && \
railway up --project c9c57e25-7e6d-45bf-89d6-361eb5647a96 --environment production --service web --detach
```
Tampoco agregues `.dockerignore` mientras esto siga así: el builder también lo recibe corrupto.

Variables: `DATABASE_URL` (referencia a Postgres), `SESSION_SECRET`, `DEMO_USER_PASSWORD`, `DEMO_MODE`,
`DEMO_BASE_DATE`, `CORS_ORIGINS`. Ver `.env.example`.
