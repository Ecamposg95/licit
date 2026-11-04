/** Tablero «Hoy», clasificación y barrido diario en SIDOF (T17). Refleja `app/schemas/hoy.py` y `app/schemas/sweep.py`. */
import { http } from '@/lib/api'
import type { IsoDate, IsoDateTime, OpportunityDetail, OpportunityRow, TaskOut, UserRef } from '@/lib/types'

export type SweepStatus = 'queued' | 'running' | 'done' | 'partial' | 'failed'

export interface SweepError {
  batch: number | null
  term?: string | null
  code: string
  message: string
}

export interface SweepOut {
  id: string
  day: IsoDate
  attempt: number
  /** daily | manual */
  trigger: string
  status: SweepStatus | string
  terms: string[]
  /** Términos que quedaron fuera por el tope de 30 por barrido. */
  dropped_terms: string[]
  /** notes, procedures, new, updated, unchanged */
  counts: Record<string, number>
  errors: SweepError[]
  /** Nulo = Sistema (barrido diario). */
  created_by: UserRef | null
  started_at: IsoDateTime | null
  finished_at: IsoDateTime | null
}

export interface HoyKpis {
  new_24h: number
  unclassified: number
  unclassified_mine: number
  submitting_7d: number
  my_overdue_tasks: number
}

export interface MatchedSearch {
  id: string
  name: string
  owner: UserRef | null
}

export interface HoyNewItem extends OpportunityRow {
  is_new_since_visit: boolean
  matched: MatchedSearch[]
  /** Coincide con una búsqueda guardada de la persona actual. */
  mine: boolean
  in_territory: boolean
}

export type KeyDateKind = 'questions' | 'submission' | 'ruling'

export interface KeyDate {
  opportunity: OpportunityRow
  kind: KeyDateKind
  at: IsoDateTime
}

export type HoyScope = 'mine' | 'team'

export interface HoyOut {
  kpis: HoyKpis
  kpis_warning: string | null
  sweep: { last: SweepOut | null; scheduled_pending: boolean }
  new_items: HoyNewItem[]
  unassigned: HoyNewItem[]
  key_dates: KeyDate[]
  my_tasks: TaskOut[]
  scope: HoyScope
  last_visit: IsoDateTime | null
}

export interface TriageBody {
  expected_version: number
  action: 'seguir' | 'descartar'
  owner_id?: string | null
  reason?: string | null
}

/** Sin `scope` el backend elige: dirección ve el equipo; los demás roles, lo suyo. */
export const getHoy = (scope?: HoyScope) =>
  http.get<HoyOut>('/hoy', { params: scope ? { scope } : undefined }).then((r) => r.data)

export const getHoyBadge = () => http.get<{ new: number }>('/hoy/badge').then((r) => r.data)

export const triage = (id: string, body: TriageBody) =>
  http.post<OpportunityDetail>(`/opportunities/${encodeURIComponent(id)}/triage`, body).then((r) => r.data)

export const listSweeps = (limit = 10) => http.get<SweepOut[]>('/sweeps', { params: { limit } }).then((r) => r.data)

/** «Volver a barrer». `key` es la clave de idempotencia (una por clic). */
export const startSweep = (key: string) =>
  http
    .post<{ sweep_id: string; job_id: string }>('/sweeps', null, { headers: { 'Idempotency-Key': key } })
    .then((r) => r.data)

