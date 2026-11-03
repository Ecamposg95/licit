import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/store/theme'

/** Cambio de tema para superficies navy (barra superior, panel del login). */
export default function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  const label = dark ? 'Modo oscuro activo: cambiar a modo claro' : 'Modo claro activo: cambiar a modo oscuro'
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      aria-pressed={dark}
      className={`inline-flex shrink-0 items-center justify-center rounded-md p-1.5 text-dpm-navy-200 transition-colors hover:bg-white/10 hover:text-white ${className}`}
    >
      {dark ? <Sun aria-hidden="true" className="h-4 w-4" /> : <Moon aria-hidden="true" className="h-4 w-4" />}
    </button>
  )
}
