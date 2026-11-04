import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  CalendarClock,
  CircleAlert,
  CircleCheck,
  Clock,
  ExternalLink,
  Hourglass,
  LoaderCircle,
  RefreshCw,
  SearchX,
  TriangleAlert,
} from 'lucide-react'
import TasksTable from '@/components/TasksTable'
import TriageDialog, { type TriageAction } from '@/components/TriageDialog'
import { DateTimeText } from '@/components/dates'
import { EmptyState, ErrorMeta, ErrorPanel, Forbidden, LoadingBlock } from '@/components/feedback'
import { getOpportunity, toApiError, type ApiError } from '@/lib/api'
import {
  getHoy,
  startSweep,
  type HoyNewItem,
  type HoyOut,
  type HoyScope,
  type KeyDateKind,
  type SweepOut,
} from '@/lib/api-hoy'
import { newIdempotencyKey } from '@/lib/api-search'
import { formatDateTime, formatInstantDate, getDisplayTimeZone, parseInstant, todayInDisplayTz } from '@/lib/format'
import { useApi } from '@/lib/useApi'
import type { OpportunityDetail } from '@/lib/types'
import { useAuth, useCan } from '@/store/auth'

/** Mientras el barrido está en cola o en curso, el tablero se vuelve a pedir cada tanto. */
const POLL_MS = 5000

// ── Utilidades de fecha (zona de visualización) ──────────────────────────────

function dayOf(value: string): string {
  const d = parseInstant(value)
  if (!d) return value.slice(0, 10)
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: getDisplayTimeZone(),
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(d)
  const get = (t: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === t)?.value ?? '00'
  return `${get('year')}-${get('month')}-${get('day')}`
}

function timeOf(value: string | null | undefined): string | null {
  if (!value) return null
  const d = parseInstant(value)
  if (!d) return null
  return new Intl.DateTimeFormat('es-MX', {
    timeZone: getDisplayTimeZone(),
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(d)
}

function greeting(): string {
  const h = Number(
    new Intl.DateTimeFormat('en-US', { timeZone: getDisplayTimeZone(), hour: 'numeric', hourCycle: 'h23' }).format(new Date()),
  )
  if (h < 12) return 'Buenos días'
  if (h < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

/** «Detectada hoy» o «Detectada el 2 nov 2026». */
function detectedText(createdAt: string): string {
  if (dayOf(createdAt) === todayInDisplayTz()) return 'Detectada hoy'
  return `Detectada el ${formatInstantDate(createdAt) ?? createdAt}`
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

// ── Estado del barrido ───────────────────────────────────────────────────────

type Tone = 'ok' | 'warn' | 'bad' | 'info'

const TONE_CLASS: Record<Tone, string> = {
  ok: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  warn: 'border-amber-300 bg-amber-50 text-amber-950',
  bad: 'border-red-200 bg-red-50 text-red-900',
  info: 'border-slate-200 bg-slate-50 text-slate-800',
}

const TONE_ICON = {
  ok: CircleCheck,
  warn: TriangleAlert,
  bad: CircleAlert,
  info: Hourglass,
} as const

function sweepCounts(s: SweepOut): string {
  const notes = s.counts.notes ?? 0
  const fresh = s.counts.new ?? 0
  return `${plural(notes, 'nota', 'notas')} · ${plural(fresh, 'nueva', 'nuevas')}`
}

function sweepWhen(s: SweepOut): string {
  const at = s.finished_at ?? s.started_at
  if (!at) return ''
  return dayOf(at) === todayInDisplayTz() ? `de hoy ${timeOf(at)}` : `del ${formatDateTime(at)}`
}

function firstError(s: SweepOut): string {
  const e = s.errors[0]
  return (e?.message || 'sin detalle').replace(/[.\s]+$/, '')
}

function describeSweep(last: SweepOut | null, pending: boolean): { tone: Tone; title: string; detail?: ReactNode } {
  if (!last) {
    return pending
      ? { tone: 'warn', title: 'Barrido de hoy pendiente', detail: 'Ya pasó la hora del barrido diario y todavía no corre.' }
      : { tone: 'info', title: 'Todavía no se ha barrido el DOF' }
  }
  if (last.status === 'queued' || last.status === 'running') {
    return {
      tone: 'warn',
      title: last.status === 'queued' ? 'Barrido pendiente: en cola' : 'Barrido en curso',
      detail: last.terms.length ? `${plural(last.terms.length, 'término', 'términos')} por revisar en SIDOF.` : undefined,
    }
  }
  if (last.status === 'failed') {
    return {
      tone: 'bad',
      title: `El barrido ${sweepWhen(last)} falló: ${firstError(last)}`,
      detail: 'Esto no significa que no haya licitaciones nuevas.',
    }
  }
  if (last.status === 'partial') {
    const failedTerms = last.errors.map((e) => e.term).filter((t): t is string => !!t)
    return {
      tone: 'warn',
      title: `Barrido ${sweepWhen(last)} incompleto · ${sweepCounts(last)}`,
      detail: failedTerms.length
        ? `No se revisaron: ${Array.from(new Set(failedTerms)).join(', ')}. ${firstError(last)}.`
        : `${firstError(last)}.`,
    }
  }
  const title = `Barrido ${sweepWhen(last)} · ${sweepCounts(last)}`
  if (pending) {
    return { tone: 'warn', title: 'Barrido de hoy pendiente', detail: `El último: ${title.replace(/^Barrido /, '')}.` }
  }
  return { tone: 'ok', title }
}

function SweepStatus({ data, onStarted }: { data: HoyOut; onStarted: () => void }) {
  const canRun = useCan('search.run')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const { last, scheduled_pending } = data.sweep
  const running = last?.status === 'queued' || last?.status === 'running'
  const { tone, title, detail } = describeSweep(last, scheduled_pending)
  const Icon = running ? LoaderCircle : TONE_ICON[tone]

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      await startSweep(newIdempotencyKey())
      onStarted()
    } catch (e) {
      setError(toApiError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="estado-barrido" className={`mb-4 rounded-lg border px-4 py-3 ${TONE_CLASS[tone]}`}>
      <h2 id="estado-barrido" className="sr-only">
        Estado del barrido en el DOF
      </h2>
      <div className="flex flex-wrap items-start gap-3">
        <Icon aria-hidden="true" className={`mt-0.5 h-5 w-5 shrink-0 ${running ? 'animate-spin' : ''}`} />
        <div className="min-w-0 flex-1" aria-live="polite">
          <p className="font-medium">{title}</p>
          {detail && <p className="mt-0.5 text-sm">{detail}</p>}
          {last && last.dropped_terms.length > 0 && (
            <p className="mt-0.5 text-sm">
              {plural(last.dropped_terms.length, 'término quedó', 'términos quedaron')} fuera por el tope de 30 por
              barrido: {last.dropped_terms.join(', ')}.
            </p>
          )}
          {error && (
            <div role="alert" className="mt-1 text-sm text-red-900">
              <p>No se pudo iniciar el barrido: {error.message}</p>
              <ErrorMeta error={error} />
            </div>
          )}
        </div>
        {canRun && (
          <button type="button" className="btn-secondary shrink-0 py-1.5" onClick={run} disabled={busy || running}>
            <RefreshCw aria-hidden="true" className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} />
            Volver a barrer
          </button>
        )}
      </div>
    </section>
  )
}

// ── Indicadores ──────────────────────────────────────────────────────────────

function Kpi({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="card px-4 py-3">
      <dt className="text-xs font-medium text-slate-600">{label}</dt>
      <dd className="mt-1 text-3xl font-semibold tabular-nums tracking-tight text-slate-900">{value}</dd>
      {hint && <dd className="mt-0.5 text-xs text-slate-500">{hint}</dd>}
    </div>
  )
}

function Kpis({ data }: { data: HoyOut }) {
  const k = data.kpis
  const failed = data.sweep.last?.status === 'failed'
  const team = data.scope === 'team'
  return (
    <section aria-labelledby="indicadores" className="mb-6">
      <h2 id="indicadores" className="sr-only">
        Indicadores
      </h2>
      {data.kpis_warning && (
        <div role="note" className="mb-2 flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          <TriangleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <strong className="font-semibold">
              {failed ? 'El barrido falló' : 'El barrido quedó incompleto'}: estas cifras pueden estar incompletas
            </strong>
            <span className="block text-amber-900">{data.kpis_warning}</span>
          </span>
        </div>
      )}
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Kpi label="Nuevas en 24 h" value={k.new_24h} hint="Procedimientos reales detectados" />
        <Kpi label="Sin clasificar" value={k.unclassified} hint="Nuevas de toda la organización" />
        <Kpi label="Sin clasificar en mi territorio" value={k.unclassified_mine} hint="Coinciden con tus búsquedas" />
        <Kpi
          label="Presentan en ≤ 7 días"
          value={k.submitting_7d}
          hint={team ? 'Que sigue el equipo' : 'Que sigues tú'}
        />
        <Kpi label="Mis tareas vencidas" value={k.my_overdue_tasks} hint="Solo actividades reales" />
      </dl>
    </section>
  )
}

// ── Nuevas ───────────────────────────────────────────────────────────────────

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: { id: T; label: string; count?: number }[]
  onChange: (v: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-full border border-slate-300 bg-surface p-0.5">
      {options.map((o) => {
        const on = o.id === value
        return (
          <button
            key={o.id}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(o.id)}
            className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
              on ? 'bg-brand text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            {o.label}
            {o.count !== undefined && <span className="ml-1.5 tabular-nums opacity-80">{o.count}</span>}
          </button>
        )
      })}
    </div>
  )
}

function NewRow({
  item,
  meId,
  canTriage,
  onTriage,
}: {
  item: HoyNewItem
  meId: string | undefined
  canTriage: boolean
  onTriage: (item: HoyNewItem, action: TriageAction) => void
}) {
  const where = [item.buyer, item.state].filter(Boolean).join(' · ')
  return (
    <li className="flex flex-wrap items-start gap-x-4 gap-y-2 px-4 py-3">
      <span className="mt-2 w-2 shrink-0" aria-hidden={!item.is_new_since_visit}>
        {item.is_new_since_visit && (
          <>
            <span aria-hidden="true" className="block h-2 w-2 rounded-full bg-brand" title="Nueva desde tu visita" />
            <span className="sr-only">Nueva desde tu visita.</span>
          </>
        )}
      </span>
      <div className="min-w-0 flex-1 basis-80">
        <p className="break-all text-xs font-medium text-slate-500 tabular-nums">{item.external_id}</p>
        <Link
          to={`/oportunidades/${item.id}`}
          className="line-clamp-2 font-medium text-slate-900 underline-offset-2 hover:text-petrol-700 hover:underline"
          title={item.title}
        >
          {item.title}
        </Link>
        {where && <p className="mt-0.5 text-[13px] text-slate-600">{where}</p>}
        <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
          <span>{detectedText(item.created_at)}</span>
          {item.published_at && <span>DOF: {formatInstantDate(item.published_at)}</span>}
        </p>
        {item.matched.length > 0 && (
          <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label="Búsquedas guardadas que coinciden">
            {item.matched.map((m) => (
              <li
                key={m.id}
                className="rounded-full border border-petrol-200 bg-petrol-50 px-2 py-px text-xs text-petrol-800"
              >
                {m.name}
                {m.owner && m.owner.id !== meId && <span className="text-petrol-700"> · {m.owner.full_name}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        {canTriage && (
          <>
            <button type="button" className="btn-secondary py-1.5" onClick={() => onTriage(item, 'seguir')}>
              Seguir
            </button>
            <button type="button" className="btn-secondary py-1.5" onClick={() => onTriage(item, 'descartar')}>
              Descartar
            </button>
          </>
        )}
        <Link to={`/oportunidades/${item.id}`} className="btn-ghost py-1.5">
          Abrir
          <ExternalLink aria-hidden="true" className="h-3.5 w-3.5" />
        </Link>
      </div>
    </li>
  )
}

function NewList({
  items,
  ...rest
}: {
  items: HoyNewItem[]
  meId: string | undefined
  canTriage: boolean
  onTriage: (item: HoyNewItem, action: TriageAction) => void
}) {
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((i) => (
        <NewRow key={i.id} item={i} {...rest} />
      ))}
    </ul>
  )
}

function Section({ id, title, aside, description, children }: {
  id: string
  title: string
  aside?: ReactNode
  description?: ReactNode
  children: ReactNode
}) {
  return (
    <section aria-labelledby={id} className="card mb-6 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <h2 id={id} className="font-semibold text-slate-900">
            {title}
          </h2>
          {description && <p className="mt-0.5 text-xs text-slate-600">{description}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  )
}

function emptyNewText(data: HoyOut): { title: string; body?: string } {
  const last = data.sweep.last
  if (!last) return { title: 'Todavía no se ha barrido el DOF', body: 'Sin un barrido no hay nuevas que mostrar.' }
  if (last.status === 'done') return { title: 'Sin nuevas en el DOF en los últimos 7 días' }
  if (last.status === 'queued' || last.status === 'running')
    return { title: 'No hay nuevas por clasificar', body: 'El barrido sigue en curso; las nuevas aparecerán aquí.' }
  // failed o partial: nunca «0 nuevas».
  return {
    title: 'No hay nuevas registradas',
    body: 'El último barrido no terminó bien: esto no significa que no haya licitaciones nuevas.',
  }
}

type Territory = 'mine' | 'all'

function NewSection({ data, onTriage }: { data: HoyOut; onTriage: (item: HoyNewItem, action: TriageAction) => void }) {
  const meId = useAuth((s) => s.me?.id)
  const canTriage = useCan('opportunity.write')
  const mineCount = data.new_items.filter((i) => i.mine).length
  const [tab, setTab] = useState<Territory>(mineCount > 0 ? 'mine' : 'all')
  const items = tab === 'mine' ? data.new_items.filter((i) => i.mine) : data.new_items
  const fresh = items.filter((i) => i.is_new_since_visit)
  const older = items.filter((i) => !i.is_new_since_visit)
  const listProps = { meId, canTriage, onTriage }
  const empty = emptyNewText(data)

  return (
    <Section
      id="nuevas"
      title="Nuevas"
      description="Procedimientos reales sin clasificar. El punto marca lo detectado desde tu última visita."
      aside={
        <Segmented<Territory>
          label="Filtrar nuevas"
          value={tab}
          onChange={setTab}
          options={[
            { id: 'mine', label: 'Mi territorio', count: mineCount },
            { id: 'all', label: 'Todas', count: data.new_items.length },
          ]}
        />
      }
    >
      {data.new_items.length === 0 ? (
        <EmptyState title={empty.title} icon={<SearchX className="h-8 w-8" strokeWidth={1.5} />}>
          {empty.body}
        </EmptyState>
      ) : items.length === 0 ? (
        <EmptyState title="Ninguna nueva coincide con tus búsquedas guardadas">
          Revisa la pestaña «Todas» o crea una búsqueda guardada en el Radar.
        </EmptyState>
      ) : (
        <>
          {fresh.length > 0 && <NewList items={fresh} {...listProps} />}
          {older.length > 0 && (
            <>
              <h3 className="border-y border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-600">
                Siguen sin clasificar
              </h3>
              <NewList items={older} {...listProps} />
            </>
          )}
        </>
      )}
    </Section>
  )
}

// ── Fechas clave ─────────────────────────────────────────────────────────────

const KEY_DATE_LABEL: Record<KeyDateKind, string> = {
  questions: 'Junta de aclaraciones',
  submission: 'Presentación de propuestas',
  ruling: 'Fallo',
}

function KeyDates({ data, onScope }: { data: HoyOut; onScope: (s: HoyScope) => void }) {
  return (
    <Section
      id="fechas-clave"
      title="Fechas clave · próximos 14 días"
      description="Juntas, presentaciones y fallos de las oportunidades reales que se siguen."
      aside={
        <Segmented<HoyScope>
          label="Alcance de las fechas clave"
          value={data.scope}
          onChange={onScope}
          options={[
            { id: 'mine', label: 'Solo las mías' },
            { id: 'team', label: 'Todo el equipo' },
          ]}
        />
      }
    >
      {data.key_dates.length === 0 ? (
        <EmptyState title="Sin fechas clave en los próximos 14 días" icon={<CalendarClock className="h-8 w-8" strokeWidth={1.5} />}>
          {data.scope === 'mine'
            ? 'Ninguna oportunidad que sigues tiene junta, presentación o fallo en este plazo.'
            : 'Ninguna oportunidad que sigue el equipo tiene junta, presentación o fallo en este plazo.'}
        </EmptyState>
      ) : (
        <ul className="divide-y divide-slate-100">
          {data.key_dates.map((d) => (
            <li key={`${d.opportunity.id}-${d.kind}`} className="flex flex-wrap items-start gap-x-4 gap-y-1 px-4 py-3">
              <div className="w-44 shrink-0 text-sm">
                <p className="font-medium text-slate-900">
                  <DateTimeText value={d.at} />
                </p>
                <p className="text-xs text-slate-600">{KEY_DATE_LABEL[d.kind] ?? d.kind}</p>
              </div>
              <div className="min-w-0 flex-1">
                <Link
                  to={`/oportunidades/${d.opportunity.id}`}
                  className="line-clamp-2 font-medium text-slate-900 underline-offset-2 hover:text-petrol-700 hover:underline"
                >
                  {d.opportunity.title}
                </Link>
                <p className="mt-0.5 text-[13px] text-slate-600">
                  <span className="tabular-nums">{d.opportunity.external_id}</span> · {d.opportunity.buyer}
                  {d.opportunity.owner && <> · Responsable: {d.opportunity.owner.full_name}</>}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}

// ── Mis pendientes ───────────────────────────────────────────────────────────

function MyTasks({ data }: { data: HoyOut }) {
  const watermark = useAuth((s) => s.meta?.watermark)
  const demo = data.my_tasks.some((t) => t.data_kind !== 'REAL')
  return (
    <Section
      id="mis-pendientes"
      title="Mis pendientes"
      description="Actividades asignadas a ti sin cerrar, por fecha de vencimiento."
      aside={
        <Link to="/pendientes" className="link text-sm">
          Ver todas
        </Link>
      }
    >
      {data.my_tasks.length === 0 ? (
        <EmptyState title="No tienes actividades abiertas" icon={<Clock className="h-8 w-8" strokeWidth={1.5} />} />
      ) : (
        <>
          <TasksTable tasks={data.my_tasks} />
          {demo && (
            <p className="hatch-synthetic-soft border-t border-amber-300 px-4 py-2 text-[11px] font-semibold tracking-wide text-amber-950">
              {watermark ?? 'DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN'} · Las actividades que no son
              reales no cuentan en los indicadores.
            </p>
          )}
        </>
      )}
    </Section>
  )
}

// ── Sin territorio ───────────────────────────────────────────────────────────

function Unassigned({ data, onTriage }: { data: HoyOut; onTriage: (item: HoyNewItem, action: TriageAction) => void }) {
  const meId = useAuth((s) => s.me?.id)
  const canTriage = useCan('opportunity.write')
  return (
    <Section
      id="sin-territorio"
      title="Sin territorio"
      description="No coinciden con ninguna búsqueda guardada. Asígnalas o crea una búsqueda"
      aside={<span className="text-sm tabular-nums text-slate-600">{plural(data.unassigned.length, 'nueva', 'nuevas')}</span>}
    >
      {data.unassigned.length === 0 ? (
        <EmptyState title="Ninguna nueva queda fuera de las búsquedas guardadas" />
      ) : (
        <NewList items={data.unassigned} meId={meId} canTriage={canTriage} onTriage={onTriage} />
      )}
    </Section>
  )
}

// ── Página ───────────────────────────────────────────────────────────────────

export default function Hoy() {
  const canRead = useCan('opportunity.read')
  const me = useAuth((s) => s.me)
  const [scope, setScope] = useState<HoyScope | undefined>(undefined)
  const hoy = useApi(() => getHoy(scope), [scope], canRead)
  const [triageTarget, setTriageTarget] = useState<{ detail: OpportunityDetail; action: TriageAction } | null>(null)
  const [opening, setOpening] = useState<string | null>(null)
  const [openError, setOpenError] = useState<ApiError | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const status = hoy.data?.sweep.last?.status
  const sweeping = status === 'queued' || status === 'running'
  const { reload } = hoy
  // `hoy.error` también re-arma la espera: un sondeo fallido no detiene los siguientes.
  useEffect(() => {
    if (!sweeping) return
    const t = window.setTimeout(reload, POLL_MS)
    return () => window.clearTimeout(t)
  }, [sweeping, reload, hoy.data, hoy.error])

  const firstName = useMemo(() => (me?.full_name ?? '').split(/\s+/)[0], [me?.full_name])

  if (!canRead) return <Forbidden permission="opportunity.read" />

  // El diálogo necesita la versión vigente: se pide el detalle antes de abrirlo.
  const openTriage = async (item: HoyNewItem, action: TriageAction) => {
    setOpening(item.id)
    setOpenError(null)
    setNotice(null)
    try {
      setTriageTarget({ detail: await getOpportunity(item.id), action })
    } catch (e) {
      setOpenError(toApiError(e))
    } finally {
      setOpening(null)
    }
  }

  const data = hoy.data

  return (
    <div>
      <header className="mb-5">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {greeting()}
          {firstName ? `, ${firstName}` : ''}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          {data ? (
            data.last_visit ? (
              <>
                Última visita: <DateTimeText value={data.last_visit} />
              </>
            ) : (
              'Sin visita anterior registrada: todo lo pendiente cuenta como nuevo.'
            )
          ) : (
            'Lo nuevo en el DOF, lo que falta clasificar y lo que vence.'
          )}
        </p>
      </header>

      {hoy.error && !data && <ErrorPanel error={hoy.error} onRetry={hoy.reload} />}
      {hoy.error && data && (
        <div className="mb-4">
          <ErrorPanel
            error={hoy.error}
            onRetry={hoy.reload}
            title="No se pudo actualizar el tablero: las cifras y listas pueden estar desactualizadas"
          />
        </div>
      )}
      {!data && !hoy.error && <LoadingBlock label="Cargando el tablero…" />}

      {data && (
        <>
          <SweepStatus data={data} onStarted={hoy.reload} />
          <Kpis data={data} />

          <div aria-live="polite" className="empty:hidden">
            {notice && (
              <p className="mb-4 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                {notice}
              </p>
            )}
            {opening && (
              <p className="mb-4 flex items-center gap-2 text-sm text-slate-600">
                <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
                Abriendo la oportunidad…
              </p>
            )}
          </div>
          {openError && (
            <div className="mb-4">
              <ErrorPanel error={openError} title="No se pudo abrir la oportunidad" />
            </div>
          )}

          <NewSection data={data} onTriage={openTriage} />
          <KeyDates data={data} onScope={setScope} />
          <MyTasks data={data} />
          <Unassigned data={data} onTriage={openTriage} />
        </>
      )}

      <TriageDialog
        opportunity={triageTarget?.detail ?? null}
        action={triageTarget?.action ?? 'seguir'}
        onDone={(updated) => {
          setTriageTarget(null)
          if (updated) {
            setNotice(
              updated.triage_status === 'siguiendo'
                ? `«${updated.external_id}» pasó a Siguiendo con ${updated.owner?.full_name ?? 'responsable'}.`
                : `«${updated.external_id}» se descartó. Sigue registrada con su motivo.`,
            )
            hoy.reload()
          }
        }}
      />
    </div>
  )
}
