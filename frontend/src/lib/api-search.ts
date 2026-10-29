/** Búsqueda en vivo (corridas en SIDOF), trabajos asíncronos e importación manual. Refleja `app/schemas/search.py`. */
import { http } from '@/lib/api'
import type { IsoDate, IsoDateTime, OpportunityRow, UserRef } from '@/lib/types'

/** Diccionario inicial (mismo orden que `search_runs.DEFAULT_TERMS` del backend). */
export const DEFAULT_TERMS = ['osteosintesis', 'endoprotesis', 'implantes ortopedicos', 'material de osteosintesis']
export const MAX_TERMS = 10

export type SearchRunStatus = 'queued' | 'running' | 'done' | 'partial' | 'failed'

export interface SearchCounts {
  notes: number
  procedures: number
  new: number
  updated: number
  unchanged: number
}

export interface SearchTerm extends SearchCounts {
  term: string
  status: string
  checked_at: IsoDateTime | null
  total: number | null
  read: number
  skipped_non_cv: number
  seen_other_term: number
  discarded: number
  errors: number
}

export interface SearchErrorItem {
  source: string
  term: string | null
  code: 'source_unavailable' | 'zero_unconfirmed' | 'aborted' | 'truncated' | 'internal_error' | string
  message: string
}

export interface SearchRun {
  id: string
  status: SearchRunStatus
  query: { terms: string[]; date_from: IsoDate; date_to: IsoDate }
  counts: SearchCounts
  terms: SearchTerm[]
  errors: SearchErrorItem[]
  job_id: string | null
  created_by: UserRef | null
  created_at: IsoDateTime
  started_at: IsoDateTime | null
  finished_at: IsoDateTime | null
}

export interface JobOut {
  id: string
  kind: string
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  message: string | null
  result: Record<string, unknown> | null
  error: string | null
  created_at: IsoDateTime
  started_at: IsoDateTime | null
  finished_at: IsoDateTime | null
}

/** Clave nueva por clic: un doble clic reutiliza el mismo trabajo; un reintento posterior abre uno nuevo. */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

export function startSearch(body: { terms: string[]; date_from: IsoDate; date_to: IsoDate }, idempotencyKey: string) {
  return http
    .post<{ search_run_id: string; job_id: string }>('/search-runs', body, {
      headers: { 'Idempotency-Key': idempotencyKey },
    })
    .then((r) => r.data)
}

export const listSearchRuns = () => http.get<SearchRun[]>('/search-runs').then((r) => r.data)
export const getSearchRun = (id: string) => http.get<SearchRun>(`/search-runs/${id}`).then((r) => r.data)
export const getJob = (id: string) => http.get<JobOut>(`/jobs/${id}`).then((r) => r.data)

export interface ManualMetadata {
  external_id: string
  title: string
  buyer: string
  source_url: string
  /** "YYYY-MM-DDTHH:mm" sin zona: el backend la toma como hora de Ciudad de México. */
  submission_at?: string | null
  notes?: string | null
}

export type ImportOutcome = 'new' | 'updated' | 'unchanged'

export interface ProcedureChoice {
  external_id: string
  title: string | null
}

export async function importOpportunity(
  body: { url: string; external_id?: string } | { metadata: ManualMetadata },
): Promise<{ row: OpportunityRow; outcome: ImportOutcome }> {
  const r = await http.post<OpportunityRow>('/opportunities/import', body)
  const outcome = (r.headers['x-import-outcome'] as ImportOutcome | undefined) ?? (r.status === 201 ? 'new' : 'unchanged')
  return { row: r.data, outcome }
}

export const COMPRASMX_URL = 'https://comprasmx.buengobierno.gob.mx/sitiopublico/#/'
