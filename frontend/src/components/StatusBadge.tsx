import { ESTATUS_LABEL, type Estatus } from '@/lib/api'

const COLORS: Record<Estatus, string> = {
  detectada: 'bg-slate-100 text-slate-700',
  en_analisis: 'bg-sky-100 text-sky-800',
  en_preparacion: 'bg-amber-100 text-amber-800',
  presentada: 'bg-indigo-100 text-indigo-800',
  ganada: 'bg-emerald-100 text-emerald-800',
  perdida: 'bg-red-100 text-red-800',
  desierta: 'bg-zinc-200 text-zinc-700',
  cancelada: 'bg-zinc-200 text-zinc-700',
  descartada: 'bg-zinc-100 text-zinc-500',
}

export default function StatusBadge({ value, onChange }: { value: Estatus; onChange?: (v: Estatus) => void }) {
  if (!onChange) {
    return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${COLORS[value]}`}>{ESTATUS_LABEL[value]}</span>
  }
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as Estatus)}
      className={`cursor-pointer rounded-full border-0 py-1 pl-2.5 pr-7 text-xs font-medium ${COLORS[value]}`}
    >
      {Object.entries(ESTATUS_LABEL).map(([k, v]) => (
        <option key={k} value={k}>
          {v}
        </option>
      ))}
    </select>
  )
}
