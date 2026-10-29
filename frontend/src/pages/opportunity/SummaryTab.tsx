import { useState, type FormEvent, type ReactNode } from 'react'
import { CircleCheck, Pencil, RefreshCw, TriangleAlert } from 'lucide-react'
import { REQUIREMENT_STATUS_ORDER, RequirementStatusBadge } from '@/components/badges'
import { DateTimeText, SubmissionDate } from '@/components/dates'
import { ErrorMeta, ErrorPanel } from '@/components/feedback'
import { listUsers, patchOpportunity, toApiError, type ApiError } from '@/lib/api'
import { formatMoney, getDisplayTimeZone } from '@/lib/format'
import { characterLabel, procedureTypeLabel, resultLabel, verificationLabel } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import type { OpportunityDetail, OpportunityPatch } from '@/lib/types'
import { useCan } from '@/store/auth'

const NOT_PUBLISHED = 'No publicada / por verificar'

function DateCard({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <div className="card px-4 py-4">
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <p className="mt-0.5 text-xs text-slate-500">{hint}</p>
      <div className="mt-3 text-base font-medium text-slate-900">{children}</div>
    </div>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(0,180px)_minmax(0,1fr)] gap-3 border-b border-slate-100 py-2.5 text-sm last:border-b-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className="min-w-0 break-words text-slate-900">{children}</dd>
    </div>
  )
}

const Missing = ({ children = 'No declarado' }: { children?: ReactNode }) => <span className="muted">{children}</span>

function FollowUp({
  o,
  onSaved,
  onReload,
  reloading,
}: {
  o: OpportunityDetail
  onSaved: (d: OpportunityDetail) => void
  onReload: () => void
  reloading: boolean
}) {
  const canWrite = useCan('opportunity.write')
  const [editing, setEditing] = useState(false)
  const [ownerId, setOwnerId] = useState<string>(o.owner?.id ?? '')
  const [notes, setNotes] = useState<string>(o.notes ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [conflict, setConflict] = useState<number | null>(null)
  const [saved, setSaved] = useState(false)
  const users = useApi(listUsers, [], editing)

  const startEdit = () => {
    setOwnerId(o.owner?.id ?? '')
    setNotes(o.notes ?? '')
    setError(null)
    setConflict(null)
    setSaved(false)
    setEditing(true)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const patch: OpportunityPatch = { expected_version: o.version }
    if ((o.owner?.id ?? '') !== ownerId) patch.owner_id = ownerId || null
    if ((o.notes ?? '') !== notes) patch.notes = notes.trim() === '' ? null : notes
    if (!('owner_id' in patch) && !('notes' in patch)) {
      setEditing(false)
      return
    }
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const updated = await patchOpportunity(o.id, patch)
      onSaved(updated)
      setEditing(false)
      setSaved(true)
    } catch (err) {
      const apiErr = toApiError(err)
      if (apiErr.status === 409 && apiErr.code === 'version_conflict') {
        const current = (apiErr.details as { current_version?: number } | null)?.current_version
        setConflict(typeof current === 'number' ? current : -1)
      } else {
        setError(apiErr)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <section aria-labelledby="seguimiento" className="card">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <h2 id="seguimiento" className="text-sm font-semibold text-slate-800">
          Seguimiento
        </h2>
        {canWrite && !editing && (
          <button type="button" className="btn-secondary py-1.5" onClick={startEdit}>
            <Pencil aria-hidden="true" className="h-4 w-4" />
            Editar responsable y notas
          </button>
        )}
      </div>

      {!editing ? (
        <div className="px-4 py-3">
          {saved && (
            <p role="status" className="mb-2 inline-flex items-center gap-1.5 text-sm text-emerald-800">
              <CircleCheck aria-hidden="true" className="h-4 w-4" />
              Cambios guardados (versión {o.version}).
            </p>
          )}
          <dl>
            <Fact label="Responsable">{o.owner?.full_name ?? <Missing>Sin asignar</Missing>}</Fact>
            <Fact label="Notas">
              {o.notes ? <span className="whitespace-pre-line">{o.notes}</span> : <Missing>Sin notas</Missing>}
            </Fact>
          </dl>
          {!canWrite && (
            <p className="mt-2 text-xs text-slate-500">Tu rol puede consultar, pero no editar, el seguimiento.</p>
          )}
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4 px-4 py-4">
          <div>
            <label htmlFor="owner" className="label">
              Responsable
            </label>
            {users.error ? (
              <ErrorPanel error={users.error} onRetry={users.reload} title="No se pudo cargar la lista de usuarios" />
            ) : (
              <select
                id="owner"
                className="input max-w-md"
                value={ownerId}
                onChange={(e) => setOwnerId(e.target.value)}
                disabled={users.loading}
              >
                <option value="">Sin asignar</option>
                {o.owner && !users.data?.some((u) => u.id === o.owner?.id) && (
                  <option value={o.owner.id}>{o.owner.full_name}</option>
                )}
                {users.data?.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div>
            <label htmlFor="notes" className="label">
              Notas
            </label>
            <textarea
              id="notes"
              rows={4}
              className="input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {conflict !== null && (
            <div role="alert" className="flex items-start gap-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-950">
              <TriangleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="flex-1">
                <p className="font-medium">Alguien más modificó esta oportunidad desde que la abriste.</p>
                <p className="mt-0.5">
                  Tu edición partía de la versión {o.version}
                  {conflict > 0 ? ` y la versión actual es ${conflict}` : ''}. Recarga para ver los cambios; tu texto se
                  conserva en el formulario para que lo revises y guardes de nuevo.
                </p>
                <button
                  type="button"
                  className="btn-secondary mt-2 py-1.5"
                  onClick={() => {
                    setConflict(null)
                    onReload()
                  }}
                  disabled={reloading}
                >
                  <RefreshCw aria-hidden="true" className="h-4 w-4" />
                  Recargar oportunidad
                </button>
              </div>
            </div>
          )}
          {error && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
              {error.message}
              <ErrorMeta error={error} />
            </div>
          )}

          <div className="flex items-center gap-2">
            <button type="submit" className="btn-primary" disabled={saving || reloading}>
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </button>
            <button type="button" className="btn-ghost" onClick={() => setEditing(false)} disabled={saving}>
              Cancelar
            </button>
            <span className="text-xs text-slate-500">Se guarda sobre la versión {o.version}.</span>
          </div>
        </form>
      )}
    </section>
  )
}

export default function SummaryTab({
  o,
  onSaved,
  onReload,
  reloading,
  onOpenRequirements,
}: {
  o: OpportunityDetail
  onSaved: (d: OpportunityDetail) => void
  onReload: () => void
  reloading: boolean
  onOpenRequirements: () => void
}) {
  const tz = getDisplayTimeZone()
  const counts = REQUIREMENT_STATUS_ORDER.filter((s) => o.requirement_counts[s]).concat(
    Object.keys(o.requirement_counts).filter((s) => !REQUIREMENT_STATUS_ORDER.includes(s)),
  )

  return (
    <div className="space-y-6">
      <section aria-labelledby="fechas">
        <h2 id="fechas" className="sr-only">
          Fechas del procedimiento
        </h2>
        <div className="grid gap-3 md:grid-cols-3">
          <DateCard title="Junta de aclaraciones" hint="Preguntas y aclaraciones">
            <DateTimeText value={o.questions_at} empty={NOT_PUBLISHED} />
          </DateCard>
          <DateCard title="Presentación y apertura" hint="Entrega de proposiciones">
            <SubmissionDate
              value={o.submission_at}
              precision={o.submission_precision}
              sourceTimezone={o.source_timezone}
              empty={NOT_PUBLISHED}
            />
          </DateCard>
          <DateCard title="Fallo" hint="Comunicación del resultado">
            <DateTimeText value={o.ruling_at} empty={NOT_PUBLISHED} />
          </DateCard>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          Horario mostrado en {tz}. Zona de la fuente:{' '}
          {o.source_timezone ? (
            <>
              {o.source_timezone}
              {o.timezone_assumed && (
                <strong className="font-medium text-amber-800"> (supuesta: la fuente no la declara; confirmar)</strong>
              )}
            </>
          ) : (
            'no declarada'
          )}
          .
        </p>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <section aria-labelledby="datos" className="card">
          <h2 id="datos" className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800">
            Datos del procedimiento
          </h2>
          <dl className="px-4 py-1">
            <Fact label="Tipo de procedimiento">
              {o.procedure_type ? procedureTypeLabel(o.procedure_type) : <Missing />}
            </Fact>
            <Fact label="Carácter">{o.character ? characterLabel(o.character) : <Missing />}</Fact>
            <Fact label="Entidad">{o.state ?? <Missing />}</Fact>
            <Fact label="Familias">{o.families.length ? o.families.join(', ') : <Missing />}</Fact>
            <Fact label="Estado reportado por la fuente">{o.reported_status ?? <Missing />}</Fact>
            <Fact label="Grado de verificación">{verificationLabel(o.verification_status)}</Fact>
            <Fact label="Alcance de la verificación">{o.verification_scope ?? <Missing />}</Fact>
            <Fact label="Resultado del procedimiento">{resultLabel(o.result)}</Fact>
            <Fact label="Monto estimado">
              {formatMoney(o.estimated_amount, o.currency) ?? <Missing>No publicado</Missing>}
            </Fact>
            <Fact label="Revisión humana">{o.requires_human_review ? 'Requerida' : 'No requerida'}</Fact>
            <Fact label="Versión del registro">
              <span className="tabular-nums">{o.version}</span>
            </Fact>
          </dl>
        </section>

        <div className="space-y-6">
          <FollowUp o={o} onSaved={onSaved} onReload={onReload} reloading={reloading} />

          <section aria-labelledby="estado-req" className="card">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h2 id="estado-req" className="text-sm font-semibold text-slate-800">
                Requisitos por estado
              </h2>
              {counts.length > 0 && (
                <button type="button" onClick={onOpenRequirements} className="text-sm font-medium text-petrol-700 hover:underline">
                  Ver matriz
                </button>
              )}
            </div>
            {counts.length === 0 ? (
              <p className="px-4 py-4 text-sm text-slate-500">Sin requisitos capturados para esta oportunidad.</p>
            ) : (
              <ul className="divide-y divide-slate-100 px-4">
                {counts.map((s) => (
                  <li key={s} className="flex items-center justify-between py-2">
                    <RequirementStatusBadge status={s} />
                    <span className="text-sm font-semibold tabular-nums">{o.requirement_counts[s]}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
