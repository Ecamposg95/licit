import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CircleCheck, CircleX, Copy, Inbox, ShieldCheck } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import Tooltip from '@/components/Tooltip'
import { DataKindBadge, REQUIREMENT_STATUS } from '@/components/badges'
import { DateTimeText } from '@/components/dates'
import { EmptyState, ErrorPanel, Forbidden, TableSkeleton } from '@/components/feedback'
import { toApiError, type ApiError } from '@/lib/api'
import {
  getApprovals,
  getDemoRuns,
  getPermissionMatrix,
  verifyAuditChain,
  type Approval,
  type DemoRun,
  type IntegrityResult,
  type PermissionMatrix,
} from '@/lib/api-governance'
import { formatDateTime, getDisplayTimeZone } from '@/lib/format'
import { APPROVAL_KIND_LABEL, DECISION_LABEL, PHASE_LABEL, humanize } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import type { DataKind } from '@/lib/types'
import { useCan } from '@/store/auth'

// ── Integridad de la bitácora ────────────────────────────────────────────────

const INTEGRITY_LIMIT =
  'No detecta que se hayan borrado los eventos más recientes; para una garantía mayor, el último hash debe anclarse fuera de la base de datos. En producción (Postgres) un trigger impide modificar o borrar eventos.'

/** Último hash verificado, en monospace y seleccionable de un clic, con botón para copiarlo. */
function HeadHash({ hash, at }: { hash: string; at: string | null }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(hash)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // Sin permiso de portapapeles el hash sigue seleccionable con un clic.
    }
  }
  return (
    <div className="mt-3">
      <p className="text-xs font-medium text-emerald-900">
        Último hash verificado{at && <> (evento del <time dateTime={at}>{formatDateTime(at)}</time>)</>}
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <code
          data-testid="last-hash"
          className="select-all break-all rounded border border-emerald-200 bg-white px-2 py-1 font-mono text-xs text-slate-900"
        >
          {hash}
        </code>
        <button type="button" className="btn-secondary py-1 text-xs" onClick={copy}>
          <Copy aria-hidden="true" className="h-3.5 w-3.5" />
          {copied ? 'Copiado' : 'Copiar'}
        </button>
      </div>
    </div>
  )
}

function Integrity() {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<IntegrityResult | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  async function verify() {
    setBusy(true)
    setError(null)
    try {
      setResult(await verifyAuditChain())
    } catch (e) {
      setResult(null)
      setError(toApiError(e))
    } finally {
      setBusy(false)
    }
  }

  const when = result && (
    <>
      Verificado el <time dateTime={result.verified_at}>{formatDateTime(result.verified_at)}</time> ({getDisplayTimeZone()}).
    </>
  )

  return (
    <section aria-labelledby="integridad" className="card">
      <div className="flex flex-wrap items-start justify-between gap-4 px-4 py-4">
        <div className="max-w-2xl">
          <h2 id="integridad" className="font-semibold text-slate-900">
            Integridad de la bitácora
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            <strong className="font-medium text-slate-800">Detecta alteraciones o borrados en medio de la bitácora.</strong> Cada evento guarda la huella SHA-256 del anterior. Al verificar se recalcula la cadena completa de la organización
            desde lo almacenado y se avisa en qué evento se rompe, si se rompe. La verificación también queda registrada.
          </p>
          <p className="mt-2 text-xs text-slate-600">{INTEGRITY_LIMIT}</p>
        </div>
        <button type="button" className="btn-primary" onClick={verify} disabled={busy} aria-busy={busy}>
          <ShieldCheck aria-hidden="true" className="h-4 w-4" />
          {busy ? 'Verificando…' : 'Verificar integridad de la bitácora'}
        </button>
      </div>
      <div aria-live="polite" className="empty:hidden">
        {result?.ok && result.checked === 0 && (
          <div role="status" className="border-t border-slate-200 bg-slate-50 px-4 py-4 text-slate-900">
            <p className="flex items-center gap-2 font-semibold">
              <Inbox aria-hidden="true" className="h-5 w-5 text-slate-500" />
              No hay eventos que verificar
            </p>
            <p className="mt-1 text-xs text-slate-600">{when}</p>
          </div>
        )}
        {result?.ok && result.checked > 0 && (
          <div role="status" className="border-t border-slate-200 bg-emerald-50 px-4 py-4 text-emerald-950">
            <p className="flex items-center gap-2 font-semibold">
              <CircleCheck aria-hidden="true" className="h-5 w-5 text-emerald-700" />
              Los eventos verificados enlazan correctamente
            </p>
            <p className="mt-1 text-sm">
              Se verificaron <strong className="tabular-nums">{result.checked}</strong>{' '}
              {result.checked === 1 ? 'evento' : 'eventos'}: cada uno enlaza con el anterior y su huella coincide con su contenido.
            </p>
            {result.last_hash && <HeadHash hash={result.last_hash} at={result.last_event_at} />}
            <p className="mt-3 text-xs text-emerald-900">{when}</p>
          </div>
        )}
        {result && !result.ok && (
          <div role="alert" className="border-t border-red-200 bg-red-50 px-4 py-4 text-red-950">
            <p className="flex items-center gap-2 font-semibold">
              <CircleX aria-hidden="true" className="h-5 w-5 text-red-700" />
              Se detectó una alteración en la bitácora
            </p>
            <p className="mt-1 text-sm">
              La cadena se rompe en el evento <code className="rounded bg-white px-1 tabular-nums">{result.first_broken_id}</code>, el número{' '}
              <strong className="tabular-nums">{result.checked}</strong> en orden cronológico. Los eventos posteriores no son confiables
              hasta investigarlo.
            </p>
            <p className="mt-1 text-xs text-red-900">{when}</p>
          </div>
        )}
        {error && (
          <div className="border-t border-slate-200 p-4">
            <ErrorPanel error={error} title="No se pudo verificar la bitácora" />
          </div>
        )}
      </div>
    </section>
  )
}

// ── Decisiones y aprobaciones ────────────────────────────────────────────────

const ACTION_LABEL: Record<string, string> = {
  'requirement.review': 'Revisión de requisito',
  'workspace.decision': 'Decisión de participar',
  'workspace.approval': 'Aprobación del expediente',
  'workspace.ready': 'Listo para revisión final',
  'artifact.download': 'Descarga de expediente',
}

// «pendiente» se deja fuera a propósito: en una revisión de requisito es el estado del requisito, no «Sin decisión».
const OUTCOME_LABEL: Record<string, string> = {
  participar: DECISION_LABEL.participar,
  no_participar: DECISION_LABEL.no_participar,
  ...APPROVAL_KIND_LABEL,
  ...PHASE_LABEL,
}

function outcomeLabel(outcome: string | null): string | null {
  if (!outcome) return null
  // Lo que no se reconoce se muestra tal cual (p. ej. el nombre de un archivo), sin inventar una etiqueta.
  return OUTCOME_LABEL[outcome] ?? REQUIREMENT_STATUS[outcome]?.label ?? outcome
}

function ApprovalRow({ a, totalRoles }: { a: Approval; totalRoles: number }) {
  const roleLabels = a.roles.map((r) => r.label)
  const action = ACTION_LABEL[a.action] ?? humanize(a.action)
  const outcome = outcomeLabel(a.outcome)
  return (
    <tr>
      <td className="whitespace-nowrap">
        <DateTimeText value={a.created_at} />
      </td>
      <td className="min-w-[160px]">
        {a.actor ? (
          <>
            <div className="font-medium text-slate-900">{a.actor.full_name}</div>
            <div className="text-xs text-slate-500">{a.actor.email}</div>
          </>
        ) : (
          <span className="muted">Sistema</span>
        )}
      </td>
      <td className="min-w-[150px] text-xs text-slate-700">
        {roleLabels.length === 0 ? (
          <span className="muted">—</span>
        ) : roleLabels.length >= totalRoles && totalRoles > 1 ? (
          <Tooltip content={roleLabels.join(', ')} focusable>
            <span>Todos los roles</span>
          </Tooltip>
        ) : (
          roleLabels.join(', ')
        )}
      </td>
      <td className="min-w-[150px]">
        <div className="font-medium text-slate-900">{action}</div>
        {outcome && outcome !== action && <div className="break-words text-xs text-slate-600">{outcome}</div>}
      </td>
      <td className="min-w-[200px]">
        {a.target ? (
          <>
            {a.target.opportunity_id ? (
              <Link to={`/oportunidades/${a.target.opportunity_id}`} className="link tabular-nums">
                {a.target.opportunity_external_id ?? 'Oportunidad'}
              </Link>
            ) : (
              <span className="tabular-nums">{a.target.opportunity_external_id}</span>
            )}
            {a.target.requirement_code && <span className="tabular-nums text-slate-700"> · {a.target.requirement_code}</span>}
            {a.target.data_kind && (
              <div className="mt-1">
                <DataKindBadge kind={a.target.data_kind as DataKind} />
              </div>
            )}
          </>
        ) : (
          <span className="muted">{humanize(a.resource_type)}</span>
        )}
      </td>
      <td className="min-w-[220px] text-sm text-slate-800">
        {a.reason ?? <span className="muted">Sin motivo registrado</span>}
      </td>
    </tr>
  )
}

function Approvals({ totalRoles }: { totalRoles: number }) {
  const runs = useApi(getDemoRuns, [])
  const [runId, setRunId] = useState<string | undefined>(undefined)
  const approvals = useApi(() => getApprovals(runId), [runId])
  const currentId = runs.data?.find((r) => r.is_current)?.id

  return (
    <section aria-labelledby="aprobaciones" className="card overflow-hidden">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-200 px-4 py-3">
        <div className="max-w-2xl">
          <h2 id="aprobaciones" className="font-semibold text-slate-900">
            Decisiones y aprobaciones
          </h2>
          <p className="mt-0.5 text-xs text-slate-600">
            Quién revisó un requisito, decidió participar, aprobó o descargó un expediente, con su rol, la hora y el motivo.
            Cada reinicio del demo abre una corrida nueva; la bitácora anterior se conserva.
          </p>
        </div>
        <div>
          <label htmlFor="corrida" className="label">
            Corrida demo
          </label>
          <select
            id="corrida"
            className="input w-auto min-w-[16rem]"
            value={runId ?? currentId ?? ''}
            onChange={(e) => setRunId(e.target.value === currentId ? undefined : e.target.value)}
            disabled={!runs.data}
          >
            {runs.data ? (
              runs.data.map((r) => <option key={r.id} value={r.id}>{runLabel(r)}</option>)
            ) : (
              <option value="">Cargando corridas…</option>
            )}
          </select>
        </div>
      </div>
      {runs.error && (
        <div className="p-4">
          <ErrorPanel error={runs.error} title="No se pudieron cargar las corridas" onRetry={runs.reload} />
        </div>
      )}
      {approvals.error ? (
        <div className="p-4">
          <ErrorPanel error={approvals.error} onRetry={approvals.reload} />
        </div>
      ) : !approvals.data ? (
        <TableSkeleton rows={3} cols={6} />
      ) : approvals.data.length === 0 ? (
        <EmptyState title="Todavía no hay decisiones ni aprobaciones en esta corrida">
          Aparecen cuando alguien revisa un requisito, decide participar, aprueba o descarga un expediente.
        </EmptyState>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="table-base min-w-[980px]">
            <caption className="sr-only">Decisiones y aprobaciones de la corrida seleccionada</caption>
            <thead>
              <tr>
                <th scope="col">Cuándo</th>
                <th scope="col">Quién</th>
                <th scope="col">Rol</th>
                <th scope="col">Acción</th>
                <th scope="col">Sobre qué</th>
                <th scope="col">Motivo</th>
              </tr>
            </thead>
            <tbody>
              {approvals.data.map((a) => (
                <ApprovalRow key={a.id} a={a} totalRoles={totalRoles} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function runLabel(r: DemoRun): string {
  const when = formatDateTime(r.started_at) ?? r.started_at
  const count = `${r.approvals} ${r.approvals === 1 ? 'aprobación' : 'aprobaciones'}`
  return `${r.is_current ? 'Corrida actual' : 'Corrida anterior'} · ${when} · ${count}`
}

// ── Matriz de roles y permisos ───────────────────────────────────────────────

function Matrix({ matrix }: { matrix: PermissionMatrix }) {
  return (
    <section aria-labelledby="matriz" className="card overflow-hidden">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 id="matriz" className="font-semibold text-slate-900">
          Roles y permisos
        </h2>
        <p className="mt-0.5 text-xs text-slate-600">
          Tal como los aplica el servidor en cada petición. Una persona con varios roles suma sus permisos. Dirección es el
          rol con acceso a esta vista (<code>audit.read</code>).
        </p>
      </div>
      <div className="relative overflow-x-auto">
        <table className="table-base table-compact min-w-[860px]">
          <caption className="sr-only">Matriz de roles por permisos</caption>
          <thead>
            <tr>
              <th scope="col">Permiso</th>
              {matrix.roles.map((r) => (
                <th key={r.role} scope="col" className="text-center">
                  {r.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.permissions.map((p) => (
              <tr key={p.code}>
                <th scope="row" className="min-w-[280px] pl-4 font-normal">
                  <span className="text-slate-900">{p.label_es}</span>
                  <code className="ml-2 rounded bg-slate-100 px-1 text-[11px] text-slate-600">{p.code}</code>
                </th>
                {matrix.roles.map((r) => {
                  const has = r.permissions.includes(p.code)
                  return (
                    <td key={r.role} className="text-center">
                      {has ? (
                        <span className="text-base font-semibold text-emerald-700">
                          <span aria-hidden="true">✓</span>
                          <span className="sr-only">Sí</span>
                        </span>
                      ) : (
                        <span className="text-slate-500">
                          <span aria-hidden="true">—</span>
                          <span className="sr-only">No</span>
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function Gobierno() {
  const allowed = useCan('audit.read')
  const matrix = useApi(getPermissionMatrix, [], allowed)
  if (!allowed) {
    return (
      <div className="space-y-6">
        <PageHeader title="Gobierno corporativo" />
        <Forbidden permission="audit.read" />
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <PageHeader
        title="Gobierno corporativo"
        description="Control de la operación: la verificación detecta alteraciones o borrados en medio de la bitácora; además, quién puede hacer qué y quién aprobó cada decisión."
      />
      <Integrity />
      <Approvals totalRoles={matrix.data?.roles.length ?? 0} />
      {matrix.error && <ErrorPanel error={matrix.error} onRetry={matrix.reload} />}
      {!matrix.data && !matrix.error && <TableSkeleton rows={6} cols={6} />}
      {matrix.data && <Matrix matrix={matrix.data} />}
    </div>
  )
}
