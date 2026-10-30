# Informe de limitaciones

Se actualiza en cada entrega. Corte: 2026-10-29 (integración 2 de la demo de reunión). Dice lo que es verdad hoy;
si algo cambia, se corrige aquí antes de decirlo en una reunión.

## Fuentes de licitaciones

| Fuente | Estado hoy | Qué implica |
|---|---|---|
| **DOF vía SIDOF** · búsqueda por palabra `POST /busqueda/CargaNotasAvanzadas/` | Operativa desde el entorno de desarrollo (corrida real del 2026-10-29). Falta repetirla desde la IP de Railway (ensayo H4) | El endpoint **no está documentado**: lo usa el propio sitio y puede cambiar sin aviso. El **barrido diario de respaldo** con los servicios documentados (`/dof/sidof/notas/{fecha}`) **no está implementado** |
| DOF vía SIDOF · lectura de notas `/dof/sidof/notas/nota/{id}` | Operativa | Servicio documentado; cada nota se guarda como evidencia con su SHA-256 |
| `www.dof.gob.mx` | No se usa | Su robots.txt prohíbe `/nota_detalle.php?`; su búsqueda redirige a SIDOF |
| **Compras MX** | **Bloqueada para automatizar** | El listado responde 401 sin cabeceras cifradas, reCAPTCHA v3 y una prueba de trabajo (WASM). No se elude: la carga es **manual** (Radar → «Importar»), queda REAL «Por verificar» con su enlace |
| IMSS licitaciones | No integrada | Sin búsqueda; su robots.txt pide 10 s entre peticiones |
| datos.gob.mx / OCDS | Fuera | Solo histórico 2010–2022 y responde 403 a clientes con script |

- **El DOF va detrás de Compras MX:** en 10 procedimientos revisados publicó el resumen entre 0 y 28 días después, y en
  3 de 10 después de la presentación de proposiciones. Una ausencia en el DOF no significa que no exista la licitación.
  La búsqueda sirve para descubrir y dar contexto; la vigencia se confirma en Compras MX.
- **Aviso legal del DOF:** la reproducción con fines de lucro requiere consentimiento escrito de SEGOB, y la versión
  oficial es el PDF firmado de la edición. Por eso la demo **cita y enlaza** la nota oficial (enlace, huella y un
  extracto mínimo), sin republicarla completa.
- robots.txt de SIDOF: la búsqueda no consulta notas anteriores a 2021 (las que robots.txt lista son de 2011 a 2020);
  el archivo no se vuelve a leer cada día.
- Ritmo: una petición por segundo y una a la vez, con tope de 300 notas por corrida y 10 páginas por término. Una
  corrida que llega al tope o a la que le falla una página queda «incompleta» y lo dice.
- Al 2026-10-29 **no hay procedimiento abierto del giro confirmado en el DOF**: los más recientes (p. ej.
  LA-50-GYR-050GYR010-T-104-2026, IMSS Durango) ya tienen la presentación transcurrida. La demo lo dice así; no rellena
  con escenarios.

## Datos y catálogo

- **Sin IA.** La extracción de requisitos es manual (capturados con página y fragmento). No hay OCR ni lectura
  automática de bases. Un texto con instrucciones («ignora las reglas…») se trata como dato: prueba
  `tests/test_negative.py::test_injected_instructions_are_data`.
- El catálogo es el público de dipromedic.com y traufix.com (116 productos REAL con cita literal). Los errores del
  propio sitio se conservan y quedan marcados para revisión. Los precios y existencias son **ficticios** y lo dicen.
- **Certificaciones del sitio no verificadas:** los logos CE, ISO 13485, ISO 9001, COFEPRIS, FDA, ESR y GTO no se
  contrastaron con registros oficiales. La demo no los afirma como validados.
- PDFs del catálogo de **más de 25 MB** (catálogos de medicina deportiva de 43–80 MB) **solo se enlazan**, con la
  etiqueta «Archivo grande»; no se ven dentro de la app. Los de terceros (Corentec, Biotechni, Anton-Hipp, IOT, Caleb)
  también solo se enlazan. Los PDFs REAL llegan con `scripts/ingest_catalog_documents.py --fetch`; sin bucket
  (`OBJECT_STORAGE_*`) el disco del servicio se pierde al redesplegar.
- «Hoy» para la **vigencia de documentos** es la fecha real en `America/Mexico_City`, también en los escenarios
  SYNTHETIC; `DEMO_BASE_DATE` solo mueve las fechas de los escenarios, no el reloj de vigencias.
- Una base que ya tenía DEMO-LIC-001 sembrado conserva sus variantes viejas hasta el siguiente reinicio del demo:
  después de desplegar hay que reiniciar.

## Expediente y borradores

- El motor de correspondencia es determinista y preliminar: nunca concede cumplimiento ni cambia el estado de un
  requisito. Lo que el catálogo no declara queda «desconocido».
- Los **DOCX no se han abierto en Word ni en LibreOffice**; se verificaron con python-docx (contenido, tablas, encabezado
  y pie). Hay que abrirlos una vez antes de la reunión.
- **XLSX en punto flotante:** los montos de la hoja son números de hoja de cálculo (coma flotante). Vuelven al valor
  exacto a estas magnitudes, pero la referencia exacta es el texto de los DOCX y de la instantánea. El CSV no lleva dinero.
- No hay descuentos ni impuestos configurables: el tratamiento fiscal sale «pendiente de configurar».
- El ZIP nunca incluye archivos de documentos (propios ni de terceros); el manifiesto los lista como excluidos.
- Un cambio de bases (nota oficial con huella nueva) anula las aprobaciones del expediente y abre la actividad
  «Revisar cambio en bases», pero **no** reabre por sí mismo los requisitos ya validados: una persona decide cuáles
  afecta.

## Gobierno y seguridad

- **Bitácora:** `verify_chain` detecta eventos modificados o borrados en medio de la cadena, pero **no detecta que se
  borren los eventos más recientes** (truncamiento final) ni que alguien con acceso a la base recalcule todos los
  hashes. En **Postgres un trigger impide modificar o borrar eventos**; para una garantía mayor, el último hash
  verificado debe anclarse fuera de la base (la página Gobierno lo muestra con botón «Copiar»).
- `/api/v1/demo/accounts` publica correos y nombres de las cuentas demo sin sesión mientras `DEMO_MODE` sea verdadero;
  fuera de la demo debe ser `DEMO_MODE=false`. La contraseña de las cuentas demo es compartida (`DEMO_USER_PASSWORD`).
- Cambiar de cuenta recarga la página (para que ninguna lista conserve datos de la cuenta anterior).
- Despliegue: durante una ventana de cambio de versión, el contenedor viejo podría insertar eventos sin hash; aceptable
  para la demo (una réplica).

## Operación

- Una réplica: el worker de trabajos corre dentro del servicio web (`JOBS_WORKER=1`). Los trabajos atascados en
  «running» más de 10 min se marcan fallidos al arrancar.
- Respaldo y restauración de la base **no se han ensayado** (backlog T16).
- Capacidad sin medir (objetivo del pack: 10 usuarios concurrentes, 500 oportunidades, p95 < 2 s).
- Inter se carga desde Google Fonts: sin internet cae a la fuente del sistema.

## Menores diferidos (registrados en las revisiones, sin efecto en el guion)

- **Búsqueda (C):** ritmo y «una a la vez» no se aplican a la ruta de importación manual; si falla una página posterior
  se pierde el total reportado; el texto «actualizado» en registros HISTORICAL; términos por omisión silenciosos;
  precisión de fecha de junta y fallo sin columna propia; expresiones amplias para cancelaciones y modificaciones en
  encabezados centrados; «Aviso de fallo» en minúsculas cae como aviso; `capture_log.json` desactualizado; el orden de
  validación de fechas de la captura manual.
- **Red (integración 1):** netguard acepta subdominios de los hosts propios; `safe_get` no mira `Content-Length`; el
  motivo «demasiadas redirecciones» depende del texto del mensaje; el panel de cobertura y los avisos con fuente
  inaccesible no se han visto renderizados con una fuente caída (se revisa en el ensayo H4).
- **Documentos (D):** los errores en cuerpos Blob pierden el código `file_missing` en la interfaz; la detección de
  macros en DOCX es básica; la fecha del visor se muestra en UTC; `page_count` nulo en PDFs con árboles grandes; la
  tarjeta «Archivo grande» podría etiquetar mal un enlace sembrado; sin límite de largo para `note`; el servidor guarda
  el cuerpo completo antes de validar el tamaño.
- **Catálogo (B):** CLAVILOCK 200/200C con lista compartida de orificios; ids con espacios; «Ver en dipromedic.com» en
  un producto de traufix.com; etiqueta de precio sin revisar `data_kind`; parpadeo del estado vacío al cambiar de
  pestaña; la nota de duplicado muestra un identificador interno.
- **Expediente (E):** posible inversión del orden de bloqueos (requisito → expediente contra la llave foránea del
  expediente) bajo concurrencia alta; el panel y la compuerta difieren en obligatoriedad no determinable con conflicto y
  en evidencia vencida (la nota del panel lo advierte); «sin requisitos» cuenta la obligatoriedad no determinable como
  aplicable; consultas N+1 al leer el expediente; no se puede rechazar una sola evidencia vencida; el reloj demo no es
  configurable.
- **Borradores (F):** falta una prueba de regresión del orden de bloqueos en Postgres.
- **Vistas (G):** el texto de error de `/ops/status` (solo por API) no se redacta; etiquetas de estado duplicadas; falta «mostrando N de M»; el menú del selector de cuenta no atrapa
  el foco; el aviso de cuenta vencida puede aparecer tras un cierre de sesión
  deliberado (caso raro).
- **Marca (A):** la píldora de fecha puede recortarse a 768 px; el pie va dentro de `<main>`; la fecha del crédito está
  duplicada en el layout y el login; por debajo de 640 px se ocultan el nombre y el rol.
- **Fase 0:** `recover_stale_jobs` solo detecta trabajos de más de 10 min; `start_worker` sin candado ante llamadas
  simultáneas; reintentar con la misma clave de idempotencia repite el trabajo fallido (la interfaz usa una clave nueva
  por clic).
- En el historial, las fechas dentro del detalle de un evento se muestran en ISO (UTC), no en la zona de visualización.

## Fuera del alcance

No se presentan ofertas, no se firman documentos, no se envían mensajes ni correos y no se generan registros
sanitarios. Todo borrador lleva la marca `DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN`.
