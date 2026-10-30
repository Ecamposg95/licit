# Grupo Dipromedic: reconocimiento del sitio web (marca, mapa del sitio, catálogo)

- **Sitio**: https://www.dipromedic.com (también se revisó, de forma acotada, https://traufix.com, el sitio de la marca Traufix que aloja la mayoría de las técnicas quirúrgicas y brochures).
- **Fecha de revisión**: 2026-10-28. Todas las URLs citadas se consultaron ese día.
- **Método**: `curl` con User-Agent de navegador, peticiones secuenciales con pausas de 0.7 a 1.5 s. Se descargó el HTML de 23 páginas de sección y 49 páginas de producto, 8 hojas de estilo, 15 logotipos, 4 imágenes de muestra y 60 PDFs. El texto se extrajo con un parser propio. Cada `source_text` del JSON se verificó automáticamente como cita literal de la página.
- **Archivos generados**:
  - `docs/research/dipromedic-catalogo.json`: catálogo estructurado (116 registros, 323 códigos).
  - `docs/research/dipromedic/brand/`: copias locales de logotipos y mascota.
  - `docs/research/dipromedic/pdfs/`: 60 PDFs de 15 MB o menos (213 MB en total). Lleva su propio `.gitignore` (`*`) para que no se versionen por accidente. Si se quieren versionar, hay que borrar ese archivo.

---

## 1. Marca, look and feel

### 1.1 Stack técnico
| Hallazgo | Evidencia |
|---|---|
| Sitio **PHP a medida**, no WordPress ni Wix. Servidor **LiteSpeed**, cookie `PHPSESSID`, URLs limpias (`/traufix/extremidad-superior/titan`) | Cabeceras HTTP de https://www.dipromedic.com/; `/wp-json/` responde 404 |
| Basado en el template comercial **"Healdi – Medical & Health Template" (validtheme)**, v1.2, personalizado | Comentario de cabecera en https://www.dipromedic.com/style.css |
| Bootstrap 5, jQuery 3.7.1, Bootsnav (mega-menú), Owl Carousel, WOW.js + animate.css, Magnific Popup, Isotope, Parsley.js, SweetAlert2 | `<script>`/`<link>` del home |
| **Modelos 3D interactivos** (`<model-viewer>`, archivos `.glb`) en las tarjetas de producto Traufix, con auto-rotación | `/assets/js/model-viewer.js`; p. ej. `/assets/img/products/traufix/3d/titan.glb` |
| Buscador de productos (botón flotante + modal) → `GET /productos?q=` ("Búsqueda por nombre o código de producto"), renderizado en servidor | home, https://www.dipromedic.com/productos. No se ejecutaron búsquedas |
| Botón flotante de WhatsApp con icono "IA" → `https://wa.me/525599629022` | `/assets/css/fab-whatsapp-ia.css`, `/assets/img/icon/ia-icon.svg` |
| Google Analytics 4 `G-5ZQQFL4Q9S` | `<head>` de todas las páginas |
| Sin `robots.txt`, sin `sitemap.xml`, sin API JSON. El contenido está completo en el HTML, sin render por JS (excepto los modelos 3D) | ver §5 |

### 1.2 Colores (hex exactos)
Fuente principal: bloque `:root` de https://www.dipromedic.com/style.css (los comentarios en español son del propio CSS). Los colores de los logotipos se midieron como píxel dominante de los PNG.

| Token | Hex | Uso observado | Fuente |
|---|---|---|---|
| `--color-blue-dipromedic` | **#0F75BC** | Azul corporativo: palabra "DIPROMEDIC" y tagline del logo, títulos de tarjetas de producto, iconos KPI, pestañas activas, etiquetas. Comentario CSS: *"Obtenido del logo de Grupo Dipromedic"* | style.css; píxel dominante de `logo-dipromedic-color.png` (1,082 px) |
| `--color-green-fixi` | **#47AD36** | Verde de acento: subrayado de 90×5 px bajo los H2 de sección, bordes, fin del gradiente de botones. Comentario CSS: *"Obtenido de la cabeza de Fixi"* | style.css; `fixi-color.png` |
| gradiente botón | **#63F24B → #47AD36** (90°) | `.btn-gradient`, `.btn-green-gradient` (botones "Ver más", "Ver catálogo completo", "Técnica Quirúrgica") | style.css |
| verde del logotipo | **#0B9444** | Palabra "GRUPO" y swoosh del logo PNG (distinto del verde Fixi) | píxel dominante de `logo-dipromedic-color.png` |
| azul Fixi | **#244999** | Cuerpo de la mascota "Fixi" | `fixi-color.png` |
| `--color-blue-traufix` | **#004991** | Títulos de tablas de producto Traufix (inline `color: #004991`) | style.css + HTML de las páginas Traufix |
| `--color-secondary` | **#001D4C** | Fondo navy del footer (`.bg-dark`) | style.css |
| `--color-primary` | #0A0A0A | Casi negro (sustituye al teal #1ebeb6 del template, que quedó comentado) | style.css |
| `--color-heading` / `--color-paragraph` | #232323 / #666666 | Texto | style.css |
| texto del footer | #96AAC1 | Párrafos y links del footer | style.css |
| bordes / fondo gris | #E7E7E7 / #F7F7F7 | Sombras `0 0 10px #e7e7e7`, fondos | style.css |
| `.bg-gradient` (hero de páginas internas) | #1EBEB6 → #00827C | Teal heredado del template, debajo de una foto al 50% de opacidad. **No se verificó visualmente**: no había navegador headless disponible | style.css |
| cinta "Lanzamiento" | #00C6FF → #0066FF | `.ribbon-diagonal` | style.css |
| cinta "Próximamente" | #F89B34 → #EB622C | `.ribbon-diagonal-biotechni` | style.css |
| línea de tiempo | #0D6EFD | Azul Bootstrap en /nosotros | `/assets/css/timeline.css` |

**Paleta recomendada para el demo**: #0F75BC (primario), #47AD36 (acento, con gradiente #63F24B→#47AD36 en CTAs), #001D4C (navy de footer y sidebar), #004991 (variante "Traufix"), neutros #232323, #666666, #E7E7E7 y #F7F7F7.

### 1.3 Tipografía
- **Inter**, cargada desde Google Fonts: `@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap')`. Es la fuente de `body`, encabezados y botones (style.css).
  - body: 15px, line-height 30px, peso 400, color #666.
  - botones: peso 600.
  - H2 de sección: 52px, peso 600.
  - título de hero interno: 30px, peso 700, blanco.
- "Poppins" aparece en 2 reglas sueltas sin `@import`, es un residuo del template.
- Iconos: Font Awesome (5/7 Free), Themify, Flaticon.

### 1.4 Logotipos e imágenes de marca
Todos en `https://www.dipromedic.com/assets/img/branding/`. Hay copias locales en `docs/research/dipromedic/brand/`.

| Archivo | Formato / tamaño | Variante |
|---|---|---|
| `logo-dipromedic-color.png` | PNG 166×69 | **Color, para fondo claro** (header). "GRUPO" en verde, "DIPROMEDIC" en azul, swoosh verde, tagline *"Medical Devices and Health Solutions"* |
| `logo-dipromedic-blanco.svg` | SVG, viewBox 0 0 166 58, todo #FFFFFF | **Blanco, para fondo oscuro** (footer). Es el único logo vectorial de Dipromedic |
| `favicon.png` | PNG 55×55 (azul #446EB3) | Favicon |
| `fixi-color.png` | PNG 97×164 | **Mascota "Fixi"**: figura azul en forma de "X" con cabeza verde (aparece en el menú y en "Línea Dipromedic") |
| `logo-traufix-color.svg` / `logo-traufix-blanco.png` (2653×973, también .webp) | | Traufix |
| `sports-medicine-blanco.png` (1080×350, también .webp) | | Traufix Sports Medicine |
| `logo-corentec-blanco.webp` | | Corentec. El PNG referenciado `logo.corentec-blanco.png` da **404** |
| `logo-biotechni-blanco.png` (2119×973), `logo-anton-hipp-blanco.png` (3163×781) | | Marcas representadas |
| `logo-fixier-color.svg`, `logo-lionter-color.svg`, `logo-imedicom-color.svg`, `logo-bencox-color.svg`, `logo-lospa-*.svg`, `logo-dipromedic-{bajio,occidente,morelia,interdipro}-color.svg`, `logo-biortotec-color.svg`, `logo-traufix-old.svg` | SVG 1200×480 | Usados en la línea de tiempo de /nosotros |

No existe `logo-dipromedic-color.svg` ni una versión PNG del logo blanco: se probaron 6 nombres y todos dan 404.

### 1.5 Estilo visual, componentes y tono
- **Imágenes**:
  - Heroes claros, de estilo "tech": por ejemplo `/assets/img/banner/hero-1.webp` es una infografía "Servicios Integrales" con circuitos y destellos azules, el logo al centro y 9 pilares: *Sistema de trazabilidad, Somos fabricantes, Mejor relación Calidad-Precio, Experiencia de servicio, Siempre disponibles, Técnicos calificados, Conocemos el proceso quirúrgico, Mantenimiento de equipos, Vigilancia post-venta, ISO 9001 enfoque servicios integrales*.
  - Foto de stock familiar (`/assets/img/banner/family.webp`, de Envato según /propiedad-intelectual) bajo los heroes de páginas internas.
  - Render del corporativo de Querétaro (`dipromedic-corporativo.webp`).
  - Retratos de médicos en PNG y banners de congresos.
  - **Fotos de producto**: renders 1200×1200 en PNG transparente, con titanio anodizado verde-azulado y tornillos dorados. Son pesados (~6 MB cada uno). Además hay modelos `.glb`.
- **Botones**: tipo pastilla (`border-radius: 40–50px`), gradiente verde, texto blanco y peso 600. Llevan un icono chevron `fa-angle-right` dentro de un círculo blanco de 30 px.
- **Tarjetas de producto** (`.department-items .item`): fondo blanco, esquinas rectas y sombra `0 0 10px #e7e7e7`. Título H5 centrado en #0F75BC, descripción corta y botón "Ver más". Cinta diagonal arriba a la izquierda ("Lanzamiento", "Próximamente", "Nuevos productos").
- **Hero de páginas internas**: logotipo blanco de la marca, título separado por un borde izquierdo blanco de 5 px, foto al 50% sobre gradiente, onda SVG blanca abajo (`white-wave-breadcrumb.svg`) y patrón hexagonal de fondo (`hex-background-shape.svg`).
- **Tablas de producto**: título en azul Traufix y en negrita. Pares "Versión Izq. (Cód. X) / Der. (Cód. Y)" seguidos de la lista de orificios o medidas.
- **Footer**: navy #001D4C con texto #96AAC1, logo blanco, correo, "Línea Dipromedic", links legales y direcciones CDMX/Querétaro.
- **Tono**: español institucional y cálido, orientado al cirujano y al servicio. Taglines y frases:
  - *"Servicio, Excelencia, Responsabilidad."*
  - *"Servicios Integrales de Excelencia."*
  - *"Medical Devices and Health Solutions"* (en el logo)
  - *"Continuamos innovando y creciendo contigo."*
  - *"¡Una historia de éxito!"*
  - *"Expertos Que Impulsan Nuestra Innovación"*
  - *"Por eso existimos: para impulsar la evolución de la ortopedia y la traumatología mediante innovación, autonomía y confianza en cada etapa del proceso."* (/nosotros)

---

## 2. Mapa del sitio (verificado el 2026-10-28; todas las páginas responden HTTP 200 salvo que se indique otra cosa)

**Institucional**: `/` (=`/home`) · `/nosotros` (filosofía, línea de tiempo, misión, visión, valores, testimonios) · `/contacto` (formulario, oficinas, `#distribuidores-autorizados`) · `/eventos` (`#proximoEvento`) · `/atraccion-de-talento` (vacantes) · `/aviso-de-privacidad` · `/propiedad-intelectual` · `/productos?q=` (buscador). `/recursos` aparece enlazado en comentarios HTML pero responde **404**.

**Traufix**
- Categorías:
  - `/traufix/extremidad-superior`
  - `/traufix/extremidad-inferior`
  - `/traufix/clavos-intramedulares`
  - `/traufix/bandas-cerclaje`
  - `/traufix/otras-soluciones`
  - `/traufix/sports-medicine`
- Productos de extremidad superior: `/traufix/extremidad-superior/{titan, telios, lionter, clavilock-sin-gancho, clavilock-con-gancho*, placa-bloqueada-alp}`
- Productos de extremidad inferior: `/traufix/extremidad-inferior/{tibi-al, tidis, fibule, condyfix, optimus, tlp, placas-sosten, placas-rectas}`
- Placa de acero inoxidable: `/traufix/placas-acero-inoxidable/placa-reconstruccion`
- Clavos: `/traufix/clavos-intramedulares/{t-fix, h-fix, elix, intralock-femoral-anterogrado, intralock-femoral-retrogrado, intralock-tibia-anterogrado, talofix}`
- Cerclaje: `/traufix/bandas-cerclaje/ultra-tape`
- Otras soluciones: `/traufix/otras-soluciones/{spider-hto, herbert-y-headless, tarfix}`
- Sports Medicine: `/traufix/sports-medicine/{anclas, tornillos-interferenciales, miscelaneos, sistema-fijacion-cortical, instrumental}`

**Corentec**
- Categorías: `/corentec/{cadera, rodilla-primaria, rodilla-revision, hombro, columna}`
- Productos:
  - `/corentec/cadera/{vastago-id-stem, m-stem, mirabo-z, mirabo-copa-multihole, copa-bipolar, copa-hibrida*}`
  - `/corentec/rodilla-primaria/{lospa, exult}`
  - `/corentec/rodilla-revision/lospa`
  - `/corentec/hombro/coralis`
  - `/corentec/columna/{tornillos-transpediculares, cajas-intersomaticas-tlif}`

**Biotechni**: `/biotechni/cadera` → `/biotechni/cadera/{vastago-filler, vastago-tthr-easy, vastago-tthr-modular, apogee}`

**Otras marcas**
- Caleb: `/caleb/lavador-pulsatil-e7`
- Imedicom: `/imedicom/sistema-extraccion-copa`
- Anton-Hipp: `/anton-hipp/sistema-osteosintesis` → `/anton-hipp/sistema-osteosintesis/{placas-craneomaxilofacial, placas-mano-pie}`
- IOT: `/otros/purist`

`*` = la página de detalle está publicada, pero su tarjeta está **comentada** en el HTML de la categoría, así que no aparece en el listado público.

En el HTML también hay tarjetas comentadas, sin página propia: **PROH-LOCK** ("Placa bloqueada anatómica para fracturas proximales de húmero", con modelo `proh-lock.glb`), **Clavo Pediátrico ESIN** y **Placas Olecranon**.

**Externos**:
- Facebook `grupodipromedic`, Instagram `grupodipromedic`, YouTube (canal `UChv6r_U-prSwVCzfTHmDSDA`).
- Bolsa de trabajo `dipromedic.pandape.computrabajo.com`.
- Muchos videos de producto en YouTube.
- **traufix.com**: WordPress + Yoast. Repite el catálogo Traufix y aloja los PDFs. Añade 1 producto que no está en dipromedic.com (*INTRALOCK Clavo Intramedular para Húmero*) y páginas de certificaciones, instructivos, estudios clínicos y blog.

---

## 3. Catálogo: resumen
El detalle completo está en `docs/research/dipromedic-catalogo.json`.

**Totales**: 7 líneas, 116 registros y 323 códigos.
- Traufix: 95 registros. Son 16 placas, 8 clavos (incluye Intralock húmero de traufix.com), 1 cerclaje, 4 de otras soluciones, 37 grupos de Sports Medicine y 29 tornillos/pernos/tapones. Los tornillos se deduplicaron a partir de las listas "Tornillos" de cada placa o clavo.
- Corentec: 12.
- Biotechni: 4.
- Caleb: 1.
- Imedicom: 1.
- Anton-Hipp: 2.
- IOT (Purist): 1.

**Dónde hay datos técnicos reales y dónde solo nombres comerciales**
- **Traufix (placas, clavos, tornillos, cerclaje)**: es la información más rica.
  - Material: "aleación de Titanio (Ti6Al4V ELI, ASTM F136)"; acero 316LS de 2.5 mm en la placa de reconstrucción.
  - Tablas con **códigos Izq./Der.** y **número de orificios**.
  - Clavos: **diámetros × longitudes por código**.
  - Perfil en mm, ángulos (±15°, 125°, 18°), lateralidad y esterilidad.
  - Cada placa trae su lista de tornillos compatibles, con código y rango de longitud (p. ej. "3.5mm Tornillo de Cortical ALP Titanio (Cód. 106, Longitud 12mm-60mm)").
- **Traufix Sports Medicine**: tablas con **códigos SKU tipo `STRAUFIX-XXX-0000`**, diámetro, número de agujas, sutura USP, medidas y ángulos. Los equipos de instrumental se listan con cantidad y medidas, pero sin códigos.
- **Corentec y Biotechni**: solo texto técnico descriptivo, **sin códigos ni tablas de tallas**. Datos destacables:
  - cono 12/14, inclinación humeral 145°, flexión 140°
  - porosidad >30%, 12 cejas, 10 Mrad
  - Apogee: 10 tamaños de 44 a 62 mm, cabezas de 22/28 mm
  - TTHR Easy: longitudes 190/240/290/340 mm, diámetros distales 10/12 mm
  - Lospa revisión: adaptadores 2/4/6 mm
  - Hybrid Cup: cabezas 28/32/36/40 mm
- **Anton-Hipp**: solo sistemas por diámetro (1.6/2.0 mm para craneomaxilofacial; 1.6/2.3/2.7 mm para mano), sin códigos.
- **Caleb E7, Imedicom EZX, Purist**: solo descripción y características comerciales y funcionales. Sin códigos ni medidas.

**Regla aplicada**: nada se dedujo del nombre comercial. `family` y `subfamily` son etiquetas normalizadas a partir de la categoría del sitio. `region_anatomica` cita el título o la descripción de la página (p. ej. "TITAN Placa bloqueada ALP para Húmero Proximal"). Todos los demás atributos llevan su `source_text` literal.

**Solo en el catálogo PDF de Traufix**: `/assets/docs/catalogos/traufix/Catalogo-Traufix-ES.pdf` (20 páginas, 7.2 MB) menciona artículos que no tienen página web:
- **equipos de instrumental**: grandes y pequeños fragmentos ALP, pelvis y acetábulo, DHS/DCS, canulado 4.0 y 7.0, y un equipo por cada clavo
- **All in One Kit**
- **Sistema modular ALP**
- **alambres Kirschner y clavillos**
- **tornillos de acero** (esponjoso 4.0/6.5, cortical 3.5/4.5, canulados 4.0/7.0)

La lista está en `pdf_only_mentions` del JSON. Se obtuvo por extracción automática del texto del PDF y no se transcribió en detalle. Es relevante para licitaciones porque muchas piden "equipo en comodato".

### 3.1 Productos (excepto los tornillos sueltos; la columna "Atributos técnicos" cuenta las claves de `attributes`)
| Línea | Familia / subfamilia | Producto | Códigos | Atributos técnicos | Página |
|---|---|---|---|---|---|
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad superior | TITAN Placa bloqueada ALP para Húmero Proximal | 7 | 9 | /traufix/extremidad-superior/titan |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad superior | TELIOS Placa bloqueada para Húmero Distal Lateral y Medial | 8 | 6 | /traufix/extremidad-superior/telios |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad superior | LIONTER Placa bloqueada Radio Distal Volar | 8 | 8 | /traufix/extremidad-superior/lionter |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad superior | CLAVILOCK Placa ALP para clavícula superior anterior (con y sin extensión lateral) | 7 | 5 | /traufix/extremidad-superior/clavilock-sin-gancho |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad superior | Placa ALP para clavícula con gancho CLAVILOCK (no listado) | 2 | 4 | /traufix/extremidad-superior/clavilock-con-gancho |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad superior | Placa bloqueada ALP 3.5 | 3 | 4 | /traufix/extremidad-superior/placa-bloqueada-alp |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | Tibi-AL Placa Bloqueada ALP para Tibia Distal Anterolateral | 6 | 6 | /traufix/extremidad-inferior/tibi-al |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | TIDIS II Placa bloqueada ALP para Tibia Distal Medial | 5 | 9 | /traufix/extremidad-inferior/tidis |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | TIDIS Placa bloqueada ALP para Tibia Distal Medial | 5 | 6 | /traufix/extremidad-inferior/tidis |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | FIBULE Placa bloqueada ALP para Peroné Distal | 6 | 7 | /traufix/extremidad-inferior/fibule |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | CONDYFIX Placa bloqueada ALP para Fémur Distal | 5 | 5 | /traufix/extremidad-inferior/condyfix |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | OPTIMUS Placa bloqueada ALP para Tibia Proximal | 5 | 5 | /traufix/extremidad-inferior/optimus |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | TLP Placa bloqueada ALP para Fémur Proximal | 6 | 5 | /traufix/extremidad-inferior/tlp |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | Placas de sostén en “T” y “L” bloqueadas ALP Titanio | 6 | 4 | /traufix/extremidad-inferior/placas-sosten |
| Traufix | Osteosíntesis / Placas bloqueadas ALP titanio – extremidad inferior | Placa bloqueada Angosta y Ancha ALP 4.5 | 5 | 5 | /traufix/extremidad-inferior/placas-rectas |
| Traufix | Osteosíntesis / Placas de acero inoxidable | Placa de Reconstrucción Recta y Curva 3.5 | 3 | 3 | /traufix/placas-acero-inoxidable/placa-reconstruccion |
| Traufix | Clavos intramedulares / Clavos intramedulares titanio | T-Fix Clavo Intramedular para Tibia Supra & Infrapatelar | 9 | 6 | /traufix/clavos-intramedulares/t-fix |
| Traufix | Clavos intramedulares / Clavos intramedulares titanio | H-Fix Clavo Intramedular para Húmero | 9 | 7 | /traufix/clavos-intramedulares/h-fix |
| Traufix | Clavos intramedulares / Clavos intramedulares titanio | ELIX Clavo Intramedular Antirrotacional para Fémur Proximal | 10 | 9 | /traufix/clavos-intramedulares/elix |
| Traufix | Clavos intramedulares / Clavos intramedulares titanio | INTRALOCK Clavo Intramedular para Fémur (Anterógrado Diafisiario y Subtrocantérico) | 12 | 5 | /traufix/clavos-intramedulares/intralock-femoral-anterogrado |
| Traufix | Clavos intramedulares / Clavos intramedulares titanio | INTRALOCK Clavo Intramedular para Fémur Retrógrado | 11 | 5 | /traufix/clavos-intramedulares/intralock-femoral-retrogrado |
| Traufix | Clavos intramedulares / Clavos intramedulares titanio | INTRALOCK Clavo Intramedular para Tibia | 4 | 5 | /traufix/clavos-intramedulares/intralock-tibia-anterogrado |
| Traufix | Clavos intramedulares / Clavos intramedulares titanio | TALOFIX Clavo Intramedular para Artrodesis de Tobillo | 10 | 7 | /traufix/clavos-intramedulares/talofix |
| Traufix | Cerclaje / Bandas de cerclaje | Ultra-taPE Sistema de cerclaje autobloqueante | 6 | 4 | /traufix/bandas-cerclaje/ultra-tape |
| Traufix | Otras soluciones / Osteotomía | SPIDER HTO (High Tibial Osteotomy) Placa para Osteotomía Valguizante Tibial Proximal con cuña de apertura medial | 5 | 6 | /traufix/otras-soluciones/spider-hto |
| Traufix | Otras soluciones / Tornillos de compresión canulados | HERBERT HFS Tornillo de compresión canulado | 3 | 4 | /traufix/otras-soluciones/herbert-y-headless |
| Traufix | Otras soluciones / Tornillos de compresión canulados | HEADLESS THS Tornillo de compresión canulado | 6 | 4 | /traufix/otras-soluciones/herbert-y-headless |
| Traufix | Otras soluciones / Tornillos canulados (pie) | TARFIX Tornillo subtalar canulado para corrección del pie plano valgo | 1 | 4 | /traufix/otras-soluciones/tarfix |
| Traufix | Clavos intramedulares / Clavos intramedulares titanio | INTRALOCK Clavo Intramedular para Húmero (no listado) | 18 | 5 | https://traufix.com/clavos-intramedulares/intralock-clavo-intramedular-para-humero/ |
| Traufix | Medicina deportiva / Anclas | Ancla todo sutura | 5 | 1 | /traufix/sports-medicine/anclas |
| Traufix | Medicina deportiva / Anclas | Ancla de PEEK + PEEK sin nudo | 2 | 1 | /traufix/sports-medicine/anclas |
| Traufix | Medicina deportiva / Anclas | Ancla PEEK con aguja | 4 | 1 | /traufix/sports-medicine/anclas |
| Traufix | Medicina deportiva / Anclas | Ancla de titanio con aguja | 4 | 1 | /traufix/sports-medicine/anclas |
| Traufix | Medicina deportiva / Anclas | Ancla sin nudo Presslock | 1 | 1 | /traufix/sports-medicine/anclas |
| Traufix | Medicina deportiva / Anclas | Ancla Trustlock | 3 | 1 | /traufix/sports-medicine/anclas |
| Traufix | Medicina deportiva / Tornillos interferenciales | Tornillo interferencial PEEK | 7 | 1 | /traufix/sports-medicine/tornillos-interferenciales |
| Traufix | Medicina deportiva / Tornillos interferenciales | Tornillo interferencial de titanio | 4 | 1 | /traufix/sports-medicine/tornillos-interferenciales |
| Traufix | Medicina deportiva / Tornillos interferenciales | Tornillo interferencial Biocompuesto | 8 | 1 | /traufix/sports-medicine/tornillos-interferenciales |
| Traufix | Medicina deportiva / Sistema de fijación cortical | Sistema doble botón | 3 | 1 | /traufix/sports-medicine/sistema-fijacion-cortical |
| Traufix | Medicina deportiva / Sistema de fijación cortical | Sistema ajustable - lado superior | 2 | 1 | /traufix/sports-medicine/sistema-fijacion-cortical |
| Traufix | Medicina deportiva / Sistema de fijación cortical | Sistema de fijación Knitbutton | 2 | 1 | /traufix/sports-medicine/sistema-fijacion-cortical |
| Traufix | Medicina deportiva / Sistema de fijación cortical | Sistema de fijación Knitrope - H.T.H | 1 | 0 | /traufix/sports-medicine/sistema-fijacion-cortical |
| Traufix | Medicina deportiva / Sistema de fijación cortical | Sistema de fijación Knitrope - Loop | 1 | 0 | /traufix/sports-medicine/sistema-fijacion-cortical |
| Traufix | Medicina deportiva / Sistema de fijación cortical | Botón de extensión | 1 | 0 | /traufix/sports-medicine/sistema-fijacion-cortical |
| Traufix | Medicina deportiva / Sistema de fijación cortical | Botón Knitrope | 2 | 0 | /traufix/sports-medicine/sistema-fijacion-cortical |
| Traufix | Medicina deportiva / Misceláneos | Suturas de alta resistencia | 4 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Suturas Lasso | 4 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Pin de nitinol para nanofix | 1 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Alambre guía de nitinol y guía inicial de paso | 3 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Aguja de tipo escorpión para pasador de sutura | 2 | 0 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Cánulas | 4 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Sistema de mosaicoplastía donante - Receptor | 3 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Cortador de sutura | 2 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Sistema de reparación meniscal trustknot | 1 | 0 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Grapa de blount dentada | 3 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Tubería para bomba de artroscopía | 2 | 0 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Cuchillas shaver | 3 | 0 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Sistema de reparación meniscal | 3 | 0 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Punta de radiofrecuencia monopolar | 1 | 1 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Misceláneos | Fresa ovalada - Mediana | 3 | 0 | /traufix/sports-medicine/miscelaneos |
| Traufix | Medicina deportiva / Instrumental | Alambre de Kirschner | 2 | 1 | /traufix/sports-medicine/instrumental |
| Traufix | Medicina deportiva / Instrumental | Brocas | 3 | 1 | /traufix/sports-medicine/instrumental |
| Traufix | Medicina deportiva / Instrumental | Guías | 5 | 0 | /traufix/sports-medicine/instrumental |
| Traufix | Medicina deportiva / Instrumental | Equipo All Inside | 0 | 0 | /traufix/sports-medicine/instrumental |
| Traufix | Medicina deportiva / Instrumental | Equipo ACL / PCL | 0 | 0 | /traufix/sports-medicine/instrumental |
| Traufix | Medicina deportiva / Instrumental | Equipo de hombro | 0 | 0 | /traufix/sports-medicine/instrumental |
| Corentec | Cadera / Vástagos | Vástago cementado y no cementado | 0 | 3 | /corentec/cadera/vastago-id-stem |
| Corentec | Cadera / Vástagos | Vástago M-Stem | 0 | 2 | /corentec/cadera/m-stem |
| Corentec | Cadera / Copas | Mirabo Z | 0 | 4 | /corentec/cadera/mirabo-z |
| Corentec | Cadera / Copas | Mirabo Multi-Hole | 0 | 2 | /corentec/cadera/mirabo-copa-multihole |
| Corentec | Cadera / Copas | Copa Bipolar | 0 | 0 | /corentec/cadera/copa-bipolar |
| Corentec | Cadera / Copas | Hybrid Cup (no listado) | 0 | 5 | /corentec/cadera/copa-hibrida |
| Corentec | Rodilla / Rodilla primaria | Lospa rodilla primaria | 0 | 2 | /corentec/rodilla-primaria/lospa |
| Corentec | Rodilla / Rodilla primaria | Exult rodilla primaria | 0 | 2 | /corentec/rodilla-primaria/exult |
| Corentec | Rodilla / Rodilla de revisión | Lospa rodilla revisión | 0 | 3 | /corentec/rodilla-revision/lospa |
| Corentec | Hombro | Coralis | 0 | 3 | /corentec/hombro/coralis |
| Corentec | Columna / LOSPA IS | Tornillos Transpediculares | 0 | 5 | /corentec/columna/tornillos-transpediculares |
| Corentec | Columna / LOSPA IS | Cajas Intersomáticas TLIF | 0 | 2 | /corentec/columna/cajas-intersomaticas-tlif |
| Biotechni | Cadera / Vástago primario | Vástago primario Filler | 0 | 5 | /biotechni/cadera/vastago-filler |
| Biotechni | Cadera / Vástago revisión | Vástago revisión monoblock TTHR EASY | 0 | 6 | /biotechni/cadera/vastago-tthr-easy |
| Biotechni | Cadera / Vástago revisión | Vástago revisión modular TTHR | 0 | 4 | /biotechni/cadera/vastago-tthr-modular |
| Biotechni | Cadera / Copas | Copa Apogee Dual Movility | 0 | 4 | /biotechni/cadera/apogee |
| Caleb | Lavado pulsátil | Lavador Pulsátil E7 (Pulse Lavage, un solo uso) | 0 | 2 | /caleb/lavador-pulsatil-e7 |
| Imedicom | Extracción de copa | Sistema de extracción de copa acetabular EZX (kit EZX) | 0 | 2 | /imedicom/sistema-extraccion-copa |
| Anton-Hipp | Osteosíntesis / Sistema de osteosíntesis (titanio, mini/micro) | Placas para craneomaxilofacial | 0 | 1 | /anton-hipp/sistema-osteosintesis/placas-craneomaxilofacial |
| Anton-Hipp | Osteosíntesis / Sistema de osteosíntesis (titanio, mini/micro) | Placas para mano y pie | 0 | 2 | /anton-hipp/sistema-osteosintesis/placas-mano-pie |
| IOT | Posicionamiento de pierna / mesa quirúrgica | Mesa de abordaje Purist (Leg Positioning System) | 0 | 2 | /otros/purist |


### 3.2 Tornillos, pernos y tapones Traufix (29, deduplicados; con código y rango de longitud)
Fuente: listas "Tornillos" de cada página de placa o clavo. En el JSON están con la familia "Tornillos y accesorios" y el campo `used_with`.

- 3.5mm Tornillo de Cortical Autorroscante (Cód. 057A, Longitud 10mm-50mm) — usado en 1 producto(s)
- 3.5mm Tornillo de Cortical ALP Titanio (Cód. 106, Longitud 12mm-60mm) — usado en 7 producto(s)
- 3.5mm Tornillo de Esponjoso ALP Titanio (Cód. 107, Longitud 12mm-60mm) — usado en 5 producto(s)
- 5.0mm Tornillo de Cortical ALP Titanio (Cód. 108, Longitud 20mm-70mm) — usado en 7 producto(s)
- 5.5mm Tornillo de Esponjoso ALP Titanio (Cód. 109, Longitud 40mm-90mm) — usado en 5 producto(s)
- 3.5mm Tornillo de Cortical Titanio (Cód. 112, Longitud 12mm-60mm) — usado en 7 producto(s)
- 4.5mm Tornillo de Cortical Titanio (Cód. 126, Longitud 12mm-70mm) — usado en 6 producto(s)
- 2.5mm Tornillo de Cortical Titanio Torx (Cód. 154X, Longitud 08mm-30mm) — usado en 1 producto(s)
- 2.5mm Tornillo de cortical ALP Titanio (Cód. 155, Longitud 08mm-30mm) — usado en 2 producto(s)
- 2.5mm Tornillo de Cortical ALP Titanio Torx (Cód. 155X, Longitud 08mm-30mm) — usado en 2 producto(s)
- 7.3mm Tornillo de Esponjoso ALP Canulado Titanio (Cód.156, Longitud 45mm-110mm) — usado en 1 producto(s)
- 4.5mm Tornillo de Bloqueo para Clavo Intramedular (Cód. 166, Longitud 25mm-80mm) — usado en 3 producto(s)
- 6.5mm Tornillo Deslizante Subtrocantérico Intralock (Cód. 167, Longitud 60mm-105mm) — usado en 1 producto(s)
- Tapón de Cierre Clavo Intramedular Fémur Intralock (Cód. 168.12) — usado en 2 producto(s)
- Tapón de Cierre Clavo Intramedular Tibia Intralock (Cód. 169.11) — usado en 1 producto(s)
- 2.7mm Tornillo de Cortical ALP Titanio (Cód. 170, Longitud 06mm-60mm) — usado en 2 producto(s)
- 6.4mm Tornillo de Compresión para Clavo Retrógrado Intralock (Cód. 178, Longitud 40mm-120mm) — usado en 1 producto(s)
- 6.4mm Tornillo para Clavo Retrógrado Intralock (Cód. 179, Longitud 25mm-120mm) — usado en 1 producto(s)
- Arandela de Titanio para Tornillo de 4.5mm a 6.5mm (Cód. 182.65) — usado en 1 producto(s)
- 3.5mm Tornillo de bloqueo para clavo intramedular H-Fix Torx (Cód. 195X, Longitud 25mm-55mm) — usado en 1 producto(s)
- 5.5mm Tornillo de Esponjoso ALP Cabeza Lisa Titanio (Cód. 263, Longitud 25mm-50mm) — usado en 1 producto(s)
- Tapón de Cierre: Prolongación 0mm (Cód. 314.00), 5mm (Cód. 314.05) y 10mm (Cód. 314.10) — usado en 1 producto(s)
- 3.5mm Tornillo de bloqueo para clavo intramedular H-Fix (Cód. 421, Longitud 25mm-55mm) — usado en 1 producto(s)
- 4.5mm Perno de bloqueo para clavo intramedular H-Fix (Cód. 423, Longitud 20mm-60mm) — usado en 1 producto(s)
- 5.0mm Perno de bloqueo para clavo intramedular Talofix (Cód. 424, Longitud 25mm-110mm) — usado en 1 producto(s)
- Tapón de Cierre: Prolongación 5mm (Cód. 426.05), 10mm (Cód. 426.10) y 15mm (Cód. 426.15) — usado en 1 producto(s)
- 4.5mm Tornillo de bloqueo para clavo intramedular T-Fix (Cód. 554, Longitud 25mm-50mm) — usado en 1 producto(s)
- 5.0mm Tornillo de bloqueo para clavo intramedular T-Fix (Cód. 556, Longitud 25mm-80mm) — usado en 1 producto(s)
- 4.3mm Tornillo de bloqueo para clavo intramedular T-Fix (Cód. 661, Longitud 26mm-45mm) — usado en 1 producto(s)


### 3.3 Problemas de calidad de datos encontrados en el sitio
Están anotados en `data_quality_notes` de cada producto del JSON.
1. **Códigos con letras cirílicas homógrafas** en Sports Medicine > Anclas: `STRAUFIX-РКА-0351`, `STRAUFIX-PКA-0501` y `STRAUFIX-РКА-0651`. La "Р", la "К" y la "А" son cirílicas, y lo mismo pasa con la "О" de "USP О". Una búsqueda por código en ASCII no los encontraría. El JSON incluye `Código_normalizado_ascii`.
2. **CLAVILOCK con gancho**: el texto dice "Cuatro tamaños de longitud: de 3 a 6 orificios", pero la tabla dice "6, 8, 10 orificios" y usa los mismos Cód. 143/142 que la placa superior anterior. Además, la página `clavilock-sin-gancho` lleva el H3 "Placa ALP para clavícula **con gancho** CLAVILOCK".
3. **INTRALOCK anterógrado**: el título de su tabla dice "INTRALOCK Clavo Femoral **Retrógrado**".
4. La tarjeta **"T-FIX Tibial"** dice "para fracturas diafisarias de **fémur**", mientras que la página de detalle es de tibia.
5. **Placa bloqueada ALP 3.5**: incluye la nota de las placas "Ancha ALP 4.5mm" y tornillos de 4.5/5.0 mm, probablemente copiados de la página de 4.5.
6. Sports Medicine:
   - "STRAUFIX-TKP-0700 TENODESIS ø0.70mm" (¿7.0 mm?)
   - "STRAUFIX-PL-00010" (un dígito de más)
   - "STRAUFIX-DB-3070-SPORTS" (K-wire con un código parecido al del doble botón)
   - "Kintrope" en lugar de "Knitrope"
   - En las tablas de instrumental, la columna "Código" contiene medidas.
7. Enlaces rotos:
   - brochure Herbert/Headless en traufix.com → 404
   - `logo.corentec-blanco.png` → 404
   - `/recursos` → 404
   - el `alt` de la imagen EZX dice "Lavador pulsatil E7"
8. /nosotros dice "Desde hace más de 13 años", aunque la empresa existe desde 2008 (texto desactualizado). El menú escribe "Biotechnni" (con doble n). La oficina de Lima muestra el mismo teléfono que la de Occidente.

---

## 4. Datos corporativos para la narrativa del demo

**Quiénes son** (home, https://www.dipromedic.com/): *"En Dipromedic nos especializamos en el desarrollo, comercialización y distribución de productos para traumatología y ortopedia, ofreciendo soluciones integrales con altos estándares de calidad e innovación para el sector salud."*
- Seis oficinas comerciales: Ciudad de México (Casa Matriz – Zona Centro), Guadalajara (Occidente), León (Bajío), Monterrey, Morelia y el nuevo corporativo en Querétaro.
- Más de 80 distribuidores en el país.
- Operaciones en Perú.

**Indicadores 2025** (home): +27,000 procedimientos de trauma, +3,500 de rodilla, +1,500 de cadera y **+260,000 implantes vendidos en 2025**.

**Filosofía** (https://www.dipromedic.com/nosotros):
- *Misión*: "Desarrollamos, comercializamos y distribuimos productos ortopédicos comprometidos con un servicio de alta eficiencia, adaptabilidad y mejora continua, para superar las expectativas de nuestros clientes, colaboradores y accionistas."
- *Visión*: "Consolidarnos como empresa mexicana líder en comercialización, innovación, desarrollo de productos médicos a nivel mundial, con un equipo de profesionales y socios estratégicos de alto nivel, para garantizar el crecimiento sostenido y sustentable en el sector salud."

**Línea de tiempo** (/nosotros, sección "¡Una historia de éxito!")
| Año | Hito |
|---|---|
| 2008 | Inicio de Dipromedic |
| 2009 | Creación de marca Traufix; se incorpora Biortotec |
| 2011 | Inauguración Dipromedic Occidente (Jalisco, Michoacán, Nayarit y Colima) |
| 2012 | Fabricación Osteosíntesis (logo Fixier) |
| 2013 | Certificación ISO 9001 y Certificación ISO 13485 |
| 2014 | Inauguramos Dipromedic Bajío (Querétaro, SLP, Guanajuato) |
| 2015 | Implantes de cadera Bencox Hip System (Corentec) |
| 2016 | Rodilla Lospa Knee System (Corentec); inauguración Dipromedic Morelia |
| 2017 | "Implantes de cadera Lospa IS Spinal System" (texto literal; el logo es de columna LOSPA IS) |
| 2018 | Columna y fémur Bencox Mirabo cup & M Stem; rodilla Bencox Moc Knee System; desarrollo placa radio distal Lionter; **inicio de exportación a Perú** (Interdipro) |
| 2019 | Se integra EZX (Imedicom) |
| 2020 | Lanzamiento de la placa Lionter; "¡Estamos listos para un nuevo inicio!" (nuevo logo Traufix) |
| 2021 | Placas bloqueadas ALP de titanio; Anton Hipp; Tidis II; Fibule |
| 2022 | Se integra Telios |
| 2023 | Traslado a la sede corporativa de Querétaro |
| 2024 | Lanzamiento de Cortinium Copa Mirabo Z |
| 2025 | TITAN, ELIX y SPIDER HTO; nuevo edificio corporativo y Cafetería "Coffix"; **alianza comercial con Biotechni** |
| 2026 | Lanzamiento de Tibi-Al |

**Fabricación y certificaciones**
- /nosotros: *"nuestra planta Fixier, ya cuenta con las Certificaciones ISO 13485 … e ISO 9001"*.
- En el carrusel "Certificaciones" de casi todas las páginas aparecen los logos **CE, ISO 13485, ISO 9001, COFEPRIS, ESR, FDA y GTO** (`/assets/img/certifications/*.png`). El sitio no dice qué producto ni qué entidad cubre cada certificación.
- El catálogo Traufix en PDF menciona "ISO 9001 e ISO 13485, FDA y marcaje CE".
- Planta Fixier, según https://traufix.com/certificaciones/: Carretera Dr. Mora–San Miguel de Allende km 3.4, Comunidad de San Rafael, 37967 Dr. Mora, Gto. Oficina Traufix USA: San Antonio, Texas. Contacto `internationalsales@fixier.com.mx`.
- **Ninguna de estas certificaciones se verificó contra registros oficiales.**

**Oficinas** (https://www.dipromedic.com/contacto)
| Oficina | Dirección (como aparece) | Contacto |
|---|---|---|
| Dipromedic CDMX | Nápoles, Benito Juárez, C.P. 03900, CDMX | gerencia.cirugiadirecta@dipromedic.com · (55) 9000 4888 / 89 / 90 / 91 |
| Corporativo Dipromedic Querétaro | Colinas del Cimatario, 76090 Santiago de Querétaro, Qro. (el mapa comentado indica "Av Colinas del Cimatario 448") | 442 244 3721 y 55 6817 7634 |
| Dipromedic Bajío | Col. Jardines del Moral, León, Gto. | ventas.bajio@dipromedic.com · (477) 717 11 73 |
| Dipromedic Occidente | Jardines de Los Arcos, 44500 Guadalajara, Jal. | ventas.occidente@dipromedic.com · (33) 3640-3446 ext. 102 |
| Dipromedic Morelia | Fray Antonio de San Miguel Iglesias, C.P. 58277 Morelia, Mich. | (correo nominal en la página) |
| Dipromedic Monterrey Norfix | Mitras Centro, C.P. 64460 Monterrey, N.L. | norfix@dipromedic.com |
| Dipromedic Lima Perú | Urb Aurora Miraflores, Lima, Perú | ventas.interdipro.peru@dipromedic.com |

Más datos de contacto:
- **Línea Dipromedic**: 55 9962 9022, también por WhatsApp.
- Domicilio fiscal en el aviso de privacidad: **DIPROMEDIC S.A. DE C.V., Galveston #53, Col. Nápoles, C.P. 03810**.
- Datos personales y marketing: webmaster@dipromedic.com.
- Talento: talento@dipromedic.com.

**Distribuidores autorizados** (/contacto#distribuidores-autorizados, 12 en la lista):
- Ortfix del Noroeste (Tijuana, BC)
- Orthomed de la Península (Yucatán y Campeche)
- AO Medical (Chihuahua)
- Orthoage (Hermosillo, Son.)
- Sax Medical (Tlaxcala, Puebla)
- Medical Orthosis (Guerrero)
- Implanmed (Oaxaca)
- Comercializadora Ortopédica del Norte
- Comercializadora Ortopédica de Saltillo
- Comercializadora Ortopédica de Durango
- Alenio Álvarez Rengifo (Guadalajara, Jal.)
- Norfix (Monterrey, N.L.)

Los teléfonos y correos (algunos personales) están en la página; aquí no se copiaron.

**Prueba social**:
- Home: 3 médicos aliados ("Expertos Que Impulsan Nuestra Innovación") con perfil en Doctoralia.
- Home y /nosotros: 6 testimonios de cirujanos con citas breves sobre la asistencia técnica y los implantes ("excelente", "10 de 10").
- Para el demo conviene usar personas ficticias en lugar de copiar nombres o cédulas reales.

**Eventos** (https://www.dipromedic.com/eventos):
- Próximo evento: banner "SMOP 2026".
- Tabla de 2026: *SMCHC: Encuentro de la Sociedad Mexicana de Cirujanos de Hombro y Codo*, 19 al 21 de noviembre, Hotel Camino Real, Monterrey, N.L.
- Logos de sociedades: Cirujanos de Hombro y Codo, Pelvis y Acetábulo, AMECRA, FEMECOT y SMCC.
- Banners FEMECOT 2026, SMOP 2026 y SMCHC 2026.

**Vacantes** (https://www.dipromedic.com/atraccion-de-talento): Auxiliar de almacén (Querétaro) y Técnico Instrumentista (León). Ambas sirven como narrativa de operación: almacén, instrumentistas en quirófano y servicio integral.

---

## 5. Aspectos legales y robots
- **https://www.dipromedic.com/robots.txt → HTTP 404**: devuelve la página HTML "404 - Not Found", con `<meta name="robots" content="noindex">`. No hay directivas que restrinjan el rastreo. `/sitemap.xml`, `/sitemap_index.xml` y `/wp-json/` también dan 404.
- **https://traufix.com/robots.txt** (Yoast): `User-agent: * / Disallow:` (todo permitido) y `Sitemap: https://traufix.com/sitemap_index.xml`. Su mod_security bloquea el UA corto `Mozilla/5.0` (HTTP 406), pero acepta un UA de navegador completo.
- **https://www.dipromedic.com/propiedad-intelectual**:
  - *"El contenido del portal incluyendo los materiales, documentos, bases de datos, diseños, marcas, logotipos, fotografías, gráficos, etc., se encuentra protegido … siendo propiedad exclusiva de DIPROMEDIC S.A. DE C.V. **Se puede hacer uso del contenido y/o distribuir la información de este sitio web, siempre y cuando se mencione como propietario a DIPROMEDIC S.A. DE C.V. y el enlace al sitio web: www.dipromedic.com.**"*
  - Los logotipos de Traufix, Corentec, Biotechni, Caleb, Imedicom, Anton-Hipp e Innovative Orthopedic Technologies *"son propiedad de sus respectivos dueños"*.
  - Las fotos de fondo e iconos son de stock (Envato/Magnific) con licencia.
  - **Implicación para el demo**: hay que acreditar "Fuente: DIPROMEDIC S.A. DE C.V. – www.dipromedic.com". Las marcas de terceros (Corentec, etc.) y las fotos de stock no deben reutilizarse fuera de un demo privado sin autorización.
- **https://www.dipromedic.com/aviso-de-privacidad**: aviso LFPDPPP estándar y uso de cookies (GA). No menciona el scraping.
- Cortesía aplicada:
  - ≈ 340 peticiones en total (incluye 2 HEAD por PDF y 60 descargas de PDF), secuenciales y con pausas
  - no se usó el buscador `/productos?q=`
  - no se enviaron formularios
- Problema técnico: un PDF de traufix.com llegó truncado por HTTP/2 y se volvió a descargar por HTTP/1.1. Los 60 PDFs se validaron con cabecera `%PDF-` y trailer `%%EOF`, y sus tamaños coinciden con `Content-Length`.

---

## 6. PDFs enlazados (76 enlaces únicos; 60 descargados ≤ 15 MB; 15 > 15 MB solo listados; 1 roto)
Las rutas locales son relativas a `docs/research/dipromedic/`. Los dos enlaces a `Placas-ALP-Rectas-3.5-y-4.5_TQ042.pdf` (2024/08 y 2024/12) apuntan a archivos idénticos (mismo SHA-256), así que se guardó una sola copia.

| Título (enlace en el sitio) | Host | Tamaño | Estado | Copia local |
|---|---|---|---|---|
| [Brochure – Lavador Pulsátil E7 (Pulse Lavage, un solo uso)](https://www.dipromedic.com/assets/docs/brochure/caleb/E-7-brochure.pdf) | dipromedic.com | 0.5 MB | 200 | pdfs/dipromedic/brochure/caleb/E-7-brochure.pdf |
| [Brochure – Vástago M-Stem](https://www.dipromedic.com/assets/docs/brochure/corentec/Bencox-M-Stem.pdf) | dipromedic.com | 6.6 MB | 200 | pdfs/dipromedic/brochure/corentec/Bencox-M-Stem.pdf |
| [Brochure – Copa Bipolar](https://www.dipromedic.com/assets/docs/brochure/corentec/BencoxBipolarCup.pdf) | dipromedic.com | 1.1 MB | 200 | pdfs/dipromedic/brochure/corentec/BencoxBipolarCup.pdf |
| [Brochure cementado – Vástago cementado y no cementado](https://www.dipromedic.com/assets/docs/brochure/corentec/BencoxIDCementedStem.pdf) | dipromedic.com | 0.6 MB | 200 | pdfs/dipromedic/brochure/corentec/BencoxIDCementedStem.pdf |
| [Brochure no cementado – Vástago cementado y no cementado](https://www.dipromedic.com/assets/docs/brochure/corentec/BencoxIDStem.pdf) | dipromedic.com | 0.6 MB | 200 | pdfs/dipromedic/brochure/corentec/BencoxIDStem.pdf |
| [Brochure – Mirabo Multi-Hole](https://www.dipromedic.com/assets/docs/brochure/corentec/BencoxMiraboMultihole.pdf) | dipromedic.com | 5.4 MB | 200 | pdfs/dipromedic/brochure/corentec/BencoxMiraboMultihole.pdf |
| [Brochure – Exult rodilla primaria](https://www.dipromedic.com/assets/docs/brochure/corentec/Exult-Overview.pdf) | dipromedic.com | 1.6 MB | 200 | pdfs/dipromedic/brochure/corentec/Exult-Overview.pdf |
| [Brochure – Lospa rodilla revisión](https://www.dipromedic.com/assets/docs/brochure/corentec/Product-Overview-Lospa-Modular-Knee-System.pdf) | dipromedic.com | 1.2 MB | 200 | pdfs/dipromedic/brochure/corentec/Product-Overview-Lospa-Modular-Knee-System.pdf |
| [Brochure – Lospa rodilla primaria](https://www.dipromedic.com/assets/docs/brochure/corentec/Product-Overview-Lospa-knee-system.pdf) | dipromedic.com | 1.1 MB | 200 | pdfs/dipromedic/brochure/corentec/Product-Overview-Lospa-knee-system.pdf |
| [Brochure – Coralis](https://www.dipromedic.com/assets/docs/brochure/corentec/coralis-brochure.pdf) | dipromedic.com | 19.7 MB | 200 | no (> 15 MB) |
| [Brochure – Mirabo Z](https://www.dipromedic.com/assets/docs/brochure/corentec/overview-mirabo-z-cup.pdf) | dipromedic.com | 1.8 MB | 200 | pdfs/dipromedic/brochure/corentec/overview-mirabo-z-cup.pdf |
| [Brochure – Mesa de abordaje Purist (Leg Positioning System)](https://www.dipromedic.com/assets/docs/brochure/iot/Purist-Overview.pdf) | dipromedic.com | 0.3 MB | 200 | pdfs/dipromedic/brochure/iot/Purist-Overview.pdf |
| [Ver catálogo de anclas – Ancla PEEK con aguja; Ver catálogo de anclas – Ancla Trustlock; Ver catálogo de an...](https://www.dipromedic.com/assets/docs/brochure/sports_medicine/catalogo-anclas.pdf) | dipromedic.com | 45.1 MB | 200 | no (> 15 MB) |
| [Ver catálogo de instrumentales – Alambre de Kirschner; Ver catálogo de instrumentales – Brocas; Ver catálog...](https://www.dipromedic.com/assets/docs/brochure/sports_medicine/catalogo-instrumentales.pdf) | dipromedic.com | 43.7 MB | 200 | no (> 15 MB) |
| [Ver catálogo de misceláneos – Aguja de tipo escorpión para pasador de sutura; Ver catálogo de misceláneos –...](https://www.dipromedic.com/assets/docs/brochure/sports_medicine/catalogo-miscelaneos.pdf) | dipromedic.com | 60.1 MB | 200 | no (> 15 MB) |
| [Ver catálogo del sistema de fijación cortical – Botón Knitrope; Ver catálogo del sistema de fijación cortic...](https://www.dipromedic.com/assets/docs/brochure/sports_medicine/catalogo-sistema-fijacion-cortical.pdf) | dipromedic.com | 47.3 MB | 200 | no (> 15 MB) |
| [catalogo-sports-medicine.pdf](https://www.dipromedic.com/assets/docs/brochure/sports_medicine/catalogo-sports-medicine.pdf) | dipromedic.com | 80.2 MB | 200 | no (> 15 MB) |
| [Ver catálogo de tornillos interferenciales – Tornillo interferencial Biocompuesto; Ver catálogo de tornillo...](https://www.dipromedic.com/assets/docs/brochure/sports_medicine/catalogo-tornillos-interferenciales.pdf) | dipromedic.com | 43.0 MB | 200 | no (> 15 MB) |
| [Ver catálogo completo (página de categoría) – CLAVILOCK Placa ALP para clavícula superior anterior (con y s...](https://www.dipromedic.com/assets/docs/catalogos/traufix/Catalogo-Traufix-ES.pdf) | dipromedic.com | 7.2 MB | 200 | pdfs/dipromedic/catalogos/traufix/Catalogo-Traufix-ES.pdf |
| [Técnica Quirúrgica – Placas para mano y pie](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/anton-hipp/hand-implantate.pdf) | dipromedic.com | 4.7 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/anton-hipp/hand-implantate.pdf |
| [Técnica Quirúrgica – Placas para craneomaxilofacial](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/anton-hipp/osteo-synthese.pdf) | dipromedic.com | 4.4 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/anton-hipp/osteo-synthese.pdf |
| [Técnica Qurúrgica – Copa Apogee Dual Movility](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/biotechni/apogee.pdf) | dipromedic.com | 1.1 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/biotechni/apogee.pdf |
| [Técnica Qurúrgica – Vástago primario Filler](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/biotechni/filler.pdf) | dipromedic.com | 2.9 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/biotechni/filler.pdf |
| [Técnica Qurúrgica – Vástago revisión monoblock TTHR EASY](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/biotechni/tthr-easy.pdf) | dipromedic.com | 2.2 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/biotechni/tthr-easy.pdf |
| [Técnica Qurúrgica – Vástago revisión modular TTHR](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/biotechni/tthr-modular.pdf) | dipromedic.com | 0.7 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/biotechni/tthr-modular.pdf |
| [Técnica Qurúrgica – Exult rodilla primaria](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/corentec/Exult_Knee_System_Surgical_Technique_rev_1.pdf) | dipromedic.com | 5.6 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/corentec/Exult_Knee_System_Surgical_Technique_rev_1.pdf |
| [Técnica Qurúrgica – Lospa rodilla primaria](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/corentec/Surgical-Manual-for-Lospa-TKR-System.pdf) | dipromedic.com | 5.4 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/corentec/Surgical-Manual-for-Lospa-TKR-System.pdf |
| [Técnica Quirúrgica – Vástago M-Stem; Técnica Quirúrgica – Vástago cementado y no cementado; Técnica Qurúrgi...](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/corentec/Surgical_Technique_Bencox_Hip_System_compressed.pdf) | dipromedic.com | 1.0 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/corentec/Surgical_Technique_Bencox_Hip_System_compressed.pdf |
| [Técnica Qurúrgica – Lospa rodilla revisión](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/corentec/Tecnica-Quirurgica-Rodilla-de-Revision.pdf) | dipromedic.com | 3.8 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/corentec/Tecnica-Quirurgica-Rodilla-de-Revision.pdf |
| [Técnica Qurúrgica – Tornillos Transpediculares](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/corentec/TecnicaLospaISSpinalSystem.pdf) | dipromedic.com | 1.3 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/corentec/TecnicaLospaISSpinalSystem.pdf |
| [Técnica Qurúrgica – Coralis](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/corentec/Tecnica_Quirurgica_CORALIS_SHOULDER_SYSTEM.pdf) | dipromedic.com | 3.4 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/corentec/Tecnica_Quirurgica_CORALIS_SHOULDER_SYSTEM.pdf |
| [Técnica Qurúrgica – Cajas Intersomáticas TLIF](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/corentec/tecnicaSistemadeCajaTLIF.pdf) | dipromedic.com | 0.6 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/corentec/tecnicaSistemadeCajaTLIF.pdf |
| [Checklist – Mesa de abordaje Purist (Leg Positioning System)](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/iot/Purist-Checklist.pdf) | dipromedic.com | 0.1 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/iot/Purist-Checklist.pdf |
| [Técnica Quirúrgica – Mesa de abordaje Purist (Leg Positioning System)](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/iot/Purist-Technique.pdf) | dipromedic.com | 0.9 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/iot/Purist-Technique.pdf |
| [Técnica Quirúrgica – Placa ALP para clavícula con gancho CLAVILOCK](https://www.dipromedic.com/assets/docs/tecnicas-quirurgicas/traufix/extremidad-superior/clavilock-con-gancho.pdf) | dipromedic.com | 0.4 MB | 200 | pdfs/dipromedic/tecnicas-quirurgicas/traufix/clavilock-con-gancho.pdf |
| [Técnica Quirúrgica – CLAVILOCK Placa ALP para clavícula superior anterior (con y sin extensión lateral)](https://traufix.com/wp-content/uploads/2024/08/CLAVILOCK-Clavicula-Superior_TQ16.pdf) | traufix.com | 0.5 MB | 200 | pdfs/traufix.com/CLAVILOCK-Clavicula-Superior_TQ16.pdf |
| [Técnica Quirúrgica – LIONTER Placa bloqueada Radio Distal Volar](https://traufix.com/wp-content/uploads/2024/08/LIONTER-Placa-ALP-para-Radio-Distal_QT.018.pdf) | traufix.com | 25.2 MB | 200 | no (> 15 MB) |
| [Brochure – LIONTER Placa bloqueada Radio Distal Volar](https://traufix.com/wp-content/uploads/2024/08/Placa-ALP-para-Radio-Distal-Lionter.pdf) | traufix.com | 39.6 MB | 200 | no (> 15 MB) |
| [Técnica Quirúrgica – Placa bloqueada ALP 3.5](https://traufix.com/wp-content/uploads/2024/08/Placas-ALP-Rectas-3.5-y-4.5_TQ042.pdf) | traufix.com | 2.6 MB | 200 | pdfs/traufix.com/Placas-ALP-Rectas-3.5-y-4.5_TQ042.pdf |
| [Técnica Quirúrgica – Placas de sostén en “T” y “L” bloqueadas ALP Titanio](https://traufix.com/wp-content/uploads/2024/08/Placas-en-T-y-L-4.5_QT043.pdf) | traufix.com | 1.7 MB | 200 | pdfs/traufix.com/Placas-en-T-y-L-4.5_QT043.pdf |
| [Brochure – HEADLESS THS Tornillo de compresión canulado; Brochure – HERBERT HFS Tornillo de compresión canu...](https://traufix.com/wp-content/uploads/2024/08/Sistema-de-tornillos-de-compresion-canulados-Herbert-y-Headless.pdf) | traufix.com | - MB | 404 | no (404) |
| [Brochure – INTRALOCK Clavo Intramedular para Fémur Retrógrado](https://traufix.com/wp-content/uploads/2024/09/Clavo-Intramedular-para-Femur-Intralock-1.pdf) | traufix.com | 26.6 MB | 200 | no (> 15 MB) |
| [Brochure – INTRALOCK Clavo Intramedular para Fémur (Anterógrado Diafisiario y Subtrocantérico)](https://traufix.com/wp-content/uploads/2024/09/Clavo-Intramedular-para-Femur-Intralock.pdf) | traufix.com | 26.6 MB | 200 | no (> 15 MB) |
| [Brochure – INTRALOCK Clavo Intramedular para Tibia](https://traufix.com/wp-content/uploads/2024/09/Clavo-Intramedular-para-Tibia-Intralock.pdf) | traufix.com | 37.4 MB | 200 | no (> 15 MB) |
| [Técnica Quirúrgica – INTRALOCK Clavo Intramedular para Fémur (Anterógrado Diafisiario y Subtrocantérico)](https://traufix.com/wp-content/uploads/2024/09/INTRALOCK-Clavo-Intramedular-para-Femur-Anterogrado_QT015.pdf) | traufix.com | 10.6 MB | 200 | pdfs/traufix.com/INTRALOCK-Clavo-Intramedular-para-Femur-Anterogrado_QT015.pdf |
| [Técnica Quirúrgica – INTRALOCK Clavo Intramedular para Fémur Retrógrado](https://traufix.com/wp-content/uploads/2024/09/INTRALOCK-Clavo-Intramedular-para-Femur-Retrogrado_QT021.pdf) | traufix.com | 10.8 MB | 200 | pdfs/traufix.com/INTRALOCK-Clavo-Intramedular-para-Femur-Retrogrado_QT021.pdf |
| [Técnica Quirúrgica – INTRALOCK Clavo Intramedular para Tibia](https://traufix.com/wp-content/uploads/2024/09/INTRALOCK-Clavo-Intramedular-para-Tibia_QT022.pdf) | traufix.com | 5.2 MB | 200 | pdfs/traufix.com/INTRALOCK-Clavo-Intramedular-para-Tibia_QT022.pdf |
| [Técnica Quirúrgica – OPTIMUS Placa bloqueada ALP para Tibia Proximal](https://traufix.com/wp-content/uploads/2024/09/OPTIMUS-Placa-ALP-para-Tibia-Proximal_TQ_020.pdf) | traufix.com | 4.2 MB | 200 | pdfs/traufix.com/OPTIMUS-Placa-ALP-para-Tibia-Proximal_TQ_020.pdf |
| [Brochure – SPIDER HTO (High Tibial Osteotomy) Placa para Osteotomía Valguizante Tibial Proximal con cuña de...](https://traufix.com/wp-content/uploads/2024/09/Spider-HTO-Osteotomia-Tibial-Valguizante.pdf) | traufix.com | 24.7 MB | 200 | no (> 15 MB) |
| [Técnica TIDIS II – TIDIS II Placa bloqueada ALP para Tibia Distal Medial](https://traufix.com/wp-content/uploads/2024/09/TIDIS-II-Placa-ALP-para-Tibia-Distal-Medial_TQ_023.pdf) | traufix.com | 10.1 MB | 200 | pdfs/traufix.com/TIDIS-II-Placa-ALP-para-Tibia-Distal-Medial_TQ_023.pdf |
| [Técnica TIDIS – TIDIS Placa bloqueada ALP para Tibia Distal Medial](https://traufix.com/wp-content/uploads/2024/09/Tibia-Distal-Tidis-I-y-Tidis-III_TQ011.pdf) | traufix.com | 8.5 MB | 200 | pdfs/traufix.com/Tibia-Distal-Tidis-I-y-Tidis-III_TQ011.pdf |
| [Técnica Quirúrgica – FIBULE Placa bloqueada ALP para Peroné Distal](https://traufix.com/wp-content/uploads/2024/12/FIBULE-Placa-ALP-para-Perone-Distal_TQ041.pdf) | traufix.com | 1.5 MB | 200 | pdfs/traufix.com/FIBULE-Placa-ALP-para-Perone-Distal_TQ041.pdf |
| [Técnica Quirúrgica – Placa bloqueada Angosta y Ancha ALP 4.5](https://traufix.com/wp-content/uploads/2024/12/Placas-ALP-Rectas-3.5-y-4.5_TQ042.pdf) | traufix.com | 2.6 MB | 200 | pdfs/traufix.com/Placas-ALP-Rectas-3.5-y-4.5_TQ042.pdf |
| [Técnica Quirúrgica – ELIX Clavo Intramedular Antirrotacional para Fémur Proximal](https://traufix.com/wp-content/uploads/2025/01/ELIX_Clavo-Femoral-Antirrotacional_AT.pdf) | traufix.com | 2.7 MB | 200 | pdfs/traufix.com/ELIX_Clavo-Femoral-Antirrotacional_AT.pdf |
| [Técnica Quirúrgica Headless – HEADLESS THS Tornillo de compresión canulado](https://traufix.com/wp-content/uploads/2025/01/HEADLESS-THS-Tornillo-de-Compresion-Canulado_TQ040_AT.pdf) | traufix.com | 4.5 MB | 200 | pdfs/traufix.com/HEADLESS-THS-Tornillo-de-Compresion-Canulado_TQ040_AT.pdf |
| [Técnica Quirúrgica Herbert – HERBERT HFS Tornillo de compresión canulado](https://traufix.com/wp-content/uploads/2025/01/HERBERT-HFS-Tornillo-de-Compresion-Canulado_TQ039_AT.pdf) | traufix.com | 46.2 MB | 200 | no (> 15 MB) |
| [Técnica Quirúrgica – SPIDER HTO (High Tibial Osteotomy) Placa para Osteotomía Valguizante Tibial Proximal c...](https://traufix.com/wp-content/uploads/2025/01/SPIDER-HTO-Osteotomia-Tibial-Valguizante_TQ_045_AT.pdf) | traufix.com | 10.9 MB | 200 | pdfs/traufix.com/SPIDER-HTO-Osteotomia-Tibial-Valguizante_TQ_045_AT.pdf |
| [Técnica Quirúrgica – TLP Placa bloqueada ALP para Fémur Proximal](https://traufix.com/wp-content/uploads/2025/01/TLP-Placa-ALP-para-Femur-Proximal_TQ019_AT.pdf) | traufix.com | 8.0 MB | 200 | pdfs/traufix.com/TLP-Placa-ALP-para-Femur-Proximal_TQ019_AT.pdf |
| [Brochure – H-Fix Clavo Intramedular para Húmero](https://traufix.com/wp-content/uploads/2025/06/H-FIX-Clavo-para-Humero_ES.pdf) | traufix.com | 25.1 MB | 200 | no (> 15 MB) |
| [Técnica Quirúrgica – TALOFIX Clavo Intramedular para Artrodesis de Tobillo](https://traufix.com/wp-content/uploads/2025/07/Clavo-Intramedular-para-Artrodesis-de-tobillo-Talofix-TQ-51.pdf) | traufix.com | 4.2 MB | 200 | pdfs/traufix.com/Clavo-Intramedular-para-Artrodesis-de-tobillo-Talofix-TQ-51.pdf |
| [Brochure – TALOFIX Clavo Intramedular para Artrodesis de Tobillo](https://traufix.com/wp-content/uploads/2025/07/Talofix_Clavo-para-Artrodesis-de-Tobillo_cm.pdf%20) | traufix.com | 0.6 MB | 200 | pdfs/traufix.com/Talofix_Clavo-para-Artrodesis-de-Tobillo_cm.pdf |
| [Técnica Quirúrgica – TARFIX Tornillo subtalar canulado para corrección del pie plano valgo](https://traufix.com/wp-content/uploads/2025/07/Tarfix-Tornillo-Subtalar-Canulado-TQ-050.pdf) | traufix.com | 2.3 MB | 200 | pdfs/traufix.com/Tarfix-Tornillo-Subtalar-Canulado-TQ-050.pdf |
| [Técnica Quirúrgica – CONDYFIX Placa bloqueada ALP para Fémur Distal](https://traufix.com/wp-content/uploads/2025/10/CONDYFIX-Placa-ALP-para-Femur-Distal_TQ013_2.pdf) | traufix.com | 3.3 MB | 200 | pdfs/traufix.com/CONDYFIX-Placa-ALP-para-Femur-Distal_TQ013_2.pdf |
| [Brochure – FIBULE Placa bloqueada ALP para Peroné Distal; Brochure – TIDIS II Placa bloqueada ALP para Tibi...](https://traufix.com/wp-content/uploads/2025/10/Placa-ALP-FIBULE-y-TIDIS-II_cp.pdf) | traufix.com | 0.5 MB | 200 | pdfs/traufix.com/Placa-ALP-FIBULE-y-TIDIS-II_cp.pdf |
| [Brochure – TELIOS Placa bloqueada para Húmero Distal Lateral y Medial; Brochure – TITAN Placa bloqueada ALP...](https://traufix.com/wp-content/uploads/2025/12/Placa-ALP-Titan-y-Telios_cp.pdf) | traufix.com | 1.1 MB | 200 | pdfs/traufix.com/Placa-ALP-Titan-y-Telios_cp.pdf |
| [Técnica Quirúrgica – TELIOS Placa bloqueada para Húmero Distal Lateral y Medial](https://traufix.com/wp-content/uploads/2025/12/TELIOS-Placa-ALP-Humero-Distal-LateralyMedial-_TQ-017.pdf) | traufix.com | 4.6 MB | 200 | pdfs/traufix.com/TELIOS-Placa-ALP-Humero-Distal-LateralyMedial-_TQ-017.pdf |
| [Brochure – TARFIX Tornillo subtalar canulado para corrección del pie plano valgo](https://traufix.com/wp-content/uploads/2025/12/Tarfix_Tornillo-Subtalar-Canulado_ES.pdf) | traufix.com | 7.2 MB | 200 | pdfs/traufix.com/Tarfix_Tornillo-Subtalar-Canulado_ES.pdf |
| [Brochure – ELIX Clavo Intramedular Antirrotacional para Fémur Proximal](https://traufix.com/wp-content/uploads/2026/01/ELIX-Clavo-Femoral-Antirrotacional.pdf) | traufix.com | 1.6 MB | 200 | pdfs/traufix.com/ELIX-Clavo-Femoral-Antirrotacional.pdf |
| [Brochure – Tibi-AL Placa Bloqueada ALP para Tibia Distal Anterolateral](https://traufix.com/wp-content/uploads/2026/01/Tibi-AL-Tibia-Distal-Anterolateral-ES_c.pdf) | traufix.com | 1.0 MB | 200 | pdfs/traufix.com/Tibi-AL-Tibia-Distal-Anterolateral-ES_c.pdf |
| [Técnica Quirúrgica – Placa de Reconstrucción Recta y Curva 3.5](https://traufix.com/wp-content/uploads/2026/02/Placas-reconstruccion-recta-y-arqueada-TQ-054.pdf) | traufix.com | 4.9 MB | 200 | pdfs/traufix.com/Placas-reconstruccion-recta-y-arqueada-TQ-054.pdf |
| [Técnica Quirúrgica – TITAN Placa bloqueada ALP para Húmero Proximal](https://traufix.com/wp-content/uploads/2026/02/TITAN-Humero-Proximal-TQ-048.pdf) | traufix.com | 5.4 MB | 200 | pdfs/traufix.com/TITAN-Humero-Proximal-TQ-048.pdf |
| [Técnica Quirúrgica – Tibi-AL Placa Bloqueada ALP para Tibia Distal Anterolateral](https://traufix.com/wp-content/uploads/2026/02/Tibi-AL-Anterolateral-para-Tibia-Distal-TQ-053.pdf) | traufix.com | 3.0 MB | 200 | pdfs/traufix.com/Tibi-AL-Anterolateral-para-Tibia-Distal-TQ-053.pdf |
| [Técnica Quirúrgica – T-Fix Clavo Intramedular para Tibia Supra & Infrapatelar](https://traufix.com/wp-content/uploads/2026/06/T-FIX-Clavo-Intramedular-para-Tibia-Supra-Infrapatelar.pdf) | traufix.com | 4.7 MB | 200 | pdfs/traufix.com/T-FIX-Clavo-Intramedular-para-Tibia-Supra-Infrapatelar.pdf |
| [Brochure – T-Fix Clavo Intramedular para Tibia Supra & Infrapatelar](https://traufix.com/wp-content/uploads/2026/06/T-Fix_Clavo-Intramedular-para-Tibia_ES_s.pdf) | traufix.com | 1.1 MB | 200 | pdfs/traufix.com/T-Fix_Clavo-Intramedular-para-Tibia_ES_s.pdf |
| [Técnica Quirúrgica – H-Fix Clavo Intramedular para Húmero](https://traufix.com/wp-content/uploads/2026/06/TQ-049-Clavo-para-Humero-Proximal-H-Fix.pdf) | traufix.com | 14.2 MB | 200 | pdfs/traufix.com/TQ-049-Clavo-para-Humero-Proximal-H-Fix.pdf |
| [Técnica Quirúrgica – INTRALOCK Clavo Intramedular para Húmero](https://traufix.com/wp-content/uploads/2024/09/INTRALOCK-Clavo-Intramedular-para-Humero_QT024.pdf) | traufix.com | 12.8 MB | 200 | pdfs/traufix.com/INTRALOCK-Clavo-Intramedular-para-Humero_QT024.pdf |
