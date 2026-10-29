# Fuentes de licitaciones: investigación técnica para la búsqueda en vivo

Fecha: 2026-10-28. Sondeos hechos entre las 22:15 y las 22:55 (hora de Ciudad de México, UTC-6) desde la máquina de desarrollo (WSL).
Alcance: Task Pack §6 (P0: Compras MX, DOF/SIDOF, IMSS; términos de osteosíntesis, endoprótesis e implantes).

Reglas que se siguieron:

- Peticiones secuenciales y espaciadas de 1 a 10 s. Se usó `curl -A "Mozilla/5.0"`.
- Se revisaron robots.txt y avisos legales.
- No se forjaron tokens. No se resolvieron CAPTCHA ni pruebas de trabajo (PoW). No se reintentó con cabeceras disfrazadas cuando hubo un bloqueo.
- Un fragmento de buscador no cuenta como verificación. Cada resultado citado aquí se leyó en la fuente oficial.

Leyenda de los endpoints:

- **[OFICIAL]**: documentado por el operador de la fuente.
- **[OBSERVADO]**: lo llama el propio sitio público desde su JavaScript. No está documentado como API, puede cambiar sin aviso y no debe presentarse como «API oficial».

---

## 0. Resumen

| Fuente | ¿Búsqueda en vivo desde el servidor hoy? | Cómo | Bloqueos |
|---|---|---|---|
| **SIDOF (DOF)** | **Sí** | Búsqueda por contenido [OBSERVADO] más lectura de notas por código [OFICIAL] | Ninguno. Sin CAPTCHA ni autenticación. Latencia de 0.4 a 6 s |
| `dof.gob.mx` (portal clásico) | No sirve para buscar | Su búsqueda simple da 0 resultados y la avanzada redirige a SIDOF. Las RSS solo traen títulos | `www.dof.gob.mx` tiene un certificado TLS que no corresponde al host. robots prohíbe `/nota_detalle.php?` |
| **Compras MX · difusión** | **No** | — | reCAPTCHA v3, cabeceras cifradas `grc/igrc/xgrc` y desafío PoW (WASM). Sin ellos responde **401 Unauthorized**. **Se detuvo esta fuente: solo importación manual** |
| Compras MX · datos abiertos | No | — | El listado de archivos exige las mismas cabeceras `grc` (401) |
| datos.gob.mx | No, para procedimientos vigentes | Solo hay un CSV histórico de CompraNet (2010–2022) | robots: `Disallow: /api/`, `Crawl-Delay: 10`. El CSV devuelve 403 (Akamai) a clientes con script |
| Contrataciones Abiertas (OCDS) | No | — | `api.datos.gob.mx`: tiempo de conexión agotado (15 s). `contratacionesabiertas.hacienda.gob.mx`: no resuelve DNS |
| **IMSS** `licitaciones-publicas` | Parcial y de bajo valor | HTML de Drupal con **un** evento en vivo (fallos y aperturas) y YouTube | robots: `Crawl-delay: 10`. La página «vigentes» está congelada en 2022 |

**Oportunidades abiertas el 2026-10-28: no se encontró ninguna verificada.** La convocatoria compatible más reciente en el DOF
(LA-50-GYR-050GYR010-T-104-2026, IMSS Durango) tuvo su presentación el 21-10-2026. Ver §5.

**Orden de adaptadores recomendado:**

1. SIDOF: búsqueda y nota.
2. SIDOF: barrido diario documentado, como respaldo y relleno.
3. Importación manual para Compras MX (URL, código de expediente o PDF).
4. IMSS: observador de eventos, opcional y de baja prioridad.

---

## 1. SIDOF / DOF

### 1.1 Disponibilidad y latencia (2026-10-28)

| Petición | HTTP | Latencia | Tamaño | Notas |
|---|---|---|---|---|
| `GET https://sidof.segob.gob.mx/` | 200 | 2.26 s | 188 KB | Antes se habían medido más de 20 s. Hoy fue rápida |
| `GET https://sidof.segob.gob.mx/robots.txt` | 200 | 0.35 s | 3.3 KB | Ver §1.7 |
| `GET https://sidof.segob.gob.mx/notas/docFuente/5797331` | 200 | 0.59 s | 5.1 KB | HTML de la nota |
| `POST https://sidof.segob.gob.mx/busqueda/CargaNotasAvanzadas/` [OBSERVADO] | 200 | 0.4 a 5.8 s | 0.4 a 53 KB | Búsqueda por contenido. §1.3 |
| `POST https://sidof.segob.gob.mx/busqueda/cargaNotas/` [OBSERVADO] | 200 | 0.4 a 3.3 s | — | Busca solo en el título. No sirve para convocatorias |
| `GET https://sidof.segob.gob.mx/dof/sidof/notas/{dd-mm-aaaa}` [OFICIAL] | 200 | 0.67 a 0.73 s | 33 a 66 KB | JSON con todas las notas del día |
| `GET https://sidof.segob.gob.mx/dof/sidof/notas/nota/{codNota}` [OFICIAL] | 200 | 0.43 a 1.0 s | 8 a 27 KB | JSON con `cadenaContenido` (HTML) |
| `GET https://sidof.segob.gob.mx/dof/sidof/documentos/pdf/{codDiario}` [OFICIAL] | 200 | 2.9 s | 4.58 MB | PDF de la edición completa. Ignora `Range` |
| `GET https://sidof.segob.gob.mx/dof/sidof/documentos/doc/{codNota}` [OFICIAL] | 200 | 0.62 s | 65 KB | .docx de la nota |
| `GET https://sidofqa.segob.gob.mx/dof/sidof/notas/20-10-2026` | 200 | 0.63 s | 58.9 KB | El host que usa la documentación devuelve los mismos datos que producción |
| `GET https://sidof.segob.gob.mx/apiStatus` | 200 | **17.4 s** | 25 KB | Página HTML de estado. Lenta; no usarla como chequeo de salud |
| `GET https://sidof.segob.gob.mx/sitemap.xml` | 404 | 0.41 s | — | No existe |

No aparecieron CAPTCHA, autenticación ni WAF. No hace falta cookie de sesión: se comprobó una búsqueda sin cookies con respuesta 200 y resultados.

### 1.2 Servicios web documentados [OFICIAL]

En la página `https://sidof.segob.gob.mx/datos_abiertos`, pestaña «Consumo de WebServices», hay manuales en PDF y ejemplos en JSON:

| Servicio | Documentación | Métodos (versión 1.0, dic-2018; las URL del manual usan `sidofqa.segob.gob.mx`) |
|---|---|---|
| Notas | `/datos_abiertos/getPDF/57`, `/datos_abiertos/getJSON/57` | `GET /dof/sidof/notas/{fecha}`, `GET /dof/sidof/notas/nota/{codNota}`, `GET /dof/sidof/notas/obtenerNotasPorDiario/{codDiario}` |
| Diario | `/datos_abiertos/getPDF/65` | `GET /dof/sidof/diarios/porFecha/{fecha}`, `GET /dof/sidof/diarios/{año}`, `GET /dof/sidof/diarios/obtieneDiario/{fecha}/{MAT\|VES\|EXT}` |
| Documentos | `/datos_abiertos/getPDF/43` | `GET /dof/sidof/documentos/doc/{codNota}` (Word), `GET /dof/sidof/documentos/pdf/{codDiario}` (PDF de la edición) |
| Indicadores | `/datos_abiertos/getPDF/61` | No aplica |

Se probaron en el host de producción `sidof.segob.gob.mx` y funcionan. **Ninguno de estos servicios ofrece búsqueda por palabra clave.**

Estructura útil de `notas/{fecha}`:

- `NotasMatutinas`, `NotasVespertinas` y `NotasExtraordinarias` contienen notas con `codNota`, `titulo`, `fecha`, `codDiario`,
  `codOrgaUno`, `nombreCodOrgaUno`, `tipoNota`, `pagina` y `existePdf`.
- **Las convocatorias llevan `codOrgaUno: "CV"`** («CONVOCATORIAS PARA CONCURSOS DE ADQUISICIONES, ARRENDAMIENTOS, OBRAS Y SERVICIOS DEL SECTOR PUBLICO»).
- Volumen observado: 75 notas CV de 148 el 20-10; 97 de 160 el 27-10; 0 de 81 el 28-10.
- El `titulo` de una nota CV solo trae el convocante y la referencia (por ejemplo «INSTITUTO MEXICANO DEL SEGURO SOCIAL - REF:581420»).
  **El objeto está en `cadenaContenido`, que se obtiene con `notas/nota/{codNota}`.**

### 1.3 Búsqueda por palabra clave y fecha [OBSERVADO]

Origen: `/assets/js/busqueda2.js`, que alimenta la tabla DataTables de `/busqueda/{texto}` y `/busquedaAvanzada/busqueda`.
**No está documentada.**

```bash
curl -s -A "Mozilla/5.0" -X POST "https://sidof.segob.gob.mx/busqueda/CargaNotasAvanzadas/" \
  -H "X-Requested-With: XMLHttpRequest" \
  --data-urlencode "draw=1" \
  --data-urlencode "columns[0][data]=fecha" --data-urlencode "columns[1][data]=titulo" \
  --data-urlencode "columns[2][data]=codOrgaUno" --data-urlencode "columns[3][data]=codOrgaDos" \
  --data-urlencode "order[0][column]=0" --data-urlencode "order[0][dir]=desc" \
  --data-urlencode "start=0" --data-urlencode "length=100" \
  --data-urlencode "tipoBus=C"            `# C = contenido; T = índice/título` \
  --data-urlencode "textoBus=osteosintesis" \
  --data-urlencode "fechaIni=01-01-2026" --data-urlencode "fechaFin=28-10-2026"   `# dd-mm-aaaa` \
  --data-urlencode "idOrg=TODOS"          `# OBLIGATORIO: con "" devuelve 0 siempre` \
  --data-urlencode "codNotas=" --data-urlencode "sinonimos=false" \
  --data-urlencode "tipoTexto=Y"          `# Y = todas las palabras; F = frase exacta; O = alguna`
```

Respuesta 200 en JSON, aunque el `Content-Type` dice `text/html`:

```json
{"messageCode":200,"response":"OK","totalRegistros":79,
 "Notas":[{"codNota":5801639,"titulo":"INSTITUTO MEXICANO DEL SEGURO SOCIAL - REF:581420",
           "fecha":"2026/10/20","codDiario":330325,
           "codOrgaUno":"CONVOCATORIAS PARA CONCURSOS DE ADQUISICIONES, ...", ...}],
 "url":"https://sidof.segob.gob.mx/dof/sidof/buscarNotas/avanzada/formato/C/osteosintesis/28-10-2026/01-01-2026/TODOS/1/-1/fecha/desc/false"}
```

Lo que se comprobó:

- **No distingue acentos.** «osteosíntesis» y «osteosintesis» dan 79 resultados cada una; «endoprótesis» y «endoprotesis», 64.
- **Compara palabras completas.** «protesis» no encuentra «ENDOPROTESIS». Los fragmentos de un número de procedimiento (`050GYR069-T-82-2026`) dan 0.
  El número completo en modo `F` sí funciona (§1.9).
- **El índice está al día.** «junta de aclaraciones» del 27 al 28-10 da 66 notas CV del 27-10. Las notas del 28-10 ya aparecen.
- **Se pagina** con `start` y `length`. El sitio ofrece 10, 25, 50 o 1000 por página.
- **Una respuesta vacía es ambigua.** Con 0 resultados, o con parámetros incompletos, la respuesta **no trae `messageCode`**. En su lugar trae `URL`/`BODY`
  de un backend interno (`https://10.2.52.x:.../avanzadaFrontend`). El adaptador debe:
  1. Tratar `messageCode == 200` como respuesta válida.
  2. Tratar la ausencia de `messageCode` como «0 resultados no confirmados» (posible error) y no como «no hay licitaciones».
  3. No registrar ni guardar esos campos `URL`/`BODY`.
- La exportación `.../buscarNotas/avanzada/exportarJson/...` (GET) devolvió `totalRegistros: 0` para una consulta que en el POST da resultados. **No usarla.**
- La búsqueda simple `/busqueda/cargaNotas/` (`dato=...`) busca **solo en el título**. Para «osteosintesis» da 38 resultados, todos del Consejo de Salubridad General (compendios de 2012 a 2022). No encuentra convocatorias.

Resultados 2026 (del 01-01 al 28-10, `tipoBus=C`):

| Término | Modo | Total | Notas de convocatorias (CV) |
|---|---|---|---|
| osteosintesis / osteosíntesis | Y | 79 | 75. Las 4 restantes son acuerdos del CSG o de la SSA |
| endoprotesis / endoprótesis | Y | 64 | 61 |
| material de osteosintesis | F | 51 | — |
| implantes ortopedicos | Y | 1 | 0. Es un acuerdo de la SSA, falso positivo |
| protesis cadera | Y | 4 | 1. ISSSTE, 09-07-2026 |
| Del 01-09 al 28-10: «implantes ortopédicos», «prótesis de cadera», «prótesis de rodilla», «instrumental ortopédico», «clavo intramedular», «placa bloqueada» | F | 0 | — |
| Del 01-09 al 28-10: «implantes» | F | 1 | 1 (5801639) |

Convocantes de las 75 notas CV de osteosíntesis:

| Convocante | Notas |
|---|---|
| IMSS | 47 |
| ISSSTE | 12 |
| IMSS-Bienestar | 9 o 10 |
| Coahuila, Aguascalientes, Yucatán, Durango, Guanajuato y Secretaría de Salud | 1 cada uno |

Distribución por mes:

| Mes | Ene | Feb | Mar | Abr | May | Jun | Jul | Ago | Sep | Oct |
|---|---|---|---|---|---|---|---|---|---|---|
| Notas | 13 | 7 | 14 | 10 | 4 | 4 | 9 | 4 | 6 | 4 |

### 1.4 Estructura de la nota y campos que se pueden extraer

Hay dos formas de leer la nota:

- `GET /notas/docFuente/{id}`: HTML suelto, con etiquetas `<HTML><BODY>` anidadas.
- `GET /dof/sidof/notas/nota/{id}` [OFICIAL]: JSON cuyo campo `Nota.cadenaContenido` trae el mismo HTML. **Es la opción recomendada.**

En el HTML, el encabezado son líneas `<p align="center">` con la dependencia, la unidad compradora o el OOAD y «RESUMEN DE CONVOCATORIA [n/aa]».
Cada procedimiento es una tabla con filas de dos celdas, etiqueta y valor:

| Campo | Variantes de etiqueta observadas |
|---|---|
| Número de procedimiento | «Número de Licitación», «No. Licitación», «NUMERO DE LICITACION», «No. de Licitación», «Carácter, medio y No. de Licitación» (el número va dentro del texto), «Descripción de la Licitación LA-…» (el número va en la etiqueta) |
| Carácter | «Carácter de Licitación», «Tipo», «CARACTER DE LA LICITACION» |
| Objeto | «Descripción de la licitación», «Objeto de la Licitación» |
| Volumen | «Volumen a adquirir», «Volumen Estimado a Adquirir Referencial», «MONTO MINIMO/MAXIMO» |
| Publicación en Compras MX | «Fecha de publicación en Compras MX», «… en la Plataforma Digital de Contrataciones Públicas», «… en Compras MX y DOF» |
| Junta de aclaraciones | «Junta de aclaraciones», «Fecha y hora para celebrar la junta de aclaraciones» |
| Visita a instalaciones | «Visita a instalaciones», «Visita a las Instalaciones» |
| Presentación y apertura | «Presentación y apertura de proposiciones», «Fecha y hora para realizar la presentación y apertura …» |
| Fallo | «Fallo», «Fecha de Fallo», «Fecha y Hora de Fallo», «Fecha y hora para emitir el fallo». Es opcional y muchas veces no aparece |
| Código de expediente Compras MX | A veces aparece. Ejemplo: «Código Exp. Compras MX: E-2026-00097699» |

Formatos de fecha que conviven:

- «25 DE AGOSTO DE 2026 10:00 HRS.»
- «29/09/2026, 10:00 horas»
- «14 OCTUBRE DE 2026; 09:00 HORAS»
- Fechas con espacios dentro de las palabras, como «sep tiembre» o «09:0 0». Hay que normalizar quitando espacios internos antes de interpretar.

Ninguna fecha trae zona horaria explícita. Se supone America/Mexico_City y esa suposición debe quedar registrada.

Otros datos del cuerpo:

- Lugar y fecha de firma, por ejemplo «QUERETARO, QRO., A 27 DE AGOSTO DE 2026».
- Firmante.
- Referencia «(R.- 579803)».
- En muchas notas, el texto «convoca … bases … disponibles en https://comprasmx.buengobierno.gob.mx».

**Una nota puede incluir varios procedimientos.** La 5800141 trae 13, de los que solo 1 es de osteosíntesis. Por eso hay que dividir en bloques por número de procedimiento y clasificar cada bloque, no la nota entera.

La sección CV también publica **fallos**. Por ejemplo, la 5799326 trae «Nombre del Licitante ganador … EXORTA S DE RL DE CV … $6,896,551.72» para LA-50-GYR-050GYR069-T-82-2026.
Sirve como evidencia de cierre.

Falsos positivos que se observaron:

- Notas del CSG que actualizan el Compendio Nacional de Insumos.
- La NOM-137 de etiquetado.
- La 5801651: el convocante es el «Hospital de Traumatología y Ortopedia Lomas Verdes», pero el objeto son servicios de conservación.

Hay que clasificar por el **objeto** y no por el nombre del convocante.

### 1.5 Muestra verificada: notas recientes con osteosíntesis o endoprótesis

Leídas en `https://sidof.segob.gob.mx/notas/docFuente/{id}` o en `/dof/sidof/notas/nota/{id}`. Fechas tal como las publica la fuente.

| Nota DOF (fecha) | Procedimiento | Convocante | Objeto | Publicado en Compras MX | Junta | Presentación y apertura | Fallo |
|---|---|---|---|---|---|---|---|
| [5801639](https://sidof.segob.gob.mx/notas/docFuente/5801639) (20-10-2026) | LA-50-GYR-050GYR010-T-104-2026 | IMSS, OOAD Durango | Adquisición de material de osteosíntesis y endoprótesis, inventario cero, con instrumental compatible con los implantes… | 08-10-2026 | 14-10-2026 09:00 | **21-10-2026 09:00** | No se indica |
| [5800463](https://sidof.segob.gob.mx/notas/docFuente/5800463) (06-10-2026) | LA-50-GYR-050GYR026-T-135-2026 | IMSS, OOAD Coahuila | Material de osteosíntesis y endoprótesis (alambres). Mínimo 10.2 M y máximo 25.5 M MXN | 10-09-2026 | 22-09-2026 | 30-09-2026 11:00 | 07-10-2026 |
| [5800121](https://sidof.segob.gob.mx/notas/docFuente/5800121) (01-10-2026) | LA-64-072-905038959-N-57-2026 (Exp. E-2026-00097699) | Servicios de Salud de Coahuila | Servicio integral de osteosíntesis y endoprótesis | 01-10-2026 | 09-10-2026 | 16-10-2026 14:00 | 22-10-2026 |
| [5800141](https://sidof.segob.gob.mx/notas/docFuente/5800141) (01-10-2026) | LA-50-GYR-050GYR028-T-111-2026 | IMSS, OOAD Edo. Méx. Oriente | Material de osteosíntesis y endoprótesis 2026 | 11-09-2026 | 21-09-2026 | 28-09-2026 11:00 | — |
| [5799553](https://sidof.segob.gob.mx/notas/docFuente/5799553) (24-09-2026) | LA-50-GYR-050GYR074-I-45-2026 | IMSS | Suministro de material de osteosíntesis y endoprótesis | 24-09-2026 | 29-09-2026 | 06-10-2026 10:00 | 13-10-2026 |
| [5799554](https://sidof.segob.gob.mx/notas/docFuente/5799554) (24-09-2026) | LA-50-GYR-050GYR001-T-107-2026 | IMSS | Suministro de material de osteosíntesis y endoprótesis | 24-09-2026 | 28-09-2026 | 05-10-2026 08:30 | — |
| [5797620](https://sidof.segob.gob.mx/notas/docFuente/5797620) (01-09-2026) | LA-50-GYR-050GYR011-T-87-2026 | IMSS | Material de osteosíntesis y endoprótesis (6,672 piezas) | 28-08-2026 | 23-09-2026 | 07-10-2026 10:00 | 14-10-2026 |
| [5797888](https://sidof.segob.gob.mx/notas/docFuente/5797888) (03-09-2026) | LA-50-GYR-050GYR013-T-148-2026 | IMSS | Material de osteosíntesis y endoprótesis 2026 | 26-08-2026 | 01-09-2026 | 07-09-2026 11:00 | 11-09-2026 |
| [5798995](https://sidof.segob.gob.mx/notas/docFuente/5798995) (17-09-2026) | LA-50-GYR-050GYR015-T-129-2026 | IMSS | Insumos de osteosíntesis y endoprótesis, HGZ 46 y HGZ 2-A | 20-08-2026 | 25-08-2026 | 01-09-2026 | 04-09-2026 |
| [5797331](https://sidof.segob.gob.mx/notas/docFuente/5797331) (27-08-2026) | LA-50-GYR-050GYR075-I-134-2026 | IMSS, OOAD Querétaro | Servicio de osteosíntesis y endoprótesis 2026 (17,213 servicios) | 21-08-2026 | 25-08-2026 10:00 | 02-09-2026 10:00 | — |
| [5799326](https://sidof.segob.gob.mx/notas/docFuente/5799326) (22-09-2026) | LA-50-GYR-050GYR069-T-82-2026 | IMSS | **Fallo**: material de osteosíntesis y endoprótesis. Ganador EXORTA S DE RL DE CV, 4 partidas, $6,896,551.72. Fallo del 07-07-2026 | — | — | — | Publicado |

Los procedimientos más recientes (T-104, N-57 y T-135) se buscaron por número completo en modo `F` del 01-01 al 28-10.
En los tres casos solo aparece la nota de la convocatoria; **el DOF no tiene todavía ningún fallo ni cancelación publicados**, así que el resultado es desconocido.

### 1.6 Desfase entre el DOF y Compras MX: el DOF va por detrás

En los 10 procedimientos de la tabla, el DOF publicó el resumen **entre 0 y 28 días después** de Compras MX.
En **3 de 10** (5800463, 5800141 y 5798995) el resumen salió en el DOF **después de la presentación de proposiciones**,
y en 5801639 salió un día antes.

Conclusión: **el DOF sirve para descubrir procedimientos y contrastar datos oficiales, pero no garantiza detectar a tiempo una licitación abierta.**
Una ausencia en el DOF no significa que no exista la licitación en Compras MX.

### 1.7 robots.txt y términos

`sidof.segob.gob.mx/robots.txt`:

- `User-agent: *`, con `Disallow: /CopiasCert?` y unos 50 pares `Disallow: /notas/{id}` y `/notas/docFuente/{id}`. Son notas concretas de 2011 a 2020 (por ejemplo 5381640 y 5617809).
- Además, `User-agent: AdsBot-Google` con `Disallow: /`.
- **`/busqueda/` y `/dof/sidof/` no están prohibidos.** El adaptador debe descargar robots.txt cada día y saltarse los IDs listados, también cuando los consulte por la ruta `/dof/sidof/notas/nota/{id}`.

`dof.gob.mx/robots.txt` prohíbe **`/nota_detalle.php?`** en general, además de `/nota_to_doc.php?` y `/copias_cert.php?`.
Por eso no se deben leer notas desde `dof.gob.mx`: hay que usar SIDOF.

Aviso legal (`https://sidof.segob.gob.mx/avisoLegal`):

> La reproducción total o parcial … **sin fines de lucro** es permitida siempre y cuando se cite la fuente … El acceso a este sitio no implica licencia
> para la reproducción o distribución … **con fines de lucro**, y sólo se permitirá con el previo consentimiento por escrito por parte de la Secretaría de Gobernación.

También dice que desde el 05-07-2012 **el PDF firmado de la edición es la versión oficial y auténtica**. El HTML es informativo.

Implicaciones:

- Guardar evidencia interna (enlace, hash, extracto mínimo) y **citar siempre la fuente**.
- **Consultar con el área legal** antes de redistribuir contenido del DOF en un producto comercial.
- Para evidencia con valor oficial, conservar el PDF de la edición (`documentos/pdf/{codDiario}`) y su hash.

### 1.8 Portal clásico `www.dof.gob.mx` / `dof.gob.mx`

| Petición | Resultado |
|---|---|
| `GET https://www.dof.gob.mx/` | **Error TLS** (curl exit 60): el certificado es para `CN=dof.gob.mx`, con SAN solo `dof.gob.mx` y vigencia hasta el 29-01-2027. «subjectAltName does not match www.dof.gob.mx». Esto explica el «sin respuesta» del sondeo anterior |
| `GET http://www.dof.gob.mx/` | 302 a `https://www.dof.gob.mx/`, que tiene el mismo error TLS |
| `GET https://dof.gob.mx/` | 200, 0.74 a 2.6 s, 100 KB, ISO-8859-1. Una vez la conexión se reinició al final (curl exit 56) |
| `POST https://dof.gob.mx/busqueda_detalle.php` con `textobusqueda=osteosintesis` | 200, 1.2 s: «Su búsqueda no produjo ningún resultado», periodo del 28/10/2016 al 28/10/2026. Busca solo en el título y aun así no coincide con SIDOF |
| `GET https://dof.gob.mx/busqueda_avanzada.php` | 302 a `https://sidof.segob.gob.mx/busquedaAvanzada/busqueda` |
| `GET https://dof.gob.mx/sumario_licitaciones.xml` | 200, 0.28 s, RSS **con 0 elementos** el 28-10 (coincide con 0 notas CV ese día) |
| `GET https://dof.gob.mx/sumarios/sumario_31dias.xml` | 200, 5.8 s, 1.6 MB, 4,793 elementos, 618 de ellos CV. El título de los CV solo trae convocante y REF y el enlace apunta a `nota_detalle.php`, que robots prohíbe |
| `GET https://dof.gob.mx/sitemap.xml` | 200, contenido de 2007, obsoleto |

Conclusión: **no se recomienda usar `dof.gob.mx`.** Como mucho, `sumario_licitaciones.xml` puede servir de señal barata de que hubo convocatorias en el día. Los `codigo=` de sus enlaces se pueden leer después en SIDOF.

### 1.9 Recomendación de adaptador para SIDOF

**Modo en vivo**, cuando el usuario pulsa «Buscar ahora»:

1. Por cada término del diccionario (osteosintesis, endoprotesis, «material de osteosintesis» en modo F, implantes, «protesis de cadera», «protesis de rodilla», «instrumental ortopedico», «clavo intramedular», «placa bloqueada», cerclaje):
   llamar a `POST /busqueda/CargaNotasAvanzadas/` [OBSERVADO] con `tipoBus=C`, `idOrg=TODOS`, `length=100`, paginar y usar una ventana de fechas de 90 días.
   Quitar acentos no es necesario, pero tampoco estorba.
2. Conservar solo las notas cuyo `codOrgaUno` empiece por «CONVOCATORIAS PARA CONCURSOS DE ADQUISICIONES» y eliminar duplicados por `codNota`.
3. Para cada candidata, llamar a `GET /dof/sidof/notas/nota/{codNota}` [OFICIAL] y parsear `cadenaContenido`:
   - dividir en bloques por número de procedimiento (`(LA|IA|AA|LO|IO)-\d{2}-…-\d{4}`);
   - clasificar cada bloque por su **objeto**;
   - extraer las fechas y guardar el HTML con su hash SHA-256.
4. Comprobar el cierre: buscar el número completo del procedimiento en modo `F` desde la fecha de la nota hasta hoy. Si aparece un fallo, una cancelación, una nota aclaratoria o una modificación, se registra como evidencia.
5. Evidencia oficial, bajo demanda: `GET /dof/sidof/documentos/pdf/{codDiario}`, unos 4.6 MB. Guardar con hash. Usar un límite de tamaño de 50 MB.

**Respaldo documentado**, en un job nocturno o cuando el endpoint observado cambie:

- Llamar a `GET /dof/sidof/notas/{dd-mm-aaaa}` [OFICIAL] por cada día. Filtrar `codOrgaUno == "CV"` y llamar a `notas/nota/{id}` para cada nota.
- Son entre 60 y 100 notas CV por día hábil, lo que a 1 petición por segundo da unos 2 min diarios. Así se rellena el histórico sin depender del endpoint [OBSERVADO].

Límites y tiempos:

| Parámetro | Valor |
|---|---|
| Concurrencia por host | 1 |
| Ritmo | ≤ 1 petición/s |
| Timeout de conexión | 10 s |
| Timeout de lectura | 20 s (búsqueda) y 15 s (nota) |
| Reintentos | 2, con espera exponencial de 2 s y 4 s, solo ante timeout o 5xx. No reintentar ante 4xx |
| Tamaño máximo | 2 MB por JSON y 50 MB por PDF |

Cachés y seguimiento:

- Caché de búsqueda: 1 h. Caché de nota: 24 h (las notas no cambian; las correcciones salen como notas aclaratorias nuevas).
- `User-Agent` descriptivo con contacto.
- Volver a leer robots.txt cada 24 h.
- Un **canario diario** que busque «osteosintesis» en 2026 y espere un total mayor que 0 y la nota 5797331. Si falla, el estado de la fuente pasa a «degradada» y no a «sin resultados».

**Vigencia** (Task Pack §6):

- `estado_fuente` es lo que dice la nota. `estado_derivado` se calcula:
  - si la presentación es posterior a ahora (en America/Mexico_City, como suposición registrada) y no hay evidencia de cierre, es «abierta (fuente oficial)»;
  - si la presentación ya pasó y no hay fallo, es «histórica, resultado desconocido»;
  - si hay nota de fallo, es «con fallo publicado».
- Como el DOF publica tarde, una oportunidad «abierta» según el DOF debe **reconfirmarse en Compras MX a mano**, por el número de procedimiento o por el código de expediente, antes de decidir si se participa.
- `freshness_ttl` de 24 h.
- Un error de red o la falta de `messageCode` **nunca** se interpreta como ausencia de licitaciones.

---

## 2. Compras MX (`comprasmx.buengobierno.gob.mx`)

### 2.1 Qué se descargó

| Petición | HTTP | Latencia | Tamaño |
|---|---|---|---|
| `GET https://comprasmx.buengobierno.gob.mx/sitiopublico/` | 200 | 0.31 s | 4.1 KB. Esqueleto Angular/PrimeNG con `runtime.a38a37db7b901a38.js`, `polyfills…`, `scripts…` y `main.d22ee4cd39204bb9.js` |
| `GET …/sitiopublico/main.d22ee4cd39204bb9.js` | 200 | 1.44 s | 4.06 MB |
| `GET https://comprasmx.buengobierno.gob.mx/` (portal raíz) | 200 | 0.31 s | 7 KB. Otro SPA, con `main-7QYVX3TK.js` de 2.65 MB |

La CSP de la página permite `www.google.com` y `www.gstatic.com`, que es lo que necesita reCAPTCHA.

### 2.2 Backends que llama el propio sitio [OBSERVADO; no documentado]

Configuración de entorno incluida en `main.d22ee4cd39204bb9.js` (`ambiente:"PRODUCCION"`):

| Clave | URL |
|---|---|
| `sitiopublicoMuleUrl` | `https://upcp-cnetservicios.buengobierno.gob.mx/whitney/sitiopublico/` |
| `baseUrl` | `https://upcp-cnetservicios.buengobierno.gob.mx/backends/eiza` |
| `documentosUrl` | `https://upcp-cnetservicios.buengobierno.gob.mx/norah/` |
| `clockUrl` | `https://upcp-cnetservicios.buengobierno.gob.mx/adele/` (incluye `interoperabilidad/tp/reloj`, `challenge/init` y `challenge/solve`) |
| `catalogosUrl` | `https://upcp-cnetservicios.buengobierno.gob.mx/janis/catalogos/` |
| `recaptcha` | `recaptchaV3Key`, `siteKey` y una **clave pública RSA** |
| Otras | `hannaUrl`, `tableroUrl` (`backends/rita`) y `rupcUrl` (`backends/rose`) |

Métodos del servicio del sitio público (clase `ns`), con base `whitney/sitiopublico/`:

| Método | Llamada |
|---|---|
| Difusión de procedimientos | `POST expedientes?rows={n}&page={p}[&sortField=&sortOrder=]` |
| Exportar a Excel (exige CAPTCHA y PoW) | `POST expedientes/v2/pu_obtener?rows=2000&page=…` con cabeceras `X-Challenge-ID` y `X-Challenge-Answer` |
| Detalle | `GET expedientes/{uuid}?id_proceso={0\|1}[&zgrc=]` |
| Anexos | `GET expedientes/{uuid}/anexos?...` |
| Requerimientos económicos | `GET expedientes/{uuid}/reqeconomicos?...` |
| Partidas | `GET detallepartidas/{a}/{b}` y `detallepartidas/v2/pu_obtener/...` (con desafío) |
| Catálogos | `POST catalogos` |
| Documentos | `GET norah/documentos/recursos/ulck?id_documento=…&user=sitiopublico`, `POST norah/documentos/recursos/v2/pu_obtener` |

Cuerpo del filtro (`filtroSitioPublico`) tal como lo arma la SPA:

```json
{"id_ley":null,"id_tipo_procedimiento":null,"id_tipo_contratacion":null,
 "fecha_apertura_inicio":null,"fecha_apertura_fin":null,"fecha_publicacion_inicio":null,"fecha_publicacion_fin":null,
 "id_tipo_dependencia":[],"numero_procedimiento":null,"nombre_procedimiento":"OSTEOSINTESIS",
 "credito_externo":null,"exclusivo_mipymes":null,"id_forma_participacion":null,"id_entidad_federativa":[],
 "id_p_especifica":[],"id_caracter_procedimiento":null,"id_estatus":0,"id_proceso":0,
 "codigo_expediente":null,"codigo_procedimiento":null,"estatus_alterno":[],"compra_consolidada":false}
```

Sobre `id_estatus`: corresponde a la pestaña. En otro módulo del mismo bundle, 0 es VIGENTE, 1 EN PROCESO y 2 FINALIZADO. **Para procedimientos no se pudo comprobar.**

`nombre_procedimiento` parece ser el filtro de texto, pero **no se pudo comprobar** que funcione como búsqueda por palabra clave.

Ruta de detalle en la SPA: `https://comprasmx.buengobierno.gob.mx/sitiopublico/#/sitiopublico/detalle/{uuidProcedimiento}/{idProceso}`.
El `uuid` solo se obtiene del listado protegido.

### 2.3 Controles anti-automatización

Cada petición de la SPA lleva tres cabeceras: `grc`, `igrc` y `xgrc`.

- `grc` es `RSA_encrypt(publicKey, base64("siteKey,ip,horaServidor,aleatorio40,origin,pathname,accion"))`.
- La IP la obtiene de `https://jsonip.com/` y la hora del servidor de `adele/.../reloj`.

Además, el sitio usa **reCAPTCHA v3** (`recaptchaV3Service.execute`).
Para exportar y para algunos detalles exige un **CAPTCHA visual** y una **prueba de trabajo** en WASM (`assets/wasm/pow/pkg/pow_wasm_bg.wasm`, `challenge/init` y `challenge/solve`).

Prueba única, sin tokens, tal como lo haría un cliente que no ejecuta el JS:

```bash
curl -s -A "Mozilla/5.0" -X POST \
  "https://upcp-cnetservicios.buengobierno.gob.mx/whitney/sitiopublico/expedientes?rows=10&page=1" \
  -H "Content-Type: application/json" -H "Origin: https://comprasmx.buengobierno.gob.mx" \
  --data '<filtro de arriba con nombre_procedimiento="OSTEOSINTESIS">'
# → HTTP 401 en 0.34 s: {"success":false,"error":"Error","details":"Unauthorized","pid":null}
#   CORS: access-control-allow-origin: https://comprasmx.buengobierno.gob.mx (allow-credentials: true)
```

**Decisión, según el Task Pack §6:** detener la fuente.

- No se generó `grc` (sería imitar el control anti-bot).
- No se ejecutó reCAPTCHA ni se resolvió la prueba de trabajo.
- No se probó la búsqueda por palabra clave porque requiere pasar esos controles.
- No hay forma legítima de consultar Compras MX desde el servidor con lo que se sabe hoy.

### 2.4 Datos abiertos, robots y términos de Compras MX

- `https://comprasmx.buengobierno.gob.mx/datos-abiertos` es una ruta del SPA raíz. La lista de archivos sale de `GET https://upcp-cnetservicios.buengobierno.gob.mx/amy/comprasmx/portal/documentos`, con cabeceras `grc`, y se descarga con un POST de formulario con `grc`.
  Sin tokens, el listado devuelve **401** (2.6 s).
- Según los textos del bundle, en esa página se publican «los datos de los expedientes y de los contratos» en formato de datos abiertos. No se pudo confirmar el formato, la frecuencia de actualización ni si incluye procedimientos vigentes.
- `https://comprasmx.buengobierno.gob.mx/robots.txt` devuelve **el esqueleto HTML del SPA** con 200, es decir, no hay robots.txt. `https://upcp-cnetservicios.buengobierno.gob.mx/robots.txt` devuelve 404.
- El aviso de privacidad (`/avisos-privacidad`) y la página informativa (`/compras-mx`) se cargan desde la API protegida. **No se pudieron leer desde el servidor.** Falta revisarlos a mano en un navegador.
- **No se encontró documentación oficial de una API pública de Compras MX**, ni en el portal ni con una búsqueda web.

### 2.5 Recomendación para Compras MX

- **No construir adaptador automático.** Habilitar **importación manual**: el analista pega la URL de detalle del SPA o el número de procedimiento o código de expediente (por ejemplo `E-2026-00097699`), o sube el PDF de la convocatoria o de las bases que descargó en su navegador.
- El servidor guarda el archivo con hash, extrae los campos y marca la oportunidad como «verificación manual en Compras MX».
- Mostrar un enlace a `https://comprasmx.buengobierno.gob.mx/sitiopublico/#/` y el número de procedimiento listo para copiar.
- Volver a evaluar si la Secretaría Anticorrupción y Buen Gobierno publica una API o datos abiertos documentados sin `grc`.

---

## 3. Datos abiertos

| Recurso | Prueba | Resultado |
|---|---|---|
| `https://www.datos.gob.mx/` | GET | 200 en 0.6 s. Portal CKAN nuevo |
| `https://www.datos.gob.mx/robots.txt` | GET | `Disallow: /api/`, `/dataset/*/history`, `/revision/` y `/dataset/rate/`. **`Crawl-Delay: 10`** |
| `https://datos.gob.mx/busca/api/3/action/package_search?q=compranet` | GET | 404. La ruta antigua ya no existe y robots prohíbe `/api/` de todas formas |
| `https://www.datos.gob.mx/dataset?q=compranet` | GET | 1 resultado: «Contratos y expedientes del sistema histórico de Compranet» de la SABG. Cubre **2010–2022**, en CSV, con licencia CC-BY 4.0. Última actualización: 29-07-2025 |
| `https://repodatos.atdt.gob.mx/api_update/sabg/contratos_expedientes_sistema_historico_compranet/compranet_historico.csv` | GET con `Range` | **403 Access Denied (Akamai)** al cliente con script. No se reintentó con cabeceras disfrazadas. Descarga manual en el navegador si se necesita |
| `https://www.datos.gob.mx/dataset?q="compras mx"` | GET | 0 resultados |
| `https://api.datos.gob.mx/v1/contratacionesabiertas` y `/v2/…` (OCDS) | GET | Tiempo de conexión agotado (15 s) |
| `https://contratacionesabiertas.hacienda.gob.mx/` | GET | El nombre no resuelve en DNS (curl exit 6) |
| Datos abiertos de Compras MX | — | Protegidos con `grc` (401). Ver §2.4 |

Conclusión: **ninguna fuente de datos abiertos accesible desde el servidor trae procedimientos vigentes.**

- El CSV histórico (hasta 2022) podría servir más adelante (P1/P2) para analizar convocantes y adjudicaciones previas, descargándolo a mano.
- No sirve para la búsqueda en vivo.

---

## 4. IMSS

| Petición | HTTP | Latencia | Observaciones |
|---|---|---|---|
| `GET https://www.imss.gob.mx/licitaciones-publicas` | 200 | 0.83 s | 22.6 KB, Drupal 7 detrás de Incapsula (pone cookies `visid_incap_*` y `incap_ses_*`; respondió sin desafío) |
| `GET https://www.imss.gob.mx/robots.txt` | 200 | 3.6 s | **`Crawl-delay: 10`**. Prohíbe `/search/`, `/?q=search/`, `/admin/` y otras. `/licitaciones-publicas` está permitida |
| `GET https://www.imss.gob.mx/procedimientos-de-contratacion` (enlace «vigentes») | 200 | 1.48 s | 141 KB. **Página congelada de 2022** (contingencia por la caída de CompraNet en julio de 2022): 346 números `-2022` y 247 PDF en `/sites/all/statics/procedimientos2022/` |

Cómo publica el IMSS:

- `licitaciones-publicas` es HTML editado a mano. Muestra **un solo** evento destacado y en vivo; el 28-10-2026 era «Notificación de Fallo del procedimiento LA-50-GYR-050GYR047-T-105-2026 … Tira reactiva para la determinación de glucosa … 28 de octubre de 2026, 12:00 hrs.».
- Lo acompañan un vídeo de YouTube y el enlace «eventos anteriores», que apunta al canal de YouTube.
- No hay tabla, búsqueda, PDF de convocatorias vigentes ni RSS.

Filtrado por palabra clave: solo se puede analizar el texto del bloque destacado. El sitio no ofrece búsqueda y robots prohíbe `/search/`.

Recomendación:

- Adaptador **opcional y de baja prioridad**: «eventos IMSS en vivo», con 1 petición cada 30 min o más y nunca más de una cada 10 s.
- Extraer el número de procedimiento, el tipo de evento y la fecha y hora, y cruzarlos con SIDOF.
- Las convocatorias del IMSS llegan mejor por SIDOF: el IMSS publica 47 de las 75 notas CV de osteosíntesis de 2026.

---

## 5. ¿Hay hoy un procedimiento abierto que coincida?

**No se encontró ninguno verificado como abierto el 2026-10-28.**

En el DOF, a través de SIDOF y con el índice al día hasta el 28-10:

- Del 21-10 al 28-10 no hay notas CV nuevas con osteosíntesis, endoprótesis, implantes, prótesis de cadera o rodilla, instrumental ortopédico, clavo intramedular o placa bloqueada.
- La más reciente es [5801639](https://sidof.segob.gob.mx/notas/docFuente/5801639), del 20-10-2026: **LA-50-GYR-050GYR010-T-104-2026**, IMSS OOAD Durango.
  Su presentación y apertura fue el **21-10-2026 a las 09:00**, ya pasada; el fallo no se indica y no hay nota de fallo en el DOF. Estado: **histórica, resultado desconocido**.
- **LA-64-072-905038959-N-57-2026**, de Servicios de Salud de Coahuila (exp. Compras MX E-2026-00097699): presentación el 16-10-2026 y fallo programado para el 22-10-2026, ambos pasados. Estado: **histórica, resultado desconocido**.

En Compras MX **no se pudo comprobar** desde el servidor (401 y controles anti-bot).
Como el DOF va por detrás (§1.6), **puede haber procedimientos vigentes en Compras MX que el DOF todavía no publica**. Hay que revisarlo a mano en un navegador y cargarlo con la importación manual.

En el IMSS, el único evento visible es un fallo de tiras reactivas de glucosa, que no está relacionado.

---

## 6. Orden recomendado de adaptadores

| Prioridad | Adaptador | Tipo | Llamadas | Límites |
|---|---|---|---|---|
| 1 | `sidof_search` | Búsqueda en vivo | `POST /busqueda/CargaNotasAvanzadas/` [OBSERVADO], luego `GET /dof/sidof/notas/nota/{id}` [OFICIAL] | 1 petición/s, concurrencia 1, timeouts de 10 y 20 s, 2 reintentos, canario diario |
| 2 | `sidof_daily` | Respaldo y relleno nocturno | `GET /dof/sidof/notas/{fecha}` y `/notas/nota/{id}` [OFICIAL]; PDF de la edición bajo demanda | 1 petición/s; unas 100 peticiones por día hábil |
| 3 | `comprasmx_manual` | Importación manual | Ninguna automática: URL, número o expediente y PDF subido por el analista | — |
| 4 | `imss_eventos` (opcional) | Señal | `GET /licitaciones-publicas` | ≥ 10 s entre peticiones, cada 30 min o más |
| — | `dof.gob.mx`, datos.gob.mx, OCDS | No implementar en P0 | — | — |

Pendientes que hay que decidir con el usuario:

1. Revisión legal del aviso del DOF sobre «fines de lucro».
2. Aceptar o no depender de un endpoint [OBSERVADO] de SIDOF, con el respaldo [OFICIAL] diario como mitigación.
3. Volver a probar todo desde Railway: el servidor de despliegue puede tener otra IP y otra reputación ante el WAF de los portales.

---

## Apéndice: archivos y comandos

Las respuestas de los sondeos (HTML, JSON, JS y PDF de documentación) se guardaron en el directorio temporal de la sesión.
No forman parte del repositorio y no constituyen evidencia conservada.

Para reproducir:

- Las búsquedas: comando de §1.3.
- Las notas: `curl -s -A "Mozilla/5.0" https://sidof.segob.gob.mx/dof/sidof/notas/nota/5801639`.
- Las convocatorias del día: `curl -s -A "Mozilla/5.0" https://sidof.segob.gob.mx/dof/sidof/notas/27-10-2026`, filtrando `codOrgaUno == "CV"`.
