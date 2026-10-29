import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { Check, ChevronDown, LoaderCircle, Users } from 'lucide-react'
import { ErrorMeta } from '@/components/feedback'
import { ApiError, getMe, getMeta, login, toApiError } from '@/lib/api'
import { getDemoAccounts, type DemoAccount } from '@/lib/api-governance'
import { useAuth } from '@/store/auth'

const POPOVER_WIDTH = 320

interface Anchor {
  top: number
  right: number
}

/**
 * Selector de cuenta del demo. Cambiar de cuenta es un inicio de sesión real: se elige la cuenta, se escribe la
 * contraseña de demostración (que nunca se guarda) y, si el servidor la acepta, se reemplaza la sesión.
 *
 * El menú y el diálogo se dibujan en un portal sobre `document.body`: dentro de la barra superior (`.surface-dark`)
 * el anillo de foco es blanco y sería invisible sobre un fondo claro.
 */
export default function AccountSwitcher() {
  const me = useAuth((s) => s.me)
  const [accounts, setAccounts] = useState<DemoAccount[] | null>(null)
  const [open, setOpen] = useState(false)
  const [target, setTarget] = useState<DemoAccount | null>(null)
  const [anchor, setAnchor] = useState<Anchor | null>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const menuId = useId()

  // Fuera del modo demo el servidor responde 404 y el selector no existe.
  useEffect(() => {
    let active = true
    getDemoAccounts()
      .then((list) => active && setAccounts(list))
      .catch(() => active && setAccounts([]))
    return () => {
      active = false
    }
  }, [])

  const place = useCallback(() => {
    const rect = trigger.current?.getBoundingClientRect()
    if (rect) setAnchor({ top: rect.bottom + 6, right: Math.max(8, window.innerWidth - rect.right) })
  }, [])

  useLayoutEffect(() => {
    if (!open) return
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open, place])

  // Cierra con clic fuera o con Escape (también cuando el foco sigue en el botón).
  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: PointerEvent) => {
      const node = e.target as Node
      if (menu.current?.contains(node) || trigger.current?.contains(node)) return
      setOpen(false)
    }
    const onKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen(false)
      trigger.current?.focus()
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  // Al abrir (cuando el menú ya está en el DOM), el foco pasa a la cuenta actual o a la primera.
  const placed = open && anchor !== null
  useEffect(() => {
    if (!placed) return
    const current = menu.current?.querySelector<HTMLButtonElement>('button[aria-current="true"]')
    const first = menu.current?.querySelector<HTMLButtonElement>('button[data-account]:not(:disabled)')
    ;(current?.disabled ? first : current ?? first)?.focus()
  }, [placed])

  if (!accounts || accounts.length === 0) return null

  function onMenuKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const items = Array.from(menu.current?.querySelectorAll<HTMLButtonElement>('button[data-account]:not(:disabled)') ?? [])
    const i = items.indexOf(document.activeElement as HTMLButtonElement)
    let next = -1
    if (e.key === 'ArrowDown') next = (i + 1) % items.length
    else if (e.key === 'ArrowUp') next = (i - 1 + items.length) % items.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = items.length - 1
    if (next < 0) return
    e.preventDefault()
    items[next]?.focus()
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex max-w-[180px] items-center gap-1.5 rounded-md border border-white/25 px-2 py-1.5 sm:px-2.5 text-sm font-medium text-white transition-colors hover:bg-white/10"
      >
        <Users aria-hidden="true" className="h-4 w-4 shrink-0" />
        <span className="sr-only truncate sm:not-sr-only">Cambiar cuenta</span>
        <ChevronDown aria-hidden="true" className={`hidden h-3.5 w-3.5 shrink-0 transition-transform sm:block ${open ? 'rotate-180' : ''}`} />
      </button>

      {open &&
        anchor &&
        createPortal(
          <div
            ref={menu}
            id={menuId}
            role="dialog"
            aria-label="Cambiar de cuenta de demostración"
            onKeyDown={onMenuKeyDown}
            style={{ top: anchor.top, right: anchor.right, width: `min(${POPOVER_WIDTH}px, calc(100vw - 16px))` }}
            className="fixed z-50 overflow-hidden rounded-lg border border-slate-200 bg-white text-slate-900 shadow-xl"
          >
            <div className="border-b border-slate-200 px-4 py-3">
              <p className="text-sm font-semibold">Cambiar de cuenta</p>
              <p className="mt-0.5 text-xs text-slate-600">
                Cuentas ficticias del demo, una por rol. Se pedirá la contraseña de demostración.
              </p>
            </div>
            <ul className="max-h-[min(30rem,calc(100vh-8rem))] overflow-y-auto py-1">
              {accounts.map((a) => {
                const current = a.email === me?.email
                return (
                  <li key={a.email}>
                    <button
                      type="button"
                      data-account={a.email}
                      aria-current={current ? 'true' : undefined}
                      disabled={current}
                      onClick={() => {
                        setOpen(false)
                        setTarget(a)
                      }}
                      className="flex w-full items-start gap-3 px-4 py-2.5 text-left transition-colors hover:bg-dpm-blue-50 focus-visible:bg-dpm-blue-50 disabled:cursor-default disabled:bg-slate-50 disabled:hover:bg-slate-50"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-slate-900">{a.full_name}</span>
                        <span className="block truncate text-xs text-slate-600">{a.roles.join(' · ')}</span>
                      </span>
                      {current && (
                        <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-dpm-blue-700">
                          <Check aria-hidden="true" className="h-3.5 w-3.5" />
                          Cuenta actual
                        </span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>,
          document.body,
        )}

      {target && (
        <SignInDialog
          account={target}
          onClose={() => {
            setTarget(null)
            trigger.current?.focus()
          }}
        />
      )}
    </>
  )
}

/** Inicio de sesión con el correo ya escrito. La contraseña vive solo en este componente mientras está abierto. */
function SignInDialog({ account, onClose }: { account: DemoAccount; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const setSession = useAuth((s) => s.setSession)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const token = await login(account.email, password)
      // Permisos y metadatos de la cuenta nueva: la interfaz no debe conservar los de la anterior.
      const [profile, meta] = await Promise.all([getMe(token.access_token), getMeta(token.access_token)])
      // Defensa: el perfil debe ser el de la cuenta elegida. Si no coincide no se toca la sesión actual.
      if (profile.email.toLowerCase() !== account.email.toLowerCase()) {
        throw new ApiError(0, {
          code: 'profile_mismatch',
          message: 'El servidor devolvió el perfil de otra cuenta. Se conservó tu sesión actual; intenta de nuevo.',
          correlation_id: null,
          details: null,
        })
      }
      setSession(token.access_token, profile, meta)
      setPassword('')
      if (sessionPersisted(token.access_token)) {
        // Misma ruta, con todo el estado de pantalla nuevo: así ningún dato de la cuenta anterior queda en memoria.
        window.location.reload()
      } else {
        // Sin almacenamiento del navegador una recarga perdería la sesión: se navega a la misma ruta.
        navigate(location.pathname + location.search, { replace: true })
        onClose()
      }
    } catch (err) {
      setError(toApiError(err))
      setPassword('')
      setBusy(false)
    }
  }

  const roles = account.roles.join(' · ')

  return createPortal(
    <dialog
      ref={ref}
      aria-labelledby="switch-title"
      onCancel={(e) => {
        e.preventDefault()
        if (!busy) onClose()
      }}
      className="w-[min(26rem,calc(100vw-2rem))] rounded-xl border border-slate-200 p-0 text-slate-900 shadow-2xl backdrop:bg-slate-900/40"
    >
      <form onSubmit={onSubmit} noValidate>
        <div className="space-y-4 p-6">
          <div>
            <h2 id="switch-title" className="text-lg font-semibold">
              Entrar como {account.full_name}
            </h2>
            <p className="mt-0.5 text-sm text-slate-600">{roles}</p>
          </div>
          <div>
            <label htmlFor="switch-email" className="label">
              Correo
            </label>
            <input id="switch-email" type="email" className="input bg-slate-50 text-slate-700" value={account.email} readOnly autoComplete="username" />
          </div>
          <div>
            <label htmlFor="switch-password" className="label">
              Contraseña de demostración
            </label>
            <input
              id="switch-password"
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              autoFocus
              required
            />
          </div>
          {error && (
            <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
              {error.message}
              <ErrorMeta error={error} />
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={busy || !password}>
            {busy && <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />}
            {busy ? 'Entrando…' : 'Entrar'}
          </button>
        </div>
      </form>
    </dialog>,
    document.body,
  )
}

/** ¿Quedó la sesión nueva en el almacenamiento del navegador? (zustand la guarda al instante). */
function sessionPersisted(token: string): boolean {
  try {
    const raw = window.localStorage.getItem('licit-auth')
    return !!raw && (JSON.parse(raw) as { state?: { token?: string } }).state?.token === token
  } catch {
    return false
  }
}

/**
 * Monta el selector dentro de `#account-switcher-slot` (el hueco de la barra superior del Layout).
 * Se renderiza en cualquier parte del árbol autenticado; si el hueco no existe no dibuja nada.
 */
export function AccountSwitcherSlot() {
  const { pathname } = useLocation()
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  useEffect(() => {
    setSlot(document.getElementById('account-switcher-slot'))
  }, [pathname])
  return slot ? createPortal(<AccountSwitcher />, slot) : null
}
