import { useEffect, useMemo, useState } from 'react'
import { FlaskConical } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import Tabs, { type TabDef } from '@/components/Tabs'
import { EmptyState, ErrorPanel, Forbidden, LoadingBlock } from '@/components/feedback'
import { listCatalogLines, listCatalogProducts, type ProductCard } from '@/lib/api-catalog'
import { useApi } from '@/lib/useApi'
import type { DataKind } from '@/lib/types'
import { useAuth, useCan } from '@/store/auth'
import ProductCardView from '@/pages/catalog/ProductCardView'

type TabId = 'real' | 'simulado'
const KIND: Record<TabId, DataKind> = { real: 'REAL', simulado: 'SYNTHETIC' }
const WATERMARK_FALLBACK = 'DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN'

function group<T>(items: T[], key: (item: T) => string): [string, T[]][] {
  const m = new Map<string, T[]>()
  for (const item of items) m.set(key(item), [...(m.get(key(item)) ?? []), item])
  return Array.from(m.entries())
}

interface Section {
  title: string
  blocks: { heading: string | null; items: ProductCard[] }[]
}

function Results({ cards, tab, lineOrder }: { cards: ProductCard[]; tab: TabId; lineOrder: string[] }) {
  // REAL: por línea (la de más fichas primero) y, dentro de cada una, por familia. SIMULADO: sólo por familia.
  const sections = useMemo<Section[]>(() => {
    if (tab === 'simulado') {
      return group(cards, (c) => c.family).map(([family, items]) => ({ title: family, blocks: [{ heading: null, items }] }))
    }
    const rank = (line: string) => {
      const i = lineOrder.indexOf(line)
      return i < 0 ? lineOrder.length : i
    }
    return group(cards, (c) => c.line ?? 'Sin línea')
      .sort((a, b) => rank(a[0]) - rank(b[0]))
      .map(([line, items]) => ({
        title: line,
        blocks: group(items, (c) => c.family).map(([family, rows]) => ({ heading: family, items: rows })),
      }))
  }, [cards, tab, lineOrder])
  const variants = cards.reduce((n, c) => n + c.variant_count, 0)
  return (
    <div className="space-y-10">
      <p className="text-sm text-slate-600" aria-live="polite">
        {cards.length} {cards.length === 1 ? 'ficha' : 'fichas'} · {variants} {variants === 1 ? 'variante' : 'variantes'}
      </p>
      {sections.map(({ title, blocks }) => {
        const total = blocks.reduce((n, b) => n + b.items.length, 0)
        return (
          <section key={title} aria-labelledby={`sec-${title}`}>
            <h2 id={`sec-${title}`} className="flex items-baseline gap-2 text-lg font-semibold text-slate-900">
              {title}
              <span className="text-sm font-normal text-slate-500">
                {total} {total === 1 ? 'ficha' : 'fichas'}
              </span>
            </h2>
            <span className="brand-rule mb-4 mt-1.5" aria-hidden="true" />
            <div className="space-y-6">
              {blocks.map(({ heading, items }) => (
                <div key={heading ?? title}>
                  {heading && blocks.length > 1 && (
                    <h3 className="mb-2 text-sm font-semibold text-slate-700">
                      {heading}
                      <span className="ml-2 text-xs font-normal text-slate-500">{items.length}</span>
                    </h3>
                  )}
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {items.map((p) => (
                      <ProductCardView key={p.id} p={p} heading={heading && blocks.length > 1 ? 'h4' : 'h3'} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}

export default function Catalog() {
  const canRead = useCan('catalog.read')
  const watermark = useAuth((s) => s.meta?.watermark) ?? WATERMARK_FALLBACK
  const [tab, setTab] = useState<TabId>('real')
  const [line, setLine] = useState('')
  const [family, setFamily] = useState('')
  const [text, setText] = useState('')
  const [q, setQ] = useState('')

  useEffect(() => {
    const t = window.setTimeout(() => setQ(text.trim()), 350)
    return () => window.clearTimeout(t)
  }, [text])

  const kind = KIND[tab]
  const lines = useApi(listCatalogLines, [], canRead)
  // Fichas simuladas sin filtros: dan el conteo de la pestaña y las familias del filtro.
  const allSimulated = useApi(() => listCatalogProducts({ data_kind: ['SYNTHETIC'] }), [], canRead)
  const products = useApi(
    () => listCatalogProducts({ data_kind: [kind], line: tab === 'real' ? line : undefined, family, q }),
    [kind, line, family, q],
    canRead,
  )

  // Al cambiar de pestaña, `products.data` aún trae las fichas de la pestaña anterior hasta que llega la respuesta.
  const cards = useMemo(() => products.data?.filter((p) => p.data_kind === kind), [products.data, kind])
  const stale = (products.data?.length ?? 0) > 0 && (cards?.length ?? 0) === 0

  const families = useMemo(() => {
    if (tab === 'simulado') {
      return Array.from(new Set((allSimulated.data ?? []).map((p) => p.family))).sort((a, b) => a.localeCompare(b, 'es'))
    }
    const scoped = (lines.data ?? []).filter((l) => !line || l.line === line)
    return Array.from(new Set(scoped.flatMap((l) => l.families))).sort((a, b) => a.localeCompare(b, 'es'))
  }, [tab, line, lines.data, allSimulated.data])

  if (!canRead) return <Forbidden permission="catalog.read" />

  const realCount = (lines.data ?? []).reduce((n, l) => n + l.product_count, 0)
  const tabs: TabDef[] = [
    { id: 'real', label: 'Catálogo Dipromedic (REAL)', count: lines.data ? realCount : null },
    { id: 'simulado', label: 'Variantes ficticias de escenarios (SIMULADO)', count: allSimulated.data?.length ?? null },
  ]

  const changeTab = (id: string) => {
    setTab(id as TabId)
    setLine('')
    setFamily('')
  }
  const changeLine = (value: string) => {
    setLine(value)
    setFamily('')
  }

  return (
    <div>
      <PageHeader
        title="Catálogo"
        description="Productos del catálogo público de Dipromedic con la cita textual de cada atributo técnico. Un dato que el sitio no publica se muestra como no publicado; nunca se deduce del nombre."
      />

      <Tabs tabs={tabs} active={tab} onChange={changeTab} idPrefix="catalogo">
        {tab === 'simulado' ? (
          <div
            role="note"
            className="hatch-synthetic-soft mb-4 flex items-start gap-3 rounded-md border border-amber-300 px-4 py-2.5 text-sm text-amber-950"
          >
            <FlaskConical aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              <strong className="font-semibold">{watermark}.</strong> Estas variantes sirven para los escenarios de
              demostración: sus precios, existencias y registros son ficticios y no representan el catálogo ni la
              capacidad real de Dipromedic.
            </span>
          </div>
        ) : (
          <p className="mb-4 text-sm text-slate-600">
            Contenido público de dipromedic.com. Precio, existencias y registro sanitario no vienen del sitio.
          </p>
        )}

        <section aria-label="Filtros" className="card mb-5 p-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label htmlFor="c-q" className="label">
                Producto o código
              </label>
              <input
                id="c-q"
                type="search"
                className="input"
                placeholder="Nombre o SKU (por ejemplo 198)"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </div>
            {tab === 'real' && (
              <div>
                <label htmlFor="c-line" className="label">
                  Línea
                </label>
                <select id="c-line" className="input" value={line} onChange={(e) => changeLine(e.target.value)}>
                  <option value="">Todas</option>
                  {(lines.data ?? []).map((l) => (
                    <option key={l.line} value={l.line}>
                      {l.line} ({l.product_count})
                    </option>
                  ))}
                </select>
              </div>
            )}
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

        {products.error ? (
          <ErrorPanel error={products.error} onRetry={products.reload} />
        ) : !cards || (cards.length === 0 && (products.loading || stale)) ? (
          <LoadingBlock label="Cargando catálogo…" />
        ) : cards.length === 0 ? (
          <div className="card">
            <EmptyState title="Sin fichas para estos filtros">
              {tab === 'real' && !line && !family && !q
                ? 'Aún no hay un catálogo real importado en esta organización. El administrador puede importarlo al iniciar el servicio.'
                : 'Ajusta o limpia los filtros.'}
            </EmptyState>
          </div>
        ) : (
          <Results cards={cards} tab={tab} lineOrder={(lines.data ?? []).map((l) => l.line)} />
        )}
      </Tabs>
    </div>
  )
}
