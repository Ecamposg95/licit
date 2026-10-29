import { Link } from 'react-router-dom'
import { DataKindBadge, ExpiredBadge, TaskStatusBadge } from '@/components/badges'
import { CalendarDate } from '@/components/dates'
import { isBefore, referenceDate } from '@/lib/format'
import type { TaskOut } from '@/lib/types'
import { useAuth } from '@/store/auth'

const OPEN = new Set(['pendiente', 'en_progreso'])

/** Tabla de actividades. `opportunityLabels` (id → clave) permite enlazar a la oportunidad. */
export default function TasksTable({
  tasks,
  opportunityLabels,
  showOpportunity = true,
}: {
  tasks: TaskOut[]
  opportunityLabels?: Record<string, string>
  showOpportunity?: boolean
}) {
  const baseDate = useAuth((s) => s.meta?.demo_base_date)
  return (
    <div className="relative overflow-x-auto">
      <table className="table-base min-w-[860px]">
        <thead>
          <tr>
            <th scope="col">Actividad</th>
            <th scope="col">Estado</th>
            <th scope="col">Responsable</th>
            <th scope="col">Vence</th>
            {showOpportunity && <th scope="col">Oportunidad</th>}
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => {
            const overdue =
              !!t.due_date && OPEN.has(t.status) && isBefore(t.due_date, referenceDate(t.data_kind, baseDate))
            return (
              <tr key={t.id}>
                <td className="min-w-[320px]">
                  {t.code && <div className="text-xs font-medium text-slate-500 tabular-nums">{t.code}</div>}
                  <div className="text-slate-900">{t.title}</div>
                  <div className="mt-1">
                    <DataKindBadge kind={t.data_kind} />
                  </div>
                </td>
                <td>
                  <TaskStatusBadge status={t.status} />
                </td>
                <td>{t.assignee?.full_name ?? <span className="muted">Sin asignar</span>}</td>
                <td className="whitespace-nowrap">
                  <CalendarDate value={t.due_date} empty="Sin fecha" />
                  {overdue && (
                    <div className="mt-1">
                      <ExpiredBadge
                        label="Atrasada"
                        hint={
                          t.data_kind === 'SYNTHETIC'
                            ? 'Fecha anterior a la fecha base del demo.'
                            : 'Fecha anterior a hoy.'
                        }
                      />
                    </div>
                  )}
                </td>
                {showOpportunity && (
                  <td className="whitespace-nowrap">
                    {t.opportunity_id ? (
                      <Link
                        to={`/oportunidades/${t.opportunity_id}?tab=requisitos`}
                        className="font-medium text-petrol-700 underline-offset-2 hover:underline"
                      >
                        {opportunityLabels?.[t.opportunity_id] ?? 'Abrir oportunidad'}
                      </Link>
                    ) : (
                      <span className="muted">Sin oportunidad</span>
                    )}
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
