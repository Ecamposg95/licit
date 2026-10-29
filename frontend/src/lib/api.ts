import axios from 'axios'
import { useAuth } from '@/store/auth'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = useAuth.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) useAuth.getState().logout()
    return Promise.reject(err)
  },
)

export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  }
  return 'Ocurrió un error inesperado'
}

export type Estatus =
  | 'detectada'
  | 'en_analisis'
  | 'en_preparacion'
  | 'presentada'
  | 'ganada'
  | 'perdida'
  | 'desierta'
  | 'cancelada'
  | 'descartada'

export type Tipo = 'licitacion_publica' | 'invitacion_3' | 'adjudicacion_directa'
export type Caracter = 'nacional' | 'internacional_tlc' | 'internacional_abierta'

export interface Licitacion {
  id: string
  numero_procedimiento: string
  titulo: string
  dependencia: string
  unidad_compradora: string | null
  entidad_federativa: string | null
  tipo: Tipo
  caracter: Caracter
  estatus: Estatus
  fecha_publicacion: string | null
  fecha_junta_aclaraciones: string | null
  fecha_apertura: string | null
  fecha_fallo: string | null
  monto_estimado: string | null
  url_fuente: string | null
  notas: string | null
  responsable_id: string | null
}

export interface User {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'gerente' | 'analista' | 'viewer'
}

export const ESTATUS_LABEL: Record<Estatus, string> = {
  detectada: 'Detectada',
  en_analisis: 'En análisis',
  en_preparacion: 'En preparación',
  presentada: 'Presentada',
  ganada: 'Ganada',
  perdida: 'Perdida',
  desierta: 'Desierta',
  cancelada: 'Cancelada',
  descartada: 'Descartada',
}

export const TIPO_LABEL: Record<Tipo, string> = {
  licitacion_publica: 'Licitación pública',
  invitacion_3: 'Invitación a 3',
  adjudicacion_directa: 'Adjudicación directa',
}
