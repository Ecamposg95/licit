# Respuestas reales de SIDOF (fixtures de prueba)

Capturadas el **2026-10-29 entre las 15:36 y las 15:39 UTC** (09:36–09:39 en Ciudad de México) desde la máquina de
desarrollo con `scripts/capture_sidof_fixtures.py`: una petición a la vez, al menos 1 s entre peticiones y
User-Agent `LicitDemo/1.0 (+contacto Atlas Technologies)`. El detalle de cada petición (método, URL, formulario,
HTTP, bytes, segundos y hora) está en `capture_log.json`.

Cada archivo es el cuerpo de la respuesta **tal cual** llegó (bytes sin tocar). No se editan a mano.

| Archivo | Petición | Qué contiene |
|---|---|---|
| `search_osteosintesis_2026.json` | `POST /busqueda/CargaNotasAvanzadas/` [OBSERVADO], `tipoBus=C`, `idOrg=TODOS`, `textoBus=osteosintesis`, 01-01-2026 a 29-10-2026 | `messageCode: 200`, `totalRegistros: 79`, 79 notas (75 de la sección de convocatorias y 4 del Poder Ejecutivo) |
| `search_zero.json` | La misma búsqueda con `textoBus=zzzxqv` | Respuesta **sin `messageCode`**: `Notas: ""`, `totalRegistros: 0` y los campos `URL`/`BODY` de un backend interno de SIDOF. El adaptador la trata como «cero sin confirmar» y nunca guarda ni registra `URL`/`BODY` |
| `nota_5801639.json` | `GET /dof/sidof/notas/nota/5801639` [OFICIAL] | LA-50-GYR-050GYR010-T-104-2026, IMSS OOAD Durango (presentación 21-10-2026 09:00) |
| `nota_5797331.json` | `GET /dof/sidof/notas/nota/5797331` [OFICIAL] | LA-50-GYR-050GYR075-I-134-2026, IMSS OOAD Querétaro (presentación 02-09-2026 10:00) |
| `nota_5800141.json` | `GET /dof/sidof/notas/nota/5800141` [OFICIAL] · extra | Una nota con 15 procedimientos; solo uno (LA-50-GYR-050GYR028-T-111-2026) es de osteosíntesis. En la prosa repite un número con una letra distinta a la de su tabla |
| `nota_5800121.json` | `GET /dof/sidof/notas/nota/5800121` [OFICIAL] · extra | LA-64-072-905038959-N-57-2026, Servicios de Salud de Coahuila: número y código de expediente dentro de la celda de etiqueta, fechas `dd/mm/aaaa hh:mm hrs.` y fallo |
| `nota_5799326.json` | `GET /dof/sidof/notas/nota/5799326` [OFICIAL] · extra | Aviso de **fallo** (no convocatoria) con tablas en columnas: dos procedimientos y sus ganadores |

Los tres archivos marcados «extra» van más allá de los cuatro que pedía el brief; se capturaron para probar el parser
con notas irregulares reales (varios procedimientos, etiquetas raras y avisos de fallo).

## Copia derivada y dañada a propósito

`nota_mangled.json` **no es una captura**. Es una copia de `nota_5801639.json` dañada deliberadamente por
`derive_mangled()` del mismo script (`--derive-only`, sin red): se quitan todas las fechas y horas, se rompen entidades
HTML (sin punto y coma, numéricas inválidas y nombres inexistentes) y se deja una fila y un párrafo sin cerrar. Sirve a
`test_parse_tolerates_mangled_note`.

## Aviso legal

Contenido del Diario Oficial de la Federación consultado en `sidof.segob.gob.mx`. Se conserva solo como fixture de
pruebas, citando la fuente. La versión oficial y auténtica de cada edición es su PDF firmado.
