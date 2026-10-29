import { useCallback, useState } from 'react'
import { Check } from 'lucide-react'
import { DATA_KIND_CHIP_LABEL, DATA_KIND_HINT } from '@/lib/labels'
import { readStored, writeStored } from '@/lib/storage'
import { DATA_KINDS, type DataKind } from '@/lib/types'

function isDataKindList(v: unknown): v is DataKind[] {
  return Array.isArray(v) && v.every((x) => (DATA_KINDS as unknown[]).includes(x))
}

/** Selección de tipos de dato persistida en localStorage (principio §2.2). */
export function usePersistentDataKinds(storageKey: string, initial: DataKind[] = DATA_KINDS) {
  const [kinds, setKinds] = useState<DataKind[]>(() => readStored(storageKey, initial, isDataKindList))
  const update = useCallback(
    (next: DataKind[]) => {
      const ordered = DATA_KINDS.filter((k) => next.includes(k))
      setKinds(ordered)
      writeStored(storageKey, ordered)
    },
    [storageKey],
  )
  return [kinds, update] as const
}

const CHIP_ON: Record<DataKind, string> = {
  REAL: 'border-petrol-600 bg-petrol-700 text-white',
  HISTORICAL: 'border-slate-500 bg-slate-600 text-white',
  SYNTHETIC: 'border-amber-500 hatch-synthetic text-amber-950',
}

interface Props {
  value: DataKind[]
  onChange: (next: DataKind[]) => void
  /** Tipos que se ofrecen (por defecto los tres). */
  options?: DataKind[]
  label?: string
}

/** Chips REAL / HISTÓRICO / SIMULADO, siempre visibles. */
export default function DataKindChips({ value, onChange, options = DATA_KINDS, label = 'Tipo de dato' }: Props) {
  const toggle = (k: DataKind) => onChange(value.includes(k) ? value.filter((x) => x !== k) : [...value, k])
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      {options.map((k) => {
        const on = value.includes(k)
        return (
          <button
            key={k}
            type="button"
            aria-pressed={on}
            title={DATA_KIND_HINT[k]}
            onClick={() => toggle(k)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold tracking-wide transition-colors ${
              on ? CHIP_ON[k] : 'border-slate-300 bg-white text-slate-500 hover:border-slate-400 hover:text-slate-700'
            }`}
          >
            <span
              aria-hidden="true"
              className={`flex h-3.5 w-3.5 items-center justify-center rounded-sm border ${
                on ? 'border-current bg-white/90 text-slate-900' : 'border-slate-300'
              }`}
            >
              {on && <Check className="h-3 w-3" strokeWidth={3} />}
            </span>
            {DATA_KIND_CHIP_LABEL[k]}
          </button>
        )
      })}
    </div>
  )
}
