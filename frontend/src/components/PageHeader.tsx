import type { ReactNode } from 'react'

export default function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number
  pageSize: number
  total: number
  onPage: (p: number) => void
}) {
  if (total === 0) return null
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)
  const last = Math.max(1, Math.ceil(total / pageSize))
  return (
    <nav aria-label="Paginación" className="flex items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-sm">
      <span className="text-slate-600 tabular-nums">
        {from}–{to} de {total}
      </span>
      <span className="flex gap-2">
        <button type="button" className="btn-secondary py-1.5" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Anterior
        </button>
        <button type="button" className="btn-secondary py-1.5" disabled={page >= last} onClick={() => onPage(page + 1)}>
          Siguiente
        </button>
      </span>
    </nav>
  )
}
