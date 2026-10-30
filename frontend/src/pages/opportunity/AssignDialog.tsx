import { useEffect, useId, useState, type FormEvent } from 'react'
import { UserPlus } from 'lucide-react'
import { ErrorMeta, ErrorPanel } from '@/components/feedback'
import { listUsers, toApiError, type ApiError } from '@/lib/api'
import { assignRequirementTask, workspaceErrorText, type RequirementDetail } from '@/lib/api-workspace'
import { useApi } from '@/lib/useApi'
import type { TaskOut } from '@/lib/types'
import { useAuth } from '@/store/auth'
import { ModalShell } from '@/pages/opportunity/EvidenceDialog'

interface Props {
  open: boolean
  requirement: RequirementDetail | null
  onClose: () => void
  onAssigned: (task: TaskOut) => void
}

/** Asigna el requisito a una persona (o reasigna su actividad abierta). Queda en la bitácora. */
export default function AssignDialog({ open, requirement: r, onClose, onAssigned }: Props) {
  const uid = useId()
  const roles = useAuth((s) => s.meta?.roles)
  const users = useApi(listUsers, [], open)
  const [assignee, setAssignee] = useState('')
  const [due, setDue] = useState('')
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (!open) return
    setAssignee(r?.open_task?.assignee_id ?? '')
    setDue(r?.open_task?.due_date ?? '')
    setTitle('')
    setError(null)
  }, [open, r?.id])

  if (!r) return null

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!r || !assignee || busy) return
    setBusy(true)
    setError(null)
    try {
      const task = await assignRequirementTask(r.id, {
        assignee_id: assignee,
        due_date: due || null,
        title: title.trim() || null,
      })
      onAssigned(task)
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
      title={r.open_task ? 'Reasignar actividad' : 'Asignar requisito'}
      subtitle={
        <>
          <span className="font-medium tabular-nums">{r.code}</span> · {r.text}
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <div className="space-y-4 px-6 py-4">
          {r.open_task && (
            <p className="text-sm text-slate-600">
              Actividad abierta con {r.open_task.assignee ?? 'sin responsable'}. Se reasigna la misma actividad.
            </p>
          )}
          <div>
            <label htmlFor={`${uid}-who`} className="label">
              Responsable
            </label>
            {users.error ? (
              <ErrorPanel error={users.error} onRetry={users.reload} title="No se pudo cargar la lista de usuarios" />
            ) : (
              <select
                id={`${uid}-who`}
                className="input"
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                disabled={users.loading}
              >
                <option value="">Elige a una persona</option>
                {users.data?.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name}
                    {roles && u.role_names.length > 0 && u.role_names.length < 3
                      ? ` · ${u.role_names.map((n) => roles[n] ?? n).join(', ')}`
                      : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-[12rem_minmax(0,1fr)]">
            <div>
              <label htmlFor={`${uid}-due`} className="label">
                Fecha límite (opcional)
              </label>
              <input id={`${uid}-due`} type="date" className="input" value={due} onChange={(e) => setDue(e.target.value)} />
            </div>
            <div>
              <label htmlFor={`${uid}-title`} className="label">
                Título (opcional)
              </label>
              <input
                id={`${uid}-title`}
                className="input"
                maxLength={500}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={`Atender requisito ${r.code ?? ''}`}
              />
            </div>
          </div>
          {error && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
              {workspaceErrorText(error)}
              <ErrorMeta error={error} />
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={!assignee || busy}>
            <UserPlus aria-hidden="true" className="h-4 w-4" />
            {busy ? 'Asignando…' : 'Asignar'}
          </button>
        </div>
      </form>
    </ModalShell>
  )
}
