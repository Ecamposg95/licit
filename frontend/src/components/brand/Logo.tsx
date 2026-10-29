/**
 * Logotipo oficial de Grupo Dipromedic, copiado de https://www.dipromedic.com/assets/img/branding/
 * (consultado el 2026-10-28). Nunca se redibuja ni se recolorea:
 * - `color`: PNG 166×69 para fondos claros. Es raster: no mostrarlo a más de 69 px de alto
 *   (a 34 px o menos se ve nítido en pantallas de alta densidad).
 * - `white`: SVG blanco (viewBox 166×58) para fondos oscuros; escala sin pérdida.
 * El tamaño se fija con una clase de alto (`h-7`, `h-9`…); el ancho se calcula solo.
 */
const SOURCES = {
  color: { src: '/brand/logo-dipromedic-color.png', width: 166, height: 69 },
  white: { src: '/brand/logo-dipromedic-blanco.svg', width: 166, height: 58 },
} as const

export type LogoVariant = keyof typeof SOURCES

export default function Logo({ variant, className }: { variant: LogoVariant; className?: string }) {
  const { src, width, height } = SOURCES[variant]
  return (
    <img
      src={src}
      width={width}
      height={height}
      alt="Grupo Dipromedic"
      draggable={false}
      className={`block w-auto shrink-0 select-none ${className ?? 'h-8'}`}
    />
  )
}
