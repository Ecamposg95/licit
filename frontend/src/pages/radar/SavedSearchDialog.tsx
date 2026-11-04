import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { ErrorMeta } from '@/components/feedback'
import { toApiError, type ApiError } from '@/lib/api'
import {
  MAX_SAVED_TERMS,
  createSavedSearch,
  updateSavedSearch,
  type SavedSearch,
  type SavedSearchIn,
} from '@/lib/api-saved-searches'
import { MX_STATES } from '@/lib/labels'

const NAME_MAX = 120

function Chips({ values, onRemove, label }: { values: string[]; onRemove: (v: string) => void; label: string }) {
  if (values.length === 0) return null
  return (
    <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={label}>
      {values.map((v) => (
        <li
          key={v}
          className="inline-flex items-center gap-1 rounded-full border border-petrol-200 bg-petrol-50 py-px pl-2 pr-1 text-xs text-petrol-800"
        >
          {v}
          <button
            type="button"
            className="rounded-full p-0.5 hover:bg-petrol-100"
            aria-label={`Quitar ${v}`}
            onClick={() => onRemove(v)}
          >
            <X aria-hidden="true" className="h-3 w-3" />
          </button>
        </li>
      ))}
    </ul>
  )
}

/** Campo de texto libre que agrega chips con Enter o coma. */
function TextChips({
  id,
  label,
  values,
  onChange,
  max,
  placeholder,
  hint,
  disabled,
}: {
  id: string
  label: string
  values: string[]
  onChange: (v: string[]) => void
  max?: number
  placeholder: string
  hint?: string
  disabled?: boolean
}) {
  const [draft, setDraft] = useState('')
  const full = max !== undefined && values.length >= max
  const add = () => {
    const v = draft.trim().replace(/\s+/g, ' ')
    if (!v) return
    if (!full && !values.some((x) => x.toLocaleLowerCase('es') === v.toLocaleLowerCase('es'))) onChange([...values, v])
    setDraft('')
  }
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      add()
    } else if (e.key === 'Backspace' && !draft && values.length) {
      onChange(values.slice(0, -1))
    }
  }
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
        {max !== undefined && (
          <span className="ml-1 font-normal text-slate-500 tabular-nums">
            ({values.length}/{max})
          </span>
        )}
      </label>
      <input
        id={id}
        className="input"
        value={draft}
        disabled={disabled || full}
        placeholder={full ? `Máximo ${max}` : placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKey}
        onBlur={add}
      />
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      <Chips values={values} label={label} onRemove={(v) => onChange(values.filter((x) => x !== v))} />
    </div>
  )
}

/** Selección de opciones cerradas: elegir una la agrega como chip. */
function OptionChips({
  id,
  label,
  values,
  options,
  onChange,
  disabled,
}: {
  id: string
  label: string
  values: string[]
  options: string[]
  onChange: (v: string[]) => void
  disabled?: boolean
}) {
  // Un valor guardado que ya no está en las opciones sigue siendo visible y se puede quitar.
  const pool = Array.from(new Set(options)).filter((o) => !values.includes(o))
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      <select
        id={id}
        className="input"
        value=""
        disabled={disabled}
        onChange={(e) => e.target.value && onChange([...values, e.target.value])}
      >
        <option value="">Agregar…</option>
        {pool.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <Chips values={values} label={label} onRemove={(v) => onChange(values.filter((x) => x !== v))} />
    </div>
  )
}

interface Props {
  open: boolean
  /** Búsqueda que se edita; nulo = nueva. */
  editing: SavedSearch | null
  /** Valores iniciales de una búsqueda nueva (por ejemplo, los filtros vigentes del Radar). */
  prefill?: Partial<SavedSearchIn>
  familyOptions: string[]
  onClose: () => void
  onSaved: (saved: SavedSearch) => void
}

/** Crear o editar una búsqueda guardada. El backend valida condiciones, duplicados y límite; se muestra su mensaje. */
export default function SavedSearchDialog({ open, editing, prefill, familyOptions, onClose, onSaved }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const [name, setName] = useState('')
  const [terms, setTerms] = useState<string[]>([])
  const [states, setStates] = useState<string[]>([])
  const [families, setFamilies] = useState<string[]>([])
  const [buyers, setBuyers] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) {
      const src = editing ?? prefill ?? {}
      setName(editing?.name ?? '')
      setTerms(src.terms ?? [])
      setStates(src.states ?? [])
      setFamilies(src.families ?? [])
      setBuyers(src.buyers ?? [])
      setError(null)
      d.showModal()
    }
    if (!open && d.open) d.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const cleanName = name.trim()
  const submit = async () => {
    if (!cleanName) return
    setBusy(true)
    setError(null)
    const body: SavedSearchIn = { name: cleanName, terms, states, families, buyers }
    try {
      onSaved(editing ? await updateSavedSearch(editing.id, body) : await createSavedSearch(body))
    } catch (e) {
      setError(toApiError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby="saved-search-title"
      onCancel={(e) => {
        e.preventDefault()
        if (!busy) onClose()
      }}
      className="w-[min(36rem,calc(100vw-2rem))] rounded-xl border border-slate-200 bg-surface p-0 text-slate-900 shadow-2xl backdrop:bg-ink/50"
    >
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <div className="max-h-[calc(100vh-10rem)] space-y-4 overflow-y-auto p-6">
          <h2 id="saved-search-title" className="text-lg font-semibold">
            {editing ? 'Editar búsqueda' : 'Nueva búsqueda'}
          </h2>
          <div>
            <label htmlFor="ss-name" className="label">
              Nombre (obligatorio)
            </label>
            <input
              id="ss-name"
              className="input"
              value={name}
              maxLength={NAME_MAX}
              required
              disabled={busy}
              placeholder="Por ejemplo: Osteosíntesis en Jalisco"
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <TextChips
            id="ss-terms"
            label="Términos"
            values={terms}
            max={MAX_SAVED_TERMS}
            disabled={busy}
            placeholder="Escribe un término y pulsa Enter"
            hint="Coinciden con el título o la evidencia, sin importar acentos ni mayúsculas."
            onChange={setTerms}
          />
          <OptionChips id="ss-states" label="Entidades" values={states} options={MX_STATES} disabled={busy} onChange={setStates} />
          <OptionChips
            id="ss-families"
            label="Familias"
            values={families}
            options={familyOptions}
            disabled={busy}
            onChange={setFamilies}
          />
          <TextChips
            id="ss-buyers"
            label="Instituciones"
            values={buyers}
            disabled={busy}
            placeholder="Nombre o parte del nombre; Enter para agregar"
            onChange={setBuyers}
          />
          <p className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
            Lo que coincide con tus búsquedas es tu territorio en el tablero Hoy; el barrido diario también busca estos
            términos. Se debe cumplir cada condición definida; las vacías no restringen.
          </p>
          {error && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
              <p>{error.message}</p>
              <ErrorMeta error={error} />
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={busy || !cleanName}>
            {busy ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear búsqueda'}
          </button>
        </div>
      </form>
    </dialog>
  )
}
