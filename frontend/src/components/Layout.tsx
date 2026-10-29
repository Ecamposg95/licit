import type { ComponentType } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
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
import Footer from '@/components/brand/Footer'
import Logo from '@/components/brand/Logo'
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
    <header className="surface-dark sticky top-0 z-30 flex h-14 items-center gap-2 bg-dpm-navy px-3 text-white sm:gap-4 sm:px-5">
      <Link to="/radar" className="flex shrink-0 items-center gap-3 rounded-md py-1">
        <Logo variant="white" className="h-9" />
        <span aria-hidden="true" className="hidden h-6 w-px bg-white/25 sm:block" />
        <span className="hidden whitespace-nowrap text-[15px] font-semibold tracking-tight sm:inline">Licitaciones</span>
      </Link>
      <span className="shrink-0 rounded-full bg-dpm-accent px-2 py-px text-[11px] font-semibold leading-4 text-dpm-navy">
        Demo
      </span>

      <div className="flex min-w-0 flex-1 items-center justify-between gap-2 sm:gap-3 lg:pl-3">
        {/* Las píldoras no se encogen: si falta espacio, se recorta el nombre del usuario. */}
        <div className="flex min-w-0 items-center gap-2 overflow-hidden lg:shrink-0">
          {meta && (
            <Tooltip content="Los escenarios simulados calculan sus fechas a partir de esta fecha base. No modifica datos reales.">
              <span className="inline-flex shrink-0 items-center whitespace-nowrap rounded-full bg-amber-300 px-2.5 py-0.5 text-xs font-semibold text-amber-950">
                <span className="hidden sm:inline">Fecha base demo:</span>
                <span className="sm:hidden">Base demo:</span>
                <time className="ml-1 tabular-nums" dateTime={meta.demo_base_date}>
                  {formatDate(meta.demo_base_date)}
                </time>
              </span>
            </Tooltip>
          )}
          <span className="hidden shrink-0 whitespace-nowrap rounded-full border border-white/25 px-2.5 py-0.5 text-xs text-dpm-navy-200 lg:inline-flex">
            Zona: {meta?.display_timezone ?? getDisplayTimeZone()}
          </span>
        </div>
        <div className="flex min-w-0 items-center gap-3">
          {/* G monta aquí el selector de cuenta durante la integración. */}
          <div id="account-switcher-slot" className="flex shrink-0 items-center empty:hidden" />
          {me && (
            <div className="hidden min-w-0 text-right leading-tight sm:block">
              <div className="truncate text-sm font-medium text-white">{me.full_name}</div>
              {firstRole && (
                <Tooltip content={roleLabels.join(', ')}>
                  <span className="block truncate text-[11px] text-dpm-navy-300">
                    {firstRole}
                    {extra > 0 ? ` y ${extra} rol${extra > 1 ? 'es' : ''} más` : ''}
                  </span>
                </Tooltip>
              )}
            </div>
          )}
          <span aria-hidden="true" className="hidden h-6 w-px bg-white/15 sm:block" />
          <button
            type="button"
            onClick={logout}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium text-dpm-navy-200 transition-colors hover:bg-white/10 hover:text-white"
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
      className="sticky top-14 flex h-[calc(100vh-3.5rem)] w-16 shrink-0 flex-col border-r border-slate-200 bg-white lg:w-56"
    >
      <ul className="flex flex-1 flex-col gap-0.5 p-2 lg:p-3 lg:pt-4">
        {items.map((item) => {
          const Icon = item.icon
          const forcedActive = item.alsoActive?.some((p) => pathname.startsWith(p)) ?? false
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                title={item.label}
                className={({ isActive }) =>
                  // Activo: azul Dipromedic (texto 700 sobre el tinte 50, 6.16:1) y barra verde «Fixi» de 3 px.
                  `relative flex items-center justify-center gap-3 rounded-md px-2 py-2.5 text-sm font-medium transition-colors lg:justify-start lg:px-3 ${
                    isActive || forcedActive
                      ? 'bg-dpm-blue-50 text-dpm-blue-700 before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-dpm-green'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      aria-hidden="true"
                      className={`h-[18px] w-[18px] shrink-0 ${isActive || forcedActive ? 'text-dpm-blue' : ''}`}
                    />
                    <span className="sr-only lg:not-sr-only">{item.label}</span>
                  </>
                )}
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
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-dpm-navy focus:shadow-lg"
      >
        Saltar al contenido
      </a>
      <TopBar />
      <div className="flex min-h-[calc(100vh-3.5rem)]">
        <Sidebar />
        <main id="contenido" className="flex min-w-0 flex-1 flex-col px-4 pb-5 pt-6 sm:px-6">
          <div className="mx-auto w-full max-w-[1440px] flex-1">
            <Outlet />
          </div>
          <Footer checkedOn="2026-10-28" className="mx-auto mt-12 w-full max-w-[1440px]" />
        </main>
      </div>
    </div>
  )
}
