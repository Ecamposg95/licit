import { formatDate } from '@/lib/format'

/**
 * Crédito que pide el aviso de propiedad intelectual de dipromedic.com
 * (https://www.dipromedic.com/propiedad-intelectual): mencionar a DIPROMEDIC S.A. DE C.V. y el enlace al sitio.
 * Texto literal: «Contenido de catálogo: DIPROMEDIC S.A. DE C.V. · www.dipromedic.com · consultado el {checked_on}».
 * Se usa en el pie y en cada ficha importada. `checkedOn` es una fecha de calendario (YYYY-MM-DD).
 */
export function CatalogCredit({ checkedOn, className }: { checkedOn: string; className?: string }) {
  return (
    <span className={className}>
      Contenido de catálogo: <span className="whitespace-nowrap">DIPROMEDIC S.A. DE C.V.</span> ·{' '}
      <a
        href="https://www.dipromedic.com"
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-dpm-blue-700 underline-offset-2 hover:underline"
      >
        www.dipromedic.com
      </a>{' '}
      · consultado el{' '}
      <time dateTime={checkedOn} className="whitespace-nowrap tabular-nums">
        {formatDate(checkedOn)}
      </time>
    </span>
  )
}

/** Pie de las páginas autenticadas y del login. */
export default function Footer({ checkedOn, className }: { checkedOn: string; className?: string }) {
  return (
    <footer
      className={`flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-600 ${
        className ?? ''
      }`}
    >
      <p>
        <CatalogCredit checkedOn={checkedOn} />
      </p>
      <p>Las marcas de terceros pertenecen a sus respectivos dueños.</p>
    </footer>
  )
}
