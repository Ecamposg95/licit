import { useMemo, useState } from 'react'
import PageHeader, { Pagination } from '@/components/PageHeader'
import AuditList from '@/components/AuditList'
import { EmptyState, ErrorPanel, Forbidden, TableSkeleton } from '@/components/feedback'
import { listAuditEvents, listUsers } from '@/lib/api'
import { resourceTypeLabel } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import { useCan } from '@/store/auth'

const PAGE_SIZE = 50
const RESOURCE_TYPES = ['opportunity', 'requirement', 'task', 'document', 'user', 'organization']

export default function Audit() {
  const canRead = useCan('audit.read')
  const [resourceType, setResourceType] = useState('')
  const [page, setPage] = useState(1)
  const events = useApi(
    () => listAuditEvents({ resource_type: resourceType, page, page_size: PAGE_SIZE }),
    [resourceType, page],
    canRead,
  )
  const users = useApi(listUsers, [], canRead)
  const userNames = useMemo(
    () => Object.fromEntries((users.data ?? []).map((u) => [u.id, u.full_name])),
    [users.data],
  )

  if (!canRead) return <Forbidden permission="audit.read" />

  return (
    <div>
      <PageHeader
        title="Bitácora"
        description="Quién hizo qué, sobre qué recurso, con el valor anterior y el nuevo. Cada evento conserva su ID de correlación."
      />
      <section aria-label="Filtros" className="card mb-4 p-4">
        <label htmlFor="a-type" className="label">
          Recurso
        </label>
        <select
          id="a-type"
          className="input w-56"
          value={resourceType}
          onChange={(e) => {
            setResourceType(e.target.value)
            setPage(1)
          }}
        >
          <option value="">Todos</option>
          {RESOURCE_TYPES.map((t) => (
            <option key={t} value={t}>
              {resourceTypeLabel(t)}
            </option>
          ))}
        </select>
      </section>
      <div className="card overflow-hidden">
        {events.error ? (
          <div className="p-4">
            <ErrorPanel error={events.error} onRetry={events.reload} />
          </div>
        ) : !events.data ? (
          <TableSkeleton rows={6} cols={3} />
        ) : events.data.items.length === 0 ? (
          <EmptyState title="Sin eventos registrados" />
        ) : (
          <>
            <div className={events.loading ? 'opacity-60' : ''}>
              <AuditList events={events.data.items} userNames={userNames} />
            </div>
            <Pagination page={events.data.page} pageSize={events.data.page_size} total={events.data.total} onPage={setPage} />
          </>
        )}
      </div>
    </div>
  )
}
