import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  content: ReactNode
  children: ReactNode
  /** Hace enfocable el envoltorio cuando el hijo no lo es (texto, insignias). */
  focusable?: boolean
  className?: string
}

interface Position {
  x: number
  y: number
  above: boolean
}

/**
 * Tooltip accesible: aparece con puntero o foco, se cierra con Escape y su texto queda
 * vinculado con aria-describedby. Se dibuja en un portal con posición fija para que las
 * tablas con desplazamiento horizontal no lo recorten.
 */
export default function Tooltip({ content, children, focusable, className }: Props) {
  const ref = useRef<HTMLSpanElement>(null)
  const [pos, setPos] = useState<Position | null>(null)
  const id = useId()

  const show = useCallback(() => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const half = 150
    const x = Math.min(Math.max(r.left + r.width / 2, half + 8), window.innerWidth - half - 8)
    const above = r.bottom + 96 > window.innerHeight
    setPos({ x, y: above ? r.top - 6 : r.bottom + 6, above })
  }, [])
  const hide = useCallback(() => setPos(null), [])

  useEffect(() => {
    if (!pos) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && hide()
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', hide, true)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', hide, true)
    }
  }, [pos, hide])

  return (
    <span
      ref={ref}
      className={`relative inline-flex max-w-full ${focusable ? 'rounded focus-visible:outline-2' : ''} ${className ?? ''}`}
      tabIndex={focusable ? 0 : undefined}
      aria-describedby={id}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      <span id={id} className="sr-only">
        {content}
      </span>
      {pos &&
        createPortal(
          <span
            aria-hidden="true"
            className="pointer-events-none fixed z-50 w-max max-w-[300px] rounded-md bg-slate-900 px-2.5 py-1.5 text-xs leading-snug text-white shadow-lg"
            style={{
              left: pos.x,
              top: pos.y,
              transform: `translate(-50%, ${pos.above ? '-100%' : '0'})`,
            }}
          >
            {content}
          </span>,
          document.body,
        )}
    </span>
  )
}

/** Botón de una función que no existe en esta entrega: enfocable, anunciado como deshabilitado. */
export function UnavailableAction({ label, reason, icon }: { label: string; reason: string; icon?: ReactNode }) {
  return (
    <Tooltip content={reason}>
      <button
        type="button"
        aria-disabled="true"
        className="btn-unavailable"
        onClick={(e) => e.preventDefault()}
      >
        {icon}
        {label}
      </button>
    </Tooltip>
  )
}
