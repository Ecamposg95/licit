import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ClipboardCheck,
  Cpu,
  Gavel,
  Info,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  UserCheck,
} from 'lucide-react'
import ConfirmDialog from '@/components/ConfirmDialog'
import { Badge, REQUIREMENT_STATUS } from '@/components/badges'
import { DateTimeText } from '@/components/dates'
import { ErrorMeta, ErrorPanel } from '@/components/feedback'
import { toApiError, type ApiError } from '@/lib/api'
import {
  approveWorkspace,
  assessWorkspace,
  decideWorkspace,
  markWorkspaceReady,
  readinessItems,
  workspaceErrorText,
  type Affinity,
  type AffinityKey,
  type ReadinessItem,
  type WorkspaceView,
} from '@/lib/api-workspace'
import type { ApiState } from '@/lib/useApi'
import type { UserRef } from '@/lib/types'
import { useAuth, useCan } from '@/store/auth'
import { AFFINITY_LABEL, BLOCKER_LABEL, DECISION_LABEL, PHASE_LABEL } from '@/pages/opportunity/matchLabels'

export const AFFINITY_LEGEND = 'La afinidad no es probabilidad de ganar ni dictamen de elegibilidad'
const ORDER: AffinityKey[] = ['familia', 'atributos', 'documental', 'capacidad']

function percent(score: number | null): string {
  return score === null ? 'sin datos' : `${Math.round(score * 100)} %`
}

function AffinityBars({ affinity }: { affinity: Affinity }) {
  return (
    <ul className="space-y-2.5">
      {ORDER.map((key) => {
        const c = affinity.components[key]
        if (!c) return null
        const width = c.score === null ? 0 : Math.max(0, Math.min(100, c.score * 100))
        return (
          <li key={key}>
            <div className="flex items-baseline justify-between gap-2 text-xs">
              <span className="font-medium text-slate-700">
                {AFFINITY_LABEL[key]} <span className="font-normal text-slate-500">· peso {c.weight}</span>
              </span>
              <span className="tabular-nums text-slate-600">
                {percent(c.score)} · conocidos {c.known} / {c.total}
              </span>
            </div>
            <div
              role="meter"
              aria-label={`${AFFINITY_LABEL[key]}: ${percent(c.score)}, conocidos ${c.known} de ${c.total}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={c.score === null ? undefined : Math.round(width)}
              className={`mt-1 h-2 overflow-hidden rounded-full ${c.score === null ? 'border border-dashed border-slate-300 bg-white' : 'bg-slate-100'}`}
            >
              <div className="h-full rounded-full bg-dpm-blue" style={{ width: `${width}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

function Who({ user, at, empty }: { user: UserRef | null; at: string | null; empty: string }) {
  if (!user) return <span className="muted">{empty}</span>
  return (
    <span>
      <span className="font-medium text-slate-900">{user.full_name}</span>
      <span className="block text-xs text-slate-500">
        <DateTimeText value={at} />
      </span>
    </span>
  )
}

function blockerText(code: string): string {
  return BLOCKER_LABEL[code] ?? code
}

interface Props {
  opportunityId: string
  view: ApiState<WorkspaceView>
  /** Se llama tras cualquier cambio del expediente (recarga detalle y matriz). */
  onChanged: () => void
  onOpenRequirements: () => void
}

/**
 * Panel del expediente en el encabezado del detalle: afinidad por componente con su cobertura, bloqueantes,
 * decisión, aprobaciones técnica y comercial (quién y cuándo) y la compuerta «Listo para revisión final».
 * El backend decide todo; aquí solo se muestra y se piden las acciones.
 */
export default function WorkspacePanel({ opportunityId, view, onChanged, onOpenRequirements }: Props) {
  const me = useAuth((s) => s.me)
  const canWrite = useCan('opportunity.write')
  const canReview = useCan('requirement.review')
  const canAssess = canWrite || canReview
  const canDecide = useCan('bid.decide')
  const canTechnical = canReview
  const canCommercial = useCan('pricing.approve')

  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [blockers, setBlockers] = useState<ReadinessItem[] | null>(null)
  const [decisionOpen, setDecisionOpen] = useState(false)
  const [decision, setDecision] = useState<'participar' | 'no_participar'>('participar')
  const [reason, setReason] = useState('')
  const [decisionError, setDecisionError] = useState<ApiError | null>(null)
  const [readyOk, setReadyOk] = useState(false)

  async function run(key: string, action: () => Promise<WorkspaceView>) {
    setBusy(key)
    setError(null)
    setReadyOk(false)
    if (key !== 'ready') setBlockers(null)
    try {
      const next = await action()
      view.setData(next)
      onChanged()
      return true
    } catch (e) {
      const err = toApiError(e)
      if (err.code === 'not_ready') setBlockers(readinessItems(err))
      else setError(err)
      return false
    } finally {
      setBusy(null)
    }
  }

  async function submitDecision() {
    setDecisionError(null)
    setBusy('decision')
    try {
      view.setData(await decideWorkspace(opportunityId, decision, reason))
      setDecisionOpen(false)
      onChanged()
    } catch (e) {
      setDecisionError(toApiError(e))
    } finally {
      setBusy(null)
    }
  }

  if (view.error) return <ErrorPanel error={view.error} onRetry={view.reload} title="No se pudo cargar el expediente" />
  if (!view.data) {
    return <div className="card h-40 animate-pulse bg-slate-50" role="status" aria-label="Cargando expediente" />
  }
  const { workspace: ws, affinity, assessments } = view.data
  const engine = assessments[0]
  const myOtherApproval = (kind: 'tecnica' | 'comercial') =>
    kind === 'tecnica' ? ws.commercial_approval_by?.id === me?.id : ws.technical_approval_by?.id === me?.id

  return (
    <section aria-labelledby="expediente-titulo" className="card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="expediente-titulo" className="text-sm font-semibold text-slate-900">
            Expediente
          </h2>
          <Badge
            tone={{
              icon: ws.phase === 'listo_revision_final' ? ShieldCheck : ClipboardCheck,
              className:
                ws.phase === 'listo_revision_final'
                  ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                  : 'border-slate-300 bg-white text-slate-700',
            }}
          >
            {PHASE_LABEL[ws.phase] ?? ws.phase}
          </Badge>
          {ws.version > 0 && <span className="text-xs tabular-nums text-slate-500">versión {ws.version}</span>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canAssess && (
            <button
              type="button"
              className="btn-secondary py-1.5"
              disabled={busy !== null}
              onClick={() => run('assess', () => assessWorkspace(opportunityId))}
            >
              {affinity ? <RefreshCw aria-hidden="true" className="h-4 w-4" /> : <Cpu aria-hidden="true" className="h-4 w-4" />}
              {busy === 'assess' ? 'Evaluando…' : affinity ? 'Reevaluar' : 'Evaluar correspondencia'}
            </button>
          )}
          {canDecide && (
            <button
              type="button"
              className="btn-primary py-1.5"
              disabled={busy !== null}
              onClick={() => run('ready', () => markWorkspaceReady(opportunityId))}
            >
              <ShieldCheck aria-hidden="true" className="h-4 w-4" />
              {busy === 'ready' ? 'Revisando…' : 'Listo para revisión final'}
            </button>
          )}
        </div>
      </div>

      {(error || blockers || readyOk) && (
        <div className="space-y-2 border-b border-slate-200 px-4 py-3">
          {error && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
              <p className="font-medium">{workspaceErrorText(error)}</p>
              <ErrorMeta error={error} />
            </div>
          )}
          {blockers && (
            <div role="alert" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-950">
              <p className="flex items-center gap-1.5 font-semibold">
                <TriangleAlert aria-hidden="true" className="h-4 w-4" />
                No puede pasar a revisión final: {blockers.length} bloqueante{blockers.length === 1 ? '' : 's'}
              </p>
              <ul className="mt-2 grid gap-1 sm:grid-cols-2">
                {blockers.map((b) => (
                  <li key={b.code} className="text-xs">
                    <span className="font-semibold tabular-nums">{blockerText(b.code)}</span>
                    {b.message && <span className="text-amber-900"> · {b.message}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-5 px-4 py-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Afinidad orientativa</h3>
          {affinity ? (
            <>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
                {affinity.total === null ? (
                  <span className="text-base font-semibold text-amber-800">Cobertura incompleta</span>
                ) : (
                  <>
                    {affinity.total}
                    <span className="text-sm font-medium text-slate-500"> / 100</span>
                  </>
                )}
                {affinity.total !== null && !affinity.coverage_complete && (
                  <span className="ml-2 align-middle text-xs font-medium text-amber-800">con datos desconocidos</span>
                )}
              </p>
              <div className="mt-3">
                <AffinityBars affinity={affinity} />
              </div>
              {engine && (
                <p className="mt-2 text-[11px] text-slate-500">
                  Motor determinista v{engine.engine_version} · evaluado <DateTimeText value={engine.assessed_at} />
                </p>
              )}
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-600">
              Sin evaluar. El motor compara cada requisito con lo que declara el catálogo de la variante propuesta.
            </p>
          )}
          <p className="mt-3 flex items-start gap-1.5 text-xs font-medium text-slate-600">
            <Info aria-hidden="true" className="mt-px h-3.5 w-3.5 shrink-0" />
            {AFFINITY_LEGEND}
          </p>
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bloqueantes</h3>
          {view.data.blockers.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600">
              Ningún requisito obligatorio en incumple, faltante o vencido ni con obligatoriedad por determinar.
            </p>
          ) : (
            <>
              <ul className="mt-2 space-y-1.5" aria-label="Requisitos bloqueantes">
                {view.data.blockers.map((b) => (
                  <li key={b.code} className="flex flex-wrap items-center gap-1.5 text-xs text-slate-600">
                    <Badge tone={{ icon: ShieldAlert, className: 'border-red-300 bg-red-50 text-red-800' }}>{b.code}</Badge>
                    {b.reason === 'motor'
                      ? `según el motor (estado: ${REQUIREMENT_STATUS[b.status]?.label ?? b.status})`
                      : b.reason === 'no_determinable'
                        ? 'obligatoriedad no determinable'
                        : REQUIREMENT_STATUS[b.status]?.label ?? b.status}
                  </li>
                ))}
              </ul>
              <button type="button" className="link mt-2 text-xs" onClick={onOpenRequirements}>
                Ver en la matriz de requisitos
              </button>
            </>
          )}
          <p className="mt-2 text-[11px] text-slate-500">
            La compuerta además exige validar los pendientes y revisa decisión, aprobaciones, vigencia de evidencia y
            conflictos con el motor (también en requisitos de obligatoriedad no determinable).
          </p>
        </div>

        <div className="space-y-3 text-sm">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Decisión</h3>
            <div className="mt-1 flex items-start justify-between gap-2">
              <div>
                <span className="font-semibold text-slate-900">{DECISION_LABEL[ws.decision] ?? ws.decision}</span>
                {ws.decision_by && (
                  <span className="block text-xs text-slate-500">
                    {ws.decision_by.full_name} · <DateTimeText value={ws.decision_at} />
                  </span>
                )}
                {ws.decision_reason && <span className="block text-xs text-slate-600">“{ws.decision_reason}”</span>}
              </div>
              {canDecide && (
                <button
                  type="button"
                  className="btn-secondary shrink-0 px-2.5 py-1 text-xs"
                  disabled={busy !== null}
                  onClick={() => {
                    setDecision(ws.decision === 'no_participar' ? 'no_participar' : 'participar')
                    setReason('')
                    setDecisionError(null)
                    setDecisionOpen(true)
                  }}
                >
                  <Gavel aria-hidden="true" className="h-3.5 w-3.5" />
                  Registrar decisión
                </button>
              )}
            </div>
          </div>

          {(['tecnica', 'comercial'] as const).map((kind) => {
            const by = kind === 'tecnica' ? ws.technical_approval_by : ws.commercial_approval_by
            const at = kind === 'tecnica' ? ws.technical_approval_at : ws.commercial_approval_at
            const can = kind === 'tecnica' ? canTechnical : canCommercial
            return (
              <div key={kind}>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Aprobación {kind === 'tecnica' ? 'técnica' : 'comercial'}
                </h3>
                <div className="mt-1 flex items-start justify-between gap-2">
                  <Who user={by} at={at} empty="Pendiente" />
                  {can && !by && (
                    <button
                      type="button"
                      className="btn-secondary shrink-0 px-2.5 py-1 text-xs"
                      disabled={busy !== null}
                      title={
                        myOtherApproval(kind)
                          ? 'Ya diste la otra aprobación: el sistema exige que la dé otra persona.'
                          : undefined
                      }
                      onClick={() => run(kind, () => approveWorkspace(opportunityId, kind))}
                    >
                      <UserCheck aria-hidden="true" className="h-3.5 w-3.5" />
                      {busy === kind ? 'Aprobando…' : 'Aprobar'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
          {ws.approvals_stale && (
            <p className="flex items-start gap-1.5 rounded-md border border-amber-300 bg-amber-50 px-2.5 py-2 text-xs text-amber-950">
              <TriangleAlert aria-hidden="true" className="mt-px h-3.5 w-3.5 shrink-0" />
              Las aprobaciones anteriores quedaron sin efecto por un cambio posterior en los requisitos. Deben darse de
              nuevo sobre los datos actuales.
            </p>
          )}
          <p className="text-[11px] text-slate-500">
            La técnica y la comercial las dan personas distintas. La revisión final humana sigue siendo necesaria; el
            sistema no marca nada como listo para presentación. <Link to="/bitacora" className="link">Bitácora</Link>
          </p>
        </div>
      </div>

      <ConfirmDialog
        open={decisionOpen}
        title="Registrar decisión"
        confirmLabel="Guardar decisión"
        busy={busy === 'decision'}
        onConfirm={submitDecision}
        onClose={() => setDecisionOpen(false)}
      >
        <fieldset>
          <legend className="label">Decisión</legend>
          <div className="flex gap-4">
            {(['participar', 'no_participar'] as const).map((d) => (
              <label key={d} className="inline-flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="ws-decision"
                  value={d}
                  checked={decision === d}
                  onChange={() => setDecision(d)}
                  className="h-4 w-4 border-slate-300 text-dpm-blue focus:ring-dpm-blue"
                />
                {DECISION_LABEL[d]}
              </label>
            ))}
          </div>
        </fieldset>
        <div>
          <label htmlFor="ws-decision-reason" className="label">
            Motivo (obligatorio)
          </label>
          <textarea
            id="ws-decision-reason"
            rows={3}
            className="input"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
        {decisionError && (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
            {workspaceErrorText(decisionError)}
            <ErrorMeta error={decisionError} />
          </div>
        )}
      </ConfirmDialog>
    </section>
  )
}
