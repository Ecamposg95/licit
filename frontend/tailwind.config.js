/** @type {import('tailwindcss').Config} */

// Identidad Dipromedic (docs/adr/ADR-003-identidad.md). Valores del bloque :root de
// https://www.dipromedic.com/style.css, consultado el 2026-10-28 (docs/research/dipromedic-web.md §1.2).
//
// Azul corporativo: el tono de marca es el paso 600 (= DEFAULT). Contra blanco da 4.89:1 (AA para texto
// normal). Sobre el tinte 50 baja a 4.48:1, así que el texto sobre tintes claros va en 700 (6.16:1).
const dpmBlue = {
  DEFAULT: '#0F75BC',
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

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        dpm: {
          blue: dpmBlue,
          // Verde «Fixi»: barras y acentos. Nunca lleva texto blanco encima (2.88:1); el texto sobre
          // verde va en navy (5.70:1). Para texto verde sobre blanco se usa 700 (5.35:1).
          green: {
            DEFAULT: '#47AD36',
            light: '#63F24B',
            50: '#EFF9EC',
            100: '#DCF1D6',
            700: '#2E7A22',
          },
          // Navy del pie del sitio: barra superior y panel del login. 300 es el texto del pie del
          // sitio (#96AAC1, 6.89:1 sobre navy).
          navy: {
            DEFAULT: '#001D4C',
            50: '#F2F5F9',
            100: '#E3E9F0',
            200: '#C3CFDD',
            300: '#96AAC1',
            400: '#6A82A3',
            500: '#435E85',
            600: '#2B4670',
            700: '#183460',
            800: '#0A2756',
            900: '#001D4C',
            950: '#00122F',
          },
          // Azul de la línea Traufix (títulos de sus tablas de producto).
          traufix: '#004991',
        },
        // Alias de compatibilidad: las páginas de E1 usan `petrol-*`, que ahora es el azul Dipromedic.
        petrol: dpmBlue,
        canvas: '#F4F6F9',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
      backgroundImage: {
        // Degradado de los botones del sitio (.btn-gradient): 90°, #63F24B → #47AD36.
        'dpm-accent': 'linear-gradient(90deg, #63F24B 0%, #47AD36 100%)',
      },
    },
  },
  plugins: [],
}
