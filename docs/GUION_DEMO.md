# Guion de la demo · reunión con Dipromedic

Recorrido del task pack §4 en **11 min** (rango 10–12 min). Asistentes: **Gobierno** (gerente de Gobierno Corporativo) y
**Comercial** (Director Comercial). Presenta Emmanuel. El demo cubre solo el área comercial: TI y planta están fuera del
alcance (decisión del 2026-10-30), así que no hay vista de TI ni se habla de integración con planta o ERP.

Cuentas (`@dipromedic.example`, contraseña de `DEMO_USER_PASSWORD`): `presentador` (todos los roles), `analista1`,
`revisor`, `responsable`; de respaldo `direccion`. La cuenta `ti` existe solo para operar el demo y no aparece en el selector. Se cambia de cuenta con **«Cambiar cuenta»** en la barra
superior: es un inicio de sesión real (pide la contraseña), así que los permisos que se ven son los del backend.

Regla para todo el recorrido: si algo no está, se dice que no está. Nada se rellena con datos ficticios ni se
presenta lo simulado como real.

## Lista de verificación previa (la mañana de la reunión)

1. **Reinicio del demo.** Con `ti` o `presentador`: Operación → «Reiniciar demo» (o en el servidor
   `python scripts/bootstrap.py --reset`). No toca datos REAL. Comprobar que DEMO-LIC-001 está en «Análisis»,
   sin evaluación y con DEMO-REQ-005 en «Faltante».
2. **Búsqueda real.** Radar → «Buscar ahora» con los términos por omisión. Anotar la hora, notas leídas y
   procedimientos. Si no hay abiertas, se dirá así en la reunión (paso 2).
3. **Integridad en verde.** Gobierno → «Verificar integridad de la bitácora» → «Los eventos verificados enlazan
   correctamente». **Anotar el último hash** (botón «Copiar») fuera del sistema, por ejemplo en un correo a uno mismo.
4. **Estado operativo (por API, sin vista):** `GET /api/v1/ops/status` con la sesión de `presentador` →
   `worker_alive: true`, `storage_backend: "s3"` (no `"local"`), versión desplegada y revisión de la base.
5. Entrar una vez con cada cuenta del guion (no deben estar vencidas). Tener a mano la contraseña.
6. Tener abierto en el escritorio `docs/demo/Ficha_tecnica_DEMO_para_carga.pdf` (lo carga analista1 en el paso 7).
7. Abrir una vez los seis DOCX de un borrador en Word (no se han revisado en Word, solo con python-docx).
8. Navegador a 1440 px, zoom 100 %, sin otras pestañas con sesión. Plan B listo (abajo).

## Recorrido

| # | Tiempo | Cuenta | Qué se hace | Qué se dice |
|---|---|---|---|---|
| 1 | 1:00 | presentador | **Panel** (`/panel`): reales, históricos y simulados en columnas separadas; «No hay oportunidades reales abiertas verificadas en este momento». Luego **Radar**: filtros REAL / HISTÓRICO / SIMULADO y la columna de fuente y última comprobación. | **Comercial:** «Cada registro dice de dónde viene y cuándo se comprobó; lo simulado lleva rayado y la marca DEMO.» **Gobierno:** «Los tipos de dato nunca se suman: un escenario ficticio con fecha futura jamás cuenta como oportunidad real.» |
| 2 | 1:30 | presentador | Radar → **«Buscar ahora»** (osteosíntesis y endoprótesis). Se ve el avance por término, la fuente (SIDOF/DOF), la hora y el resultado (nuevos, actualizados, sin cambios). Si no hay abiertas, la pantalla lo dice. | **Comercial:** «Es una consulta real al Diario Oficial en este momento, no una lista guardada.» Si no sale ninguna abierta: «Hoy el DOF no muestra licitaciones abiertas del giro, y el DOF va de 0 a 28 días detrás de Compras MX.» **Gobierno:** «Si la fuente falla, se registra como fallo, no como "no hay licitaciones".» |
| 3 | 0:45 | presentador | Radar → filtro HISTÓRICO → **LA-50-GYR-050GYR075-I-134-2026**. Fecha de presentación transcurrida, resultado «Desconocido», «Abrir fuente». | **Comercial:** «Sirve como referencia de compradores y requisitos. No le atribuimos un fallo que no consultamos.» |
| 4 | 0:30 | presentador | Filtro SIMULADO → **DEMO-LIC-001**. Aviso «Escenario ficticio · fechas relativas a la fecha base» y la píldora «Fecha base demo» de la barra. | **Gobierno:** «A partir de aquí todo es un escenario de prueba, y la pantalla lo dice en cada bloque.» |
| 5 | 1:30 | presentador | Panel del expediente → **«Evaluar correspondencia»**; pestaña **Partidas**: partida 1 *Coincide* (placa ALP 3.5 mm de Traufix, 6 orificios, cita del catálogo), partida 2 *Incumple* (piden 11 orificios; el catálogo ofrece 5, 6, 7, 8, 9, 10 y 12), partida 3 *Desconocido* (la ficha no declara la longitud de 96 mm). Afinidad 55/100 con datos desconocidos. | **Comercial:** «Son productos reales de dipromedic.com, con la cita literal de la ficha; los precios sí son ficticios y lo dicen.» **Gobierno:** «La afinidad no es probabilidad de ganar ni dictamen. Lo que el catálogo no declara queda desconocido: no se infiere del nombre.» |
| 6 | 0:45 | presentador | Pestaña **Requisitos** (matriz) → DEMO-REQ-005 «Ficha técnica» en *Faltante* → **«Asignar»** a Analista comercial 1, fecha límite. | **Comercial:** «Cada faltante tiene responsable y fecha; aparece en "Mis pendientes" de esa persona.» |
| 7 | 2:15 | analista1 → revisor → responsable | **analista1:** «Vincular evidencia» → «Cargar documento nuevo» (la ficha DEMO) → «Vincular y enviar a revisión»: el requisito queda **En revisión**, no validado; analista1 no ve «Revisar» (validar no es de su rol). **revisor:** «Revisar» → *Cumple · validado* con motivo; luego **aprobación técnica**. **responsable:** «Registrar decisión» → participar, con motivo; **aprobación comercial**; **«Listo para revisión final»** → *No puede pasar: bloqueantes* (DEMO-REQ-001, 002, 003, 004, 006 y 007). Pestaña **Historial**: cada cambio con antes y después. | **Gobierno:** «Quien carga la evidencia no la valida; la aprobación técnica y la comercial las dan personas distintas, aunque alguien tenga los dos roles. Cada evidencia nueva anula las aprobaciones previas.» **Comercial:** «El sistema no deja marcar listo un expediente con obligatorios abiertos o con conflicto contra el catálogo.» |
| 8 | 1:00 | responsable | Pestaña **Expediente** → «Antes de generar» (versión de datos, total 198,400.00 MXN, tratamiento fiscal pendiente, pendientes abiertos) → **«Generar borrador»** (las seis plantillas). | **Comercial:** «Borrador técnico y económico, índice y matriz; los montos se calculan con aritmética exacta y lo que falta queda marcado [PENDIENTE].» |
| 9 | 1:00 | responsable | Historial de borradores → **descargar el ZIP** → «Ver manifiesto»: archivos con su SHA-256, procedencia (REAL / SIMULADO) y documentos excluidos. Abrir la propuesta económica: pie con la marca DEMO y la versión de datos. | **Gobierno:** «Cada descarga queda en la bitácora y se verifica contra su huella. No hay firmas, sellos ni registros sanitarios inventados; el aviso dice "Borrador · no apto para presentación".» |
| 10 | 0:45 | presentador | **Gobierno** (`/gobierno`): «Verificar integridad», tabla de decisiones y aprobaciones (quién, rol, motivo), matriz de permisos. **Bitácora** si preguntan. | **Gobierno:** «La bitácora encadena cada evento con SHA-256; en Postgres un trigger impide modificarla o borrarla. Para una garantía mayor, el último hash se ancla fuera de la base, como hicimos esta mañana.» |

Total: 11 min. Si hay que recortar, el paso 3 se dice sin abrir el registro (−0:30) y en el paso 10 se omite la
matriz de permisos (−0:15).

## Plan B

1. **Laptop local** (si Railway no responde). En la laptop, con el repositorio y Docker:
   ```bash
   docker compose up -d                       # postgres:17 en localhost:5432 (ver .env.example)
   export DATABASE_URL=postgresql://postgres:toor@localhost:5432/licit
   export DEMO_USER_PASSWORD=… SESSION_SECRET=… JOBS_WORKER=1 IMPORT_CATALOG=1
   .venv/bin/alembic upgrade head && .venv/bin/python scripts/bootstrap.py
   cd frontend && npm run build && cd .. && .venv/bin/uvicorn app.main:app --port 8000
   ```
   Abrir `http://localhost:8000`. Dejarlo preparado antes de salir hacia la reunión (catálogo importado y una
   búsqueda hecha). Sin bucket, los documentos viven en `STORAGE_DIR`; se dice así si alguien pregunta.
2. **Importación manual** (si tampoco responde SIDOF). Radar → «Importar»: pegar la URL de una nota de SIDOF ya
   consultada, o capturar un procedimiento de Compras MX (número, título, convocante, enlace). Queda REAL «Por
   verificar». En pantalla aparece «SIDOF no respondió… Esto no significa que no haya licitaciones»: se lee tal cual.
3. Si ni la laptop arranca: recorrer este guion con las capturas de `.superpowers/sdd/…/shots-*` y decirlo.

## Respuestas preparadas

- **¿Por qué Compras MX no está automatizado?** Su listado público responde 401 si no se le envían cabeceras
  cifradas, reCAPTCHA v3 y una prueba de trabajo (WASM). Eludir eso sería saltarse una protección del sitio, y no
  inventamos APIs. Por eso la carga es manual (URL o captura), con su procedencia. Si Buen Gobierno publica una API o
  datos abiertos, se agrega un adaptador como el de SIDOF.
- **¿Por qué no hay licitaciones abiertas?** Porque hoy el DOF no muestra procedimientos del giro con apertura
  futura; los más recientes (por ejemplo IMSS Durango T-104) ya pasaron. El DOF publica entre 0 y 28 días después que
  Compras MX y, en 3 de 10 casos revisados, después de la apertura. La búsqueda sirve para descubrir y dar contexto; la
  vigencia se confirma en Compras MX. Preferimos decir «no hay» a rellenar la pantalla con escenarios.
- **¿Qué pasa con la IA?** Esta demo no usa IA, por decisión. Los requisitos se capturan con página y fragmento, y la
  comparación la hace un motor determinista que cita el catálogo. Una IA podría proponer extracciones después, pero
  siempre como propuesta que valida una persona: nunca aprueba ni cambia estados. Hay una prueba que mete instrucciones
  maliciosas en una nota oficial y comprueba que solo se tratan como texto.
- **¿Y planta, ERP o TI?** Fuera del alcance de este demo, que es solo comercial. Las existencias (`stock_demo`) y los
  precios son ficticios y están marcados; conectarlos a datos reales es otra fase (backlog T19).
- **¿Quién mantiene esto?** Respuesta sugerida, que Emmanuel confirma antes de la reunión: hoy lo opera Atlas
  Technologies como demo en Railway. Es un stack estándar (FastAPI, React, PostgreSQL, Docker, migraciones Alembic)
  con más de 400 pruebas automáticas, así que el equipo técnico de Dipromedic puede recibirlo con el repositorio, las instrucciones,
  la evidencia de QA y el inventario de servicios (task pack §17). El adaptador de SIDOF depende de un endpoint no
  documentado y hay que vigilarlo.
