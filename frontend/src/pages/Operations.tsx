import { useState } from 'react'
import { CircleCheck, ExternalLink, RotateCcw } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import ConfirmDialog from '@/components/ConfirmDialog'
import { SourceStatusBadge } from '@/components/badges'
import { DateTimeText } from '@/components/dates'
import { EmptyState, ErrorPanel, TableSkeleton } from '@/components/feedback'
import { listSources, resetDemo, toApiError, type ApiError } from '@/lib/api'
import { fieldLabel, sourceMethodLabel } from '@/lib/labels'
import { formatDateLong } from '@/lib/format'
import { useApi } from '@/lib/useApi'
import type { DemoResetSummary } from '@/lib/types'
import { useAuth, useCan } from '@/store/auth'

function SourcesTable() {
  const sources = useApi(listSources, [])
  if (sources.error) return <div className="p-4"><ErrorPanel error={sources.error} onRetry={sources.reload} /></div>
  if (!sources.data) return <TableSkeleton cols={5} rows={4} />
  if (sources.data.length === 0) return <EmptyState title="Sin fuentes configuradas" />
  return (
    <div className="relative overflow-x-auto">
      <table className="table-base min-w-[960px]">
        <caption className="sr-only">Fuentes configuradas</caption>
        <thead>
          <tr>
            <th scope="col">Fuente</th>
            <th scope="col">Estado</th>
            <th scope="col">Método</th>
            <th scope="col">Última consulta</th>
            <th scope="col">Último error</th>
            <th scope="col">Notas</th>
          </tr>
        </thead>
        <tbody>
          {sources.data.map((s) => (
            <tr key={s.id}>
              <td className="min-w-[200px]">
                <div className="font-medium text-slate-900">{s.name}</div>
                <div className="text-xs text-slate-500 tabular-nums">{s.key}</div>
                {s.base_url && (
                  <a
                    href={s.base_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-petrol-700 hover:underline"
                  >
                    Sitio oficial
                    <ExternalLink aria-hidden="true" className="h-3 w-3" />
                    <span className="sr-only">(se abre en una pestaña nueva)</span>
                  </a>
                )}
              </td>
              <td>
                <SourceStatusBadge status={s.status} />
              </td>
              <td className="whitespace-nowrap">{sourceMethodLabel(s.method)}</td>
              <td className="whitespace-nowrap">
                <DateTimeText value={s.last_checked_at} empty="Nunca consultada" />
              </td>
              <td className="min-w-[160px] text-xs">
                {s.last_error ? <span className="text-red-800">{s.last_error}</span> : <span className="muted">Sin errores registrados</span>}
              </td>
              <td className="min-w-[260px] text-xs text-slate-700">{s.notes ?? <span className="muted">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DemoReset() {
  const baseDate = useAuth((s) => s.meta?.demo_base_date)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [summary, setSummary] = useState<DemoResetSummary | null>(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      setSummary(await resetDemo())
      setOpen(false)
    } catch (e) {
      setError(toApiError(e))
      setOpen(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="reinicio" className="card">
      <div className="flex flex-wrap items-start justify-between gap-4 px-4 py-4">
        <div className="max-w-xl">
          <h2 id="reinicio" className="font-semibold text-slate-900">
            Reiniciar demo
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Borra y vuelve a sembrar los datos simulados e históricos con la fecha base{' '}
            {formatDateLong(baseDate) ?? baseDate}. Los datos reales no se modifican. Útil antes de cada presentación.
          </p>
        </div>
        <button type="button" className="btn-secondary" onClick={() => setOpen(true)}>
          <RotateCcw aria-hidden="true" className="h-4 w-4" />
          Reiniciar demo
        </button>
      </div>
      {error && (
        <div className="px-4 pb-4">
          <ErrorPanel error={error} title="No se pudo reiniciar el demo" />
        </div>
      )}
      {summary && (
        <div role="status" className="border-t border-slate-200 px-4 py-4">
          <p className="flex items-center gap-1.5 text-sm font-medium text-emerald-800">
            <CircleCheck aria-hidden="true" className="h-4 w-4" />
            Demo reiniciado. Datos reales sin cambios.
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
            {Object.entries(summary).map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-slate-500">{fieldLabel(k)}</dt>
                <dd className="font-semibold tabular-nums text-slate-900">
                  {k === 'demo_base_date' && typeof v === 'string' ? formatDateLong(v) : String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      <ConfirmDialog
        open={open}
        title="¿Reiniciar el demo?"
        confirmLabel="Reiniciar demo"
        danger
        busy={busy}
        onConfirm={confirm}
        onClose={() => setOpen(false)}
      >
        <p>
          Se borrarán y volverán a crear los escenarios simulados, las referencias históricas, el catálogo de demostración,
          sus documentos, requisitos y actividades. Los cambios hechos durante la presentación se perderán.
        </p>
        <p>Los datos REAL no se tocan. La acción queda registrada en la bitácora.</p>
      </ConfirmDialog>
    </section>
  )
}

const MODULES: { name: string; status: string; current: boolean }[] = [
  { name: 'Identidad y permisos por rol', status: 'Disponible', current: true },
  { name: 'Oportunidades y radar', status: 'Disponible: consulta, responsable y notas', current: true },
  { name: 'Catálogo', status: 'Disponible: consulta', current: true },
  { name: 'Documentos', status: 'Disponible: metadatos', current: true },
  { name: 'Requisitos y matriz', status: 'Disponible: consulta', current: true },
  { name: 'Auditoría', status: 'Disponible', current: true },
  { name: 'Búsqueda e importación desde fuentes oficiales', status: 'Próxima entrega (E2)', current: false },
  { name: 'Revisión y motor de correspondencia', status: 'Próxima entrega (E3)', current: false },
  { name: 'Generación de expediente y paquete ZIP', status: 'Próxima entrega (E3)', current: false },
]

function Architecture() {
  return (
    <section aria-labelledby="arquitectura" className="card">
      <h2 id="arquitectura" className="border-b border-slate-200 px-4 py-3 font-semibold text-slate-900">
        Arquitectura
      </h2>
      <div className="grid gap-6 px-4 py-4 lg:grid-cols-2">
        <div>
          <p className="text-sm text-slate-700">
            Monolito modular: el navegador llama a una API autenticada; la API valida permisos, guarda estados y relaciones en
            PostgreSQL y registra cada cambio sensible en la bitácora. Las consultas a portales se harán desde el servidor,
            nunca desde el navegador.
          </p>
          <h3 className="mt-4 text-sm font-semibold text-slate-800">Módulos</h3>
          <ul className="mt-2 divide-y divide-slate-100 text-sm">
            {MODULES.map((m) => (
              <li key={m.name} className="flex items-center justify-between gap-3 py-2">
                <span className="text-slate-800">{m.name}</span>
                <span className={`shrink-0 text-xs ${m.current ? 'text-emerald-800' : 'text-slate-500'}`}>{m.status}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-4">
          <h3 className="text-sm font-semibold text-slate-800">Planta y ERP</h3>
          <p className="mt-0.5 text-xs font-medium text-slate-500">Integración futura, no construida</p>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-slate-700">
            <li>Compartir identidad y referencias de producto cuando estén homologadas.</li>
            <li>Consultar disponibilidad aprobada y capacidad de entrega como datos de origen confirmado.</li>
            <li>Hoy, existencias y capacidades del demo son simuladas y no afirman disponibilidad real.</li>
            <li>Se diseñará al conocer el sistema fuente y sus reglas.</li>
          </ul>
        </div>
      </div>
    </section>
  )
}

export default function Operations() {
  const canReset = useCan('demo.reset')
  return (
    <div className="space-y-6">
      <PageHeader
        title="Operación"
        description="Estado de cada fuente tal como está: una fuente no probada, bloqueada o inaccesible no significa que no existan procedimientos."
      />
      <section aria-labelledby="fuentes" className="card overflow-hidden">
        <h2 id="fuentes" className="border-b border-slate-200 px-4 py-3 font-semibold text-slate-900">
          Fuentes
        </h2>
        <SourcesTable />
      </section>
      {canReset && <DemoReset />}
      <Architecture />
    </div>
  )
}
