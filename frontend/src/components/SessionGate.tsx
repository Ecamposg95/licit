import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ErrorPanel, LoadingBlock } from '@/components/feedback'
import { getMe, getMeta, toApiError, type ApiError } from '@/lib/api'
import { useAuth } from '@/store/auth'

/**
 * Exige sesión y refresca identidad y metadatos al montar. Con datos en caché se muestra la app
 * mientras se actualizan; un 401 cierra la sesión (interceptor) y se vuelve a /login.
 */
export default function SessionGate({ children }: { children: ReactNode }) {
  const token = useAuth((s) => s.token)
  const hasProfile = useAuth((s) => !!s.me && !!s.meta)
  const setProfile = useAuth((s) => s.setProfile)
  const logout = useAuth((s) => s.logout)
  const location = useLocation()
  const [error, setError] = useState<ApiError | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!token) return
    let active = true
    setError(null)
    Promise.all([getMe(), getMeta()])
      .then(([me, meta]) => active && setProfile(me, meta))
      .catch((e: unknown) => active && setError(toApiError(e)))
    return () => {
      active = false
    }
  }, [token, nonce, setProfile])

  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />

  if (!hasProfile) {
    if (error) {
      return (
        <div className="mx-auto mt-24 max-w-lg space-y-3 px-4">
          <ErrorPanel error={error} title="No se pudo abrir tu sesión" onRetry={() => setNonce((n) => n + 1)} />
          <button type="button" className="btn-ghost" onClick={logout}>
            Volver a iniciar sesión
          </button>
        </div>
      )
    }
    return <LoadingBlock label="Abriendo sesión…" />
  }
  return <>{children}</>
}
