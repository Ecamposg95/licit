# Backlog del demo (task pack §14)

Estado al 2026-10-28. ✅ hecho · 🟡 parcial · ⬜ pendiente.

| ID | Tarea | Estado | Notas |
|---|---|---|---|
| T01 | Revisar repo, restricciones y accesos | ✅ | ADR-001, README, accesos a Railway y GitHub verificados |
| T02 | Base, migraciones y almacenamiento | 🟡 | Postgres + Alembic listos y probados (upgrade/downgrade). Falta el bucket de documentos (E2) |
| T03 | Identidad y permisos | ✅ | 5 roles, permisos por recurso en backend, aislamiento por organización, pruebas de acceso permitido y denegado |
| T04 | Flujos y componentes | 🟡 | Radar, detalle y matriz de solo lectura con estados vacíos y de error (E1) |
| T05 | Modelo y fixtures | ✅ | Semilla reproducible, REAL/HISTORICAL/SYNTHETIC separados, ADR-002 |
| T06 | Acceso real a fuentes | 🟡 | Sondeo: SIDOF `docFuente` responde (200, ~2 s); su portada tarda más de 20 s; `dof.gob.mx` no respondió; Compras MX es una SPA. Adaptador en E2 |
| T07 | Trabajos asíncronos y adquisición | ⬜ | E2: cola en Postgres y servicio `worker` |
| T08 | Normalización, fechas y deduplicación | 🟡 | `normalized_id`, precisión de fecha y zona supuesta listos; deduplicación con la búsqueda real (E2) |
| T09 | Importación y versiones documentales | ⬜ | E2 |
| T10 | Extracción con evidencia | ⬜ | Sin IA por decisión del usuario: captura manual y reglas, con página y fragmento |
| T11 | Reglas y comparación de partidas | ⬜ | E3 (casos A/B/C) |
| T12 | Matriz, tareas y revisiones | 🟡 | Matriz de lectura lista; revisión con `expected_version` y asignación en E3 |
| T13 | Documentos DOCX y ZIP | ⬜ | E3 |
| T14 | Recorrido completo integrado | ⬜ | E3 |
| T15 | QA funcional, permisos y fallos | 🟡 | 24 pruebas (SQLite y Postgres); faltan los casos negativos del §16 que dependen de E2 y E3 |
| T16 | Despliegue, respaldo y ensayo | 🟡 | Railway operativo; falta probar respaldo y restauración, y el ensayo |
| T17 | Búsquedas guardadas y alertas | ⬜ | P1 |
| T18 | OCR y plantillas adicionales | ⬜ | P1 |
| T19 | Portales adicionales y ERP | ⬜ | P2 |
