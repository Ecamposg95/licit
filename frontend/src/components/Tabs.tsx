import { useRef, type KeyboardEvent, type ReactNode } from 'react'

export interface TabDef {
  id: string
  label: string
  count?: number | null
}

interface Props {
  tabs: TabDef[]
  active: string
  onChange: (id: string) => void
  idPrefix: string
  children: ReactNode
}

/** Pestañas accesibles (role=tablist, flechas izquierda/derecha, Inicio/Fin). */
export default function Tabs({ tabs, active, onChange, idPrefix, children }: Props) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = tabs.findIndex((t) => t.id === active)
    let next = -1
    if (e.key === 'ArrowRight') next = (i + 1) % tabs.length
    else if (e.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = tabs.length - 1
    if (next < 0) return
    e.preventDefault()
    const id = tabs[next].id
    onChange(id)
    refs.current[id]?.focus()
  }

  return (
    <div>
      <div
        role="tablist"
        aria-label="Secciones de la oportunidad"
        onKeyDown={onKeyDown}
        className="relative flex gap-1 overflow-x-auto border-b border-slate-200"
      >
        {tabs.map((t) => {
          const selected = t.id === active
          return (
            <button
              key={t.id}
              ref={(el) => (refs.current[t.id] = el)}
              role="tab"
              type="button"
              id={`${idPrefix}-tab-${t.id}`}
              aria-selected={selected}
              aria-controls={`${idPrefix}-panel-${t.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(t.id)}
              className={`-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${
                selected
                  ? 'border-petrol-700 text-petrol-800'
                  : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900'
              }`}
            >
              {t.label}
              {t.count !== undefined && t.count !== null && (
                <span
                  className={`rounded-full px-1.5 text-xs tabular-nums ${
                    selected ? 'bg-petrol-100 text-petrol-800' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {t.count}
                </span>
              )}
            </button>
          )
        })}
      </div>
      <div
        role="tabpanel"
        id={`${idPrefix}-panel-${active}`}
        aria-labelledby={`${idPrefix}-tab-${active}`}
        tabIndex={0}
        className="pt-5 focus-visible:outline-none"
      >
        {children}
      </div>
    </div>
  )
}
