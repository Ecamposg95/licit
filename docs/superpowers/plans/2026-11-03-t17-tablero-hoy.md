# T17 · Barrido diario, búsquedas guardadas y tablero «Hoy» — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que Licit busque sola cada mañana en el DOF, que cada persona defina su territorio con búsquedas guardadas,
clasifique lo nuevo (Seguir o Descartar) y abra un tablero «Hoy» con lo nuevo, las fechas clave y sus pendientes.

**Architecture:** Backend FastAPI con tres servicios nuevos (`saved_searches.py`, `sweeps.py`, `hoy.py`) y la
clasificación en `triage.py`. El barrido es un trabajo `daily_sweep` en la cola existente (`services/jobs.py`); el
worker lo encola desde un *tick* que corre cuando no hay trabajos. Cada lote de 10 términos es un `SearchRun` normal
ligado a un `Sweep` por `sweep_id`, ejecutado con la misma lógica de `search_runs.py`. El frontend agrega la página
`/hoy` (inicio), el diálogo de clasificación y «Mis búsquedas» en el Radar.

**Tech Stack:** FastAPI · SQLAlchemy 2 · Alembic · Postgres/SQLite · pytest · React + Vite + TS + Tailwind + zustand.

**Spec:** `docs/superpowers/specs/2026-11-03-t17-tablero-hoy-design.md` (léelo completo antes de cada tarea; manda
sobre este plan). Reglas del repo: `CLAUDE.md`.

## Global Constraints

- Solo `data_kind == "REAL"` cuenta como nuevo, se clasifica o entra en indicadores (regla 1). HISTORICAL y
  SYNTHETIC tienen `triage_status = NULL`.
- Un barrido `failed` o `partial` nunca se muestra como «0 nuevas» (regla 3); el tablero lo dice con el error.
- Descartar no borra; todo cambio de clasificación, de búsqueda guardada y del barrido se audita con
  `audit.record(...)` en la misma transacción (regla 7). Acciones: `saved_search.create`, `saved_search.update`,
  `saved_search.delete`, `opportunity.triage`, `search.start`, `search.finish`, `sweep.start`, `sweep.finish`.
- Permisos: leer «Hoy» `opportunity.read`; clasificar `opportunity.write`; «Volver a barrer» `search.run`;
  búsquedas guardadas: cualquier usuario autenticado, solo las propias (otra persona → 404). Sin permisos nuevos.
- SIDOF: `MAX_TERMS = 10` por corrida; **30 términos** máximo por barrido (3 lotes); ventana de **7 días** (hoy y los
  6 anteriores, fecha de `America/Mexico_City`).
- Barrido diario: `DAILY_SWEEP` (bool, por omisión verdadero; `0` lo apaga) y `DAILY_SWEEP_HOUR` (por omisión `6`),
  hora de `America/Mexico_City`. Reintento cada **1 h**, máximo **3 intentos** por día. Clave
  `daily_sweep:{org}:{AAAA-MM-DD}:{intento}`.
- Marca de visita: se recorre si `hoy_seen_at` tiene más de **30 minutos**.
- PK/FK `String(36)`; migración con `alembic revision --autogenerate`, revisada a mano (backfill) y probada con
  `upgrade`/`downgrade` en Postgres.
- Frontend: rellenos sólidos con texto blanco usan `brand`, `danger` o `ink` (ADR-004); superficies `bg-surface`.
  Textos en español de México. Lo no REAL lleva la marca `DEMOSTRACIÓN`.
- Pruebas: `.venv/bin/python -m pytest -q` (SQLite) y con `TEST_DATABASE_URL=postgresql://postgres:toor@localhost:5433/licit`.
  Frontend: `cd frontend && npm run build`. Commit al final de cada tarea en `feat/t17-tablero`.

## Review Focus

1. **Barrido interrumpido por un deploy** (el `Job` queda `failed` por `recover_stale_jobs` y el `Sweep` sigue
   `running`): el siguiente tick debe marcar el `Sweep` como `failed` y programar el reintento. → prueba
   `test_stale_sweep_is_failed_and_retried` (Tarea 4).
2. **Una búsqueda guardada sin condiciones** filtraría todo y volvería «de mi territorio» cualquier cosa: se rechaza
   con 422. → `test_saved_search_requires_a_condition` (Tarea 3).
3. **Clasificar una oportunidad SYNTHETIC o HISTORICAL** (por API directa): 422 `not_triageable`, sin evento. →
   `test_triage_rejects_non_real` (Tarea 2).
4. **Dos pestañas abiertas / recargar «Hoy»**: la lista de nuevas no se vacía antes de 30 minutos. →
   `test_reload_within_30_minutes_keeps_new_list` (Tarea 5).
5. **Términos repetidos con acentos entre búsquedas** («osteosíntesis» y «osteosintesis») no deben gastar dos lugares
   del tope de 30. → `test_compose_terms_dedupes_and_caps` (Tarea 4).

---

### Task 1: Esquema — clasificación, búsquedas guardadas, barridos y marca de visita

**Files:**
- Modify: `app/models/opportunity.py` (columnas en `Opportunity`)
- Modify: `app/models/identity.py` (columnas en `User`)
- Modify: `app/models/workflow.py` (`SearchRun.sweep_id`, modelos `Sweep` y `SweepStatus`)
- Create: `app/models/saved_search.py` (`SavedSearch`)
- Modify: `app/models/__init__.py` (exportar `SavedSearch`, `Sweep`, `SweepStatus`, `TriageStatus`)
- Create: `alembic/versions/20261103_<rev>_t17_tablero_hoy.py`
- Test: `tests/test_t17_schema.py`

**Interfaces:**
- Produces:
  - `TriageStatus(str, Enum)`: `NUEVA="nueva"`, `SIGUIENDO="siguiendo"`, `DESCARTADA="descartada"` (en `opportunity.py`).
  - `Opportunity.triage_status: String(12) | None` (index), `triage_reason: Text | None`,
    `triage_by_id: FK users | None`, `triage_at: DateTime(tz) | None`, `published_at: DateTime(tz) | None`.
  - `User.hoy_seen_at`, `User.hoy_prev_seen_at`: `DateTime(tz) | None`.
  - `SavedSearch(OrgScoped)`, tabla `saved_searches`: `user_id` FK users (CASCADE, index), `name String(120)`,
    `terms/states/families/buyers JSON` (listas, default `list`). `UniqueConstraint("user_id", "name")`.
  - `SweepStatus`: `queued|running|done|partial|failed`.
  - `Sweep(OrgScoped)`, tabla `sweeps`: `day Date` (index), `attempt Integer`, `trigger String(10)` (`daily|manual`),
    `status String(20)`, `terms JSON`, `dropped_terms JSON`, `counts JSON` (`notes, procedures, new, updated,
    unchanged`), `errors JSON` (lista de `{batch, code, message}`), `job_id FK jobs`, `created_by_id FK users`,
    `started_at`, `finished_at`.
  - `SearchRun.sweep_id: FK sweeps | None` (index).

- [ ] **Step 1: Write the failing test** `tests/test_t17_schema.py`

```python
def test_t17_columns_and_tables_exist():
    insp = inspect(engine)
    opp_cols = {c["name"] for c in insp.get_columns("opportunities")}
    assert {"triage_status", "triage_reason", "triage_by_id", "triage_at", "published_at"} <= opp_cols
    assert {"hoy_seen_at", "hoy_prev_seen_at"} <= {c["name"] for c in insp.get_columns("users")}
    assert "sweep_id" in {c["name"] for c in insp.get_columns("search_runs")}
    assert {"saved_searches", "sweeps"} <= set(insp.get_table_names())

def test_seed_opportunities_are_not_triaged():
    db = SessionLocal()
    kinds = {(o.data_kind, o.triage_status) for o in db.scalars(select(Opportunity))}
    assert all(t is None for k, t in kinds if k != "REAL")
    db.close()
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_t17_schema.py -q` → FAIL (columnas inexistentes).
- [ ] **Step 3: Add the models and columns** listed in Interfaces. `triage_status` sin default en el modelo (lo fijan
  los puntos de creación de la Tarea 2).
- [ ] **Step 4: Generate the migration** con `alembic revision --autogenerate -m "t17 tablero hoy"` contra la base
  local de Postgres (`DATABASE_URL=postgresql://postgres:toor@localhost:5433/licit_bk`). Revisar a mano y agregar al
  final de `upgrade()` el backfill:

```python
op.execute("UPDATE opportunities SET triage_status = CASE WHEN owner_id IS NULL THEN 'nueva' ELSE 'siguiendo' END "
           "WHERE data_kind = 'REAL'")
```
  Que no aparezcan cambios ajenos (tablas legacy ignoradas por `env.py`).
- [ ] **Step 5: Verify** `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` en `licit_bk` sin
  error; y `pytest tests/test_t17_schema.py -q` → PASS; suite completa → PASS.
- [ ] **Step 6: Commit** `feat(t17): esquema de clasificación, búsquedas guardadas y barridos`.

---

### Task 2: Clasificación (Seguir / Descartar)

**Files:**
- Create: `app/services/triage.py`
- Modify: `app/services/search_runs.py` (`_new_opportunity`: `triage_status="nueva"`, `published_at=proc.published_at`)
- Modify: `app/routers/search.py` (`_import_metadata`: `triage_status="nueva"`)
- Modify: `app/routers/opportunities.py` (endpoint de clasificación; hook en `patch_opportunity`; `_row` y detalle)
- Modify: `app/schemas/v1.py` (`OpportunityRow` + `triage_status`, `published_at`, `created_at`;
  `OpportunityDetail` + `triage_reason`, `triage_by: UserRef | None`, `triage_at`; nuevo `TriageIn`)
- Test: `tests/test_triage.py`

**Interfaces:**
- Consumes: `TriageStatus`, columnas de la Tarea 1.
- Produces:
  - `triage.apply(db, opp: Opportunity, actor: User, action: Literal["seguir", "descartar"], *, owner_id: str | None,
    reason: str | None) -> None` — valida, cambia, `opp.version += 1`, audita `opportunity.triage` con
    `before/after = {triage_status, owner_id, triage_reason}`. No hace commit.
  - `triage.on_owner_assigned(db, opp, actor: User) -> None` — si `opp.triage_status == "nueva"` y `opp.owner_id`,
    pasa a `siguiendo` y audita `opportunity.triage` con `after.via = "asignacion"`.
  - `POST /api/v1/opportunities/{id}/triage` body `TriageIn{expected_version: int, action: "seguir"|"descartar",
    owner_id: str | None, reason: str | None (max 500)}` → `OpportunityDetail`. Requiere `opportunity.write`.
- Reglas: no REAL → 422 `not_triageable`; `seguir` sin `owner_id` → 422 `owner_required` (el dueño pasa por
  `get_owned(User)`); `descartar` sin motivo (vacío tras `strip`) → 422 `reason_required`; mismo estado → 422
  `triage_unchanged`; versión distinta → 409 `version_conflict`. Transiciones válidas: `nueva→siguiendo`,
  `nueva→descartada`, `siguiendo→descartada`, `descartada→siguiendo`. Seguir limpia `triage_reason`.

- [ ] **Step 1: Write the failing tests** `tests/test_triage.py` (crear oportunidades REAL directamente con un helper
  `real_opp(db, external_id, **kw)` que pone `triage_status="nueva"`):
  - `test_follow_requires_owner_and_is_audited`: sin `owner_id` → 422 `owner_required`; con `owner_id` de
    analista1 → 200, `triage_status == "siguiendo"`, `owner.id` correcto, un evento `opportunity.triage` con
    `after["triage_status"] == "siguiendo"`.
  - `test_discard_requires_reason_and_keeps_record`: `reason="  "` → 422 `reason_required`; con motivo → 200,
    la oportunidad sigue en `GET /opportunities` con `triage_status == "descartada"`.
  - `test_discarded_can_be_followed_again` y `test_same_state_rejected` (`triage_unchanged`).
  - `test_triage_rejects_non_real`: una SYNTHETIC del seed → 422 `not_triageable` y ningún evento nuevo.
  - `test_triage_needs_write_permission`: con `revisor` (sin `opportunity.write`) → 403.
  - `test_patch_owner_on_new_moves_to_following`: `PATCH owner_id` sobre una `nueva` → `siguiendo` y evento
    `opportunity.triage` con `after["via"] == "asignacion"`.
  - `test_new_real_from_search_and_import_start_as_nueva`: corrida con `FakeSidof` (reusar `tests/test_search_runs.py`)
    deja `triage_status == "nueva"` y `published_at` igual al de la nota si lo trae; `_import_metadata` también nueva.
  - `test_audit_chain_still_valid` con `audit.verify_chain` después de varias clasificaciones.
- [ ] **Step 2: Run** `pytest tests/test_triage.py -q` → FAIL.
- [ ] **Step 3: Implement** `app/services/triage.py`, el endpoint y los cambios de creación y de `patch_opportunity`
  (después de aplicar los cambios, `if "owner_id" in changes: triage.on_owner_assigned(...)`).
- [ ] **Step 4: Run** `pytest tests/test_triage.py tests/test_search_runs.py tests/test_e1.py -q` → PASS; suite
  completa → PASS.
- [ ] **Step 5: Commit** `feat(t17): clasificación Seguir/Descartar auditada`.

---

### Task 3: Búsquedas guardadas y filtro del Radar

**Files:**
- Create: `app/services/saved_searches.py`
- Create: `app/routers/saved_searches.py` (registrar en `app/main.py`)
- Create: `app/schemas/saved_search.py`
- Modify: `app/routers/opportunities.py` (`list_opportunities`: parámetro `saved_search_id`)
- Test: `tests/test_saved_searches.py`

**Interfaces:**
- Produces:
  - `SavedSearchIn{name: str (1–120), terms: list[str] (≤10), states: list[str], families: list[str],
    buyers: list[str]}`; `SavedSearchOut` = lo mismo + `id`, `created_at`, `updated_at`.
  - `saved_searches.clean(payload) -> dict` — recorta espacios, quita vacíos y repetidos (sin acentos ni mayúsculas;
    `terms` con `search_runs.normalize_terms` **sin** el relleno por omisión). Ninguna condición → 422
    `saved_search_empty`. Más de 10 términos → 422 `validation_error`. Más de **20** búsquedas por persona → 422
    `saved_search_limit`. Nombre repetido de la misma persona → 409 `saved_search_duplicate`.
  - `saved_searches.matches(ss: SavedSearch, opp: Opportunity, excerpts: Sequence[str]) -> bool` — todas las
    condiciones definidas (spec «Coincidencia»): términos con `search_runs.matches_term` sobre título y cada extracto;
    entidad por igualdad sin acentos ni mayúsculas (`normalize_text`); familias por intersección; institución por
    «contiene» sin acentos ni mayúsculas sobre `buyer`.
  - `saved_searches.excerpts_by_opportunity(db, opp_ids: list[str]) -> dict[str, list[str]]` (una consulta).
  - `saved_searches.territory(db, org_id, opps: list[Opportunity]) -> dict[str, list[SavedSearch]]` — por
    oportunidad, las búsquedas de **cualquier** persona que coinciden.
  - Endpoints: `GET/POST /api/v1/saved-searches`, `PUT/DELETE /api/v1/saved-searches/{id}` (solo las propias; de otra
    persona → 404 vía `get_owned` + `user_id == user.id`). Auditan `saved_search.create|update|delete` con
    `after` = campos limpios.
  - `GET /api/v1/opportunities?saved_search_id=…` filtra con `matches` (después de los demás filtros, en Python como
    `family`); una búsqueda ajena → 404.

- [ ] **Step 1: Write the failing tests** `tests/test_saved_searches.py`:
  - `test_crud_is_per_user_and_audited` (analista1 crea; analista2 no la ve en `GET` y recibe 404 en `PUT`/`DELETE`;
    tres eventos `saved_search.*`).
  - `test_saved_search_requires_a_condition` (todo vacío → 422 `saved_search_empty`).
  - `test_clean_dedupes_accents` (`["Osteosíntesis", "osteosintesis "]` → un término).
  - `test_matches_all_defined_conditions`: oportunidad REAL «Material de osteosíntesis», `state="Jalisco"`,
    `buyer="IMSS UMAE Jalisco"`, `families=["Osteosíntesis"]`; coincide con `terms=["osteosintesis"],
    states=["jalisco"]`; no coincide si `states=["Sonora"]`; `buyers=["umae"]` coincide; término solo en el extracto
    de evidencia también coincide.
  - `test_radar_filter_by_saved_search` (dos oportunidades, el filtro deja una; la de otra persona → 404).
- [ ] **Step 2: Run** `pytest tests/test_saved_searches.py -q` → FAIL.
- [ ] **Step 3: Implement** servicio, esquemas, router y filtro.
- [ ] **Step 4: Run** `pytest tests/test_saved_searches.py -q` → PASS; suite completa → PASS.
- [ ] **Step 5: Commit** `feat(t17): búsquedas guardadas por persona y filtro en el Radar`.

---

### Task 4: Barrido diario automático y «Volver a barrer»

**Files:**
- Modify: `app/core/config.py` (`DAILY_SWEEP = _bool("DAILY_SWEEP", True)`, `DAILY_SWEEP_HOUR = int(os.getenv(...,"6"))`)
- Modify: `app/services/jobs.py` (ganchos de *tick*)
- Modify: `app/services/search_runs.py` (extraer `execute_run`)
- Create: `app/services/sweeps.py`
- Create: `app/routers/sweeps.py` (registrar en `app/main.py`; importar `app.services.sweeps` para registrar el handler)
- Modify: `tests/conftest.py` (`os.environ["DAILY_SWEEP"] = "0"`)
- Modify: `.env.example`, `docs/OPERACION.md` (variables y cómo apagarlo)
- Test: `tests/test_sweeps.py`

**Interfaces:**
- Consumes: `SavedSearch`, `Sweep`, `SearchRun.sweep_id` (Tarea 1); `search_runs.normalize_terms`, `DEFAULT_TERMS`,
  `MAX_TERMS`, `FakeSidof` de `tests/test_search_runs.py`.
- Produces:
  - `jobs.register_tick(fn: Callable[[Session, datetime], None]) -> None`; `_loop` llama cada gancho con una sesión
    nueva cuando `run_pending_once` devuelve `None`, atrapando y registrando excepciones (un gancho que falla no
    detiene el worker).
  - `search_runs.execute_run(db, job, run, client_factory) -> dict` — el cuerpo actual de `run_search_job` a partir
    de que ya tiene la corrida; `run_search_job` queda como búsqueda de la corrida por `job_id` + `execute_run`.
    Sin cambio de comportamiento (las pruebas de `test_search_runs.py` siguen pasando sin tocarlas).
  - `sweeps.JOB_KIND = "daily_sweep"`, `MAX_SWEEP_TERMS = 30`, `WINDOW_DAYS = 7`, `RETRY_AFTER = timedelta(hours=1)`,
    `MAX_DAILY_ATTEMPTS = 3`, `TICK_EVERY = timedelta(seconds=60)`.
  - `sweeps.compose_terms(db, org_id) -> tuple[list[str], list[str]]` — `(términos, descartados)`: primero
    `DEFAULT_TERMS`, luego los de las búsquedas guardadas de la organización ordenados por cuántas búsquedas los usan
    (desempate alfabético), sin repetir (clave sin acentos), tope 30.
  - `sweeps.aggregate_status(statuses: list[str]) -> str` — todos `done` → `done`; todos `failed` (o lista vacía) →
    `failed`; si no → `partial`.
  - `sweeps.schedule_due(db, now: datetime) -> list[Sweep]` — para cada organización: si `DAILY_SWEEP` y la hora local
    ≥ `DAILY_SWEEP_HOUR`: primero sincroniza barridos `queued/running` cuyo `Job` quedó `failed` (los marca `failed`
    con `errors=[{batch: None, code: "interrupted", message: jobs.STALE_ERROR}]` y `finished_at`); luego, si no hay
    barrido `daily` de hoy → intento 1; si el último `daily` de hoy está `failed`, tiene menos de 3 intentos y
    terminó hace ≥ 1 h → intento siguiente. Crea `Sweep(status="queued")` y `jobs.enqueue(... created_by_id=None,
    idempotency_key=f"daily_sweep:{org}:{day}:{attempt}")`; audita `sweep.start` (actor nulo). Hace commit.
  - `sweeps.tick(db, now)` — llama a `schedule_due` como mucho cada `TICK_EVERY` (marca en memoria del módulo);
    registrado con `jobs.register_tick`.
  - `sweeps.start_manual(db, user, idempotency_key: str | None) -> Sweep` — `trigger="manual"`, `attempt=0`,
    `created_by_id=user.id`; clave `daily_sweep:{org}:manual:{idempotency_key}` si llega. Audita `sweep.start`.
  - `sweeps.run_sweep_job(db, job, client_factory=SidofClient) -> dict` — handler: compone términos, guarda `terms` y
    `dropped_terms`, ventana `[hoy_MX − 6, hoy_MX]`, y por cada lote de 10: crea `SearchRun(sweep_id, job_id=job.id,
    created_by_id=sweep.created_by_id, query, counts=_empty_counts)`, audita `search.start`, commit, y llama a
    `search_runs.execute_run` dentro de `try` (una excepción deja ese lote `failed` y sigue con el siguiente). Suma
    conteos, junta errores con su número de lote, `status = aggregate_status(...)`, audita `sweep.finish` y commit.
  - `sweeps.latest(db, org_id) -> Sweep | None` y `sweeps.today_state(db, org_id, now) -> dict` con
    `{last: Sweep | None, scheduled_pending: bool}` (`True` si ya pasó la hora, `DAILY_SWEEP` está activo y no hay
    barrido `daily` de hoy terminado ni en curso).
  - `POST /api/v1/sweeps` (`search.run`, cabecera `Idempotency-Key`) → `202 {sweep_id, job_id}`;
    `GET /api/v1/sweeps?limit=10` (`opportunity.read`) → lista `SweepOut{id, day, attempt, trigger, status, terms,
    dropped_terms, counts, errors, created_by: UserRef | None, started_at, finished_at}`.

- [ ] **Step 1: Write the failing tests** `tests/test_sweeps.py` (reloj inyectado con `now`; worker invocado con
  `jobs.run_pending_once`; `sweeps.run_sweep_job` con `FakeSidof`; parchear `config.DAILY_SWEEP = True` en cada prueba
  que programa):
  - `test_not_before_hour_and_once_per_day`: 05:59 CDMX → nada; 06:00 → un barrido; 07:00 otra vez → ninguno nuevo.
  - `test_sweep_runs_batches_and_aggregates`: 4 términos por omisión + 8 de búsquedas guardadas = 12 → 2 corridas con
    el mismo `sweep_id`; conteos sumados; la ventana es de 7 días; las corridas tienen `created_by_id is None`.
  - `test_mixed_batches_are_partial`: lote 1 bien, lote 2 con SIDOF caído → `partial`; todos caídos → `failed`.
  - `test_failed_sweep_retries_hourly_up_to_three`: intento 1 `failed`; a los 59 min nada; a los 60 min intento 2;
    después del 3.º fallido, nada más ese día.
  - `test_stale_sweep_is_failed_and_retried`: `Sweep` `running` con su `Job` en `failed` (`STALE_ERROR`) → el tick lo
    deja `failed` con código `interrupted` y, una hora después, programa el siguiente intento.
  - `test_compose_terms_dedupes_and_caps`: búsquedas con «osteosíntesis» y «Osteosintesis» no duplican; 40 términos
    distintos → 30 y 10 en `dropped_terms`, los del diccionario siempre dentro.
  - `test_daily_sweep_off`: `DAILY_SWEEP=False` → `schedule_due` no crea nada y `today_state().scheduled_pending` es
    `False`.
  - `test_manual_sweep_requires_search_run`: `revisor` → 403; `analista1` → 202 y `sweep.start` con su actor; misma
    `Idempotency-Key` → mismo `sweep_id`.
  - `test_tick_hook_errors_do_not_stop_worker`: un gancho que lanza no impide que `_loop` procese el siguiente
    trabajo (probar la función que envuelve los ganchos).
- [ ] **Step 2: Run** `pytest tests/test_sweeps.py -q` → FAIL.
- [ ] **Step 3: Implement** en este orden: `execute_run` (correr `tests/test_search_runs.py` → PASS sin cambios),
  ganchos en `jobs.py`, `sweeps.py`, router, config, conftest.
- [ ] **Step 4: Run** `pytest tests/test_sweeps.py tests/test_search_runs.py tests/test_jobs.py -q` → PASS; suite
  completa en SQLite y en Postgres → PASS.
- [ ] **Step 5: Docs** — `.env.example` con `DAILY_SWEEP=1` y `DAILY_SWEEP_HOUR=6`; `docs/OPERACION.md`: sección
  «Barrido diario» (qué hace, cómo apagarlo, cómo reintentar a mano).
- [ ] **Step 6: Commit** `feat(t17): barrido diario en SIDOF con reintentos y barrido manual`.

---

### Task 5: API del tablero «Hoy» y contador

**Files:**
- Create: `app/services/hoy.py`
- Create: `app/routers/hoy.py` (registrar en `app/main.py`)
- Create: `app/schemas/hoy.py`
- Test: `tests/test_hoy.py`

**Interfaces:**
- Consumes: `saved_searches.territory`, `excerpts_by_opportunity` (Tarea 3); `sweeps.today_state`, `SweepOut`
  (Tarea 4); `OpportunityRow`/`_row` de `routers/opportunities.py`; `task_out` (tareas).
- Produces:
  - `hoy.touch_visit(user: User, now: datetime) -> datetime | None` — devuelve la marca contra la que se calcula
    «nueva desde tu visita» (`hoy_prev_seen_at` después de recorrer). Primera visita: `prev = None`, `seen = now`.
    Si `now - seen > 30 min`: `prev = seen`, `seen = now`. Si no, no cambia nada.
  - `hoy.dashboard(db, user, now, scope: Literal["mine", "team"]) -> dict` con:
    - `kpis`: `new_24h` (REAL, `created_at ≥ now − 24 h`), `unclassified` (REAL `nueva`), `unclassified_mine`
      (`nueva` que coinciden con alguna de **mis** búsquedas), `submitting_7d` (REAL `siguiendo`, `submission_at` en
      `[now, now + 7 d]`, según `scope`), `my_overdue_tasks` (mías, REAL, abiertas, `due_date < hoy_MX`).
    - `sweep`: `{last: SweepOut | None, scheduled_pending: bool}`; si `last.status in ("failed", "partial")`,
      `kpis_warning` con el texto del error del barrido.
    - `new_items`: todas las REAL `nueva`, más recientes primero, cada una `OpportunityRow` + `is_new_since_visit:
      bool` (`created_at > marca`) + `matched: list[{id, name, owner: UserRef}]` + `mine: bool`. Campo
      `in_territory: bool` (= `matched` no vacío).
    - `unassigned`: las de `new_items` con `in_territory == False` (la bandeja «sin territorio»).
    - `key_dates`: REAL `siguiendo` (de `owner_id == user.id` si `scope == "mine"`), un elemento por fecha en los
      próximos 14 días: `{opportunity: OpportunityRow, kind: "questions"|"submission"|"ruling", at: datetime}`,
      ordenados por `at`.
    - `my_tasks`: mis tareas abiertas (`pendiente`, `en_progreso`), todas las `data_kind`, por vencimiento (nulas al
      final); `TaskOut` ya trae `data_kind`.
    - `scope` (el aplicado) y `last_visit` (la marca).
  - `hoy.badge_count(db, user) -> int` — REAL `nueva` con `created_at > user.hoy_seen_at` (nula → todas). No escribe.
  - `GET /api/v1/hoy?scope=mine|team` (`opportunity.read`): sin `scope`, `team` si el usuario tiene el rol `direccion`
    y `mine` si no. Llama a `touch_visit` y hace commit solo de esas dos columnas (sin auditoría).
  - `GET /api/v1/hoy/badge` → `{"new": int}`.

- [ ] **Step 1: Write the failing tests** `tests/test_hoy.py`:
  - `test_only_real_counts`: tras el seed (solo HISTORICAL/SYNTHETIC) todos los indicadores son 0 y `new_items` vacío.
  - `test_new_items_territory_and_unassigned`: analista1 guarda «osteosíntesis»; dos REAL `nueva` (una coincide) →
    para analista1 `unclassified_mine == 1`, la otra está en `unassigned`; `matched[0].name` correcto.
  - `test_reload_within_30_minutes_keeps_new_list`: primera visita en `t0`; oportunidad creada en `t0+5m`; visita en
    `t0+10m` → `is_new_since_visit` verdadero y `last_visit` es `None` (primera visita); visita en `t0+45m` →
    `last_visit == t0` y la oportunidad sigue marcada nueva.
  - `test_badge_counts_since_seen_and_does_not_write`: `badge` no cambia `hoy_seen_at`.
  - `test_failed_sweep_is_reported_not_zero`: último `Sweep` `failed` → `sweep.last.status == "failed"` y
    `kpis_warning` no vacío aunque no haya nuevas.
  - `test_key_dates_scope`: oportunidad `siguiendo` de analista2 con presentación en 3 días → aparece para `direccion`
    (por omisión `team`) y no para analista1 con `scope=mine`; con `scope=team` sí. Fecha a 20 días → no aparece.
  - `test_my_tasks_include_demo_but_kpi_counts_real_only`: tarea SYNTHETIC vencida asignada → en `my_tasks`, pero
    `my_overdue_tasks == 0`.
  - `test_hoy_requires_read`: sin sesión → 401.
- [ ] **Step 2: Run** `pytest tests/test_hoy.py -q` → FAIL.
- [ ] **Step 3: Implement** servicio, esquemas y router.
- [ ] **Step 4: Run** `pytest tests/test_hoy.py -q` → PASS; suite completa en SQLite y Postgres → PASS.
- [ ] **Step 5: Commit** `feat(t17): API del tablero Hoy y contador de nuevas`.

---

### Task 6: Frontend — página «Hoy», clasificación e inicio

**Files:**
- Create: `frontend/src/lib/api-hoy.ts` (tipos y llamadas: `getHoy(scope?)`, `getHoyBadge()`, `triage(id, body)`,
  `listSweeps()`, `startSweep(key)`)
- Create: `frontend/src/pages/Hoy.tsx`
- Create: `frontend/src/components/TriageDialog.tsx`
- Modify: `frontend/src/App.tsx` (ruta `/hoy`; `index` y `*` → `/hoy`)
- Modify: `frontend/src/pages/Login.tsx` (destino por omisión `/hoy`)
- Modify: `frontend/src/components/Layout.tsx` (primer elemento «Hoy», icono `Sun` o `CalendarCheck`, permiso
  `opportunity.read`, contador; el logo enlaza a `/hoy`)
- Modify: `frontend/src/pages/OpportunityDetail.tsx` (chip de clasificación y botones Seguir/Descartar si REAL y
  `opportunity.write`)
- Modify: `frontend/src/lib/types.ts` (`triage_status`, `published_at`, `created_at` en `OpportunityRow`; detalle)
- Modify: `frontend/src/lib/labels.ts` (etiquetas de `opportunity.triage`, `saved_search.*`, `sweep.start`,
  `sweep.finish`; estados `nueva|siguiendo|descartada`)

**Interfaces:**
- Consumes: endpoints de las Tareas 2, 4 y 5.
- Produces: `TriageDialog({opportunity, action, onDone})` — reutilizado por «Hoy» y el detalle. Seguir: selector de
  responsable (`GET /users`, por omisión la persona actual) obligatorio. Descartar: motivo obligatorio (textarea,
  500). Envía `expected_version` (el detalle lo tiene; en «Hoy» se pide el detalle antes de abrir el diálogo).

Contenido de «Hoy» (orden): encabezado con saludo y «Última visita: …»; **estado del barrido** (verde «Barrido de hoy
06:02 · 12 notas · 2 nuevas», ámbar «pendiente» o «incompleto», rojo «falló: <error>», botón «Volver a barrer» con
`search.run`); **indicadores** (5 tarjetas; si hay `kpis_warning`, aviso encima: «El barrido falló: estas cifras
pueden estar incompletas»); **Nuevas** (pestañas «Mi territorio» / «Todas», fila con número, título, institución,
entidad, «Detectada …», «DOF: …» si hay `published_at`, búsquedas que coinciden, punto «nueva desde tu visita»,
acciones Seguir/Descartar/Abrir; las que ya no son nuevas desde tu visita van bajo «Siguen sin clasificar»);
**Fechas clave 14 días** (interruptor «Solo las mías» / «Todo el equipo»); **Mis pendientes** (tareas no REAL con
`DataKindBadge`); **Sin territorio** (la bandeja, con texto «No coinciden con ninguna búsqueda guardada. Asígnalas o
crea una búsqueda»). Estados vacíos honestos: sin barrido nunca → «Todavía no se ha barrido el DOF»; barrido bien y
sin nuevas → «Sin nuevas en el DOF en los últimos 7 días» (solo si el último barrido es `done`).

Contador del menú: `getHoyBadge()` al montar el layout y en cada cambio de ruta; se oculta en 0; se pone en 0 al
abrir `/hoy`. Píldora con `bg-brand text-white`.

- [ ] **Step 1: Implement** tipos, API, `TriageDialog`, `Hoy.tsx`, rutas, menú y detalle.
- [ ] **Step 2: Verify build** `cd frontend && npm run build` → sin errores de `tsc`.
- [ ] **Step 3: Verify in browser** con la app local (uvicorn :8078 sobre `licit_bk`, `JOBS_WORKER=0`) y el
  contenedor de Playwright: crear 2 oportunidades REAL con `POST /opportunities/import` (captura `metadata` de Compras MX)
  y una búsqueda guardada; capturas de «Hoy» en claro y
  oscuro, Seguir y Descartar desde «Hoy», contador del menú, detalle con chip; consola sin errores. Login lleva a
  `/hoy`.
- [ ] **Step 4: Commit** `feat(t17): tablero Hoy como inicio, clasificación y contador en el menú`.

---

### Task 7: Frontend — «Mis búsquedas» en el Radar

**Files:**
- Create: `frontend/src/lib/api-saved-searches.ts`
- Create: `frontend/src/pages/radar/SavedSearchesMenu.tsx` (aplicar / editar / borrar)
- Create: `frontend/src/pages/radar/SavedSearchDialog.tsx` (crear y editar)
- Modify: `frontend/src/pages/Radar.tsx` (parámetro de URL `ss` → `saved_search_id`; botón «Guardar como búsqueda»
  que precarga `q` como término, `state` y `family`; chip «Búsqueda: <nombre> ×» cuando está aplicada)
- Modify: `frontend/src/lib/api.ts` (`OpportunityQuery.saved_search_id`)

**Interfaces:**
- Consumes: endpoints de la Tarea 3; errores `saved_search_empty`, `saved_search_duplicate`, `saved_search_limit`
  mostrados con su mensaje del backend.
- Produces: el diálogo con campos Nombre, Términos (chips; máximo 10), Entidades (selección de `MX_STATES`),
  Familias (opciones del Radar), Instituciones (texto libre, chips). Nota fija: «Lo que coincide con tus búsquedas es
  tu territorio en el tablero Hoy; el barrido diario también busca estos términos».

- [ ] **Step 1: Implement** API, menú, diálogo y cambios del Radar.
- [ ] **Step 2: Verify build** `cd frontend && npm run build` → sin errores.
- [ ] **Step 3: Verify in browser** (claro y oscuro): crear, aplicar (la lista se filtra y la URL lleva `ss`), editar,
  borrar; la búsqueda aparece como «coincide» en «Hoy»; consola sin errores.
- [ ] **Step 4: Commit** `feat(t17): mis búsquedas guardadas en el Radar`.

---

### Task 8: Documentación y cierre

**Files:**
- Modify: `docs/BACKLOG.md` (T17 entrega 1 ✅ con lo que quedó; entrega 2 pendiente)
- Modify: `docs/LIMITACIONES.md` (barrido diario implementado: usa la búsqueda no documentada de SIDOF, no el respaldo
  por fecha; tope 30 términos; ventana 7 días; «nueva» = detectada por Licit; Compras MX sigue manual; el tick vive en
  el worker de la única réplica)
- Modify: `docs/OPERACION.md` (si la Tarea 4 no lo dejó completo)

- [ ] **Step 1: Update docs** con lo verificado (sin afirmar nada que no se haya probado; el barrido real desde
  Railway queda «por observar el primer día»).
- [ ] **Step 2: Full verification** `pytest -q` en SQLite y Postgres, `npm run build`, `alembic upgrade head` desde
  cero en una base vacía de Postgres.
- [ ] **Step 3: Commit** `docs(t17): backlog, limitaciones y operación del barrido diario`.
