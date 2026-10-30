import { useMemo, useState } from 'react'
import PageHeader from '@/components/PageHeader'
import TasksTable from '@/components/TasksTable'
import { EmptyState, ErrorPanel, Forbidden, TableSkeleton } from '@/components/feedback'
import { listOpportunities, listTasks } from '@/lib/api'
import { useApi } from '@/lib/useApi'
import { useCan } from '@/store/auth'

const STATUSES = [
  { value: '', label: 'Todos los estados' },
  { value: 'pendiente', label: 'Pendiente' },
  { value: 'en_progreso', label: 'En progreso' },
  { value: 'hecha', label: 'Hecha' },
  { value: 'cancelada', label: 'Cancelada' },
]

export default function Tasks() {
  const canRead = useCan('task.read')
  const [mine, setMine] = useState(true)
  const [status, setStatus] = useState('')
  const tasks = useApi(() => listTasks({ mine, status }), [mine, status], canRead)
  // Clave de cada oportunidad para rotular el enlace; si falla, el enlace se muestra genérico.
  const opps = useApi(() => listOpportunities({ page_size: 200 }), [], canRead)
  const labels = useMemo(
    () => Object.fromEntries((opps.data?.items ?? []).map((o) => [o.id, o.external_id])),
    [opps.data],
  )

  if (!canRead) return <Forbidden permission="task.read" />

  return (
    <div>
      <PageHeader
        title="Mis pendientes"
        description="Actividades asignadas para resolver requisitos. Abre la oportunidad para ver el requisito y su evidencia."
      />

      <section aria-label="Filtros" className="card mb-4 flex flex-wrap items-end gap-4 p-4">
        <div role="group" aria-label="Asignación">
          <span className="label">Asignación</span>
          <div className="inline-flex overflow-hidden rounded-md border border-slate-300">
            {[
              { v: true, l: 'Asignadas a mí' },
              { v: false, l: 'Todo el equipo' },
            ].map((o) => (
              <button
                key={String(o.v)}
                type="button"
                aria-pressed={mine === o.v}
                onClick={() => setMine(o.v)}
                className={`border-r border-slate-300 px-3 py-1.5 text-sm last:border-r-0 ${
                  mine === o.v ? 'bg-petrol-700 font-medium text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                {o.l}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label htmlFor="t-status" className="label">
            Estado
          </label>
          <select id="t-status" className="input w-48" value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </section>

      <div className="card overflow-hidden">
        {tasks.error ? (
          <div className="p-4">
            <ErrorPanel error={tasks.error} onRetry={tasks.reload} />
          </div>
        ) : !tasks.data || tasks.loading ? (
          <TableSkeleton cols={5} />
        ) : tasks.data.length === 0 ? (
          <EmptyState title={mine ? 'No tienes actividades asignadas' : 'Sin actividades'}>
            {mine ? (
              <>
                Revisa{' '}
                <button type="button" className="font-medium text-petrol-700 underline" onClick={() => setMine(false)}>
                  todo el equipo
                </button>{' '}
                para ver las asignadas a otras personas.
              </>
            ) : (
              'Ajusta el filtro de estado.'
            )}
          </EmptyState>
        ) : (
          <>
            <p className="border-b border-slate-200 px-4 py-2.5 text-sm text-slate-600" aria-live="polite">
              {tasks.data.length} {tasks.data.length === 1 ? 'actividad' : 'actividades'}
            </p>
            <TasksTable tasks={tasks.data} opportunityLabels={labels} />
          </>
        )}
      </div>
    </div>
  )
}
