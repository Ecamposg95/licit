/**
 * Crédito de Atlas Tech en el pie, como en Atlas One («Desarrollado con ❤️ por Atlas Tech»).
 * Marca y wordmark según la guía de Atlas Tech: «A» en círculo con `currentColor`, ATLAS (800) + _TECH (400),
 * mayúsculas y tracking 0.08em. Va en el color del texto: el turquesa de Atlas no da contraste de texto sobre blanco.
 * La identidad del demo sigue siendo Dipromedic; Atlas solo aparece aquí (decisión del 2026-11-02).
 */
function AtlasMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 375.71 340" aria-hidden="true" className={className}>
      <g fill="currentColor">
        <polygon points="252.36 236.3 195.47 110.84 140.66 236.21 98.8 235.8 174.88 71.93 216.92 71.85 295.23 235.73 252.36 236.3" />
        <polygon points="235.1 264.18 156.85 264.18 169.04 236.37 222.59 236.45 235.1 264.18" />
        <path d="M322.77,271.46c-5.63,7.02-12.31,13.43-18.68,19.74-31,30.74-75.65,46.25-119.14,44.73-92.04-3.23-164.14-80-162.22-171.68C24.29,89.2,76.26,23.61,149.63,4.95,164.96,1.05,180.47-.39,196.78.09c49.74,1.45,95.910,25.54,126.33,64.35,47.43,60.52,48.14,146.58-.34,207.02ZM285.77,268.38c61.55-58.4,56.66-157.12-9.84-209.36-54.27-42.64-132.41-38.36-181.82,10.11-54.43,53.4-55.5,140.38-2.56,195.07,52.52,54.26,139.28,56.32,194.22,4.19Z" />
      </g>
    </svg>
  )
}

export default function AtlasCredit({ className = '' }: { className?: string }) {
  return (
    <p className={`inline-flex items-center gap-1.5 whitespace-nowrap ${className}`}>
      Desarrollado con <span role="img" aria-label="cariño">❤️</span> por
      <span className="inline-flex items-center gap-1 text-slate-800">
        <AtlasMark className="h-3.5 w-auto" />
        <span className="font-extrabold tracking-[0.08em]">
          ATLAS<span className="font-normal">_TECH</span>
        </span>
      </span>
    </p>
  )
}
