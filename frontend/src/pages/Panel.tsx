import { Link } from 'react-router-dom'
import { CircleAlert, SearchX } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import { Badge, DataKindBadge, DerivedBadge } from '@/components/badges'
import { DateTimeText, SubmissionDate } from '@/components/dates'
import { EmptyState, ErrorPanel, LoadingBlock, TableSkeleton } from '@/components/feedback'
import {
  getDirectionDashboard,
  type DirectionDashboard,
  type KindSummary,
  type SearchRunBrief,
} from '@/lib/api-governance'
import { DATA_KIND_HINT, humanize } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import type { DataKind } from '@/lib/types'
import { useAuth } from '@/store/auth'

/** Estados derivados (`Derived.code`) tal como los define el backend en `services/status.py`. */
const STATE_LABEL: Record<string, string> = {
  abierta_verificada: 'Abierta verificada',
  por_verificar: 'Por verificar',
  desactualizada: 'Desactualizada',
  fuente_inaccesible: 'Fuente inaccesible',
  fecha_transcurrida: 'Fecha de presentación transcurrida',
  historica: 'Referencia histórica',
  simulada: 'Escenario simulado',
}

const COLUMNS: { kind: DataKind; title: string; empty: string }[] = [
  {
    kind: 'REAL',
    title: 'Reales',
    empty: 'Todavía no hay procedimientos reales. Se obtienen consultando fuentes oficiales desde el Radar.',
  },
  { kind: 'HISTORICAL', title: 'Históricos', empty: 'No hay referencias históricas.' },
  { kind: 'SYNTHETIC', title: 'Simulados', empty: 'No hay escenarios simulados. Reinicia el demo desde Operación.' },
]

const BAR: Record<DataKind, string> = {
  REAL: 'bg-dpm-blue',
  HISTORICAL: 'bg-slate-400',
  // El rayado ámbar es la marca exclusiva de lo ficticio.
  SYNTHETIC: 'hatch-synthetic',
}

function KindColumn({ kind, title, empty, summary }: { kind: DataKind; title: string; empty: string; summary: KindSummary }) {
  const watermark = useAuth((s) => s.meta?.watermark)
  const states = Object.entries(summary.por_estado).sort((a, b) => b[1] - a[1])
  const synthetic = kind === 'SYNTHETIC'
  return (
    <section aria-labelledby={`kind-${kind}`} className="card relative flex flex-col overflow-hidden">
      {synthetic && <span aria-hidden="true" className="hatch-synthetic absolute inset-x-0 top-0 h-2" />}
      <div className="flex-1 px-4 pb-4 pt-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id={`kind-${kind}`} className="font-semibold text-slate-900">
            {title}
          </h2>
          <DataKindBadge kind={kind} />
        </div>
        <p className="mt-1 text-xs text-slate-600">{DATA_KIND_HINT[kind]}</p>
        <p className="mt-4 flex items-baseline gap-2">
          <span className="text-4xl font-semibold tabular-nums tracking-tight text-slate-900">{summary.total}</span>
          <span className="text-sm text-slate-600">{summary.total === 1 ? 'procedimiento' : 'procedimientos'}</span>
        </p>
        {summary.total === 0 ? (
          <p className="mt-3 text-sm text-slate-600">{empty}</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {states.map(([code, count]) => (
              <li key={code}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="text-slate-800">{STATE_LABEL[code] ?? humanize(code)}</span>
                  <span className="font-semibold tabular-nums text-slate-900">{count}</span>
                </div>
                {/* La barra compara estados dentro del mismo tipo de dato; nunca contra otro tipo. */}
                <div aria-hidden="true" className="mt-1 h-1.5 rounded-full bg-slate-100">
                  <div className={`h-full rounded-full ${BAR[kind]}`} style={{ width: `${(count / summary.total) * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      {synthetic && (
        <p className="hatch-synthetic-soft border-t border-amber-300 px-4 py-2 text-[11px] font-semibold tracking-wide text-amber-950">
          {watermark ?? 'DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN'}
        </p>
      )}
    </section>
  )
}

function UpcomingReal({ rows }: { rows: DirectionDashboard['upcoming_real'] }) {
  return (
    <section aria-labelledby="proximas" className="card overflow-hidden">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 id="proximas" className="font-semibold text-slate-900">
          Próximas oportunidades reales verificadas
        </h2>
        <p className="mt-0.5 text-xs text-slate-600">
          Solo procedimientos consultados en una fuente oficial, con fecha de presentación futura y comprobación reciente.
          Los escenarios simulados con fecha futura no cuentan aquí.
        </p>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No hay oportunidades reales abiertas verificadas en este momento" icon={<SearchX className="h-8 w-8" strokeWidth={1.5} />}>
          Eso no significa que no existan procedimientos: puede que nadie haya consultado las fuentes oficiales o que la
          última consulta no haya respondido.
        </EmptyState>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="table-base min-w-[760px]">
            <caption className="sr-only">Próximas oportunidades reales verificadas, por fecha de presentación</caption>
            <thead>
              <tr>
                <th scope="col">Procedimiento</th>
                <th scope="col">Presentación</th>
                <th scope="col">Última comprobación</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => (
                <tr key={o.id}>
                  <td className="min-w-[260px]">
                    <Link
                      to={`/oportunidades/${o.id}`}
                      className="font-medium text-slate-900 underline-offset-2 hover:text-petrol-700 hover:underline"
                    >
                      {o.title}
                    </Link>
                    <div className="mt-0.5 text-[13px] text-slate-600">
                      {o.buyer} · <span className="tabular-nums">{o.external_id}</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap">
                    <SubmissionDate value={o.submission_at} precision={o.submission_precision} sourceTimezone={null} />
                  </td>
                  <td className="whitespace-nowrap">
                    <DateTimeText value={o.last_checked_at} empty="Sin comprobar" />
                  </td>
                  <td>
                    <DerivedBadge derived={o.derived} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

const SEARCH_STATUS: Record<string, string> = {
  queued: 'En cola',
  running: 'En curso',
  done: 'Completada',
  partial: 'Parcial: algún término falló',
  failed: 'Fallida',
}

function describe(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (typeof value === 'object') {
    const o = value as Record<string, unknown>
    const text = ['message', 'error', 'detail'].map((k) => o[k]).find((v) => typeof v === 'string')
    const where = ['term', 'source', 'key'].map((k) => o[k]).find((v) => typeof v === 'string')
    if (text) return where ? `${where}: ${text}` : String(text)
    return JSON.stringify(value)
  }
  return String(value)
}

function LastSearch({ run }: { run: SearchRunBrief | null }) {
  const problem = run && (run.status === 'failed' || run.status === 'partial' || run.errors.length > 0)
  return (
    <section aria-labelledby="ultima-busqueda" className="card">
      <h2 id="ultima-busqueda" className="border-b border-slate-200 px-4 py-3 font-semibold text-slate-900">
        Última búsqueda en fuentes oficiales
      </h2>
      {run === null ? (
        <p className="px-4 py-5 text-sm text-slate-600">
          Todavía no se ha ejecutado ninguna búsqueda. Sin una búsqueda no hay cifras reales que mostrar, y eso no
          equivale a que no existan procedimientos.
        </p>
      ) : (
        <div className="space-y-3 px-4 py-4 text-sm">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
            <div>
              <dt className="text-xs text-slate-500">Resultado</dt>
              <dd className="mt-0.5 font-medium text-slate-900">{SEARCH_STATUS[run.status] ?? humanize(run.status)}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Inicio</dt>
              <dd className="mt-0.5 text-slate-900">
                <DateTimeText value={run.started_at} empty="Sin iniciar" />
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Fin</dt>
              <dd className="mt-0.5 text-slate-900">
                <DateTimeText value={run.finished_at} empty="Sin terminar" />
              </dd>
            </div>
            {Object.entries(run.counts).map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-slate-500">{humanize(k)}</dt>
                <dd className="mt-0.5 font-semibold tabular-nums text-slate-900">{describe(v)}</dd>
              </div>
            ))}
          </dl>
          {run.errors.length > 0 && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-900">
              <p className="flex items-center gap-1.5 font-medium">
                <CircleAlert aria-hidden="true" className="h-4 w-4" />
                Errores de la búsqueda
              </p>
              <ul className="mt-1 list-disc pl-5 text-xs">
                {run.errors.map((e, i) => (
                  <li key={i}>{describe(e)}</li>
                ))}
              </ul>
            </div>
          )}
          {problem && (
            <p className="text-xs text-slate-600">Una búsqueda fallida o parcial no significa que no existan procedimientos.</p>
          )}
        </div>
      )}
    </section>
  )
}

function ScenariosAtRisk({ rows }: { rows: DirectionDashboard['scenarios_at_risk'] }) {
  const watermark = useAuth((s) => s.meta?.watermark)
  return (
    <section aria-labelledby="riesgo" className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <h2 id="riesgo" className="font-semibold text-slate-900">
          Escenarios simulados en riesgo
        </h2>
        <DataKindBadge kind="SYNTHETIC" />
      </div>
      <p className="hatch-synthetic-soft border-b border-amber-300 px-4 py-2 text-[11px] font-semibold tracking-wide text-amber-950">
        {watermark ?? 'DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN'}
      </p>
      {rows.length === 0 ? (
        <p className="px-4 py-5 text-sm text-slate-600">
          Ningún escenario simulado tiene requisitos obligatorios que incumplan, falten o estén vencidos.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {rows.map((r) => (
            <li key={r.opportunity_id} className="relative px-4 py-3 pl-5">
              <span aria-hidden="true" className="hatch-synthetic absolute inset-y-0 left-0 w-1" />
              <Link
                to={`/oportunidades/${r.opportunity_id}`}
                className="text-sm font-medium text-slate-900 underline-offset-2 hover:text-petrol-700 hover:underline"
              >
                {r.title}
              </Link>
              <div className="mt-0.5 text-xs tabular-nums text-slate-600">{r.external_id}</div>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-slate-600">Bloqueantes:</span>
                {r.blocking.map((code) => (
                  <Badge key={code} tone={{ icon: CircleAlert, className: 'border-red-300 bg-red-50 text-red-800' }}>
                    {code}
                  </Badge>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function Panel() {
  const dash = useApi(getDirectionDashboard, [])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Panel de dirección"
        description="Cartera por tipo de dato y riesgos de los expedientes. Los conteos nunca se suman entre tipos: lo simulado no se mezcla con lo real."
      />
      {dash.error && <ErrorPanel error={dash.error} onRetry={dash.reload} />}
      {!dash.data && !dash.error && (
        <>
          <LoadingBlock label="Cargando el panel…" />
          <TableSkeleton rows={3} cols={4} />
        </>
      )}
      {dash.data && (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            {COLUMNS.map((c) => (
              <KindColumn
                key={c.kind}
                kind={c.kind}
                title={c.title}
                empty={c.empty}
                summary={dash.data!.by_data_kind[c.kind] ?? { total: 0, por_estado: {} }}
              />
            ))}
          </div>
          <UpcomingReal rows={dash.data.upcoming_real} />
          <div className="grid gap-4 lg:grid-cols-2">
            <LastSearch run={dash.data.last_search} />
            <ScenariosAtRisk rows={dash.data.scenarios_at_risk} />
          </div>
        </>
      )}
    </div>
  )
}
