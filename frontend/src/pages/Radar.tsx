import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ExternalLink, FileUp, RotateCcw, Search, SearchX } from 'lucide-react'
import PageHeader, { Pagination } from '@/components/PageHeader'
import DataKindChips, { usePersistentDataKinds } from '@/components/DataKindChips'
import Tooltip, { UnavailableAction } from '@/components/Tooltip'
import { DataKindBadge, DerivedBadge, SourceStatusBadge } from '@/components/badges'
import { DateTimeText, SubmissionDate, TimezoneNote } from '@/components/dates'
import { EmptyState, ErrorPanel, TableSkeleton } from '@/components/feedback'
import { listOpportunities, listProducts, listSources } from '@/lib/api'
import { MX_STATES, procedureTypeLabel } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import type { OpportunityRow, SourceOut } from '@/lib/types'

const PAGE_SIZE = 25
/** Familias del diccionario inicial (task pack §6); se amplían con el catálogo y los resultados. */
const BASE_FAMILIES = ['Osteosíntesis', 'Endoprótesis', 'Instrumental']

function SourceCoverage({ sources }: { sources: SourceOut[] }) {
  const official = sources.filter((s) => s.method !== 'fixture')
  if (official.length === 0) return null
  const anyActive = official.some((s) => s.status === 'activa')
  return (
    <section aria-labelledby="cobertura" className="card mb-4 px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <h2 id="cobertura" className="text-xs font-semibold text-slate-700">
          Cobertura de fuentes
        </h2>
        {official.map((s) => (
          <span key={s.id} className="inline-flex items-center gap-2 text-sm text-slate-700">
            {s.name}
            <SourceStatusBadge status={s.status} />
          </span>
        ))}
      </div>
      {!anyActive && (
        <p className="mt-2 text-xs text-slate-600">
          Ninguna fuente oficial se ha consultado en vivo todavía. Los registros históricos provienen de resúmenes públicos
          capturados con su enlace; los escenarios son ficticios.
        </p>
      )}
    </section>
  )
}

function OpportunityRowView({ o }: { o: OpportunityRow }) {
  const synthetic = o.data_kind === 'SYNTHETIC'
  return (
    <tr className="hover:bg-slate-50/70">
      <td className="relative min-w-[220px]">
        {synthetic && <span aria-hidden="true" className="hatch-synthetic absolute inset-y-0 left-0 w-1" />}
        <Link
          to={`/oportunidades/${o.id}`}
          className="font-medium text-slate-900 underline-offset-2 hover:text-petrol-700 hover:underline"
        >
          {o.title}
        </Link>
        <div className="mt-0.5 text-[13px] text-slate-600">{o.buyer}</div>
        <div className="mt-1.5">
          <DataKindBadge kind={o.data_kind} />
        </div>
      </td>
      <td className="min-w-[140px] max-w-[165px]">
        <div className="break-all text-xs font-medium text-slate-800 tabular-nums">{o.external_id}</div>
        <div className="mt-0.5 text-xs text-slate-500">
          {o.procedure_type ? procedureTypeLabel(o.procedure_type) : 'Tipo no declarado'}
        </div>
      </td>
      <td className="min-w-[120px]">
        <div>{o.families.length ? o.families.join(', ') : <span className="muted">Sin familia</span>}</div>
        <div className="mt-0.5 text-xs text-slate-500">{o.state ?? 'Entidad no declarada'}</div>
      </td>
      <td className="whitespace-nowrap">
        <SubmissionDate value={o.submission_at} precision={o.submission_precision} />
      </td>
      <td className="min-w-[140px] max-w-[175px]">
        <DerivedBadge derived={o.derived} wrap />
      </td>
      <td className="min-w-[130px] text-xs">
        <div className="text-[13px] text-slate-800">{o.source?.name ?? <span className="muted">Sin fuente</span>}</div>
        <div className="mt-0.5 text-slate-500">
          {o.last_checked_at ? (
            <>
              Comprobado <DateTimeText value={o.last_checked_at} />
            </>
          ) : (
            'Sin comprobación registrada'
          )}
        </div>
        {o.source_url && (
          <a
            href={o.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-flex items-center gap-1 font-medium text-petrol-700 hover:underline"
          >
            Abrir fuente
            <ExternalLink aria-hidden="true" className="h-3 w-3" />
            <span className="sr-only">(se abre en una pestaña nueva)</span>
          </a>
        )}
      </td>
      <td className="text-center">
        <Tooltip content="Se calcula en el motor de correspondencia (E3)" focusable>
          <span className="text-slate-400">—</span>
        </Tooltip>
      </td>
      <td className="min-w-[100px]">{o.owner?.full_name ?? <span className="muted">Sin asignar</span>}</td>
      <td className="text-right tabular-nums">
        <span className={o.open_requirements > 0 ? 'font-semibold text-slate-900' : 'text-slate-400'}>
          {o.open_requirements}
        </span>
      </td>
    </tr>
  )
}

export default function Radar() {
  const [params, setParams] = useSearchParams()
  const [kinds, setKinds] = usePersistentDataKinds('licit.radar.dataKinds')
  const q = params.get('q') ?? ''
  const family = params.get('family') ?? ''
  const state = params.get('state') ?? ''
  const source = params.get('source') ?? ''
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const page = Math.max(1, Number(params.get('page')) || 1)

  const [text, setText] = useState(q)
  useEffect(() => setText(q), [q])

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  // Búsqueda de texto con espera breve para no consultar en cada tecla.
  useEffect(() => {
    if (text === q) return
    const t = window.setTimeout(() => setParam('q', text.trim()), 350)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text])

  const noKinds = kinds.length === 0
  const result = useApi(
    () =>
      listOpportunities({
        q,
        family,
        state,
        source,
        data_kind: kinds,
        period_from: from,
        period_to: to,
        page,
        page_size: PAGE_SIZE,
      }),
    [q, family, state, source, kinds.join(','), from, to, page],
    !noKinds,
  )
  const sources = useApi(listSources, [])
  const products = useApi(() => listProducts({}), [])

  const [seenFamilies, setSeenFamilies] = useState<string[]>([])
  useEffect(() => {
    const fams = result.data?.items.flatMap((o) => o.families) ?? []
    if (fams.length) setSeenFamilies((prev) => Array.from(new Set([...prev, ...fams])))
  }, [result.data])

  const familyOptions = useMemo(() => {
    const set = new Set([...BASE_FAMILIES, ...seenFamilies, ...(products.data?.map((p) => p.family) ?? [])])
    if (family) set.add(family)
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'es'))
  }, [seenFamilies, products.data, family])

  const stateOptions = useMemo(() => {
    const set = new Set(MX_STATES)
    if (state) set.add(state)
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'es'))
  }, [state])

  const hasFilters = !!(q || family || state || source || from || to)
  const clearFilters = () => {
    setText('')
    setParams(new URLSearchParams(), { replace: true })
  }

  const onlyReal = kinds.length === 1 && kinds[0] === 'REAL'

  return (
    <div>
      <PageHeader
        title="Radar de oportunidades"
        description="Procedimientos con su fuente y última comprobación. Los tipos de dato se filtran por separado y la selección se conserva."
        actions={
          <>
            <UnavailableAction
              label="Importar"
              icon={<FileUp aria-hidden="true" className="h-4 w-4" />}
              reason="Importación de URL o documento oficial: próxima entrega (E2)"
            />
            <UnavailableAction
              label="Buscar ahora"
              icon={<Search aria-hidden="true" className="h-4 w-4" />}
              reason="Búsqueda en vivo en DOF/SIDOF: próxima entrega (E2)"
            />
          </>
        }
      />

      {sources.data && <SourceCoverage sources={sources.data} />}

      <section aria-label="Filtros" className="card mb-4 p-4">
        <DataKindChips value={kinds} onChange={(k) => {
          setKinds(k)
          setParam('page', '')
        }} />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-[minmax(220px,2fr)_repeat(5,minmax(0,1fr))]">
          <div>
            <label htmlFor="f-q" className="label">
              Texto
            </label>
            <input
              id="f-q"
              type="search"
              className="input"
              placeholder="Objeto, clave o institución"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="f-family" className="label">
              Familia
            </label>
            <select id="f-family" className="input" value={family} onChange={(e) => setParam('family', e.target.value)}>
              <option value="">Todas</option>
              {familyOptions.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="f-state" className="label">
              Entidad
            </label>
            <select id="f-state" className="input" value={state} onChange={(e) => setParam('state', e.target.value)}>
              <option value="">Todas</option>
              {stateOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="f-source" className="label">
              Fuente
            </label>
            <select id="f-source" className="input" value={source} onChange={(e) => setParam('source', e.target.value)}>
              <option value="">Todas</option>
              {sources.data?.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="f-from" className="label">
              Presentación desde
            </label>
            <input
              id="f-from"
              type="date"
              className="input"
              value={from}
              max={to || undefined}
              onChange={(e) => setParam('from', e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="f-to" className="label">
              Presentación hasta
            </label>
            <input
              id="f-to"
              type="date"
              className="input"
              value={to}
              min={from || undefined}
              onChange={(e) => setParam('to', e.target.value)}
            />
          </div>
        </div>
        {hasFilters && (
          <button type="button" className="btn-ghost mt-3 text-xs" onClick={clearFilters}>
            <RotateCcw aria-hidden="true" className="h-3.5 w-3.5" />
            Limpiar filtros
          </button>
        )}
      </section>

      <section aria-label="Resultados" className="card overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-2.5 text-sm">
          <span className="text-slate-600" aria-live="polite">
            {noKinds
              ? 'Sin tipo de dato seleccionado'
              : result.loading
                ? 'Consultando…'
                : result.data
                  ? `${result.data.total} ${result.data.total === 1 ? 'resultado' : 'resultados'}`
                  : ''}
          </span>
          <TimezoneNote className="hidden text-xs text-slate-500 md:inline" />
        </div>

        {noKinds ? (
          <EmptyState title="Activa al menos un tipo de dato">
            Elige REAL, HISTÓRICO o SIMULADO para ver resultados.
          </EmptyState>
        ) : result.error ? (
          <div className="p-4">
            <ErrorPanel error={result.error} onRetry={result.reload} />
          </div>
        ) : result.loading && !result.data ? (
          <TableSkeleton cols={8} />
        ) : result.data && result.data.items.length === 0 ? (
          <EmptyState title="Sin resultados para estos filtros" icon={<SearchX className="h-8 w-8" strokeWidth={1.5} />}>
            {onlyReal
              ? 'No hay oportunidades reales registradas con estos filtros. La consulta en vivo a fuentes oficiales llega en la próxima entrega; no se muestran datos ficticios en su lugar.'
              : 'Ajusta o limpia los filtros. No se completan resultados con datos ficticios.'}
          </EmptyState>
        ) : result.data ? (
          <>
            <div className={`relative overflow-x-auto ${result.loading ? 'opacity-60' : ''}`}>
              <table className="table-base table-compact min-w-[1100px]">
                <caption className="sr-only">Oportunidades encontradas</caption>
                <thead>
                  <tr>
                    <th scope="col">Oportunidad e institución</th>
                    <th scope="col">Procedimiento</th>
                    <th scope="col">Familias y entidad</th>
                    <th scope="col">Presentación</th>
                    <th scope="col">Verificación</th>
                    <th scope="col">Fuente</th>
                    <th scope="col">Afinidad</th>
                    <th scope="col">Responsable</th>
                    <th scope="col" className="w-16 !whitespace-normal text-right">
                      Req. abiertos
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.data.items.map((o) => (
                    <OpportunityRowView key={o.id} o={o} />
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={result.data.page}
              pageSize={result.data.page_size}
              total={result.data.total}
              onPage={(p) => setParam('page', String(p))}
            />
          </>
        ) : null}
      </section>
    </div>
  )
}
