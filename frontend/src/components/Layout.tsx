import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/store/auth'

export default function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="text-lg font-semibold text-brand-900">
              Licit <span className="font-normal text-slate-400">· Dipromedic</span>
            </span>
            <nav className="flex gap-1">
              <NavLink
                to="/licitaciones"
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm ${isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`
                }
              >
                Licitaciones
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-500 sm:inline">{user?.full_name}</span>
            <button className="btn-ghost" onClick={logout}>
              Salir
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
