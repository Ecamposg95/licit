import { FormEvent, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api, errorMessage, type User } from '@/lib/api'
import { useAuth } from '@/store/auth'

export default function Login() {
  const { token, setSession } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (token) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const form = new URLSearchParams({ username: email, password })
      const { data } = await api.post<{ access_token: string }>('/auth/login', form)
      const me = await api.get<User>('/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` },
      })
      setSession(data.access_token, me.data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-900 to-brand-700 px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-xl bg-white p-8 shadow-xl">
        <h1 className="text-2xl font-semibold text-brand-900">Licit</h1>
        <p className="mb-6 text-sm text-slate-500">Licitaciones públicas · Grupo Dipromedic</p>
        <label className="label">Correo</label>
        <input className="input mb-4" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label className="label">Contraseña</label>
        <input
          className="input mb-6"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
        <button className="btn-primary w-full" disabled={loading}>
          {loading ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
