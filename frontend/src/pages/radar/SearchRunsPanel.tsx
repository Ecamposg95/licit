import { CircleAlert, CircleCheck, CircleX, Clock, History, LoaderCircle, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/badges'
import { DateTimeText } from '@/components/dates'
import { ErrorPanel } from '@/components/feedback'
import { errorCodeLabel, listSearchRuns, type SearchRun, type SearchRunStatus } from '@/lib/api-search'
import { formatDate } from '@/lib/format'
import { useApi } from '@/lib/useApi'

const STATUS: Record<SearchRunStatus, { label: string; icon: typeof Clock; className: string }> = {
  queued: { label: 'En cola', icon: Clock, className: 'border-slate-300 bg-slate-100 text-slate-700' },
  running: { label: 'En curso', icon: LoaderCircle, className: 'border-dpm-blue-200 bg-dpm-blue-50 text-dpm-blue-800' },
  done: { label: 'Terminada', icon: CircleCheck, className: 'border-emerald-300 bg-emerald-50 text-emerald-800' },
  partial: { label: 'Parcial', icon: CircleAlert, className: 'border-amber-300 bg-amber-50 text-amber-900' },
  failed: { label: 'Fallida', icon: CircleX, className: 'border-red-300 bg-red-50 text-red-800' },
}

export function SearchRunStatusBadge({ status }: { status: SearchRunStatus }) {
  const s = STATUS[status] ?? STATUS.queued
  return <Badge tone={s}>{s.label}</Badge>
}

function Counts({ run }: { run: SearchRun }) {
  const c = run.counts
  return (
    <span className="tabular-nums">
      {c.notes} notas · {c.procedures} proc. · <strong className="font-semibold text-slate-900">{c.new} nuevas</strong>
      {' · '}
      {c.updated} actualizadas · {c.unchanged} sin cambios
    </span>
  )
}

/** Historial plegable de corridas: hora, términos, estado y conteos (las 20 más recientes). */
export default function SearchRunsPanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const runs = useApi(listSearchRuns, [refreshKey])
  const items = runs.data ?? []
  return (
    <details className="group rounded-lg border border-slate-200 bg-white">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50">
        <History aria-hidden="true" className="h-4 w-4 text-slate-500" />
        Historial de búsquedas
        {runs.data && <span className="text-xs font-normal text-slate-500">({items.length})</span>}
        <span className="ml-auto text-xs font-normal text-slate-500 group-open:hidden">Mostrar</span>
        <span className="ml-auto hidden text-xs font-normal text-slate-500 group-open:inline">Ocultar</span>
      </summary>
      <div className="border-t border-slate-200 px-4 py-3">
        {runs.error ? (
          <ErrorPanel error={runs.error} onRetry={runs.reload} title="No se pudo cargar el historial" />
        ) : runs.loading && !runs.data ? (
          <p className="text-sm text-slate-500">Cargando…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-slate-500">Todavía no se ha lanzado ninguna búsqueda en vivo.</p>
        ) : (
          <>
            <div className="mb-2 flex justify-end">
              <button type="button" className="btn-ghost py-1 text-xs" onClick={runs.reload}>
                <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
                Actualizar
              </button>
            </div>
            <ul className="divide-y divide-slate-100">
              {items.map((run) => (
                <li key={run.id} className="py-2 text-xs text-slate-600">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="font-medium text-slate-800">
                      SIDOF · <DateTimeText value={run.started_at ?? run.created_at} />
                    </span>
                    <SearchRunStatusBadge status={run.status} />
                    <Counts run={run} />
                  </div>
                  <div className="mt-0.5">
                    {run.query.terms.map((t) => `«${t}»`).join(', ')} · del {formatDate(run.query.date_from)} al{' '}
                    {formatDate(run.query.date_to)}
                    {run.created_by && <> · {run.created_by.full_name}</>}
                  </div>
                  {run.errors.length > 0 && (
                    <div className="mt-0.5 text-amber-900">
                      {run.errors.length} {run.errors.length === 1 ? 'aviso' : 'avisos'}:{' '}
                      {Array.from(new Set(run.errors.map((e) => errorCodeLabel(e.code)))).join(', ')}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </details>
  )
}
