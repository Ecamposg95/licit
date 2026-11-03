# T17 · Barrido diario, búsquedas guardadas y tablero «Hoy» (entrega 1)

Fecha: 2026-11-03 · Autor del diseño: Claude, a partir de la conversación con Emmanuel.
Spec base: `docs/spec/Task_Pack_Maestro_Dipromedic.md` (T17: «Búsquedas guardadas y alertas internas. Las preferencias
persisten sin enviar mensajes externos»). Reglas no negociables: CLAUDE.md §1–8.

## Intención

Dipromedic no usaba ninguna plataforma para buscar licitaciones. Lo que se busca es que **todo el equipo comercial
adopte Licit** para encontrar y ganar la mayor cantidad de licitaciones. Para eso la app tiene que trabajar sola (buscar
cada mañana) y cada persona tiene que abrirla y ver de inmediato qué hay de nuevo y qué le toca hacer.

Lo pidió Emmanuel: **todos** abren un tablero con las licitaciones nuevas publicadas y sus pendientes, y se propone un
flujo para operarlo. Aprobó la propuesta («sí, arranca con T17»).

## Flujo de operación (completo; esta entrega cubre los pasos 1–2 y el tablero)

1. **06:00 (CDMX) · barrido automático en el DOF** con el diccionario de términos y los de las búsquedas guardadas.
   Compras MX sigue con carga manual (Radar → Importar), porque no se puede automatizar.
2. **Clasificación** de cada oportunidad nueva, en máximo un día hábil: **Seguir** (con responsable) o **Descartar**
   (con motivo).
3. Verificación en Compras MX · 4. Análisis · 5. Decisión de participar · 6. Expediente. Estos pasos ya existen.
7. Resultado (presentada, ganada o perdida) y embudo de conversión: **entrega 2**, fuera de este documento.

## Metas de la entrega 1

- **Barrido diario automático** en SIDOF, sin intervención, idempotente por día y visible en el tablero (último barrido,
  estado y errores).
- **Búsquedas guardadas por persona** (nombre, términos, entidades, familias e instituciones), que se pueden aplicar en el
  Radar y que definen el **territorio** de la persona.
- **Clasificación**: Seguir (asigna responsable) o Descartar (motivo obligatorio), auditada.
- **Tablero «Hoy»** como pantalla de inicio para todos los roles, con:
  - Indicadores: nuevas en 24 h, sin clasificar (total y las mías), presentan en ≤ 7 días, mis tareas vencidas, estado
    del último barrido.
  - **Nuevas publicadas desde tu última visita**, filtrables por «mi territorio» o «todas», con acciones rápidas
    (Seguir, Descartar, Abrir) y la búsqueda guardada que coincidió.
  - **Fechas clave en los próximos 14 días** (junta, presentación, fallo) de las oportunidades REAL que se siguen.
  - **Mis pendientes**: tareas asignadas sin cerrar, ordenadas por vencimiento.
  - **Bandeja sin territorio**: nuevas que no coinciden con ninguna búsqueda guardada. La ve todo el mundo y la asigna
    quien tenga `opportunity.write`.
- **Contador de nuevas** en el menú lateral (desde la última visita al tablero).

## No metas (entrega 1)

- Embudo, resultado de la licitación, montos de fallo y tasa de conversión (entrega 2).
- Mensajes externos de cualquier tipo: correo, WhatsApp, push. Todo aviso vive dentro de la app (spec T17).
- Automatizar Compras MX o IMSS.
- Alertas configurables por persona (frecuencia, silencio). Los avisos se calculan, no se configuran.
- Búsquedas compartidas entre personas o editadas por otra persona.

## Anti-metas (sería un fracaso aunque funcione)

- Que un barrido **fallido** o **incompleto** se vea como «0 nuevas». Regla 3: una fuente caída no significa que no haya
  licitaciones. El tablero lo dice en rojo, con el error.
- Que lo SIMULADO o lo HISTÓRICO cuente como nuevo o aparezca en «nuevas publicadas». Regla 1: solo REAL.
- Que Descartar borre algo, o que una oportunidad descartada desaparezca sin rastro. Se conserva, filtrable y auditada.
- Que el barrido cree oportunidades a partir de avisos que no son convocatoria. Ya lo impide `upsert_procedure`.
- Inventar fechas, instituciones o montos al mostrar las nuevas. Lo desconocido se muestra como desconocido.

## Restricciones

- SIDOF: una petición por segundo, máximo 10 términos por corrida y tope de 300 notas (`search_runs.py`). El barrido
  debe respetarlos. Si hay más de 10 términos en total, se parten en varias corridas del mismo barrido.
- Una sola réplica en Railway con el worker dentro del servicio web (`JOBS_WORKER=1`). No hay cron externo.
- Permisos en el backend (`require_permission`), aislamiento con `get_owned()` y auditoría en la misma transacción.
- Esquema con Alembic (`revision --autogenerate`, revisar el archivo, probar upgrade y downgrade). PK y FK UUID
  `String(36)`.
- Pruebas en SQLite y Postgres. Frontend con zustand y Tailwind, compatible con el tema oscuro (ADR-004: rellenos
  sólidos con `brand`, `danger` o `ink`).

## Decisiones tomadas

- **Territorio = búsquedas guardadas** (decisión de Claude, marcada así porque Emmanuel no respondió a la pregunta de
  reparto). Una oportunidad nueva es «de mi territorio» si coincide con al menos una de mis búsquedas guardadas. Lo que
  no coincide con ninguna búsqueda de nadie va a la bandeja sin territorio.
- **Coincidencia**: una búsqueda guardada coincide si se cumplen todas las condiciones que tenga definidas:
  - términos: al menos uno aparece en el título o el extracto de la evidencia, con `matches_term`, que ignora acentos y
    usa palabras completas;
  - entidades: el `state` está en la lista;
  - familias: hay intersección con `families`;
  - instituciones: texto contenido en `buyer`, sin distinguir mayúsculas ni acentos.

  Una condición vacía no filtra.
- **«Nueva»** = oportunidad REAL creada por el barrido, por una búsqueda manual o por importación, con clasificación
  `nueva` (sin Seguir ni Descartar). «Desde tu última visita» usa una marca por persona que se actualiza al abrir el
  tablero.
- **Clasificación** en la oportunidad: `triage_status` (`nueva` | `siguiendo` | `descartada`), `triage_reason`,
  `triage_by_id` y `triage_at`. Las oportunidades que ya existían al migrar quedan como `siguiendo` si tienen
  responsable y `nueva` si no; HISTORICAL y SYNTHETIC quedan fuera de la clasificación (nulo). Seguir exige
  responsable (`owner_id`); Descartar exige motivo. Ambas requieren `opportunity.write`.
- **Barrido**: un trabajo `daily_sweep` encolado por el propio worker cuando son ≥ 06:00 en `America/Mexico_City` y no
  existe todavía el de ese día. La clave de idempotencia `daily_sweep:{org}:{AAAA-MM-DD}` evita duplicados aunque se
  reinicie el proceso. Busca en los **últimos 7 días** de publicación: el DOF publica con retraso y la deduplicación ya
  existe. Términos = diccionario por omisión ∪ términos de todas las búsquedas guardadas, en lotes de 10. Corre sin
  actor (`created_by_id` nulo) y se audita como `search.start` y `search.finish` con actor nulo («Sistema»). Se puede
  apagar con `DAILY_SWEEP=0` y cambiar la hora con `DAILY_SWEEP_HOUR`.
- **Estado del barrido en el tablero**: hora y resultado del último barrido (`done`, `partial` o `failed`), con conteos
  de notas, procedimientos y nuevas. Si el de hoy no ha corrido después de su hora, se avisa como «pendiente». Si falló,
  los indicadores de nuevas llevan la advertencia.
- **Pantalla de inicio**: «Hoy» reemplaza a `/radar` como destino después del login para todos los roles. El panel de
  dirección actual se conserva en `/panel`.
- **Permisos nuevos**: ninguno. Leer el tablero exige `opportunity.read`, clasificar exige `opportunity.write` y cada
  persona maneja solo sus búsquedas guardadas (cualquier rol autenticado).
- **Auditoría**: `saved_search.create`, `saved_search.update`, `saved_search.delete`, `opportunity.triage` y los
  `search.*` del barrido.

## Decisiones de Claude tras la revisión del constructor

Las ocho preguntas de la revisión se resolvieron así. Son decisiones de Claude, no de Emmanuel, y él las revisa al
aprobar este documento.

1. **Reintento del barrido.** Si el barrido del día termina `failed` (o lo marca así `recover_stale_jobs` tras un
   reinicio), el worker lo reintenta cada hora hasta 3 intentos en el día. La clave pasa a ser
   `daily_sweep:{org}:{AAAA-MM-DD}:{intento}`. Además hay un botón «Volver a barrer» en el tablero para quien tenga
   `search.run` (permiso existente). Corre como búsqueda manual, con su actor, y comparte el candado de «una a la vez».
2. **Un barrido, varias corridas.** El trabajo `daily_sweep` ejecuta los lotes de 10 términos en línea, uno tras otro.
   Cada lote es un `SearchRun` con una columna nueva `sweep_id`, que apunta a una tabla `sweeps` (org, fecha, intento,
   estado, conteos sumados, inicio y fin).
   - **Estado del barrido:** `done` si todos los lotes quedan `done`; `failed` si todos fallan; `partial` en cualquier
     otra mezcla, y el tablero dice cuáles términos no se revisaron.
   - **Tope de términos:** 30 en total por barrido (3 lotes). Si las búsquedas guardadas suman más, se toman primero
     los del diccionario y luego los más usados, y el tablero avisa cuántos quedaron fuera.
3. **«Nueva» se mide por cuándo la detectó Licit** (`created_at`), no por la fecha del DOF. El tablero lo rotula como
   «Detectada hoy» o «Detectada el …». Si el aviso del DOF trae fecha de publicación, se guarda en una columna nueva
   `published_at` (nula si no se conoce, por ejemplo en las importaciones de Compras MX) y se muestra junto a la de
   detección. Las existentes no se rellenan con fechas inventadas.
4. **Máquina de clasificación.**
   - Toda oportunidad REAL nueva (barrido, búsqueda manual, importación o captura) nace `nueva`.
   - Asignar responsable por `PATCH /opportunities/{id}` a una `nueva` la pasa a `siguiendo` en la misma transacción,
     con el evento `opportunity.triage`. Así nadie se salta la clasificación.
   - La clasificación se puede cambiar después: `descartada → siguiendo` y `siguiendo → descartada` (con motivo). Cada
     cambio se audita. No hay regreso a `nueva`.
5. **Fechas clave y «presentan en ≤ 7 días»** cubren todas las oportunidades REAL `siguiendo` de la organización, con un
   filtro «Solo las mías» (`owner_id`). Dirección ve todo el equipo por omisión; los demás roles ven «Solo las mías»
   por omisión.
6. **Tareas en «Mis pendientes».** Se muestran todas las tareas asignadas (REAL, HISTORICAL y SYNTHETIC). Las que no son
   REAL llevan la marca `DEMOSTRACIÓN` (regla 8) y **no** cuentan en los indicadores. Así el tablero no se ve vacío en
   la demo y no infla los números.
7. **Marca de última visita.** Hay dos columnas en `users`: `hoy_seen_at` (visita actual) y `hoy_prev_seen_at` (visita
   anterior). `GET /hoy` lista lo detectado después de `hoy_prev_seen_at`. Al abrir el tablero, si `hoy_seen_at` tiene
   más de 30 minutos, se recorre: `prev ← seen` y `seen ← ahora`. Así recargar no vacía la lista, y el contador del menú
   se calcula contra `hoy_seen_at`. `GET /hoy` es la única lectura que escribe, y solo esas dos columnas, sin auditoría
   (no es un cambio sensible).
8. **«Aplicar» una búsqueda guardada en el Radar** filtra la lista de oportunidades ya guardadas con sus cuatro
   condiciones (opción a). No lanza una búsqueda en vivo en SIDOF. Para eso está el barrido o «Buscar ahora» con sus
   propios términos.

## Lo que se deja al constructor

- Forma exacta de los endpoints (sugerido: `GET /api/v1/hoy`, CRUD `/api/v1/saved-searches`,
  `POST /api/v1/opportunities/{id}/triage`) y de los esquemas Pydantic.
- Diseño visual del tablero dentro de la identidad actual (ADR-003 y ADR-004) y textos en español.
- Cómo partir el código entre `services/` y `routers/` siguiendo los patrones existentes (`dashboard.py`,
  `search_runs.py`).
