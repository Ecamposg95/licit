import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { LoaderCircle } from 'lucide-react'
import { ErrorMeta } from '@/components/feedback'
import { getMe, getMeta, login, toApiError, type ApiError } from '@/lib/api'
import { useAuth } from '@/store/auth'

const DEMO_ACCOUNTS = [
  'presentador',
  'direccion',
  'analista1',
  'revisor',
  'responsable',
]

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const token = useAuth((s) => s.token)
  const setSession = useAuth((s) => s.setSession)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(false)

  const from = (location.state as { from?: string } | null)?.from
  const target = from && from !== '/login' ? from : '/radar'

  if (token && !loading) return <Navigate to={target} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const t = await login(email.trim(), password)
      const [me, meta] = await Promise.all([getMe(t.access_token), getMeta(t.access_token)])
      setSession(t.access_token, me, meta)
      navigate(target, { replace: true })
    } catch (err) {
      setError(toApiError(err))
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-canvas lg:flex-row">
      <section className="flex flex-col justify-between bg-petrol-900 px-8 py-8 text-petrol-50 lg:w-[42%] lg:px-14 lg:py-12">
        <p className="text-base font-semibold text-white">Dipromedic · Demo</p>
        <div className="my-10 max-w-md lg:my-0">
          <h1 className="text-3xl font-semibold leading-tight text-white lg:text-[2.1rem]">
            Licitaciones de osteosíntesis, endoprótesis e instrumental
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-petrol-100">
            Radar de procedimientos con su fuente y última comprobación, matriz de requisitos con evidencia y
            pendientes por responsable.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-petrol-100">
            <li className="flex gap-2">
              <span aria-hidden="true" className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-petrol-300" />
              Los datos reales, históricos y simulados se distinguen siempre.
            </li>
            <li className="flex gap-2">
              <span aria-hidden="true" className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-petrol-300" />
              Sin evidencia, un requisito queda pendiente o desconocido; nunca se da por cumplido.
            </li>
          </ul>
        </div>
        <p className="hidden text-xs text-petrol-300 lg:block">Entorno de demostración. No apto para presentar propuestas.</p>
      </section>

      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <h2 className="text-xl font-semibold text-slate-900">Iniciar sesión</h2>
          <p className="mt-1 text-sm text-slate-600">Usa tu cuenta del entorno de demostración.</p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="label">
                Correo
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div>
              <label htmlFor="password" className="label">
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
                {error.message}
                <ErrorMeta error={error} />
              </div>
            )}

            <button type="submit" className="btn-primary w-full py-2.5" disabled={loading || !email || !password}>
              {loading && <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />}
              {loading ? 'Entrando…' : 'Entrar'}
            </button>
          </form>

          <div className="mt-8 rounded-md border border-slate-200 bg-white px-4 py-3 text-xs text-slate-600">
            <p className="font-medium text-slate-700">Cuentas de demostración</p>
            <p className="mt-1">
              Usuarios ficticios con dominio <code className="text-slate-800">@dipromedic.example</code>, uno por rol:{' '}
              {DEMO_ACCOUNTS.join(', ')}. La contraseña se define en la configuración del entorno.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
