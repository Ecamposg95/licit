import { useMemo, useState } from 'react'
import { FileText } from 'lucide-react'
import { REQUIREMENT_STATUS, REQUIREMENT_STATUS_ORDER, RequirementStatusBadge } from '@/components/badges'
import { CalendarDate } from '@/components/dates'
import { EmptyState, ErrorPanel, TableSkeleton } from '@/components/feedback'
import { getOpportunityRequirements } from '@/lib/api'
import { isBefore } from '@/lib/format'
import { attributeLabel, evidenceDecisionLabel, operatorSymbol, reqTypeLabel, scopeLabel } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import type { RequirementRow } from '@/lib/types'

function Mandatory({ value }: { value: boolean | null }) {
  if (value === null) return <span className="italic text-slate-500">No determinable</span>
  return value ? <span className="font-medium text-slate-900">Obligatorio</span> : <span className="text-slate-700">Opcional</span>
}

function Evidence({ r }: { r: RequirementRow }) {
  if (r.evidence.length === 0) return <span className="italic text-slate-500">Sin evidencia vinculada</span>
  return (
    <ul className="space-y-2">
      {r.evidence.map((e) => {
        const expiresBefore =
          !!e.document_valid_until && !!r.required_valid_until && isBefore(e.document_valid_until, r.required_valid_until)
        return (
          <li key={e.id} className="text-xs">
            <div className="flex items-start gap-1.5">
              <FileText aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
              <div className="min-w-0">
                <div className="text-slate-900">
                  {e.document_code && <span className="font-medium tabular-nums">{e.document_code} · </span>}
                  {e.document_title}
                </div>
                <div className="text-slate-500">
                  {e.page !== null ? `p. ${e.page}` : 'página no indicada'} · {evidenceDecisionLabel(e.decision)}
                </div>
                {e.fragment && <blockquote className="mt-0.5 border-l-2 border-slate-200 pl-2 text-slate-600">“{e.fragment}”</blockquote>}
                {e.document_valid_until && (
                  <div className={expiresBefore ? 'font-medium text-rose-700' : 'text-slate-500'}>
                    Vigente hasta <CalendarDate value={e.document_valid_until} />
                    {expiresBefore && ' · vence antes de la fecha exigida'}
                  </div>
                )}
              </div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/** Cita en las bases (principio §2.4): página, fuente, versión y fragmento. */
function Citation({ r }: { r: RequirementRow }) {
  const parts = [r.page !== null ? `p. ${r.page}` : 'página no indicada']
  if (r.source_label) parts.push(r.source_label)
  if (r.bases_version) parts.push(`bases ${r.bases_version}`)
  return (
    <div className="mt-1.5 text-xs text-slate-500">
      <span className="font-medium text-slate-600">Cita:</span> {parts.join(' · ')}
      {r.fragment && <blockquote className="mt-1 border-l-2 border-slate-200 pl-2 text-slate-600">“{r.fragment}”</blockquote>}
    </div>
  )
}

export default function RequirementsTab({ opportunityId }: { opportunityId: string }) {
  const reqs = useApi(() => getOpportunityRequirements(opportunityId), [opportunityId])
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [lotFilter, setLotFilter] = useState<string>('')

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const r of reqs.data ?? []) c[r.status] = (c[r.status] ?? 0) + 1
    return c
  }, [reqs.data])

  const lots = useMemo(() => {
    const m = new Map<string, string>()
    for (const r of reqs.data ?? []) if (r.lot) m.set(r.lot.id, `Partida ${r.lot.number}`)
    return Array.from(m.entries())
  }, [reqs.data])

  if (reqs.error) return <ErrorPanel error={reqs.error} onRetry={reqs.reload} />
  if (!reqs.data) return <div className="card"><TableSkeleton cols={7} /></div>
  if (reqs.data.length === 0) {
    return (
      <div className="card">
        <EmptyState title="Sin requisitos capturados">
          Los requisitos se extraen de las bases con página y fragmento. Mientras no existan, nada se considera cumplido.
        </EmptyState>
      </div>
    )
  }

  const statuses = REQUIREMENT_STATUS_ORDER.filter((s) => counts[s]).concat(
    Object.keys(counts).filter((s) => !REQUIREMENT_STATUS_ORDER.includes(s)),
  )
  const rows = reqs.data.filter(
    (r) =>
      (!statusFilter || r.status === statusFilter) &&
      (!lotFilter || (lotFilter === '__none__' ? !r.lot : r.lot?.id === lotFilter)),
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div role="group" aria-label="Filtrar por estado" className="flex flex-wrap gap-2">
          <button
            type="button"
            aria-pressed={statusFilter === null}
            onClick={() => setStatusFilter(null)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${
              statusFilter === null ? 'border-petrol-700 bg-petrol-700 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            Todos · {reqs.data.length}
          </button>
          {statuses.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={statusFilter === s}
              onClick={() => setStatusFilter(statusFilter === s ? null : s)}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                statusFilter === s ? 'border-petrol-700 bg-petrol-700 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              {REQUIREMENT_STATUS[s]?.label ?? s} · {counts[s]}
            </button>
          ))}
        </div>
        {lots.length > 0 && (
          <div>
            <label htmlFor="req-lot" className="label">
              Partida
            </label>
            <select id="req-lot" className="input w-48" value={lotFilter} onChange={(e) => setLotFilter(e.target.value)}>
              <option value="">Todas</option>
              {lots.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
              <option value="__none__">Sin partida (generales)</option>
            </select>
          </div>
        )}
      </div>

      <div className="card relative overflow-x-auto">
        <table className="table-base table-compact min-w-[1120px]">
          <caption className="sr-only">Matriz de requisitos: una fila por requisito</caption>
          <thead>
            <tr>
              <th scope="col">Requisito y cita</th>
              <th scope="col">Obligatoriedad y alcance</th>
              <th scope="col">Evidencia</th>
              <th scope="col">Estado</th>
              <th scope="col">Revisor y vencimientos</th>
              <th scope="col">Próxima acción</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="!py-8 text-center text-slate-500">
                  Ningún requisito coincide con el filtro.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="min-w-[260px]">
                  {r.code && <div className="text-xs font-medium text-slate-500 tabular-nums">{r.code}</div>}
                  <div className="text-slate-900">{r.text}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {r.req_type ? reqTypeLabel(r.req_type) : 'Tipo no declarado'}
                    {r.attribute && (
                      <>
                        {' · '}
                        {attributeLabel(r.attribute)} {operatorSymbol(r.operator)} {r.expected_value ?? 'no declarado'}
                        {r.unit ? ` ${r.unit}` : ''}
                      </>
                    )}
                  </div>
                  <Citation r={r} />
                </td>
                <td className="min-w-[130px]">
                  <Mandatory value={r.mandatory} />
                  <div className="mt-1 text-xs text-slate-600">
                    {r.scope === 'partida' && r.lot ? null : r.scope ? scopeLabel(r.scope) : 'Alcance no declarado'}
                    {r.lot && (
                      <span title={r.lot.description}>
                        {r.scope === 'partida' ? '' : ' · '}Partida {r.lot.number}
                      </span>
                    )}
                  </div>
                </td>
                <td className="min-w-[200px]">
                  <Evidence r={r} />
                </td>
                <td className="min-w-[170px] max-w-[220px]">
                  <RequirementStatusBadge status={r.status} />
                  {r.status_reason && <p className="mt-1.5 text-xs text-slate-600">{r.status_reason}</p>}
                </td>
                <td className="min-w-[160px] text-xs">
                  <div className="text-sm">{r.reviewer?.full_name ?? <span className="muted">Sin revisor</span>}</div>
                  <div className="mt-1">
                    <span className="text-slate-500">Vence: </span>
                    <CalendarDate value={r.due_date} empty="sin fecha" />
                  </div>
                  <div className="mt-0.5">
                    <span className="text-slate-500">Vigencia exigida al: </span>
                    <CalendarDate value={r.required_valid_until} empty="no indicada" />
                  </div>
                </td>
                <td className="min-w-[170px]">
                  {r.next_action ? <div className="text-slate-900">{r.next_action}</div> : <span className="muted">Sin acción definida</span>}
                  {r.open_task && (
                    <div className="mt-1.5 rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700">
                      Actividad abierta: {r.open_task.assignee ?? 'sin responsable'}
                      {r.open_task.due_date && (
                        <>
                          {' · vence '}
                          <CalendarDate value={r.open_task.due_date} />
                        </>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
