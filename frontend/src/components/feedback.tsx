import type { ReactNode } from 'react'
import { CircleAlert, Inbox, LoaderCircle, Lock, RefreshCw } from 'lucide-react'
import type { ApiError } from '@/lib/api'

/** Error de API: mensaje del servidor y correlation_id en letra pequeña para soporte. */
export function ErrorPanel({ error, onRetry, title }: { error: ApiError; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
      <CircleAlert aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-red-700" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title ?? 'No se pudo cargar la información'}</p>
        <p className="mt-0.5">{error.message}</p>
        <ErrorMeta error={error} />
      </div>
      {onRetry && (
        <button type="button" className="btn-secondary shrink-0 py-1.5" onClick={onRetry}>
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
          Reintentar
        </button>
      )}
    </div>
  )
}

export function ErrorMeta({ error }: { error: ApiError }) {
  return (
    <p className="mt-1 text-[11px] text-red-800/80">
      Código {error.code}
      {error.status ? ` · HTTP ${error.status}` : ''}
      {error.correlationId ? ` · ID de correlación ${error.correlationId}` : ''}
    </p>
  )
}

export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <span aria-hidden="true" className="mb-3 text-slate-400">
        {icon ?? <Inbox className="h-8 w-8" strokeWidth={1.5} />}
      </span>
      <p className="font-medium text-slate-800">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  )
}

export function TableSkeleton({ rows = 6, cols = 6, label = 'Cargando…' }: { rows?: number; cols?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" className="animate-pulse">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 border-b border-slate-100 px-4 py-4 last:border-b-0">
          {Array.from({ length: cols }).map((__, c) => (
            <div
              key={c}
              className="h-3.5 rounded bg-slate-200"
              style={{ width: `${c === 0 ? 22 : 100 / cols - 2}%`, opacity: 1 - c * 0.08 }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export function LoadingBlock({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 px-4 py-8 text-sm text-slate-500">
      <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
      {label}
    </div>
  )
}

export function Forbidden({ permission }: { permission: string }) {
  return (
    <div className="card">
      <EmptyState title="Tu rol no tiene acceso a esta sección" icon={<Lock className="h-8 w-8" strokeWidth={1.5} />}>
        Se requiere el permiso <code className="rounded bg-slate-100 px-1">{permission}</code>. Pide a Administración TI que
        revise tus roles.
      </EmptyState>
    </div>
  )
}
