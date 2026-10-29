import { useEffect, useId, useState, type FormEvent } from 'react'
import { ClipboardCheck, RefreshCw, ShieldAlert, TriangleAlert } from 'lucide-react'
import { RequirementStatusBadge } from '@/components/badges'
import { CalendarDate } from '@/components/dates'
import { ErrorMeta } from '@/components/feedback'
import { toApiError, type ApiError } from '@/lib/api'
import {
  reviewRequirement,
  workspaceErrorText,
  type RequirementDetail,
  type ReviewDecision,
} from '@/lib/api-workspace'
import { useAuth } from '@/store/auth'
import { ModalShell } from '@/pages/opportunity/EvidenceDialog'
import { MatchResultBadge, REVIEW_DECISIONS, ValidityText } from '@/pages/opportunity/matchLabels'

interface Props {
  open: boolean
  requirement: RequirementDetail | null
  onClose: () => void
  onReviewed: (row: RequirementDetail) => void
  /** Recarga la matriz cuando el servidor responde que la versión cambió. */
  onReload: () => void
}

/**
 * Revisión humana de un requisito: decisión, motivo obligatorio y la versión que se tiene a la vista
 * (`expected_version`). El backend rechaza la autoaprobación, la evidencia vencida y las versiones desfasadas.
 */
export default function ReviewDialog({ open, requirement: r, onClose, onReviewed, onReload }: Props) {
  const uid = useId()
  const me = useAuth((s) => s.me)
  const [decision, setDecision] = useState<ReviewDecision>('cumple_validado')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (!open) return
    setDecision(r && r.evidence.some((e) => e.decision !== 'rechazada') ? 'cumple_validado' : 'faltante')
    setReason('')
    setError(null)
  }, [open, r?.id, r?.version])

  if (!r) return null
  const mine = r.evidence.some((e) => e.created_by?.id === me?.id || e.uploaded_by?.id === me?.id)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!r || busy) return
    setBusy(true)
    setError(null)
    try {
      const row = await reviewRequirement(r.id, { decision, reason, expected_version: r.version })
      onReviewed(row)
      onClose()
    } catch (err) {
      setError(toApiError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <ModalShell
      open={open}
      busy={busy}
      onClose={onClose}
      title="Revisar requisito"
      subtitle={
        <>
          <span className="font-medium tabular-nums">{r.code}</span> · {r.text}
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <div className="max-h-[62vh] space-y-4 overflow-y-auto px-6 py-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-slate-500">Estado actual:</span>
            <RequirementStatusBadge status={r.status} />
            <span className="text-xs tabular-nums text-slate-500">· se guarda sobre la versión {r.version}</span>
          </div>

          {r.assessment && (
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
              <span className="mr-1.5 font-medium">Motor de correspondencia:</span>
              <MatchResultBadge result={r.assessment.result} />
              <p className="mt-1">{r.assessment.explanation}</p>
            </div>
          )}

          <div>
            <p className="label">Evidencia vinculada</p>
            {r.evidence.length === 0 ? (
              <p className="text-sm italic text-slate-500">Sin evidencia: no se puede validar.</p>
            ) : (
              <ul className="space-y-1.5 text-xs">
                {r.evidence.map((e) => (
                  <li key={e.id} className="rounded border border-slate-200 px-2.5 py-1.5">
                    <div className="text-slate-900">
                      {e.document_code && <span className="font-medium tabular-nums">{e.document_code} · </span>}
                      {e.document_title}
                      {e.document_version ? ` · v${e.document_version}` : ''}
                      {e.page ? ` · p. ${e.page}` : ''}
                    </div>
                    <div className="mt-0.5 text-slate-500">
                      Vinculó: {e.created_by?.full_name ?? 'semilla del demo'}
                      {e.uploaded_by && <> · subió: {e.uploaded_by.full_name}</>} · <ValidityText validity={e.validity} />
                      {e.document_valid_until && (
                        <>
                          {' '}
                          (vigente hasta <CalendarDate value={e.document_valid_until} />
                          {r.required_by && (
                            <>
                              ; se exige al <CalendarDate value={r.required_by} />
                            </>
                          )}
                          )
                        </>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {mine && (
            <p className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-950">
              <ShieldAlert aria-hidden="true" className="mt-px h-4 w-4 shrink-0" />
              Tú cargaste o vinculaste evidencia de este requisito. El sistema no te dejará validarlo ni cerrarlo: lo
              decide otra persona.
            </p>
          )}

          <fieldset>
            <legend className="label">Decisión</legend>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {REVIEW_DECISIONS.map((d) => (
                <label
                  key={d.value}
                  className={`flex cursor-pointer items-start gap-2 rounded-md border p-2 text-sm ${
                    decision === d.value ? 'border-dpm-blue bg-dpm-blue-50' : 'border-slate-300 bg-white'
                  }`}
                >
                  <input
                    type="radio"
                    name={`${uid}-decision`}
                    value={d.value}
                    checked={decision === d.value}
                    onChange={() => setDecision(d.value as ReviewDecision)}
                    className="mt-1 h-4 w-4 border-slate-300 text-dpm-blue focus:ring-dpm-blue"
                  />
                  <span>
                    <span className="block font-medium text-slate-900">{d.label}</span>
                    <span className="block text-xs text-slate-600">{d.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label htmlFor={`${uid}-reason`} className="label">
              Motivo (obligatorio, queda en la bitácora)
            </label>
            <textarea
              id={`${uid}-reason`}
              rows={3}
              className="input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Qué revisaste y contra qué parte de las bases"
            />
          </div>
        </div>
        {error && (
          <div className="border-t border-slate-200 px-6 py-3">
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
              <p className="flex items-start gap-1.5 font-medium">
                <TriangleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
                {workspaceErrorText(error)}
              </p>
              <ErrorMeta error={error} />
              {error.code === 'version_conflict' && (
                <button
                  type="button"
                  className="btn-secondary mt-2 py-1.5"
                  onClick={() => {
                    onReload()
                    onClose()
                  }}
                >
                  <RefreshCw aria-hidden="true" className="h-4 w-4" />
                  Recargar matriz
                </button>
              )}
            </div>
          </div>
        )}
        <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={busy || !reason.trim()}>
            <ClipboardCheck aria-hidden="true" className="h-4 w-4" />
            {busy ? 'Guardando…' : 'Guardar revisión'}
          </button>
        </div>
      </form>
    </ModalShell>
  )
}
