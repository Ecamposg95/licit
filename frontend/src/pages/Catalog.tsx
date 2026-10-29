import { useEffect, useMemo, useState } from 'react'
import { FileSpreadsheet } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import DataKindChips, { usePersistentDataKinds } from '@/components/DataKindChips'
import Tooltip, { UnavailableAction } from '@/components/Tooltip'
import { DataKindBadge, ReviewStatusBadge } from '@/components/badges'
import { EmptyState, ErrorPanel, Forbidden, TableSkeleton } from '@/components/feedback'
import { listProducts } from '@/lib/api'
import { formatInteger, formatMoney, formatValue } from '@/lib/format'
import { attributeLabel, attributeUnit } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import type { ProductOut, VariantOut } from '@/lib/types'
import { useCan } from '@/store/auth'

function Attributes({ attrs }: { attrs: Record<string, unknown> }) {
  const entries = Object.entries(attrs)
  if (entries.length === 0) return <span className="muted">Sin atributos</span>
  return (
    <ul className="space-y-0.5 text-xs">
      {entries.map(([k, v]) => {
        const missing = v === null || v === undefined || v === ''
        const unit = attributeUnit(k)
        return (
          <li key={k} title={k}>
            <span className="text-slate-600">{attributeLabel(k)}:</span>{' '}
            {missing ? (
              <span className="italic text-slate-500">no declarado</span>
            ) : (
              <span className="text-slate-900">
                {formatValue(v)}
                {unit ? ` ${unit}` : ''}
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function Regulatory({ value }: { value: string | null }) {
  if (!value) return <span className="muted">No declarada</span>
  if (value === 'DEMO-SIN-VALIDEZ') {
    return (
      <Tooltip content="Registro ficticio: no corresponde a ningún registro sanitario." focusable>
        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-900 ring-1 ring-amber-200">{value}</span>
      </Tooltip>
    )
  }
  return <span className="text-xs">{value}</span>
}

function VariantsTable({ variants }: { variants: VariantOut[] }) {
  return (
    <div className="relative overflow-x-auto">
      <table className="table-base min-w-[980px]">
        <thead>
          <tr>
            <th scope="col">SKU</th>
            <th scope="col">Variante</th>
            <th scope="col">Atributos</th>
            <th scope="col">Unidad</th>
            <th scope="col" className="text-right">
              Precio demo
            </th>
            <th scope="col" className="text-right">
              Existencia
            </th>
            <th scope="col">Referencia regulatoria</th>
            <th scope="col">Revisión</th>
          </tr>
        </thead>
        <tbody>
          {variants.map((v) => (
            <tr key={v.id}>
              <td className="whitespace-nowrap text-xs font-medium tabular-nums">{v.sku}</td>
              <td className="min-w-[220px]">{v.name}</td>
              <td className="min-w-[160px]">
                <Attributes attrs={v.attributes} />
              </td>
              <td>{v.unit}</td>
              <td className="whitespace-nowrap text-right tabular-nums">
                {formatMoney(v.price, v.currency) ?? <span className="muted">Sin precio</span>}
                {v.price && v.data_kind === 'SYNTHETIC' && <div className="text-[11px] text-amber-800">ficticio</div>}
              </td>
              <td className="whitespace-nowrap text-right tabular-nums">
                {v.stock_demo !== null ? (
                  <>
                    {formatInteger(v.stock_demo)}
                    <div className="text-[11px] text-amber-800">simulado</div>
                  </>
                ) : (
                  <span className="muted">No declarada</span>
                )}
              </td>
              <td>
                <Regulatory value={v.regulatory_reference} />
              </td>
              <td>
                <ReviewStatusBadge status={v.review_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ProductBlock({ p }: { p: ProductOut }) {
  return (
    <article className="card overflow-hidden" aria-labelledby={`prod-${p.id}`}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <h3 id={`prod-${p.id}`} className="font-semibold text-slate-900">
            {p.name}
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Marca: {p.brand ?? 'no declarada'} · Fabricante declarado: {p.manufacturer ?? 'no declarado'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DataKindBadge kind={p.data_kind} />
          <ReviewStatusBadge status={p.review_status} />
        </div>
      </header>
      {p.variants.length ? <VariantsTable variants={p.variants} /> : <p className="px-4 py-3 text-sm text-slate-500">Sin variantes.</p>}
    </article>
  )
}

export default function Catalog() {
  const canRead = useCan('catalog.read')
  const [kinds, setKinds] = usePersistentDataKinds('licit.catalog.dataKinds')
  const [family, setFamily] = useState('')
  const [text, setText] = useState('')
  const [q, setQ] = useState('')

  useEffect(() => {
    const t = window.setTimeout(() => setQ(text.trim()), 350)
    return () => window.clearTimeout(t)
  }, [text])

  const noKinds = kinds.length === 0
  const products = useApi(() => listProducts({ family, q, data_kind: kinds }), [family, q, kinds.join(',')], canRead && !noKinds)
  // Familias disponibles: catálogo completo, sin filtros.
  const allProducts = useApi(() => listProducts({}), [], canRead)
  const families = useMemo(
    () => Array.from(new Set((allProducts.data ?? []).map((p) => p.family))).sort((a, b) => a.localeCompare(b, 'es')),
    [allProducts.data],
  )

  const grouped = useMemo(() => {
    const m = new Map<string, ProductOut[]>()
    for (const p of products.data ?? []) m.set(p.family, [...(m.get(p.family) ?? []), p])
    return Array.from(m.entries())
  }, [products.data])

  if (!canRead) return <Forbidden permission="catalog.read" />

  const variantCount = (products.data ?? []).reduce((n, p) => n + p.variants.length, 0)

  return (
    <div>
      <PageHeader
        title="Catálogo"
        description="Productos y variantes con atributos técnicos y unidades. Un atributo sin dato se muestra como no declarado; nunca se deduce del nombre."
        actions={
          <UnavailableAction
            label="Importar CSV"
            icon={<FileSpreadsheet aria-hidden="true" className="h-4 w-4" />}
            reason="Importación con previsualización: próxima entrega"
          />
        }
      />

      <div
        role="note"
        className="hatch-synthetic-soft mb-4 rounded-md border border-amber-300 px-4 py-2.5 text-sm text-amber-950"
      >
        <strong className="font-semibold">Datos ficticios.</strong> Productos, precios, existencias y registros de este
        catálogo son de demostración; no representan el catálogo ni la capacidad real de Dipromedic.
      </div>

      <section aria-label="Filtros" className="card mb-4 p-4">
        <DataKindChips value={kinds} onChange={setKinds} />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:max-w-2xl">
          <div>
            <label htmlFor="c-q" className="label">
              Producto
            </label>
            <input
              id="c-q"
              type="search"
              className="input"
              placeholder="Nombre del producto"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="c-family" className="label">
              Familia
            </label>
            <select id="c-family" className="input" value={family} onChange={(e) => setFamily(e.target.value)}>
              <option value="">Todas</option>
              {families.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {noKinds ? (
        <div className="card">
          <EmptyState title="Activa al menos un tipo de dato">Elige REAL, HISTÓRICO o SIMULADO para ver productos.</EmptyState>
        </div>
      ) : products.error ? (
        <ErrorPanel error={products.error} onRetry={products.reload} />
      ) : !products.data ? (
        <div className="card">
          <TableSkeleton cols={6} />
        </div>
      ) : products.data.length === 0 ? (
        <div className="card">
          <EmptyState title="Sin productos para estos filtros">
            {kinds.includes('SYNTHETIC')
              ? 'Ajusta o limpia los filtros.'
              : 'El catálogo de demostración es ficticio: activa SIMULADO para verlo. Aún no hay un catálogo real importado.'}
          </EmptyState>
        </div>
      ) : (
        <div className="space-y-8">
          <p className="text-sm text-slate-600" aria-live="polite">
            {products.data.length} productos · {variantCount} variantes
          </p>
          {grouped.map(([fam, items], i) => (
            <section key={fam} aria-labelledby={`fam-${i}`}>
              <h2 id={`fam-${i}`} className="mb-3 flex items-baseline gap-2 text-lg font-semibold text-slate-900">
                {fam}
                <span className="text-sm font-normal text-slate-500">
                  {items.length} {items.length === 1 ? 'producto' : 'productos'}
                </span>
              </h2>
              <div className="space-y-4">
                {items.map((p) => (
                  <ProductBlock key={p.id} p={p} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
