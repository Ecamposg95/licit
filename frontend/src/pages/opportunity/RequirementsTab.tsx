import { useMemo, useState } from 'react'
import { CircleCheck, ClipboardCheck, Eye, FileText, Link2, UserPlus } from 'lucide-react'
import { REQUIREMENT_STATUS, REQUIREMENT_STATUS_ORDER, RequirementStatusBadge } from '@/components/badges'
import { CalendarDate } from '@/components/dates'
import { EmptyState, ErrorPanel, TableSkeleton } from '@/components/feedback'
import { getRequirementMatrix, type EvidenceDetail, type RequirementDetail } from '@/lib/api-workspace'
import { evidenceDecisionLabel, reqTypeLabel, scopeLabel } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import type { DataKind } from '@/lib/types'
import { useCan } from '@/store/auth'
import AssignDialog from '@/pages/opportunity/AssignDialog'
import EvidenceDialog, { EvidenceViewerDialog } from '@/pages/opportunity/EvidenceDialog'
import ReviewDialog from '@/pages/opportunity/ReviewDialog'
import { MatchResultBadge, ValidityText, requiredExpression } from '@/pages/opportunity/matchLabels'

function Mandatory({ value }: { value: boolean | null }) {
  if (value === null) return <span className="italic text-slate-500">No determinable</span>
  return value ? <span className="font-medium text-slate-900">Obligatorio</span> : <span className="text-slate-700">Opcional</span>
}

function Evidence({ r, onView }: { r: RequirementDetail; onView: (e: EvidenceDetail) => void }) {
  if (r.evidence.length === 0) return <span className="italic text-slate-500">Sin evidencia vinculada</span>
  return (
    <ul className="space-y-2">
      {r.evidence.map((e) => (
        <li key={e.id} className="text-xs">
          <div className="flex items-start gap-1.5">
            <FileText aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
            <div className="min-w-0">
              <div className="text-slate-900">
                {e.document_code && <span className="font-medium tabular-nums">{e.document_code} · </span>}
                {e.document_title}
              </div>
              <div className="text-slate-500">
                {e.document_version ? `v${e.document_version} · ` : ''}
                {e.page !== null ? `p. ${e.page}` : 'página no indicada'} · {evidenceDecisionLabel(e.decision)}
              </div>
              {e.fragment && <blockquote className="mt-0.5 border-l-2 border-slate-200 pl-2 text-slate-600">“{e.fragment}”</blockquote>}
              <div className="mt-0.5 text-slate-500">
                {e.created_by ? `Vinculó ${e.created_by.full_name}` : 'Vinculada en la semilla del demo'}
                {e.uploaded_by && e.uploaded_by.id !== e.created_by?.id && ` · subió ${e.uploaded_by.full_name}`}
              </div>
              {e.reviewer && (
                <div className="text-slate-500">
                  {e.decision === 'aceptada' ? 'Aceptó' : 'Revisó'} {e.reviewer.full_name}
                </div>
              )}
              <div>
                <ValidityText validity={e.validity} />
                {e.document_valid_until && (
                  <span className="text-slate-500">
                    {' '}
                    · hasta <CalendarDate value={e.document_valid_until} />
                  </span>
                )}
              </div>
              {e.document_version && (
                <button type="button" className="link mt-0.5 inline-flex items-center gap-1" onClick={() => onView(e)}>
                  <Eye aria-hidden="true" className="h-3.5 w-3.5" />
                  Ver documento
                </button>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}

/** Cita en las bases (principio §2.4): página, fuente, versión y fragmento. */
function Citation({ r }: { r: RequirementDetail }) {
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

type Dialog = { kind: 'assign' | 'evidence' | 'review'; id: string } | null

interface Props {
  opportunityId: string
  opportunityDataKind: DataKind
  /** Se llama tras asignar, vincular o revisar (el expediente y los conteos cambian). */
  onChanged?: () => void
}

/**
 * Matriz de requisitos con acciones según permisos: asignar, vincular evidencia (existente o nueva) y revisar con
 * motivo y versión esperada. El backend valida cada acción; la interfaz solo muestra lo que el rol puede pedir.
 */
export default function RequirementsTab({ opportunityId, opportunityDataKind, onChanged }: Props) {
  const reqs = useApi(() => getRequirementMatrix(opportunityId), [opportunityId])
  const canAssign = useCan('task.assign')
  const canUpload = useCan('document.upload')
  const canReview = useCan('requirement.review')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [lotFilter, setLotFilter] = useState<string>('')
  const [dialog, setDialog] = useState<Dialog>(null)
  const [viewing, setViewing] = useState<EvidenceDetail | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

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

  const data = reqs.data
  const current = dialog ? data.find((r) => r.id === dialog.id) ?? null : null
  const statusLabel = (s: string) => REQUIREMENT_STATUS[s]?.label ?? s
  const replace = (row: RequirementDetail, message: string) => {
    reqs.setData(data.map((r) => (r.id === row.id ? row : r)))
    setNotice(message)
    onChanged?.()
  }

  const statuses = REQUIREMENT_STATUS_ORDER.filter((s) => counts[s]).concat(
    Object.keys(counts).filter((s) => !REQUIREMENT_STATUS_ORDER.includes(s)),
  )
  const rows = data.filter(
    (r) =>
      (!statusFilter || r.status === statusFilter) &&
      (!lotFilter || (lotFilter === '__none__' ? !r.lot : r.lot?.id === lotFilter)),
  )
  const anyAction = canAssign || canUpload || canReview

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
            Todos · {data.length}
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
              {statusLabel(s)} · {counts[s]}
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

      {notice && (
        <p role="status" className="flex items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          <CircleCheck aria-hidden="true" className="h-4 w-4 shrink-0" />
          {notice}
        </p>
      )}

      <div className="card relative overflow-x-auto">
        <table className="table-base table-compact min-w-[1150px]">
          <caption className="sr-only">Matriz de requisitos: una fila por requisito</caption>
          <thead>
            <tr>
              <th scope="col">Requisito y cita</th>
              <th scope="col">Obligatoriedad y alcance</th>
              <th scope="col">Evidencia</th>
              <th scope="col">Estado</th>
              <th scope="col">Revisor y vencimientos</th>
              <th scope="col">Próxima acción</th>
              {anyAction && <th scope="col">Acciones</th>}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={anyAction ? 7 : 6} className="!py-8 text-center text-slate-500">
                  Ningún requisito coincide con el filtro.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="min-w-[220px]">
                  {r.code && <div className="text-xs font-medium text-slate-500 tabular-nums">{r.code}</div>}
                  <div className="text-slate-900">{r.text}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {r.req_type ? reqTypeLabel(r.req_type) : 'Tipo no declarado'}
                    {r.attribute && <> · {requiredExpression(r)}</>}
                  </div>
                  <Citation r={r} />
                </td>
                <td className="min-w-[120px]">
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
                  <Evidence r={r} onView={setViewing} />
                </td>
                <td className="min-w-[160px] max-w-[220px]">
                  <RequirementStatusBadge status={r.status} />
                  {r.status_reason && <p className="mt-1.5 text-xs text-slate-600">{r.status_reason}</p>}
                  {r.assessment && (
                    <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-slate-500">
                      Motor:
                      <MatchResultBadge result={r.assessment.result} />
                    </div>
                  )}
                </td>
                <td className="min-w-[130px] text-xs">
                  <div className="text-sm">{r.reviewer?.full_name ?? <span className="muted">Sin revisor</span>}</div>
                  <div className="mt-1">
                    <span className="text-slate-500">Vence: </span>
                    <CalendarDate value={r.due_date} empty="sin fecha" />
                  </div>
                  <div className="mt-0.5">
                    <span className="text-slate-500">Vigencia exigida al: </span>
                    <CalendarDate value={r.required_by} empty="no indicada" />
                  </div>
                </td>
                <td className="min-w-[140px]">
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
                {anyAction && (
                  <td className="min-w-[132px]">
                    <div className="flex flex-col items-stretch gap-1.5">
                      {canAssign && (
                        <button
                          type="button"
                          className="btn-secondary justify-start px-2.5 py-1 text-xs"
                          onClick={() => setDialog({ kind: 'assign', id: r.id })}
                          aria-label={`${r.open_task ? 'Reasignar' : 'Asignar'} ${r.code ?? 'requisito'}`}
                        >
                          <UserPlus aria-hidden="true" className="h-3.5 w-3.5" />
                          {r.open_task ? 'Reasignar' : 'Asignar'}
                        </button>
                      )}
                      {canUpload && (
                        <button
                          type="button"
                          className="btn-secondary justify-start px-2.5 py-1 text-xs"
                          onClick={() => setDialog({ kind: 'evidence', id: r.id })}
                          aria-label={`Vincular evidencia a ${r.code ?? 'requisito'}`}
                        >
                          <Link2 aria-hidden="true" className="h-3.5 w-3.5" />
                          Vincular evidencia
                        </button>
                      )}
                      {canReview && (
                        <button
                          type="button"
                          className="btn-secondary justify-start px-2.5 py-1 text-xs"
                          onClick={() => setDialog({ kind: 'review', id: r.id })}
                          aria-label={`Revisar ${r.code ?? 'requisito'}`}
                        >
                          <ClipboardCheck aria-hidden="true" className="h-3.5 w-3.5" />
                          Revisar
                        </button>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <AssignDialog
        open={dialog?.kind === 'assign'}
        requirement={dialog?.kind === 'assign' ? current : null}
        onClose={() => setDialog(null)}
        onAssigned={(task) => {
          setNotice(`${current?.code ?? 'Requisito'} asignado a ${task.assignee?.full_name ?? 'la persona elegida'}.`)
          reqs.reload()
          onChanged?.()
        }}
      />
      <EvidenceDialog
        open={dialog?.kind === 'evidence'}
        requirement={dialog?.kind === 'evidence' ? current : null}
        opportunityId={opportunityId}
        opportunityDataKind={opportunityDataKind}
        onClose={() => setDialog(null)}
        onLinked={(row) => replace(row, `${row.code} pasó a «${statusLabel(row.status)}»: lo valida otra persona.`)}
      />
      <ReviewDialog
        open={dialog?.kind === 'review'}
        requirement={dialog?.kind === 'review' ? current : null}
        onClose={() => setDialog(null)}
        onReload={reqs.reload}
        onReviewed={(row) => replace(row, `${row.code} quedó en «${statusLabel(row.status)}».`)}
      />
      <EvidenceViewerDialog evidence={viewing} onClose={() => setViewing(null)} />
    </div>
  )
}
