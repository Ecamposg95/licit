import AuditDiff from '@/components/AuditDiff'
import { DateTimeText } from '@/components/dates'
import { auditActionLabel, resourceTypeLabel } from '@/lib/labels'
import type { AuditOut } from '@/lib/types'

/** Eventos de auditoría con actor, acción, recurso, diferencia y correlación. */
export default function AuditList({ events, userNames }: { events: AuditOut[]; userNames?: Record<string, string> }) {
  return (
    <ol className="divide-y divide-slate-100">
      {events.map((e) => (
        <li key={e.id} className="grid gap-3 px-4 py-4 md:grid-cols-[200px_minmax(0,1fr)]">
          <div className="text-sm">
            <div className="text-slate-900">
              <DateTimeText value={e.created_at} />
            </div>
            <div className="mt-0.5 text-slate-600">{e.actor?.full_name ?? 'Sistema'}</div>
          </div>
          <div className="min-w-0">
            <p className="text-sm">
              <span className="font-medium text-slate-900">{auditActionLabel(e.action)}</span>
              <span className="text-slate-500">
                {' '}
                en {resourceTypeLabel(e.resource_type).toLowerCase()}
              </span>
              {e.action !== auditActionLabel(e.action) && (
                <code className="ml-2 rounded bg-slate-100 px-1 text-[11px] text-slate-600">{e.action}</code>
              )}
            </p>
            {(e.before || e.after) && (
              <div className="mt-2 max-w-2xl rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <AuditDiff before={e.before} after={e.after} userNames={userNames} />
              </div>
            )}
            <p className="mt-1.5 text-[11px] text-slate-500 tabular-nums">
              {e.resource_id && <>Recurso {e.resource_id}</>}
              {e.correlation_id && <> · Correlación {e.correlation_id}</>}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}
