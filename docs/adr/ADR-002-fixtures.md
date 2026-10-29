# ADR-002 · Ajustes a los fixtures de demostración

Estado: aceptado · 2026-10-28 · actualizado 2026-10-29 (DEMO-LIC-001 sobre productos reales)

## Contexto

`app/fixtures/datos_demo.json` se conserva tal como se entregó. Al revisarlo:

1. No trae partidas, y el paso 5 del recorrido compara tres partidas contra el catálogo.
2. Los 20 requisitos se reparten de forma rotativa y no corresponden al título de su escenario. Por ejemplo,
   DEMO-LIC-002 «Medida incompatible» recibía «Material titanio · desconocido».
3. Los 12 documentos no indican ámbito, tipo ni producto.
4. El §5 y la US04 usan un estado «pendiente de revisión», ausente de los 7 estados del §10.

## Decisión

- `app/fixtures/escenarios_demo.json` complementa el original sin modificarlo. Agrega partidas por escenario,
  reasigna texto y estado a los 20 requisitos conservando sus IDs `DEMO-REQ-001…020`, agrega ámbito y tipo a los
  documentos, cuatro vínculos de evidencia y un nuevo mapeo tarea → requisito.
- DEMO-LIC-001 queda listo para el recorrido y, desde la versión de reunión (spec §2.2), compara contra
  **productos reales de Traufix** del catálogo público importado (`DPM-…`, `data_kind = REAL`):
  - Partida 1, placa bloqueada de titanio 3.5 mm de 6 orificios, contra `DPM-198` (Placa Bloqueada ALP 3.5mm
    Titanio). La página cita «Cód. 198 | 5, 6, 7, 8, 9, 10 y 12 orificios» y «Fabricada en aleación de Titanio
    (Ti6Al4V ELI, ASTM F136).»: coincidencia preliminar (caso A del §10).
  - Partida 2, la misma placa con 11 orificios, contra `DPM-198`: incumple («Medidas disponibles: 5, 6, 7, 8, 9,
    10 y 12»), sin asumir equivalencia ni tolerancia.
  - Partida 3, placa angosta de titanio 4.5 mm con longitud de 96 mm, contra `DPM-199` (Placa Bloqueada Angosta ALP
    4.5mm Titanio). La página no declara longitudes para ese código (verificado en `catalogo_dipromedic.json`):
    desconocido (caso C); no se infiere del nombre.
  - Los requisitos de material usan el operador `contains` («titanio» dentro de «Aleación de titanio Ti6Al4V
    ELI»); los de orificios y longitud, `eq`.
  - Cada partida lleva un precio unitario **ficticio** en MXN (`unit_price` 2450.00, 2680.00 y 3120.00) con
    `price_data_kind = "SYNTHETIC"`: el producto es real, el precio no. Existencias y registro sanitario no se
    toman del sitio.
  - Si el catálogo real no está importado (pruebas, `IMPORT_CATALOG=0`), cada partida usa su `fallback_variant`
    ficticia (DEMO-PLA-001, DEMO-PLA-003 y DEMO-PLA-002), que reproduce los mismos tres casos, y la semilla
    deja un aviso en el log. Por eso `bootstrap()` importa el catálogo **antes** de sembrar.
  - DEMO-REQ-005 (ficha técnica, faltante) y DEMO-REQ-006 quedan sin tarea, para asignarlos en vivo (paso 6).
- DEMO-LIC-002 reproduce el caso B (6 contra 8 orificios, sin tolerancia).
- DEMO-LIC-005 incluye el requisito de servicio e instrumental del §11: suministrar la pieza no cubre el contrato.
- Se agrega el estado `en_revision`. Una evidencia nueva lleva el requisito a revisión, nunca directo a
  `cumple_validado`.
- Referencias históricas: el convocante y la entidad sólo se registran cuando el resumen oficial los declara
  (IMSS Querétaro, IMSS Bienestar Estado de México). El tercero queda «Por verificar». La fecha de presentación
  se guarda con `submission_precision="date"` y la zona horaria marcada como supuesta.

## Consecuencias

Los estados de los fixtures son una instantánea inicial. El motor de correspondencia (frente E) guarda su
resultado aparte, en `match_assessments`, con la cita del catálogo y la versión del motor; **no cambia el estado
del requisito**. El estado solo lo cambia una persona: una evidencia nueva lo lleva a `en_revision` y un revisor
distinto de quien la cargó decide.

Una base que ya tenía DEMO-LIC-001 sembrado antes de importar el catálogo conserva las variantes ficticias hasta
el siguiente reinicio del demo (`POST /api/v1/demo/reset` o `scripts/bootstrap.py --reset`).
