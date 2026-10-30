# Demo comercial Dipromedic · Diseño de la versión de reunión

Fecha: 2026-10-29 · Dueño de producto: Emmanuel Campos · Estado: para aprobación · **Reunión en menos de 1 semana**

Fuentes de este diseño: `docs/spec/Task_Pack_Maestro_Dipromedic.md` (el pack), `docs/spec/Dossier_Dipromedic_Fase_1.docx`,
la conversación con Emmanuel del 2026-10-28, E1 ya construido (commit `47309a1`, rama `feat/e1-base`) y las
investigaciones en `docs/research/`.

## 1. Intención y por qué

La demo se presenta en una reunión con el área comercial de Dipromedic y su gobierno corporativo:

| Asistente | Lo que necesita ver *(lectura del equipo, confirmada por Emmanuel)* |
|---|---|
| Gerente de Gobierno Corporativo | Control: quién aprueba qué, separación de funciones, bitácora inmutable, que nada se presente sin revisión humana y que el sistema no invente firmas, registros ni cumplimiento |
| Director Comercial | Encontrar oportunidades reales a tiempo, contrastarlas con **sus** productos, ver faltantes y salir con un expediente borrador descargable |

Éxito: los asistentes salen dispuestos a validar el alcance de la fase 1 del dossier (designar responsables, habilitar el
diagnóstico). «Vistoso», en palabras de Emmanuel, significa **profesional, funcional y con el branding de Dipromedic**.

## 2. Metas

1. **Identidad Dipromedic.** Colores, tipografía, logotipo real tomado de su sitio (nunca uno inventado) y tono de copy.
   La etiqueta «Demo» sigue visible. *Decisión de Emmanuel; sustituye el modo white label del pack §5 (ADR-003).*
2. **Catálogo real.** Las líneas, familias y productos públicos de dipromedic.com se importan como `REAL`, con URL de
   origen y fecha de consulta. Cada atributo técnico guarda el texto de la página que lo sustenta. Precio, existencias y
   registro sanitario **no** se toman del sitio: si se muestran, son `SYNTHETIC` y están marcados campo por campo.
3. **Búsqueda en vivo (E2).** Consulta real desde el servidor a las fuentes que la investigación declare usables,
   ejecutada como trabajo asíncrono con avance, fuente, hora y conteos. Los resultados se guardan con evidencia (URL y
   hash) y se deduplican. Si una fuente falla, se ve el fallo y se ofrece la importación manual (URL o captura).
4. **Expediente funcional (E3).**
   - Motor de correspondencia determinista con los casos A/B/C del pack §10.
   - Afinidad 40/30/20/10 mostrada por componente y con su cobertura.
   - Matriz de requisitos interactiva: asignar, cargar evidencia (pasa a `en_revision`), revisar con versión esperada
     y motivo, y recalcular.
5. **Documentos y generación (E3).**
   - Almacenamiento de archivos (Railway Bucket compatible con S3) con hash, versión, tipo MIME validado y límite de tamaño.
   - Las plantillas P0 del pack §12 se generan en DOCX con la marca DEMO.
   - ZIP con `manifest.json`, la matriz en CSV/XLSX y un README de pendientes. Cada generación es una instantánea
     versionada y su descarga se autoriza en el backend.
6. **Una vista por asistente.**
   - **Panel de dirección:** cartera, riesgos y avance, contando solo datos reales y separados por tipo de dato.
     Sin KPIs ni ahorros inventados.
   - **Gobierno corporativo:** bitácora filtrable, matriz de roles y permisos visible, y quién aprobó cada requisito.
7. **Guion de 10–12 minutos** que recorre los 10 pasos del pack §4 en orden. Se incluye reinicio del demo y un ensayo
   con datos reiniciados.

### 2.1 Alcance para la reunión (menos de 1 semana)

La reunión está a menos de una semana (Emmanuel). Entra solo lo que sostiene el recorrido central. Si el tiempo no
alcanza, se recorta en el orden de la columna «Recorte», del 1 al último.

| Pieza | Entra para la reunión | Recorte |
|---|---|---|
| Branding Dipromedic (meta 1) | Sí | — |
| Catálogo real (meta 2) | Sí, importado por script desde `dipromedic-catalogo.json`. Traufix completo; el resto de las líneas como fichas de texto | — |
| Importación CSV con previsualización (pack §5) | No; se muestra deshabilitada con su explicación | 3 |
| Búsqueda en vivo SIDOF (meta 3) | Sí: búsqueda por palabra + lectura de cada nota por servicio documentado + importación manual | — |
| Barrido diario de SIDOF | No | 1 |
| Vigilancia del evento en vivo de IMSS | No | 2 |
| Motor A/B/C, afinidad y matriz interactiva (meta 4) | Sí | — |
| Flujo del expediente completo (decisión de participar, aprobación técnica, aprobación comercial y compuerta «listo para revisión final») | Sí (pack US05/US06, prueba del Gerente de Gobierno Corporativo) | — |
| Almacenamiento de archivos y evidencia (meta 5) | Sí | — |
| Plantillas P0 (6) + ZIP con manifiesto (meta 5) | Sí | 4: si falta tiempo, se fusionan matriz, faltantes e índice en un solo DOCX |
| Plantillas P1 (cartas, cuadro de preguntas) | No | — |
| Panel de dirección y vista de gobierno corporativo (meta 6) | Sí | — |
| Cambio rápido de cuenta demo | Sí | — |
| Guion, reinicio y ensayo (meta 7) | Sí | — |

### 2.2 Productos en el contraste: mixto (Emmanuel)

- **DEMO-LIC-001**, el escenario del recorrido, se rehace con **productos reales de Traufix**:
  - Partida 1: coincidencia técnica preliminar con un producto real cuyos atributos (material, orificios, lado) vienen
    citados de su página.
  - Partida 2: discrepancia de medida contra un producto real.
  - Partida 3: atributo exigido que la página real no declara, resultado «desconocido».
  - El builder elige los códigos concretos del JSON para que los tres casos sean verdaderos con los datos citados.
- Precio, existencias y registro sanitario de esos productos son `SYNTHETIC` y se marcan campo por campo en la
  pantalla y en la propuesta económica (DOCX y ZIP). El documento generado lleva la marca DEMO aunque nombre
  productos reales.
- Los otros 7 escenarios siguen con las variantes ficticias `DEMO-*` para cubrir los casos difíciles: vencido,
  capacidad, servicio, fecha por verificar y fuente inaccesible.
- Las oportunidades reales de SIDOF **no** pasan por partidas ni por el ZIP en esta versión. Las notas no traen
  partidas y no hay IA para extraerlas. Se ven en el radar y en el detalle, con la nota oficial enlazada y la opción
  «capturar partidas manualmente» marcada como próxima entrega.

### 2.3 Separación de funciones (Emmanuel)

- El backend impide que quien cargó una evidencia la apruebe, y que la aprobación técnica y la comercial del mismo
  expediente las dé la misma persona. **Aplica aunque la persona acumule roles:** la cuenta `presentador` no se
  autoaprueba.
- En modo demo hay un «cambio rápido de cuenta»: lista las cuentas `@dipromedic.example` y abre un inicio de sesión con
  el correo ya escrito. Es un **inicio de sesión real** con otra cuenta (no suplantación) y queda en la bitácora.
  Fuera de `DEMO_MODE` no existe.

### 2.4 Dónde corre (Emmanuel)

- Railway, con Emmanuel presentando.
- Plan B, si la IP de Railway falla contra SIDOF: la misma app en su laptop. Si tampoco, el fallo se muestra con
  honestidad y se usa la importación manual.
- Después de la reunión, los asistentes pueden recibir cuentas demo con vencimiento (`expires_at` en el usuario,
  revisado al iniciar sesión).

## 3. No-metas

Las áreas de TI y planta (decisión de Emmanuel del 2026-10-30: el demo se enfoca solo en comercial; no hay vista de TI,
ni diagrama de arquitectura, ni integración con planta o ERP, ni siquiera como texto); envío a portales, firma o presentación de ofertas; IA o LLM (decisión de Emmanuel: la extracción es
manual o por reglas, con página y fragmento); multiempresa comercial; precios o existencias reales; app móvil.

## 4. Anti-metas (fallaría aunque funcione)

- Un resultado ficticio presentado como búsqueda en vivo, o una búsqueda vacía rellenada con fixtures.
- Un KPI, ahorro o probabilidad de ganar inventados.
- Un logotipo, certificado, registro sanitario o firma inventados.
- Una referencia histórica mostrada como abierta.
- Un atributo inferido del nombre comercial.
- Que se vea como plantilla genérica o «hecho por IA» en lugar de una aplicación empresarial de Dipromedic.

## 5. Restricciones

- Todas las reglas del pack §2, §10, §11 y §13 siguen vigentes (ver CLAUDE.md).
- Stack ya decidido (ADR-001): FastAPI, SQLAlchemy 2, Postgres, Alembic, React/Vite/TS/Tailwind y Railway con Dockerfile.
- Se despliega a Railway solo cuando hay un avance significativo, no por cada cambio. El push lo autoriza Emmanuel.
- Robots y términos de dipromedic.com y de las fuentes públicas se respetan; si una fuente bloquea (CAPTCHA o
  autenticación), se documenta y se usa carga manual.
- El idioma de la interfaz es español de México; la zona de visualización es America/Mexico_City.

## 6. Decisiones ya tomadas

| Tema | Decisión | Quién |
|---|---|---|
| Identidad | Branding Dipromedic con etiqueta «Demo» | Emmanuel |
| Catálogo | Real del sitio público y campos comerciales ficticios marcados | Emmanuel (propuesta aceptada) |
| Búsqueda | DOF/SIDOF directo primero; Compras MX según la investigación | Emmanuel |
| IA | Ninguna en esta versión | Emmanuel |
| Migraciones | Alembic | Emmanuel |
| Escenarios | Mixto: DEMO-LIC-001 con productos reales de Traufix y los demás con variantes ficticias (§2.2) | Emmanuel |
| Separación de funciones | La impone el backend, con cambio rápido de cuenta en modo demo (§2.3) | Emmanuel |
| Ejecución | Railway con Emmanuel presentando; laptop como plan B (§2.4) | Emmanuel |
| Fuente de búsqueda | SIDOF: búsqueda por palabra (no documentada) + lectura por servicios documentados + barrido diario de respaldo. Compras MX solo manual | Equipo, con base en la investigación |
| Crédito | Pie «Contenido de catálogo: DIPROMEDIC S.A. DE C.V. · www.dipromedic.com», con fecha de consulta en cada ficha | Equipo |
| Ejecución | Frentes en paralelo con subagentes y worktrees; un integrador resuelve el esquema común y las rutas | Emmanuel |

## 7. Hallazgos de la investigación

*Se completa con `docs/research/dipromedic-web.md`, `dipromedic-catalogo.json` y `fuentes-licitaciones.md`.*

### Marca (`docs/research/dipromedic-web.md`, recursos en `docs/research/dipromedic/brand/`)

- Colores tomados de su `style.css`:

  | Color | Hex | Uso en su sitio |
  |---|---|---|
  | Azul corporativo | `#0F75BC` | Logo, títulos, pestañas activas |
  | Verde «Fixi» | `#47AD36` | Acentos y subrayados |
  | Degradado de botones | `#63F24B → #47AD36` | Botones |
  | Navy del pie | `#001D4C` | Pie de página |
  | Azul Traufix | `#004991` | Línea Traufix |

- Tipografía: Inter.
- Logotipos reales: PNG a color (166×69) para fondos claros y SVG blanco para fondos oscuros. Los logos de las líneas
  (Traufix, Fixier y otras) ya están descargados.
- Sitio PHP sobre la plantilla médica «Healdi». Las tarjetas de Traufix muestran modelos 3D (`.glb`).
- La página de propiedad intelectual permite reutilizar contenido si se acredita a «DIPROMEDIC S.A. DE C.V.» y
  www.dipromedic.com. La demo pone ese crédito en el pie y en cada ficha importada. Los logos de marcas de terceros
  (Corentec y otras) pertenecen a sus dueños: se muestran solo como texto, salvo autorización.
- Las certificaciones que el sitio muestra como logos (CE, ISO, COFEPRIS, FDA) **no se verificaron**. La demo no las
  afirma como validadas.

### Catálogo real (`docs/research/dipromedic-catalogo.json`)

Son 7 líneas, 116 registros y 323 códigos. Cada atributo guarda la cita exacta de la página.

| Línea | Registros | Calidad técnica |
|---|---|---|
| **Traufix** | 95 | **Alta.** Placas y clavos en titanio Ti6Al4V ELI (ASTM F136), códigos por lado izquierdo/derecho, número de orificios, tablas de diámetro × longitud de clavos y tornillos compatibles. Medicina deportiva: códigos `STRAUFIX-…` con medidas, sin descripción |
| Corentec | 12 | Media: texto técnico (cono 12/14, ángulos, porosidad, rangos de tallas), sin códigos |
| Biotechni | 4 | Media |
| Caleb, Imedicom, Anton-Hipp, IOT | 5 | Solo descripción de marketing |

- 76 PDFs: 60 descargados (211 MB), 15 grandes solo enlazados y 1 roto. Son técnicas quirúrgicas y folletos, la
  mayoría alojados en traufix.com. Sirven como **evidencia documental REAL**, citando página.
- Errores del propio sitio se conservan tal cual y quedan marcados para revisión: los orificios de CLAVILOCK se
  contradicen, la tabla anterógrada de INTRALOCK dice «Retrógrado» y T-FIX dice fémur en un lugar y tibia en otro.
  Tres códigos traen letras cirílicas parecidas a las latinas; se normalizan para búsqueda y se conserva el original.
- El catálogo PDF menciona sets de instrumental y tornillos de acero sin página web (`pdf_only_mentions`). Esto
  importa para partidas de «equipo en comodato»: aparecen como «mencionado en catálogo, sin ficha».

### Fuentes en vivo (`docs/research/fuentes-licitaciones.md`)

| Fuente | Uso en la demo | Detalle |
|---|---|---|
| **SIDOF · búsqueda por palabra** `POST /busqueda/CargaNotasAvanzadas/` | Adaptador 1: «Buscar ahora» | Lo usa el propio sitio, pero **no está documentado**. Sin CAPTCHA, 0.4–6 s. Necesita `tipoBus=C` e `idOrg=TODOS`. Ignora acentos y busca palabra completa. En 2026: 79 notas de «osteosintesis» y 64 de «endoprotesis» |
| **SIDOF · servicios documentados** `GET /dof/sidof/notas/{dd-mm-aaaa}`, `/notas/nota/{codNota}`, `/documentos/pdf/{codDiario}` | Lectura de cada nota, evidencia y barrido diario de respaldo | Oficiales (página de datos abiertos). Los avisos de compra traen `codOrgaUno=="CV"` |
| Compras MX | Solo importación manual (URL, número de procedimiento o PDF) | Listado con 401: pide cabeceras cifradas, reCAPTCHA v3 y prueba de trabajo. **No se elude** |
| datos.gob.mx / OCDS | Fuera | Solo histórico 2010–2022, devuelve 403 a scripts y el API de OCDS no respondió (timeout) |
| IMSS | Opcional: vigilar su evento en vivo | Sin búsqueda; su robots.txt pide 10 s entre peticiones |

Consecuencias para el diseño:
- Campos que se pueden extraer de una nota: número de procedimiento, convocante, objeto, volumen, fecha de
  publicación en Compras MX, junta de aclaraciones, apertura y, a veces, fallo. **Una nota puede traer varios
  procedimientos.** También se publican los avisos de fallo con el ganador.
- El DOF publica entre 0 y 28 días después que Compras MX, y en 3 de 10 casos lo hizo después de la apertura. La
  búsqueda en vivo sirve para **descubrir y dar contexto histórico**; la vigencia de una oportunidad se confirma con
  Compras MX de forma manual.
- Al 2026-10-28 no hay procedimiento abierto confirmado. Los más recientes ya pasaron: LA-50-GYR-050GYR010-T-104-2026
  (IMSS Durango, apertura 21-10) y LA-64-072-905038959-N-57-2026 (Coahuila, apertura 16-10). La demo debe decirlo así.
- Una búsqueda sin resultados devuelve una respuesta sin `messageCode`, que se registra como «cero, sin confirmar» y
  nunca como «no hay licitaciones».
- Ritmo: 1 petición/s, una a la vez; timeout de 10 s para conectar y 20 s para leer; 2 reintentos. Hay que volver a
  probar desde la IP de Railway.
- **Riesgos para Emmanuel:** (a) el aviso legal del SIDOF pide consentimiento escrito de SEGOB para reproducir
  contenido del DOF con fines de lucro, así que en la demo se cita y se enlaza la nota oficial, sin republicarla
  completa; (b) la búsqueda depende de un endpoint no documentado, con el barrido diario documentado como respaldo.

## 8. Decisiones del builder (para que Emmanuel las revise)

1. **Bitácora inmutable.** La tabla de auditoría es solo de inserción, y en Postgres lo hace cumplir un trigger que
   rechaza UPDATE y DELETE. Cada evento guarda `prev_hash` y `hash` (cadena SHA-256). La vista de gobierno corporativo
   tiene un botón «Verificar integridad» que recorre la cadena y muestra el resultado.
2. **El reinicio del demo nunca borra la bitácora.** Cada reinicio abre una «corrida demo» (`demo_run_id`) que se
   guarda en cada evento. El historial de una oportunidad muestra solo la corrida actual, para que los eventos del
   ensayo no aparezcan en la reunión. La bitácora global muestra todas las corridas, etiquetadas.
3. **Qué borra el reinicio:** solo `SYNTHETIC`, más las 3 referencias `HISTORICAL` del pack, que se vuelven a sembrar
   igual. Los resultados de SIDOF son `REAL` (vienen de la fuente en vivo aunque su fecha ya haya pasado) y
   sobreviven al reinicio, igual que las corridas de búsqueda y sus evidencias. Los archivos de documentos `SYNTHETIC`
   en el bucket se borran.
4. **PDFs como evidencia.** Los PDFs propios de Dipromedic y Traufix se suben una vez al bucket con un script, con
   SHA-256, y se citan por página. Los de terceros (Corentec, Biotechni, Anton-Hipp, IOT) **solo se enlazan**, con la
   etiqueta «documento de tercero · enlace externo». Su reutilización no está cubierta por el aviso de Dipromedic.
5. **Trabajos asíncronos.** Para esta semana corre un worker dentro del servicio `web`, en un hilo de fondo, que lee
   una tabla de trabajos en Postgres con `SKIP LOCKED`. Separarlo en un servicio `worker` queda como evolución en
   ADR-001; el contrato es el mismo.
6. **Vista de gobierno corporativo:** la ve Dirección (permiso `audit.read`). No se crea un rol nuevo. El rol
   `admin_ti` sigue en el backend solo para reiniciar el demo y operar fuentes, pero no aparece en la demo.
7. **Licencia de reutilización:** las fichas importadas y el pie de página llevan el crédito «DIPROMEDIC S.A. DE C.V. ·
   www.dipromedic.com» y la fecha de consulta. El contenido del DOF se cita y se enlaza a la nota oficial, sin
   republicar el texto completo.

## 9. Lo que queda al builder

- Estructura interna de módulos, nombres de tablas nuevas y el orden de los trabajos dentro de cada frente.
- El diseño visual detallado dentro de la identidad Dipromedic: densidad, componentes y microinteracciones.
- El formato exacto de las plantillas DOCX, siempre que contengan los campos del pack §12 y la marca DEMO.
- La librería de generación (python-docx, openpyxl) y el cliente S3 (boto3), con versiones fijadas.
