import { useEffect, useRef, useState } from 'react'
import { ErrorMeta } from '@/components/feedback'
import { listUsers, toApiError, type ApiError } from '@/lib/api'
import { triage } from '@/lib/api-hoy'
import { useApi } from '@/lib/useApi'
import type { OpportunityDetail } from '@/lib/types'
import { useAuth } from '@/store/auth'

const REASON_MAX = 500

export type TriageAction = 'seguir' | 'descartar'

interface Props {
  /** Detalle vigente: el diálogo envía su `version` como `expected_version`. Nulo = cerrado. */
  opportunity: OpportunityDetail | null
  action: TriageAction
  /** `updated` es el detalle que devolvió el backend; sin argumento, se canceló. */
  onDone: (updated?: OpportunityDetail) => void
}

/**
 * Clasificación de una oportunidad REAL (T17). Seguir exige responsable (por omisión, la persona actual);
 * Descartar exige motivo. Lo usan el tablero «Hoy» y el detalle de la oportunidad.
 */
export default function TriageDialog({ opportunity, action, onDone }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const me = useAuth((s) => s.me)
  const open = opportunity !== null
  const seguir = action === 'seguir'
  const users = useApi(listUsers, [], open && seguir)
  const [ownerId, setOwnerId] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) {
      setOwnerId(me?.id ?? '')
      setReason('')
      setError(null)
      d.showModal()
    }
    if (!open && d.open) d.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const cleanReason = reason.trim()
  const valid = seguir ? !!ownerId : cleanReason.length > 0

  const submit = async () => {
    if (!opportunity || !valid) return
    setBusy(true)
    setError(null)
    try {
      const updated = await triage(opportunity.id, {
        expected_version: opportunity.version,
        action,
        ...(seguir ? { owner_id: ownerId } : { reason: cleanReason }),
      })
      onDone(updated)
    } catch (e) {
      setError(toApiError(e))
    } finally {
      setBusy(false)
    }
  }

  const options = users.data ?? []
  const titleId = 'triage-dialog-title'

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault()
        if (!busy) onDone()
      }}
      className="w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-slate-200 bg-surface p-0 text-slate-900 shadow-2xl backdrop:bg-ink/50"
    >
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <div className="p-6">
          <h2 id={titleId} className="text-lg font-semibold">
            {seguir ? 'Seguir oportunidad' : 'Descartar oportunidad'}
          </h2>
          {opportunity && (
            <p className="mt-1 text-sm text-slate-600">
              <span className="tabular-nums">{opportunity.external_id}</span> · {opportunity.title}
            </p>
          )}

          <div className="mt-4 space-y-2 text-sm text-slate-700">
            {seguir ? (
              <>
                <label htmlFor="triage-owner" className="label">
                  Responsable (obligatorio)
                </label>
                <select
                  id="triage-owner"
                  className="input"
                  value={ownerId}
                  required
                  disabled={busy || users.loading}
                  onChange={(e) => setOwnerId(e.target.value)}
                >
                  <option value="">Elige a una persona</option>
                  {/* Mientras carga la lista, la opción actual sigue visible. */}
                  {ownerId && !options.some((u) => u.id === ownerId) && (
                    <option value={ownerId}>
                      {ownerId === me?.id ? me.full_name : opportunity?.owner?.full_name ?? 'Responsable actual'}
                    </option>
                  )}
                  {options.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name}
                    </option>
                  ))}
                </select>
                {users.error && <p className="text-xs text-red-800">No se pudo cargar la lista de personas: {users.error.message}</p>}
                <p className="text-xs text-slate-500">La oportunidad pasa a «Siguiendo» y la persona elegida queda como responsable.</p>
              </>
            ) : (
              <>
                <label htmlFor="triage-reason" className="label">
                  Motivo (obligatorio)
                </label>
                <textarea
                  id="triage-reason"
                  className="input min-h-[96px]"
                  maxLength={REASON_MAX}
                  required
                  value={reason}
                  disabled={busy}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Por ejemplo: no es de trauma ni ortopedia; la entidad está fuera de cobertura."
                />
                <p className="text-right text-xs tabular-nums text-slate-500">
                  {reason.length}/{REASON_MAX}
                </p>
                <p className="text-xs text-slate-500">Descartar no borra la oportunidad: queda registrada con su motivo y se puede volver a seguir.</p>
              </>
            )}
          </div>

          {error && (
            <div role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
              <p>
                {error.status === 409
                  ? 'Alguien más cambió esta oportunidad mientras la revisabas. Ciérrala y vuelve a abrirla para ver lo último.'
                  : error.message}
              </p>
              <ErrorMeta error={error} />
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button type="button" className="btn-secondary" onClick={() => onDone()} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" className={seguir ? 'btn-primary' : 'btn-danger'} disabled={busy || !valid}>
            {busy ? 'Guardando…' : seguir ? 'Seguir' : 'Descartar'}
          </button>
        </div>
      </form>
    </dialog>
  )
}
