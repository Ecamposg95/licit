import { http } from '@/lib/api'
import type { DataKind, IsoDateTime, OpportunityRow, SourceOut, UserRef } from '@/lib/types'
import type { SearchRun } from '@/lib/api-search'

/** Contratos de gobierno, panel de dirección y estado operativo (app/schemas/governance.py). */

// ── Cuentas demo ─────────────────────────────────────────────────────────────

/** Lo único que publica el backend de una cuenta demo: nunca contraseñas, hashes ni identificadores. */
export interface DemoAccount {
  email: string
  full_name: string
  /** Etiquetas de rol en español. */
  roles: string[]
}

/** Sin autenticación y solo con DEMO_MODE; fuera del modo demo responde 404. */
export const getDemoAccounts = () => http.get<DemoAccount[]>('/demo/accounts').then((r) => r.data)

// ── Gobierno corporativo ─────────────────────────────────────────────────────

export interface IntegrityResult {
  ok: boolean
  checked: number
  first_broken_id: string | null
  verified_at: IsoDateTime
  /** Hash y hora del último evento verificado; null si la cadena está rota o no hay eventos. */
  last_hash: string | null
  last_event_at: IsoDateTime | null
}

export const verifyAuditChain = () => http.get<IntegrityResult>('/governance/audit/verify').then((r) => r.data)

export interface PermissionMatrix {
  roles: { role: string; label: string; permissions: string[] }[]
  permissions: { code: string; label_es: string }[]
}

export const getPermissionMatrix = () => http.get<PermissionMatrix>('/governance/permissions').then((r) => r.data)

export interface ApprovalTarget {
  opportunity_id: string | null
  opportunity_external_id: string | null
  opportunity_title: string | null
  requirement_code: string | null
  data_kind: DataKind | string | null
}

export interface Approval {
  id: string
  action: string
  created_at: IsoDateTime
  actor: UserRef | null
  roles: { role: string; label: string }[]
  resource_type: string
  resource_id: string | null
  target: ApprovalTarget | null
  reason: string | null
  outcome: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  demo_run_id: string | null
}

/** Sin `demoRunId` devuelve la corrida actual. */
export const getApprovals = (demoRunId?: string) =>
  http
    .get<Approval[]>('/governance/approvals', { params: demoRunId ? { demo_run_id: demoRunId } : undefined })
    .then((r) => r.data)

export interface DemoRun {
  id: string
  started_at: IsoDateTime
  actor: UserRef | null
  summary: Record<string, unknown> | null
  is_current: boolean
  events: number
  approvals: number
}

export const getDemoRuns = () => http.get<DemoRun[]>('/governance/runs').then((r) => r.data)

// ── Panel de dirección ───────────────────────────────────────────────────────

export interface KindSummary {
  total: number
  /** Conteo por estado derivado (código de `Derived`). */
  por_estado: Record<string, number>
}

export interface ScenarioAtRisk {
  external_id: string
  opportunity_id: string
  title: string
  blocking: string[]
  data_kind: 'SYNTHETIC'
}

export interface DirectionDashboard {
  /** No existe un total combinado: cada tipo de dato se cuenta por separado. */
  by_data_kind: Partial<Record<DataKind, KindSummary>>
  upcoming_real: OpportunityRow[]
  /** Mismo contrato que `GET /search-runs/{id}` (frente C). */
  last_search: SearchRun | null
  scenarios_at_risk: ScenarioAtRisk[]
}

export const getDirectionDashboard = () => http.get<DirectionDashboard>('/dashboard/direccion').then((r) => r.data)

