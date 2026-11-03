# ADR-004 · Tema claro/oscuro y crédito de Atlas Tech

Estado: aceptado · 2026-11-02

## Contexto

Para el beta, Emmanuel pidió un cambio de tema claro/oscuro como el de Atlas One y el crédito de Atlas Tech en el pie.
Decidió que el oscuro conserve la identidad Dipromedic (ADR-003) y que Atlas Tech aparezca solo en el pie.

Atlas One usa la clase `dark` en `<html>`, la preferencia en `localStorage` y colores en variables CSS. Licit tenía los
colores escritos en las clases de Tailwind (unas 1,050 en 46 archivos) y ningún modo oscuro.

## Decisión

- **Mismo patrón que Atlas One**: `darkMode: 'class'`, `src/store/theme.ts` (clave `licit_theme`; sin preferencia
  guardada se usa la del sistema) y un script en `index.html` que pone la clase antes de pintar. El botón va en la barra
  superior y en el panel del login.
- **Paleta por variables** (`frontend/theme.palettes.js`): `slate`, los colores de estado (red, amber, emerald, orange,
  rose, sky, violet, yellow) y `dpm-blue` leen variables CSS que cambian con `.dark`. Así las páginas cambian de tema
  sin reescribirlas. En oscuro los neutros pasan a la escala navy de Dipromedic (texto secundario ≥ 5:1 sobre la
  superficie) y las escalas de estado se invierten (el tinte 50 pasa a 950 y el texto 700 a 300). `canvas` y `surface`
  son las superficies (`bg-surface` reemplaza a `bg-white` en tarjetas, tablas, campos y diálogos).
- **Colores fijos** para rellenos sólidos con texto blanco encima: `brand`, `danger` e `ink`. **Regla:** un relleno
  sólido con texto blanco no usa un paso de una escala tematizada, porque en oscuro esos pasos se aclaran.
- La barra superior y el panel del login siguen en navy (`dpm-navy`, fijo). Las fotos del catálogo siguen sobre blanco.
- **Crédito** (`components/brand/AtlasCredit.tsx`): «Desarrollado con ❤️ por ATLAS_TECH», con la «A» en círculo de la
  guía de Atlas en `currentColor`, en el pie de la app y del login, junto al crédito de catálogo de Dipromedic, que se
  mantiene. El turquesa de Atlas no se usa como texto porque sobre blanco no tiene contraste suficiente.

## Consecuencias

- Revisado en navegador, en ambos temas: login, radar, detalle de oportunidad, catálogo, centro documental, panel,
  gobierno, bitácora, pendientes, diálogo de búsqueda, tooltip y pie.
- Los colores nuevos que no estén en las escalas tematizadas (p. ej. `teal`, `indigo`) no cambian con el tema. Si se
  agregan, hay que sumarlos a `STATUS_NAMES`.
