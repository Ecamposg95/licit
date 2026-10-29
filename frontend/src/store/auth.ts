import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { Me, Meta, Permission } from '@/lib/types'
import { setDisplayTimeZone } from '@/lib/format'

/** Aviso que ve quien llega a /login porque el backend rechazó su sesión por cuenta demo vencida. */
export const ACCOUNT_EXPIRED_NOTICE = 'Tu cuenta de demostración venció. Pide a Administración TI que la renueve.'

interface AuthState {
  token: string | null
  me: Me | null
  meta: Meta | null
  /** Motivo del último cierre de sesión forzado; solo en memoria (no se persiste). */
  notice: string | null
  setSession: (token: string, me: Me, meta: Meta) => void
  setProfile: (me: Me, meta: Meta) => void
  logout: () => void
  /** Cierre forzado por el servidor (p. ej. cuenta vencida): lleva a /login con el motivo. */
  endSession: (notice: string) => void
}

/** localStorage puede no estar disponible (modo privado): se degrada a memoria. */
const safeStorage = createJSONStorage(() => {
  try {
    const probe = '__licit_probe__'
    window.localStorage.setItem(probe, '1')
    window.localStorage.removeItem(probe)
    return window.localStorage
  } catch {
    const mem = new Map<string, string>()
    return {
      getItem: (k: string) => mem.get(k) ?? null,
      setItem: (k: string, v: string) => void mem.set(k, v),
      removeItem: (k: string) => void mem.delete(k),
    }
  }
})

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      me: null,
      meta: null,
      notice: null,
      setSession: (token, me, meta) => {
        setDisplayTimeZone(meta.display_timezone)
        set({ token, me, meta, notice: null })
      },
      setProfile: (me, meta) => {
        setDisplayTimeZone(meta.display_timezone)
        set({ me, meta })
      },
            logout: () => set({ token: null, me: null, meta: null, notice: null }),
      endSession: (notice) => set({ token: null, me: null, meta: null, notice }),
    }),
    {
      name: 'licit-auth',
      version: 2,
      storage: safeStorage,
      partialize: (s) => ({ token: s.token, me: s.me, meta: s.meta }),
      // Versiones anteriores guardaban otro contrato (/api/...): se descartan.
      migrate: () => ({ token: null, me: null, meta: null, notice: null }) as unknown as AuthState,
      onRehydrateStorage: () => (state) => {
        if (state?.meta) setDisplayTimeZone(state.meta.display_timezone)
      },
    },
  ),
)

/** ¿El usuario actual tiene el permiso? (El backend vuelve a validarlo en cada petición.) */
export function useCan(perm: Permission): boolean {
  return useAuth((s) => s.me?.permissions.includes(perm) ?? false)
}
