# ADR-003 · Identidad visual Dipromedic

Estado: aceptado · 2026-10-28

## Contexto

E1 se construyó como white label («Dipromedic · Demo»), con un acento verde petróleo y Public Sans. Para la reunión con
Gobierno Corporativo, Dirección Comercial y TI de Dipromedic, la demo debe verse como una aplicación de la empresa.
Emmanuel decidió el 2026-10-28 usar la identidad real de Dipromedic, con la etiqueta «Demo» siempre visible.

La investigación del sitio está en `docs/research/dipromedic-web.md` §1. El sitio se consultó el 2026-10-28.

## Decisión

### Fuente de colores, tipografía y logotipos

- Los colores vienen del bloque `:root` de https://www.dipromedic.com/style.css. Los comentarios de ese archivo los
  atribuyen al logo y a la mascota Fixi.

  | Token Tailwind | Hex | Origen en el sitio | Uso en la demo |
  |---|---|---|---|
  | `dpm-blue` (= `dpm-blue-600`) | `#0F75BC` | `--color-blue-dipromedic` | Acción principal, elemento activo, enlaces |
  | `dpm-green` | `#47AD36` | `--color-green-fixi` | Barra del menú activo, viñetas, subrayado de marca |
  | `bg-dpm-accent` | `#63F24B → #47AD36` (90°) | `.btn-gradient` | `.btn-accent`, píldora «Demo», `.brand-rule` |
  | `dpm-navy` | `#001D4C` | `--color-secondary` (fondo del pie) | Barra superior, panel del login |
  | `dpm-navy-300` | `#96AAC1` | Texto del pie | Texto secundario sobre navy |
  | `dpm-traufix` | `#004991` | `--color-blue-traufix` | Reservado para la línea Traufix |

  La escala `dpm-blue-50…950` se derivó del azul de marca, que ocupa el paso 600. Los demás pasos no existen en el
  sitio.
- Tipografía: Inter 400/500/600/700, la misma del sitio, cargada desde Google Fonts. Respaldo: `system-ui`.
- Logotipos: archivos originales de https://www.dipromedic.com/assets/img/branding/, sin redibujar ni recolorear,
  copiados a `frontend/public/brand/`.
  - `logo-dipromedic-blanco.svg` (vectorial) para fondos oscuros. Se usa en la barra y en el login.
  - `logo-dipromedic-color.png` (166×69, raster) para fondos claros. No se muestra a más de 69 px de alto. El sitio
    no publica una versión vectorial a color.
  - `favicon.png` es el favicon del sitio.
  - `fixi-color.png` es la mascota. Aparece solo como acento decorativo en el login (`alt=""`).
- El componente `<Logo variant="color" | "white" />` (`frontend/src/components/brand/Logo.tsx`) es la única forma de
  mostrar el logotipo.

### Regla de contraste (WCAG AA)

- Nunca va texto blanco pequeño sobre el verde `#47AD36` (2.88:1). El texto sobre verde o sobre el degradado va en
  navy: 5.70:1 en el extremo oscuro y 11.20:1 en el claro.
- El botón primario es azul `#0F75BC` con texto blanco (4.89:1). El verde no se usa como color de acción principal.
- Sobre el tinte claro `dpm-blue-50` el azul de marca baja a 4.48:1, así que el texto va en `dpm-blue-700` (6.16:1).
  Los enlaces usan `dpm-blue-700` (6.73:1 sobre blanco).
- Sobre navy, el texto blanco da 16.40:1, `dpm-navy-200` da 10.38:1 y `dpm-navy-300` da 6.89:1. El contorno de
  foco pasa a blanco dentro de `.surface-dark`.
- El rayado ámbar `.hatch-synthetic` sigue siendo la marca exclusiva de lo SYNTHETIC. Ningún color de marca lo
  sustituye ni se parece a él.

### Marcas de terceros

- Los logotipos de marcas representadas (Corentec, Biotechni, Caleb, Imedicom, Anton-Hipp, Innovative Orthopedic
  Technologies, Bencox y otras) pertenecen a sus dueños. La demo los nombra **solo como texto** y no copia sus
  archivos a `frontend/public/brand/`.
- Traufix y Fixier son líneas propias de Dipromedic. La línea de tiempo de /nosotros registra la creación de la marca
  Traufix en 2009 y asocia el logo Fixier a «Fabricación Osteosíntesis» en 2012. Aun así, el aviso de propiedad
  intelectual menciona a Traufix junto a las marcas de terceros. Esta entrega no muestra esos logotipos. Si se
  agregan, van solo en el contexto de su línea.
- Los logos de certificaciones del sitio (CE, ISO, COFEPRIS, FDA) no se verificaron y la demo no los muestra.

### Crédito por el aviso de propiedad intelectual

https://www.dipromedic.com/propiedad-intelectual permite usar el contenido del sitio si se menciona como propietario a
DIPROMEDIC S.A. DE C.V. y se enlaza www.dipromedic.com. Por eso:

- El pie de cada página autenticada y del login muestra, literal:
  `Contenido de catálogo: DIPROMEDIC S.A. DE C.V. · www.dipromedic.com · consultado el {checked_on}`.
  Lo pinta `<Footer checkedOn="2026-10-28" />` (`frontend/src/components/brand/Footer.tsx`).
- Cada ficha importada repite el mismo crédito con su propia fecha de consulta, mediante
  `<CatalogCredit checkedOn={…} />`, exportado del mismo archivo.

## Consecuencias

- Las páginas de E1 heredan la identidad sin cambios: `petrol-*` es un alias de `dpm-blue-*`. El código nuevo usa
  `dpm-*`. El alias se retira cuando ninguna página lo use.
- Los botones pasan a pastilla y peso 600, como los del sitio, y conservan sus nombres (`.btn-primary`,
  `.btn-secondary`…). Se agregan `.btn-accent`, `.link`, `.brand-rule` y `.surface-dark`.
- Inter depende de Google Fonts. Sin red, el navegador usa la fuente del sistema: la demo funciona igual, pero se ve
  distinta.
- Si Dipromedic entrega un logotipo vectorial a color o pide otra versión de la marca, solo cambian
  `frontend/public/brand/` y `Logo.tsx`.
