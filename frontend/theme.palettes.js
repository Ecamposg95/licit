// Tema claro/oscuro (patrón de Atlas One: clase `dark` en <html> y colores en variables CSS).
//
// Las páginas usan clases de Tailwind con la paleta de siempre (`text-slate-600`, `bg-red-50`, `text-dpm-blue-700`…).
// Aquí esas escalas pasan a leer variables CSS que cambian con `.dark`, así que las páginas cambian de tema sin
// reescribirse. Decisión del 2026-11-02: el oscuro conserva la identidad Dipromedic (neutros en navy, azul y verde de
// marca); Atlas Tech solo aparece en el pie.
//
// Regla para quien edite páginas: un relleno sólido con texto blanco encima usa los colores fijos `brand`, `danger` o
// `ink` (tailwind.config.js), no un paso de una escala tematizada, porque en oscuro esos pasos se aclaran.
import colors from 'tailwindcss/colors'

const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]

/** Neutros: claro = slate de Tailwind; oscuro = navy Dipromedic, con el texto 400–600 en ≥ 5:1 sobre `surface`. */
const neutralDark = {
  50: '#0D2550', // fondo sutil (encabezados de tabla, filas alternas)
  100: '#12305F', // hover, chips
  200: '#1F3B6B', // bordes
  300: '#2D4B7F', // bordes fuertes
  400: '#7F95B6', // texto tenue · 5.3:1 sobre surface
  500: '#9FB1CB', // texto secundario · 7.4:1
  600: '#B7C6DA',
  700: '#D3DCE9',
  800: '#E3E9F0',
  900: '#F2F5F9', // texto principal
  950: '#FFFFFF',
}

export const dpmBlue = {
  50: '#EEF6FC',
  100: '#D8EAF8',
  200: '#B3D6F1',
  300: '#7FBAE6',
  400: '#4398D6',
  500: '#1F84CB',
  600: '#0F75BC',
  700: '#0C5F9A',
  800: '#0B4E7E',
  900: '#0A3F66',
  950: '#072943',
}

/** Invierte una escala: el tinte claro (50) pasa a ser el tono oscuro (950) y el texto 700 pasa a 300. */
const inverted = (scale) => Object.fromEntries(STEPS.map((s, i) => [s, scale[STEPS[STEPS.length - 1 - i]]]))

export const STATUS_NAMES = ['red', 'amber', 'emerald', 'orange', 'rose', 'sky', 'violet', 'yellow']

/** Escalas tematizadas: nombre → { light, dark }. */
export const THEMED = {
  slate: { light: colors.slate, dark: neutralDark },
  'dpm-blue': { light: dpmBlue, dark: inverted(dpmBlue) },
  ...Object.fromEntries(STATUS_NAMES.map((n) => [n, { light: colors[n], dark: inverted(colors[n]) }])),
}

/** Superficies sueltas (sin escala). */
export const SURFACES = {
  canvas: { light: '#F4F6F9', dark: '#00122F' }, // fondo de la página
  surface: { light: '#FFFFFF', dark: '#0A1F44' }, // tarjetas, tablas, menús, campos
  // El azul de marca como texto o borde: en oscuro sube a 400 para leerse sobre navy (5.0:1 sobre surface).
  'dpm-blue-default': { light: dpmBlue[600], dark: dpmBlue[400] },
}

const hexToRgb = (hex) => {
  const n = parseInt(hex.slice(1), 16)
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`
}

/** Variables CSS para un modo. */
export function cssVars(mode) {
  const vars = {}
  for (const [name, scale] of Object.entries(THEMED)) {
    for (const s of STEPS) vars[`--c-${name}-${s}`] = hexToRgb(scale[mode][s])
  }
  for (const [name, v] of Object.entries(SURFACES)) vars[`--c-${name}`] = hexToRgb(v[mode])
  return vars
}

const ref = (name) => `rgb(var(--c-${name}) / <alpha-value>)`

/** Escala de Tailwind que apunta a las variables. */
export const themedScale = (name) => Object.fromEntries(STEPS.map((s) => [s, ref(`${name}-${s}`)]))
export const themedColor = ref
