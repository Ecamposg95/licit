import { create } from 'zustand'

/**
 * Tema claro/oscuro, como en Atlas One: clase `dark` en <html> y preferencia por navegador en localStorage.
 * index.html aplica la clase antes de pintar (sin parpadeo); este store la mantiene al cambiarla.
 * Sin preferencia guardada se sigue la del sistema operativo.
 */
export type Theme = 'light' | 'dark'

export const THEME_KEY = 'licit_theme'

function readStored(): Theme | null {
  try {
    const v = window.localStorage.getItem(THEME_KEY)
    return v === 'dark' || v === 'light' ? v : null
  } catch {
    return null
  }
}

function initial(): Theme {
  return readStored() ?? (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
}

function apply(theme: Theme) {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.classList.toggle('light', theme === 'light')
}

interface ThemeState {
  theme: Theme
  toggle: () => void
}

export const useTheme = create<ThemeState>((set, get) => {
  const theme = initial()
  apply(theme)
  return {
    theme,
    toggle: () => {
      const next: Theme = get().theme === 'dark' ? 'light' : 'dark'
      apply(next)
      try {
        window.localStorage.setItem(THEME_KEY, next)
      } catch {
        /* modo privado: el cambio dura hasta recargar */
      }
      set({ theme: next })
    },
  }
})
