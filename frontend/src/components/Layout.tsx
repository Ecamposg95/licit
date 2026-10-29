import type { ComponentType } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  FolderOpen,
  ListChecks,
  LogOut,
  Package,
  Radar,
  ScrollText,
  Settings2,
  type LucideProps,
} from 'lucide-react'
import Tooltip from '@/components/Tooltip'
import { DataKindBadge } from '@/components/badges'
import { formatDate, getDisplayTimeZone } from '@/lib/format'
import type { Permission } from '@/lib/types'
import { useAuth } from '@/store/auth'

interface NavItem {
  to: string
  label: string
  icon: ComponentType<LucideProps>
  /** Prefijos de ruta adicionales que marcan el elemento como activo. */
  alsoActive?: string[]
  permission?: Permission
}

const NAV: NavItem[] = [
  { to: '/radar', label: 'Radar', icon: Radar, alsoActive: ['/oportunidades'] },
  { to: '/catalogo', label: 'Catálogo', icon: Package, permission: 'catalog.read' },
  { to: '/documentos', label: 'Centro documental', icon: FolderOpen, permission: 'document.read' },
  { to: '/pendientes', label: 'Mis pendientes', icon: ListChecks, permission: 'task.read' },
  { to: '/bitacora', label: 'Bitácora', icon: ScrollText, permission: 'audit.read' },
  { to: '/operacion', label: 'Operación', icon: Settings2 },
]

function TopBar() {
  const { me, meta, logout } = useAuth()
  const roleLabels = (me?.role_names ?? []).map((r) => meta?.roles[r] ?? r)
  const firstRole = roleLabels[0]
  const extra = roleLabels.length - 1

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center border-b border-petrol-950 bg-petrol-900 text-white">
      <div className="flex h-full shrink-0 items-center border-r border-petrol-800 px-3 lg:w-56 lg:px-5">
        <span className="whitespace-nowrap text-sm font-semibold tracking-tight lg:text-[15px]">Dipromedic · Demo</span>
      </div>
      <div className="flex min-w-0 flex-1 items-center justify-between gap-3 px-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-2 overflow-hidden">
          {meta && (
            <Tooltip content="Los escenarios simulados calculan sus fechas a partir de esta fecha base. No modifica datos reales.">
              <span className="inline-flex shrink-0 items-center whitespace-nowrap rounded-full bg-amber-300 px-2.5 py-0.5 text-xs font-semibold text-amber-950">
                Fecha base demo: <time className="ml-1 tabular-nums" dateTime={meta.demo_base_date}>{formatDate(meta.demo_base_date)}</time>
              </span>
            </Tooltip>
          )}
          <span className="hidden shrink-0 whitespace-nowrap rounded-full border border-petrol-600 px-2.5 py-0.5 text-xs text-petrol-100 md:inline-flex">
            Zona: {meta?.display_timezone ?? getDisplayTimeZone()}
          </span>
        </div>
        <div className="flex min-w-0 items-center gap-3">
          {me && (
            <div className="min-w-0 text-right leading-tight">
              <div className="truncate text-sm font-medium">{me.full_name}</div>
              {firstRole && (
                <Tooltip content={roleLabels.join(', ')}>
                  <span className="block truncate text-[11px] text-petrol-200">
                    {firstRole}
                    {extra > 0 ? ` y ${extra} rol${extra > 1 ? 'es' : ''} más` : ''}
                  </span>
                </Tooltip>
              )}
            </div>
          )}
          <button
            type="button"
            onClick={logout}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-petrol-100 hover:bg-petrol-800 hover:text-white"
          >
            <LogOut aria-hidden="true" className="h-4 w-4" />
            <span className="hidden sm:inline">Salir</span>
            <span className="sr-only sm:hidden">Salir</span>
          </button>
        </div>
      </div>
    </header>
  )
}

function Sidebar() {
  const permissions = useAuth((s) => s.me?.permissions ?? [])
  const { pathname } = useLocation()
  const items = NAV.filter((n) => !n.permission || permissions.includes(n.permission))

  return (
    <nav
      aria-label="Navegación principal"
      className="sticky top-12 flex h-[calc(100vh-3rem)] w-16 shrink-0 flex-col border-r border-slate-200 bg-white lg:w-56"
    >
      <ul className="flex flex-1 flex-col gap-0.5 p-2 lg:p-3">
        {items.map((item) => {
          const Icon = item.icon
          const forcedActive = item.alsoActive?.some((p) => pathname.startsWith(p)) ?? false
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                title={item.label}
                className={({ isActive }) => {
                  const active = isActive || forcedActive
                  return `relative flex items-center justify-center gap-3 rounded-md px-2 py-2.5 text-sm font-medium transition-colors lg:justify-start lg:px-3 ${
                    active
                      ? 'bg-petrol-50 text-petrol-800 before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-petrol-700'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`
                }}
              >
                <Icon aria-hidden="true" className="h-[18px] w-[18px] shrink-0" />
                <span className="sr-only lg:not-sr-only">{item.label}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
      <div className="hidden border-t border-slate-200 p-4 lg:block">
        <p className="mb-2 text-xs font-medium text-slate-600">Tipos de dato</p>
        <ul className="space-y-1.5">
          <li>
            <DataKindBadge kind="REAL" />
          </li>
          <li>
            <DataKindBadge kind="HISTORICAL" />
          </li>
          <li>
            <DataKindBadge kind="SYNTHETIC" />
          </li>
        </ul>
      </div>
    </nav>
  )
}

export default function Layout() {
  return (
    <div className="min-h-screen">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-sm"
      >
        Saltar al contenido
      </a>
      <TopBar />
      <div className="flex">
        <Sidebar />
        <main id="contenido" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-6">
          <div className="mx-auto max-w-[1440px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
