import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ExternalLink, FlaskConical, UserCheck } from 'lucide-react'
import Tabs, { type TabDef } from '@/components/Tabs'
import { Badge, DataKindBadge, DerivedBadge, SourceStatusBadge } from '@/components/badges'
import { DateTimeText } from '@/components/dates'
import { EmptyState, ErrorPanel, Forbidden, LoadingBlock } from '@/components/feedback'
import { getOpportunity } from '@/lib/api'
import { formatDateLong } from '@/lib/format'
import { useApi } from '@/lib/useApi'
import type { OpportunityDetail as Detail } from '@/lib/types'
import { useAuth, useCan } from '@/store/auth'
import SummaryTab from '@/pages/opportunity/SummaryTab'
import LotsTab from '@/pages/opportunity/LotsTab'
import RequirementsTab from '@/pages/opportunity/RequirementsTab'
import ExpedienteTab from '@/pages/opportunity/ExpedienteTab'
import { DocumentsTab, HistoryTab, TasksTab } from '@/pages/opportunity/RelatedTabs'
import WorkspacePanel from '@/pages/opportunity/WorkspacePanel'
import { getWorkspace } from '@/lib/api-workspace'

const TAB_IDS = ['resumen', 'partidas', 'requisitos', 'documentos', 'actividades', 'expediente', 'historial'] as const
type TabId = (typeof TAB_IDS)[number]

function Header({ o }: { o: Detail }) {
  const baseDate = useAuth((s) => s.meta?.demo_base_date)
  return (
    <header className="mb-5">
      <Link to="/radar" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-petrol-700">
        <ArrowLeft aria-hidden="true" className="h-4 w-4" />
        Radar
      </Link>

      {o.data_kind === 'SYNTHETIC' && (
        <div
          role="note"
          className="relative mt-3 flex items-center gap-3 overflow-hidden rounded-md border border-amber-300 bg-amber-50 py-2.5 pl-5 pr-4 text-sm text-amber-950"
        >
          <span aria-hidden="true" className="hatch-synthetic absolute inset-y-0 left-0 w-2" />
          <FlaskConical aria-hidden="true" className="h-4 w-4 shrink-0" />
          <span>
            <strong className="font-semibold">Escenario ficticio</strong> · fechas relativas a la fecha base{' '}
            <time dateTime={baseDate}>{formatDateLong(baseDate) ?? baseDate}</time>. No existe en ninguna fuente oficial.
          </span>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <DataKindBadge kind={o.data_kind} />
        <DerivedBadge derived={o.derived} />
        {o.requires_human_review && (
          <Badge tone={{ icon: UserCheck, className: 'border-slate-300 bg-white text-slate-700' }}>
            Requiere revisión humana
          </Badge>
        )}
      </div>
      <p className="mt-3 break-all text-sm font-medium text-slate-600 tabular-nums">{o.external_id}</p>
      <h1 className="mt-0.5 text-2xl font-semibold tracking-tight text-slate-900">{o.title}</h1>
      <p className="mt-1 text-[15px] text-slate-700">
        {o.buyer}
        {o.buying_unit && <span className="text-slate-500"> · {o.buying_unit}</span>}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-600">
        <span className="inline-flex items-center gap-2">
          Fuente: <span className="font-medium text-slate-800">{o.source?.name ?? 'Sin fuente'}</span>
          {o.source && <SourceStatusBadge status={o.source.status} />}
        </span>
        <span>
          Última comprobación: <DateTimeText value={o.last_checked_at} empty="sin registro" />
        </span>
        {o.source_url && (
          <a
            href={o.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-petrol-700 hover:underline"
          >
            Abrir fuente
            <ExternalLink aria-hidden="true" className="h-3.5 w-3.5" />
            <span className="sr-only">(se abre en una pestaña nueva)</span>
          </a>
        )}
      </div>
    </header>
  )
}

export default function OpportunityDetail() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const detail = useApi(() => getOpportunity(id), [id])
  const workspace = useApi(() => getWorkspace(id), [id])
  // Un cambio en la matriz o en el expediente actualiza el panel y los conteos del detalle.
  const refresh = () => {
    workspace.reload()
    detail.reload()
  }
  const canReqs = useCan('requirement.read')
  const canDocs = useCan('document.read')
  const canTasks = useCan('task.read')

  const raw = params.get('tab')
  const tab: TabId = (TAB_IDS as readonly string[]).includes(raw ?? '') ? (raw as TabId) : 'resumen'
  const setTab = (t: string) => {
    const next = new URLSearchParams(params)
    next.set('tab', t)
    setParams(next, { replace: true })
  }

  if (detail.error) {
    if (detail.error.status === 404) {
      return (
        <div className="card">
          <EmptyState title="Oportunidad no encontrada">
            Puede haberse eliminado al reiniciar el demo. <Link to="/radar" className="text-petrol-700 underline">Volver al radar</Link>
          </EmptyState>
        </div>
      )
    }
    return <ErrorPanel error={detail.error} onRetry={detail.reload} />
  }
  if (!detail.data) return <LoadingBlock label="Cargando oportunidad…" />

  const o = detail.data
  const reqTotal = Object.values(o.requirement_counts).reduce((a, b) => a + b, 0)
  const tabs: TabDef[] = [
    { id: 'resumen', label: 'Resumen' },
    { id: 'partidas', label: 'Partidas', count: o.lots.length },
    { id: 'requisitos', label: 'Requisitos', count: reqTotal },
    { id: 'documentos', label: 'Documentos' },
    { id: 'actividades', label: 'Actividades' },
    { id: 'expediente', label: 'Expediente' },
    { id: 'historial', label: 'Historial' },
  ]

  return (
    <div>
      <Header o={o} />
      {o.data_kind !== 'HISTORICAL' && (o.lots.length > 0 || reqTotal > 0) && (
        <div className="mb-5">
          <WorkspacePanel
            opportunityId={o.id}
            view={workspace}
            onChanged={refresh}
            onOpenRequirements={() => setTab('requisitos')}
          />
        </div>
      )}
      <Tabs tabs={tabs} active={tab} onChange={setTab} idPrefix="opp">
        {tab === 'resumen' && (
          <SummaryTab
            o={o}
            onSaved={detail.setData}
            onReload={detail.reload}
            reloading={detail.loading}
            onOpenRequirements={() => setTab('requisitos')}
            workspace={workspace.data}
            onOpenLots={() => setTab('partidas')}
          />
        )}
        {tab === 'partidas' && <LotsTab lots={o.lots} opportunityId={o.id} workspace={workspace} />}
        {tab === 'requisitos' &&
          (canReqs ? (
            <RequirementsTab opportunityId={o.id} opportunityDataKind={o.data_kind} onChanged={refresh} />
          ) : (
            <Forbidden permission="requirement.read" />
          ))}
        {tab === 'documentos' &&
          (canDocs ? <DocumentsTab opportunityId={o.id} /> : <Forbidden permission="document.read" />)}
        {tab === 'actividades' && (canTasks ? <TasksTab opportunityId={o.id} /> : <Forbidden permission="task.read" />)}
        {tab === 'expediente' &&
          (o.data_kind === 'HISTORICAL' ? (
            <div className="card">
              <EmptyState title="Las referencias históricas no se preparan como expediente">
                Este procedimiento ya pasó; sirve como referencia de precios, compradores y requisitos, no para generar
                borradores.
              </EmptyState>
            </div>
          ) : (
            <ExpedienteTab opportunityId={o.id} />
          ))}
        {tab === 'historial' && <HistoryTab opportunityId={o.id} version={o.version} />}
      </Tabs>
    </div>
  )
}
