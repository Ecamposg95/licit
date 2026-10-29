import axios, { type AxiosError } from 'axios'
import { ACCOUNT_EXPIRED_NOTICE, useAuth } from '@/store/auth'
import type {
  ApiErrorBody,
  AuditOut,
  DemoResetSummary,
  DocumentOut,
  Me,
  Meta,
  OpportunityDetail,
  OpportunityPatch,
  OpportunityQuery,
  OpportunityRow,
  Page,
  RequirementRow,
  SourceOut,
  TaskOut,
  Token,
  UserOut,
  DataKind,
} from '@/lib/types'

export const http = axios.create({
  baseURL: '/api/v1',
  // data_kind=REAL&data_kind=SYNTHETIC (FastAPI espera parámetros repetidos, no data_kind[]).
  paramsSerializer: { indexes: null },
})

http.interceptors.request.use((config) => {
  const token = useAuth.getState().token
  // Un Authorization explícito (getMe(token) al cambiar de cuenta) gana sobre el de la sesión guardada.
  if (token && !config.headers.has('Authorization')) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    // Sesión vencida o inválida: se cierra y RequireAuth redirige a /login.
    const isLogin = err.config?.url?.endsWith('/auth/login')
    // Una petición hecha con el token de otra cuenta (el selector, antes de reemplazar la sesión) no cierra la actual.
    const sent = String(err.config?.headers?.Authorization ?? '')
    const current = useAuth.getState().token
    const foreignToken = !!current && !!sent && sent !== `Bearer ${current}`
    if (err.response?.status === 401 && !isLogin && !foreignToken) {
      const code = (err.response.data as { code?: string } | undefined)?.code
      if (code === 'account_expired') useAuth.getState().endSession(ACCOUNT_EXPIRED_NOTICE)
      else useAuth.getState().logout()
    }
    return Promise.reject(toApiError(err))
  },
)

/** Error normalizado de la API con correlation_id para soporte. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly correlationId: string | null
  readonly details: unknown

  constructor(status: number, body: ApiErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.correlationId = body.correlation_id
    this.details = body.details
  }
}

function isErrorBody(x: unknown): x is ApiErrorBody {
  return typeof x === 'object' && x !== null && 'code' in x && 'message' in x
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err
  if (axios.isAxiosError(err)) {
    const status = err.response?.status ?? 0
    const headerCid = (err.response?.headers?.['x-correlation-id'] as string | undefined) ?? null
    const data = err.response?.data
    if (isErrorBody(data)) {
      return new ApiError(status, { ...data, correlation_id: data.correlation_id ?? headerCid })
    }
    if (!err.response) {
      return new ApiError(0, {
        code: 'network_error',
        message: 'No se pudo conectar con el servidor. Revisa tu conexión e intenta de nuevo.',
        correlation_id: null,
        details: null,
      })
    }
    return new ApiError(status, {
      code: 'http_error',
      message: `El servidor respondió con un error (${status}).`,
      correlation_id: headerCid,
      details: null,
    })
  }
  return new ApiError(0, {
    code: 'unexpected',
    message: err instanceof Error ? err.message : 'Ocurrió un error inesperado.',
    correlation_id: null,
    details: null,
  })
}

// ── Identidad ────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<Token> {
  const body = new URLSearchParams({ username: email, password })
  const { data } = await http.post<Token>('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export const getMe = (token?: string) =>
  http
    .get<Me>('/auth/me', token ? { headers: { Authorization: `Bearer ${token}` } } : undefined)
    .then((r) => r.data)

export const getMeta = (token?: string) =>
  http
    .get<Meta>('/meta', token ? { headers: { Authorization: `Bearer ${token}` } } : undefined)
    .then((r) => r.data)

export const listUsers = () => http.get<UserOut[]>('/users').then((r) => r.data)

// ── Oportunidades ────────────────────────────────────────────────────────────

export function listOpportunities(query: OpportunityQuery) {
  const params: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v) && v.length === 0) continue
    params[k] = v
  }
  return http.get<Page<OpportunityRow>>('/opportunities', { params }).then((r) => r.data)
}

export const getOpportunity = (id: string) =>
  http.get<OpportunityDetail>(`/opportunities/${encodeURIComponent(id)}`).then((r) => r.data)

export const patchOpportunity = (id: string, patch: OpportunityPatch) =>
  http.patch<OpportunityDetail>(`/opportunities/${encodeURIComponent(id)}`, patch).then((r) => r.data)

export const getOpportunityRequirements = (id: string) =>
  http.get<RequirementRow[]>(`/opportunities/${encodeURIComponent(id)}/requirements`).then((r) => r.data)

export const getOpportunityDocuments = (id: string) =>
  http.get<DocumentOut[]>(`/opportunities/${encodeURIComponent(id)}/documents`).then((r) => r.data)

export const getOpportunityTasks = (id: string) =>
  http.get<TaskOut[]>(`/opportunities/${encodeURIComponent(id)}/tasks`).then((r) => r.data)

export const getOpportunityHistory = (id: string) =>
  http.get<AuditOut[]>(`/opportunities/${encodeURIComponent(id)}/history`).then((r) => r.data)

// ── Recursos ─────────────────────────────────────────────────────────────────

export const listDocuments = (params: { scope?: string; data_kind?: DataKind[] }) =>
  http.get<DocumentOut[]>('/documents', { params: clean(params) }).then((r) => r.data)

export const listSources = () => http.get<SourceOut[]>('/sources').then((r) => r.data)

export const listTasks = (params: { mine?: boolean; status?: string }) =>
  http.get<TaskOut[]>('/tasks', { params: clean(params) }).then((r) => r.data)

export const listAuditEvents = (params: {
  resource_type?: string
  action?: string
  page?: number
  page_size?: number
}) => http.get<Page<AuditOut>>('/audit-events', { params: clean(params) }).then((r) => r.data)

export const resetDemo = () => http.post<DemoResetSummary>('/demo/reset').then((r) => r.data)

function clean(params: Record<string, unknown>) {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '' || v === false) continue
    if (Array.isArray(v) && v.length === 0) continue
    out[k] = v
  }
  return out
}
