import { useMemo } from 'react'
import AuditList from '@/components/AuditList'
import DocumentsTable from '@/components/DocumentsTable'
import TasksTable from '@/components/TasksTable'
import { EmptyState, ErrorPanel, TableSkeleton } from '@/components/feedback'
import { getOpportunityDocuments, getOpportunityHistory, getOpportunityTasks, listUsers } from '@/lib/api'
import { useApi } from '@/lib/useApi'

export function DocumentsTab({ opportunityId }: { opportunityId: string }) {
  const docs = useApi(() => getOpportunityDocuments(opportunityId), [opportunityId])
  if (docs.error) return <ErrorPanel error={docs.error} onRetry={docs.reload} />
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        Documentos del expediente, de los productos propuestos y los vinculados como evidencia. Un documento no se considera
        válido por su nombre: cuenta su revisión.
      </p>
      <div className="card overflow-hidden">
        {!docs.data ? (
          <TableSkeleton cols={7} />
        ) : docs.data.length === 0 ? (
          <EmptyState title="Sin documentos relacionados" />
        ) : (
          <DocumentsTable docs={docs.data} />
        )}
      </div>
    </div>
  )
}

export function TasksTab({ opportunityId }: { opportunityId: string }) {
  const tasks = useApi(() => getOpportunityTasks(opportunityId), [opportunityId])
  if (tasks.error) return <ErrorPanel error={tasks.error} onRetry={tasks.reload} />
  return (
    <div className="card overflow-hidden">
      {!tasks.data ? (
        <TableSkeleton cols={4} />
      ) : tasks.data.length === 0 ? (
        <EmptyState title="Sin actividades">Las actividades aparecen al asignar requisitos faltantes a una persona.</EmptyState>
      ) : (
        <TasksTable tasks={tasks.data} showOpportunity={false} />
      )}
    </div>
  )
}

export function HistoryTab({ opportunityId, version }: { opportunityId: string; version: number }) {
  // `version` recarga el historial después de guardar cambios.
  const events = useApi(() => getOpportunityHistory(opportunityId), [opportunityId, version])
  const users = useApi(listUsers, [])
  const userNames = useMemo(
    () => Object.fromEntries((users.data ?? []).map((u) => [u.id, u.full_name])),
    [users.data],
  )
  if (events.error) return <ErrorPanel error={events.error} onRetry={events.reload} />
  return (
    <div className="card overflow-hidden">
      {!events.data ? (
        <TableSkeleton rows={4} cols={3} />
      ) : events.data.length === 0 ? (
        <EmptyState title="Sin cambios registrados">
          Cada cambio a la oportunidad, sus requisitos y actividades queda aquí con su versión anterior.
        </EmptyState>
      ) : (
        <AuditList events={events.data} userNames={userNames} />
      )}
    </div>
  )
}
