import { REQUIREMENT_STATUS } from '@/components/badges'
import { approvalKindLabel, decisionLabel, fieldLabel, matchResultText, phaseLabel } from '@/lib/labels'

type Obj = Record<string, unknown>
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)

/** Afinidad guardada (`serialize_affinity`): total o «cobertura incompleta», y cuántos bloqueantes. */
function affinityText(v: Obj): string {
  const total = typeof v.total === 'number' ? `${v.total} / 100` : 'Cobertura incompleta'
  const n = Array.isArray(v.blocking) ? v.blocking.length : 0
  return `${total} · ${n === 1 ? '1 bloqueante' : `${n} bloqueantes`}`
}

/** Conteo por resultado del motor: «Coincide: 2 · Incumple: 1 · Desconocido: 1». */
function resultsText(v: Obj): string {
  const parts = Object.entries(v).map(([k, n]) => `${matchResultText(k)}: ${String(n)}`)
  return parts.length ? parts.join(' · ') : 'Sin requisitos comparables'
}

function show(key: string, v: unknown, action?: string): string {
  if (v === undefined) return '—'
  if (v === null) return 'vacío'
  if (typeof v === 'boolean') return v ? 'Sí' : 'No'
  if (typeof v === 'string') {
    if (v === '') return 'vacío'
    if (key === 'phase') return phaseLabel(v)
    if (key === 'kind' && action === 'workspace.approval') return approvalKindLabel(v)
    if (key === 'decision' && action?.startsWith('workspace.')) return decisionLabel(v)
    if ((key === 'decision' || key === 'status') && action?.startsWith('requirement.'))
      return REQUIREMENT_STATUS[v]?.label ?? v
    return v
  }
  if (Array.isArray(v)) return v.length ? v.map((x) => show(key, x, action)).join(', ') : 'vacío'
  if (isObj(v)) {
    if (key === 'affinity' && ('total' in v || 'blocking' in v)) return affinityText(v)
    if (key === 'results') return resultsText(v)
    // Cualquier otro objeto se lee como «Campo: valor», nunca como JSON crudo.
    const parts = Object.entries(v).map(([k, x]) => `${fieldLabel(k)}: ${show(k, x, action)}`)
    return parts.length ? parts.join(' · ') : 'vacío'
  }
  return String(v)
}

/** Diferencia antes → después de un evento de auditoría. */
export default function AuditDiff({
  before,
  after,
  userNames,
  action,
}: {
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  /** id → nombre, para mostrar responsables en lugar de UUID. */
  userNames?: Record<string, string>
  /** Acción del evento: decide cómo leer campos ambiguos («decision», «status»). */
  action?: string
}) {
  const fmt = (k: string, v: unknown) =>
    k.endsWith('_id') && typeof v === 'string' && userNames?.[v] ? userNames[v] : show(k, v, action)
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]))
  if (keys.length === 0) return <span className="text-xs text-slate-500">Sin cambios de datos registrados</span>
  const hasBefore = before !== null
  return (
    <table className="w-full text-xs">
      <caption className="sr-only">Cambios registrados</caption>
      <thead>
        <tr className="text-left text-slate-500">
          <th scope="col" className="py-1 pr-3 font-medium">
            Campo
          </th>
          {hasBefore && (
            <th scope="col" className="py-1 pr-3 font-medium">
              Antes
            </th>
          )}
          <th scope="col" className="py-1 font-medium">
            {hasBefore ? 'Después' : 'Valor'}
          </th>
        </tr>
      </thead>
      <tbody>
        {keys.map((k) => {
          const b = before?.[k]
          const a = after?.[k]
          return (
            <tr key={k} className="border-t border-slate-100 align-top">
              <th scope="row" className="py-1 pr-3 font-medium text-slate-700">
                {fieldLabel(k)}
              </th>
              {hasBefore && <td className="break-words py-1 pr-3 text-slate-500 line-through decoration-slate-300">{fmt(k, b)}</td>}
              <td className="break-words py-1 text-slate-900">{fmt(k, a)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
