# ADR-002 · Ajustes a los fixtures de demostración

Estado: aceptado · 2026-10-28

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
- DEMO-LIC-001 queda listo para el recorrido:
  - Partida 1, placa de 6 orificios, contra DEMO-PLA-001 (6 orificios): coincidencia preliminar (caso A del §10).
  - Partida 2, placa de 12 orificios, contra DEMO-PLA-003 (10 orificios): discrepancia de medida.
  - Partida 3, clavo de 10 mm, contra DEMO-CLA-001 (sin diámetro declarado): desconocido (caso C).
  - DEMO-REQ-005 (ficha técnica, faltante) y DEMO-REQ-006 quedan sin tarea, para asignarlos en vivo (paso 6).
- DEMO-LIC-002 reproduce el caso B (6 contra 8 orificios, sin tolerancia).
- DEMO-LIC-005 incluye el requisito de servicio e instrumental del §11: suministrar la pieza no cubre el contrato.
- Se agrega el estado `en_revision`. Una evidencia nueva lleva el requisito a revisión, nunca directo a
  `cumple_validado`.
- Referencias históricas: el convocante y la entidad sólo se registran cuando el resumen oficial los declara
  (IMSS Querétaro, IMSS Bienestar Estado de México). El tercero queda «Por verificar». La fecha de presentación
  se guarda con `submission_precision="date"` y la zona horaria marcada como supuesta.

## Consecuencias

Los estados de los fixtures son una instantánea inicial. En E3 el motor de correspondencia los recalcula a
partir de los atributos y la evidencia.
