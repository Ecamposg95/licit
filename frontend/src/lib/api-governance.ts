import { http } from '@/lib/api'
import type { DataKind, IsoDateTime, OpportunityRow, SourceOut, UserRef } from '@/lib/types'

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

export interface SearchRunBrief {
  id: string
  status: string
  started_at: IsoDateTime | null
  finished_at: IsoDateTime | null
  counts: Record<string, unknown>
  errors: unknown[]
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
  last_search: SearchRunBrief | null
  scenarios_at_risk: ScenarioAtRisk[]
}

export const getDirectionDashboard = () => http.get<DirectionDashboard>('/dashboard/direccion').then((r) => r.data)

// ── Estado operativo (TI) ────────────────────────────────────────────────────

export interface JobBrief {
  id: string
  kind: string
  status: string
  progress: number
  message: string | null
  error: string | null
  attempts: number
  created_at: IsoDateTime
  started_at: IsoDateTime | null
  finished_at: IsoDateTime | null
}

export interface OpsStatus {
  version: string
  /** Revisión de Alembic aplicada en la base; null si el esquema no se creó con Alembic. */
  alembic_head: string | null
  storage_backend: 's3' | 'local' | 'invalid'
  storage_error: string | null
  worker_alive: boolean
  sources: SourceOut[]
  jobs: JobBrief[]
  demo_run: { id: string; started_at: IsoDateTime; actor: UserRef | null; summary: Record<string, unknown> | null } | null
}

export const getOpsStatus = () => http.get<OpsStatus>('/ops/status').then((r) => r.data)
