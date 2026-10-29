import { fieldLabel } from '@/lib/labels'

function show(v: unknown): string {
  if (v === undefined) return '—'
  if (v === null) return 'vacío'
  if (typeof v === 'string') return v === '' ? 'vacío' : v
  if (Array.isArray(v)) return v.length ? v.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(', ') : 'vacío'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/** Diferencia antes → después de un evento de auditoría. */
export default function AuditDiff({
  before,
  after,
  userNames,
}: {
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  /** id → nombre, para mostrar responsables en lugar de UUID. */
  userNames?: Record<string, string>
}) {
  const fmt = (k: string, v: unknown) =>
    k.endsWith('_id') && typeof v === 'string' && userNames?.[v] ? userNames[v] : show(v)
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
