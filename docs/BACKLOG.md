# Backlog del demo (task pack §14)

Estado al 2026-10-29 (integración 2 de la demo de reunión, antes del despliegue y el ensayo H4).
✅ hecho · 🟡 parcial · ⬜ pendiente. Límites detallados en `docs/LIMITACIONES.md`; guion en `docs/GUION_DEMO.md`.

| ID | Tarea | Estado | Notas |
|---|---|---|---|
| T01 | Revisar repo, restricciones y accesos | ✅ | ADR-001 a ADR-003, README/CLAUDE.md, accesos a Railway y GitHub |
| T02 | Base, migraciones y almacenamiento | ✅ | Postgres + Alembic (una sola head, `alembic check` limpio), almacenamiento S3 compatible o disco local con prueba de escritura y lectura (`tests/test_storage.py`). En Railway, el bucket ya existe; sin él el disco es efímero |
| T03 | Identidad y permisos | ✅ | 5 roles, permisos por recurso en backend, aislamiento por organización, cuentas demo con vencimiento, segregación técnica/comercial y sin autoaprobación |
| T04 | Flujos y componentes | ✅ | Radar, detalle con pestañas, matriz interactiva, centro documental, catálogo, panel de dirección y gobierno, con estados vacíos y de error |
| T05 | Modelo y fixtures | ✅ | Semilla reproducible (`stable_id`), REAL/HISTORICAL/SYNTHETIC separados, DEMO-LIC-001 sobre productos reales de Traufix con precios ficticios marcados (ADR-002) |
| T06 | Acceso real a fuentes | ✅ | Búsqueda real en SIDOF trazable (corrida del 2026-10-29); Compras MX bloqueado y documentado, con carga manual visible. Falta repetir la búsqueda desde la IP de Railway (H4) |
| T07 | Trabajos asíncronos y adquisición | ✅ | Cola en Postgres con idempotencia, worker en el servicio web, progreso, tiempo límite, reintentos, resultado parcial y recuperación de trabajos atascados |
| T08 | Normalización, fechas y deduplicación | ✅ | Número normalizado, fechas en español con zona supuesta de Ciudad de México, evidencia por nota con SHA-256; los históricos nunca aparecen abiertos |
| T09 | Importación y versiones documentales | ✅ | Validación por firma (PDF, DOCX sin macros, PNG, JPEG), 15 MB, nombres saneados, versiones recuperables, descarga autorizada y auditada |
| T10 | Extracción con evidencia | 🟡 | Sin IA por decisión: requisitos capturados con página y fragmento, desconocidos conservados. No hay extracción automática de bases ni evaluación de precisión |
| T11 | Reglas y comparación de partidas | ✅ | Motor determinista con citas del catálogo: coincide, incumple, desconocido y no comparable (casos A/B/C del §10); afinidad por componente con cobertura |
| T12 | Matriz, tareas y revisiones | ✅ | Evidencia a revisión, validación con `expected_version` y motivo, asignación de actividades, decisión, aprobaciones segregadas, compuerta de revisión final y cambio de bases; todo en la bitácora |
| T13 | Documentos DOCX y ZIP | ✅ | Seis plantillas con marca DEMO y `[PENDIENTE]`, totales exactos con Decimal, matriz CSV/XLSX, manifiesto con SHA-256 y descarga verificada. Falta abrirlos en Word |
| T14 | Recorrido completo integrado | 🟡 | Fase 0 y las dos oleadas integradas; recorrido del guion probado por API y en el navegador local. Falta el ensayo completo en producción (H4) |
| T15 | QA funcional, permisos y fallos | ✅ | Suite en SQLite y Postgres con los casos negativos del §16 (`tests/test_negative.py`); limitaciones registradas |
| T16 | Despliegue, respaldo y ensayo | 🟡 | Railway con bucket y variables listos; el despliegue del hito 1 espera que se renombren las tablas viejas de producción. Falta desplegar la integración 2, probar respaldo y restauración, y el ensayo |
| T17 | Búsquedas guardadas y alertas | ⬜ | P1 |
| T18 | OCR y plantillas adicionales | ⬜ | P1 |
| T19 | Portales adicionales y ERP | ⬜ | P2. Fuera del alcance: el demo es solo comercial (decisión del 2026-10-30); se quitaron la vista de TI y el diagrama de planta/ERP |
