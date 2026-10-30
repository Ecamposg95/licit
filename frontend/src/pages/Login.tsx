import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { LoaderCircle } from 'lucide-react'
import Footer from '@/components/brand/Footer'
import Logo from '@/components/brand/Logo'
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
  const notice = useAuth((s) => s.notice)
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
      <section className="surface-dark relative flex flex-col bg-dpm-navy px-6 py-7 text-dpm-navy-200 sm:px-10 lg:w-[44%] lg:max-w-[680px] lg:px-14 lg:py-12">
        <Logo variant="white" className="h-12 self-start lg:h-16" />

        <div className="mt-10 max-w-[30rem] lg:my-auto lg:py-10">
          <h1 className="text-[1.75rem] font-semibold leading-[1.15] tracking-tight text-white sm:text-[2.15rem]">
            {/* «públicas ·» no se separa: ninguna línea empieza con el punto medio. */}
            Plataforma de licitaciones <span className="whitespace-nowrap">públicas ·</span> Demostración
          </h1>
          <span aria-hidden="true" className="brand-rule mt-6" />
          <p className="mt-6 text-[15px] leading-relaxed text-dpm-navy-200">
            Procedimientos de osteosíntesis, endoprótesis e instrumental con su fuente y última comprobación, una
            matriz de requisitos con evidencia y los pendientes de cada responsable.
          </p>
          <ul className="mt-6 hidden space-y-2.5 text-sm leading-relaxed text-dpm-navy-200 sm:block">
            <li className="flex gap-3">
              <span aria-hidden="true" className="mt-[0.55rem] h-1.5 w-1.5 shrink-0 rounded-full bg-dpm-green" />
              Los datos reales, históricos y simulados se distinguen siempre.
            </li>
            <li className="flex gap-3">
              <span aria-hidden="true" className="mt-[0.55rem] h-1.5 w-1.5 shrink-0 rounded-full bg-dpm-green" />
              Sin evidencia, un requisito queda pendiente o desconocido; nunca se da por cumplido.
            </li>
          </ul>
        </div>

        <div className="mt-8 hidden items-end justify-between gap-6 lg:flex">
          <p className="max-w-[16rem] text-xs leading-5 text-dpm-navy-300">
            Entorno de demostración. No apto para presentar propuestas.
          </p>
          <img src="/brand/fixi-color.png" width={97} height={164} alt="" className="h-20 w-auto select-none" draggable={false} />
        </div>
      </section>

      <main className="flex flex-1 flex-col px-6 pb-6 pt-10 sm:px-10">
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm">
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Iniciar sesión</h2>
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

              {notice && !error && (
                <div role="alert" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
                  {notice}
                </div>
              )}
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
        </div>
        <Footer checkedOn="2026-10-28" className="mx-auto mt-10 w-full max-w-2xl" />
      </main>
    </div>
  )
}
