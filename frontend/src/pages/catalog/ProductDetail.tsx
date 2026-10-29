import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ExternalLink, FlaskConical, TriangleAlert } from 'lucide-react'
import DocumentsTable from '@/components/DocumentsTable'
import Tooltip from '@/components/Tooltip'
import { DataKindBadge } from '@/components/badges'
import { CatalogCredit } from '@/components/brand/Footer'
import { ErrorPanel, Forbidden, LoadingBlock } from '@/components/feedback'
import { getCatalogProduct, type CatalogVariant, type ProductDetail as Detail } from '@/lib/api-catalog'
import { formatInteger, formatMoney } from '@/lib/format'
import { useApi } from '@/lib/useApi'
import { useAuth, useCan } from '@/store/auth'
import AttributeTable, { attributeView, catalogAttributeLabel, CitedValue } from '@/pages/catalog/AttributeTable'
import { CatalogReviewBadge, ProductImage } from '@/pages/catalog/shared'

const NOT_PUBLISHED = 'No publicado en el sitio'
const SIDE_LABEL = { izquierda: 'Izquierda', derecha: 'Derecha' } as const
const SIDE_ORDER = { izquierda: 0, derecha: 1 } as const
const WATERMARK_FALLBACK = 'DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN'
/** Atributos que salen de la fila de la tabla del sitio; van en columnas propias de la tabla de variantes. */
const ROW_KEYS = ['holes', 'diameter_mm', 'length_mm'] as const

const baseName = (v: CatalogVariant) => v.name.replace(/ · (izquierda|derecha)$/, '')

/** Variantes agrupadas por nombre de fila y, dentro de cada grupo, izquierda antes que derecha. */
function sortVariants(variants: CatalogVariant[]): CatalogVariant[] {
  return [...variants].sort((a, b) => {
    const byName = baseName(a).localeCompare(baseName(b), 'es', { numeric: true })
    if (byName !== 0) return byName
    const sa = a.side ? SIDE_ORDER[a.side] : 2
    const sb = b.side ? SIDE_ORDER[b.side] : 2
    return sa - sb || a.sku.localeCompare(b.sku, 'es', { numeric: true })
  })
}

function Gallery({ name, images }: { name: string; images: string[] }) {
  const [index, setIndex] = useState(0)
  const current = images[Math.min(index, Math.max(images.length - 1, 0))]
  return (
    <div>
      <ProductImage
        key={current ?? 'none'}
        src={current}
        alt={`Imagen del producto publicada en dipromedic.com: ${name}`}
        className="h-64 w-full rounded-md border border-slate-200"
      />
      {images.length > 1 && (
        <ul className="mt-2 flex gap-2 overflow-x-auto" aria-label="Imágenes del producto">
          {images.map((src, i) => (
            <li key={src} className="shrink-0">
              <button
                type="button"
                onClick={() => setIndex(i)}
                aria-label={`Ver imagen ${i + 1} de ${images.length}`}
                aria-current={i === index}
                className={`block overflow-hidden rounded border ${i === index ? 'border-dpm-blue' : 'border-slate-200'}`}
              >
                <ProductImage src={src} alt="" className="h-14 w-14" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function CommercialNotice({ variants }: { variants: CatalogVariant[] }) {
  const any = {
    price: variants.some((v) => v.price !== null),
    stock: variants.some((v) => v.stock_demo !== null),
    registry: variants.some((v) => v.regulatory_reference),
  }
  const rows: [string, boolean][] = [
    ['Precio', any.price],
    ['Existencias', any.stock],
    ['Registro sanitario', any.registry],
  ]
  return (
    <section aria-labelledby="comercial" className="card p-4">
      <h2 id="comercial" className="text-sm font-semibold text-slate-900">
        Datos comerciales
      </h2>
      <dl className="mt-2 space-y-1.5 text-sm">
        {rows.map(([label, present]) => (
          <div key={label} className="flex flex-wrap justify-between gap-x-4">
            <dt className="text-slate-600">{label}</dt>
            <dd className={present ? 'text-slate-900' : 'italic text-slate-500'}>
              {present ? 'Ver tabla de variantes' : NOT_PUBLISHED}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        Estos datos no se toman del sitio. Si se agregan, son simulados y se marcan campo por campo.
      </p>
    </section>
  )
}

function VariantsTable({ variants, productAttrs, synthetic }: { variants: CatalogVariant[]; productAttrs: Record<string, unknown>; synthetic: boolean }) {
  const rows = useMemo(() => sortVariants(variants), [variants])
  const has = (key: (typeof ROW_KEYS)[number]) => rows.some((v) => key in v.attributes)
  const showHoles = has('holes')
  const showDiameter = has('diameter_mm')
  const showLength = has('length_mm')
  const showSide = rows.some((v) => v.side)
  const showUnit = rows.some((v) => v.unit)
  // Lo que no es común a todas las variantes ni sale de la fila (datos ficticios con atributos planos).
  const otherKeys = useMemo(() => {
    const keys = new Set<string>()
    for (const v of rows) {
      for (const k of Object.keys(v.attributes)) {
        if (!(ROW_KEYS as readonly string[]).includes(k) && !(k in productAttrs)) keys.add(k)
      }
    }
    return Array.from(keys)
  }, [rows, productAttrs])
  const showPrice = rows.some((v) => v.price !== null)
  const showStock = rows.some((v) => v.stock_demo !== null)
  const showRegistry = rows.some((v) => v.regulatory_reference)
  const showQuote = rows.some((v) => v.source_text)

  const cell = (v: CatalogVariant, key: (typeof ROW_KEYS)[number]) =>
    key in v.attributes ? <CitedValue raw={v.attributes[key]} /> : <span className="muted">—</span>

  return (
    <div className="relative overflow-x-auto">
      <table className="table-base min-w-[760px]">
        <caption className="sr-only">Variantes y códigos publicados</caption>
        <thead>
          <tr>
            <th scope="col">SKU</th>
            {showSide && <th scope="col">Lado</th>}
            <th scope="col">Variante</th>
            {showHoles && <th scope="col">Orificios</th>}
            {showDiameter && <th scope="col">Diámetro</th>}
            {showLength && <th scope="col">Longitud</th>}
            {otherKeys.length > 0 && <th scope="col">Otros atributos</th>}
            {showUnit && <th scope="col">Unidad</th>}
            {showPrice && <th scope="col" className="text-right">Precio</th>}
            {showStock && <th scope="col" className="text-right">Existencia</th>}
            {showRegistry && <th scope="col">Registro</th>}
            {showQuote && <th scope="col">Fila de la tabla del sitio</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((v) => (
            <tr key={v.id}>
              <td className="whitespace-nowrap text-xs font-semibold tabular-nums">{v.sku}</td>
              {showSide && (
                <td className="whitespace-nowrap">
                  {v.side ? SIDE_LABEL[v.side] : <span className="muted" aria-label="Sin lado">—</span>}
                </td>
              )}
              <td className="min-w-[200px]">{baseName(v)}</td>
              {showHoles && <td>{cell(v, 'holes')}</td>}
              {showDiameter && <td>{cell(v, 'diameter_mm')}</td>}
              {showLength && <td className="min-w-[140px]">{cell(v, 'length_mm')}</td>}
              {otherKeys.length > 0 && (
                <td className="min-w-[160px] text-xs">
                  {otherKeys
                    .filter((k) => k in v.attributes)
                    .map((k) => (
                      <div key={k}>
                        <span className="text-slate-600">{catalogAttributeLabel(k)}:</span> {attributeView(v.attributes[k]).text}
                      </div>
                    ))}
                </td>
              )}
              {showUnit && <td>{v.unit}</td>}
              {showPrice && (
                <td className="whitespace-nowrap text-right tabular-nums">
                  {formatMoney(v.price, v.currency) ?? <span className="muted">{NOT_PUBLISHED}</span>}
                  {v.price && <div className="text-[11px] text-amber-800">ficticio</div>}
                </td>
              )}
              {showStock && (
                <td className="whitespace-nowrap text-right tabular-nums">
                  {v.stock_demo !== null ? (
                    <>
                      {formatInteger(v.stock_demo)}
                      <div className="text-[11px] text-amber-800">simulado</div>
                    </>
                  ) : (
                    <span className="muted">{NOT_PUBLISHED}</span>
                  )}
                </td>
              )}
              {showRegistry && (
                <td className="text-xs">
                  {v.regulatory_reference ? (
                    v.regulatory_reference === 'DEMO-SIN-VALIDEZ' ? (
                      <Tooltip content="Registro ficticio: no corresponde a ningún registro sanitario." focusable>
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-amber-900 ring-1 ring-amber-200">
                          {v.regulatory_reference}
                        </span>
                      </Tooltip>
                    ) : (
                      v.regulatory_reference
                    )
                  ) : (
                    <span className="muted">{NOT_PUBLISHED}</span>
                  )}
                </td>
              )}
              {showQuote && (
                <td className="max-w-xs text-xs italic text-slate-600">
                  {v.source_text ? `«${v.source_text}»` : <span className="not-italic muted">{synthetic ? '—' : 'Sin texto de fila'}</span>}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Fiche({ p }: { p: Detail }) {
  const watermark = useAuth((s) => s.meta?.watermark) ?? WATERMARK_FALLBACK
  const synthetic = p.data_kind === 'SYNTHETIC'
  const hasNotes = p.data_quality_notes.length > 0

  return (
    <article aria-labelledby="producto-titulo">
      <Link to="/catalogo" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-dpm-blue-700">
        <ArrowLeft aria-hidden="true" className="h-4 w-4" />
        Catálogo
      </Link>

      {synthetic && (
        <div
          role="note"
          className="relative mt-3 flex items-center gap-3 overflow-hidden rounded-md border border-amber-300 bg-amber-50 py-2.5 pl-5 pr-4 text-sm text-amber-950"
        >
          <span aria-hidden="true" className="hatch-synthetic absolute inset-y-0 left-0 w-2" />
          <FlaskConical aria-hidden="true" className="h-4 w-4 shrink-0" />
          <span>
            <strong className="font-semibold">{watermark}</strong> · producto, precios, existencias y registros de
            demostración; no representan el catálogo de Dipromedic.
          </span>
        </div>
      )}

      <header className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          {p.line && <p className="text-xs font-semibold uppercase tracking-wide text-dpm-blue-700">{p.line}</p>}
          <h1 id="producto-titulo" className="text-2xl font-semibold tracking-tight text-slate-900">
            {p.name}
          </h1>
          <span className="brand-rule mt-2" aria-hidden="true" />
          <p className="mt-2 text-sm text-slate-600">
            {p.family}
            {p.subfamily ? ` · ${p.subfamily}` : ''}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <DataKindBadge kind={p.data_kind} />
            <CatalogReviewBadge status={p.review_status} />
            <span className="text-xs text-slate-600">
              {p.variant_count === 0
                ? 'Sin códigos cargados'
                : `${p.variant_count} ${p.variant_count === 1 ? 'código' : 'códigos'}`}
            </span>
          </div>
        </div>
        {p.source_url && (
          <a href={p.source_url} target="_blank" rel="noopener noreferrer" className="btn-secondary">
            Ver en dipromedic.com
            <ExternalLink aria-hidden="true" className="h-4 w-4" />
          </a>
        )}
      </header>

      {hasNotes && (
        <section
          aria-labelledby="calidad"
          className="mt-5 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950"
        >
          <h2 id="calidad" className="flex items-center gap-2 font-semibold">
            <TriangleAlert aria-hidden="true" className="h-4 w-4 shrink-0" />
            Observaciones sobre la página de origen
          </h2>
          <p className="mt-1 text-xs text-amber-900">
            Son inconsistencias de la propia página. Se conservan tal cual y la ficha queda marcada para revisión.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {p.data_quality_notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,320px)_1fr]">
        <div className="space-y-4">
          <Gallery name={p.name} images={p.images} />
          {!synthetic && <CommercialNotice variants={p.variants} />}
        </div>

        <div className="min-w-0 space-y-6">
          {p.description && (
            <section aria-labelledby="descripcion">
              <h2 id="descripcion" className="mb-1 text-base font-semibold text-slate-900">
                Descripción
              </h2>
              <p className="text-sm text-slate-700">{p.description}</p>
            </section>
          )}

          {p.features.length > 0 && (
            <section aria-labelledby="caracteristicas">
              <h2 id="caracteristicas" className="mb-1 text-base font-semibold text-slate-900">
                Características
                <span className="ml-2 text-xs font-normal text-slate-500">texto literal del sitio</span>
              </h2>
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                {p.features.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="atributos">
            <h2 id="atributos" className="mb-2 text-base font-semibold text-slate-900">
              Atributos técnicos
              <span className="ml-2 text-xs font-normal text-slate-500">
                {synthetic ? 'comunes a todas las variantes' : 'de la ficha del producto'}
              </span>
            </h2>
            <AttributeTable attributes={p.attributes} caption={`Atributos técnicos de ${p.name}`} />
          </section>
        </div>
      </div>

      {p.variants.length === 0 && (
        <section aria-labelledby="variantes" className="mt-8">
          <h2 id="variantes" className="mb-2 text-base font-semibold text-slate-900">
            Variantes y códigos
          </h2>
          <p className="text-sm muted">Sin códigos cargados en el catálogo; revisa la página de origen.</p>
        </section>
      )}

      {p.variants.length > 0 && (
        <section aria-labelledby="variantes" className="mt-8">
          <h2 id="variantes" className="mb-2 text-base font-semibold text-slate-900">
            Variantes y códigos
            <span className="ml-2 text-xs font-normal text-slate-500">
              {p.variants.some((v) => v.side)
                ? 'orificios por lado, con la cita de la fila'
                : p.variants.some((v) => v.source_text)
                  ? 'con la cita de la fila'
                  : ''}
            </span>
          </h2>
          <div className="card overflow-hidden">
            <VariantsTable variants={p.variants} productAttrs={p.attributes} synthetic={synthetic} />
          </div>
        </section>
      )}

      <section aria-labelledby="documentos" className="mt-8">
        <h2 id="documentos" className="mb-2 text-base font-semibold text-slate-900">
          Documentos del producto
        </h2>
        {p.documents.length === 0 ? (
          <p className="text-sm muted">Todavía no hay documentos vinculados a esta ficha.</p>
        ) : (
          <div className="card overflow-hidden">
            <DocumentsTable docs={p.documents} />
          </div>
        )}
      </section>

      {p.checked_on && (
        <p className="mt-8 border-t border-slate-200 pt-3 text-xs text-slate-600">
          <CatalogCredit checkedOn={p.checked_on} />
        </p>
      )}
    </article>
  )
}

export default function ProductDetail() {
  const { productId = '' } = useParams()
  const canRead = useCan('catalog.read')
  const product = useApi(() => getCatalogProduct(productId), [productId], canRead)

  if (!canRead) return <Forbidden permission="catalog.read" />
  if (product.error) {
    return (
      <div>
        <Link to="/catalogo" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-dpm-blue-700">
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
          Catálogo
        </Link>
        <ErrorPanel error={product.error} onRetry={product.reload} title="No se pudo cargar la ficha" />
      </div>
    )
  }
  if (!product.data) return <LoadingBlock label="Cargando ficha…" />
  return <Fiche p={product.data} />
}
