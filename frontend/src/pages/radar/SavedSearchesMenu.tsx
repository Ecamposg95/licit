import { useEffect, useRef, useState } from 'react'
import { Bookmark, ChevronDown, Pencil, Plus, Trash2 } from 'lucide-react'
import type { SavedSearch } from '@/lib/api-saved-searches'

interface Props {
  searches: SavedSearch[]
  activeId: string
  loading?: boolean
  onApply: (s: SavedSearch) => void
  onEdit: (s: SavedSearch) => void
  onDelete: (s: SavedSearch) => void
  onNew: () => void
}

function summary(s: SavedSearch) {
  const parts = [...s.terms, ...s.states, ...s.families, ...s.buyers]
  return parts.join(' · ')
}

/** Lista «Mis búsquedas»: aplicar, editar o borrar. */
export default function SavedSearchesMenu({ searches, activeId, loading, onApply, onEdit, onDelete, onNew }: Props) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const down = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false)
    }
    const key = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', down)
    document.addEventListener('keydown', key)
    return () => {
      document.removeEventListener('mousedown', down)
      document.removeEventListener('keydown', key)
    }
  }, [open])

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        className="btn-secondary"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <Bookmark aria-hidden="true" className="h-4 w-4" />
        Mis búsquedas{loading ? '' : ` (${searches.length})`}
        <ChevronDown aria-hidden="true" className="h-4 w-4" />
      </button>
      {open && (
        <div className="absolute left-0 z-30 mt-1 w-[min(26rem,calc(100vw-2rem))] rounded-lg border border-slate-200 bg-surface p-1 shadow-xl">
          {searches.length === 0 ? (
            <p className="px-3 py-3 text-sm text-slate-600">
              Aún no tienes búsquedas guardadas. Guarda los filtros del Radar o crea una nueva.
            </p>
          ) : (
            <ul className="max-h-72 overflow-y-auto">
              {searches.map((s) => (
                <li key={s.id} className="flex items-center gap-1 rounded-md hover:bg-slate-50">
                  <button
                    type="button"
                    className="min-w-0 flex-1 px-3 py-2 text-left"
                    aria-current={s.id === activeId ? 'true' : undefined}
                    onClick={() => {
                      setOpen(false)
                      onApply(s)
                    }}
                  >
                    <span className={`block truncate text-sm ${s.id === activeId ? 'font-semibold text-petrol-800' : 'font-medium text-slate-900'}`}>
                      {s.name}
                    </span>
                    <span className="block truncate text-xs text-slate-500">{summary(s)}</span>
                  </button>
                  <button
                    type="button"
                    className="btn-ghost !p-1.5"
                    aria-label={`Editar ${s.name}`}
                    onClick={() => {
                      setOpen(false)
                      onEdit(s)
                    }}
                  >
                    <Pencil aria-hidden="true" className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    className="btn-ghost !p-1.5"
                    aria-label={`Borrar ${s.name}`}
                    onClick={() => {
                      setOpen(false)
                      onDelete(s)
                    }}
                  >
                    <Trash2 aria-hidden="true" className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-slate-200 p-1">
            <button
              type="button"
              className="btn-ghost w-full justify-start text-sm"
              onClick={() => {
                setOpen(false)
                onNew()
              }}
            >
              <Plus aria-hidden="true" className="h-4 w-4" />
              Nueva búsqueda
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
