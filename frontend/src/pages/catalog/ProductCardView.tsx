import { Link } from 'react-router-dom'
import { CatalogCredit } from '@/components/brand/Footer'
import { ProductImage, CatalogReviewBadge } from '@/pages/catalog/shared'
import type { ProductCard } from '@/lib/api-catalog'

/**
 * Tarjeta de producto. La línea (Traufix, Corentec…) va como texto: los logos de marcas de terceros
 * no se muestran. Los productos SIMULADO llevan el rayado ámbar y no tienen crédito de catálogo.
 */
export default function ProductCardView({ p, heading: Heading = 'h3' }: { p: ProductCard; heading?: 'h3' | 'h4' }) {
  const synthetic = p.data_kind === 'SYNTHETIC'
  return (
    <article
      className={`card relative flex flex-col overflow-hidden transition-shadow focus-within:shadow-md hover:shadow-md ${
        synthetic ? 'border-amber-300' : ''
      }`}
      aria-labelledby={`card-${p.id}`}
    >
      {synthetic && <span aria-hidden="true" className="hatch-synthetic block h-2" />}
      <ProductImage src={p.images[0]} alt="" className="h-40 w-full border-b border-slate-100" />
      <div className="flex flex-1 flex-col gap-2 p-4">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-dpm-blue-700">
          {p.line ?? (synthetic ? 'Simulado · ficticio' : p.family)}
        </p>
        <Heading id={`card-${p.id}`} className="font-semibold leading-snug text-slate-900">
          <Link to={`/catalogo/${encodeURIComponent(p.id)}`} className="after:absolute after:inset-0 hover:text-dpm-blue-700">
            {p.name}
          </Link>
        </Heading>
        <p className="text-xs text-slate-600">
          {p.family}
          {p.subfamily ? ` · ${p.subfamily}` : ''}
        </p>
        {p.description && <p className="line-clamp-3 text-xs text-slate-600">{p.description}</p>}
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
          <span className="text-xs font-medium text-slate-700">
            {p.variant_count === 0
              ? 'Sin códigos cargados'
              : `${p.variant_count} ${p.variant_count === 1 ? 'código' : 'códigos'}`}
          </span>
          {p.review_status === 'por_revisar' && <CatalogReviewBadge status={p.review_status} />}
        </div>
      </div>
      {p.checked_on && (
        <p className="relative border-t border-slate-100 bg-slate-50 px-4 py-2 text-[11px] leading-4 text-slate-600">
          <CatalogCredit checkedOn={p.checked_on} />
        </p>
      )}
    </article>
  )
}
