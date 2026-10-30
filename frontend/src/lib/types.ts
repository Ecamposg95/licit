/**
 * Tipos de la API v1. Reflejan `app/schemas/v1.py` (fuente de verdad).
 *
 * Convenciones de serialización:
 * - `datetime` → string ISO 8601 (instante; si llega sin zona se interpreta como UTC).
 * - `date` → string "YYYY-MM-DD" (fecha de calendario, sin conversión de zona).
 * - `Decimal` → string decimal (p. ej. "1500.00"); nunca se opera como float.
 */

export type IsoDateTime = string
export type IsoDate = string
export type DecimalString = string

export type DataKind = 'REAL' | 'HISTORICAL' | 'SYNTHETIC'
export const DATA_KINDS: DataKind[] = ['REAL', 'HISTORICAL', 'SYNTHETIC']

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** Cuerpo normalizado de error (§9): {code, message, correlation_id, details}. */
export interface ApiErrorBody {
  code: string
  message: string
  correlation_id: string | null
  details: unknown
}

// ── Identidad ────────────────────────────────────────────────────────────────

export interface Token {
  access_token: string
  token_type: string
  expires_in: number
}

export interface UserRef {
  id: string
  full_name: string
  email: string
}

export interface UserOut extends UserRef {
  role_names: string[]
  is_active: boolean
}

export interface Me extends UserOut {
  permissions: string[]
  organization_id: string
}

export interface Meta {
  organization: string
  demo_mode: boolean
  demo_base_date: IsoDate
  watermark: string
  display_timezone: string
  freshness_ttl_hours: number
  server_time: IsoDateTime
  roles: Record<string, string>
}

export type Permission =
  | 'opportunity.read'
  | 'opportunity.write'
  | 'opportunity.import'
  | 'search.run'
  | 'catalog.read'
  | 'catalog.import'
  | 'catalog.edit'
  | 'document.read'
  | 'document.upload'
  | 'document.validate'
  | 'requirement.read'
  | 'requirement.review'
  | 'task.read'
  | 'task.assign'
  | 'task.update'
  | 'bid.decide'
  | 'pricing.approve'
  | 'proposal.generate'
  | 'artifact.download'
  | 'audit.read'
  | 'user.manage'
  | 'source.manage'
  | 'demo.reset'

// ── Fuentes y oportunidades ──────────────────────────────────────────────────

export type SourceStatus = 'no_probada' | 'activa' | 'bloqueada' | 'inaccesible'

export interface SourceOut {
  id: string
  key: string
  name: string
  base_url: string | null
  method: string
  status: SourceStatus | string
  last_checked_at: IsoDateTime | null
  last_error: string | null
  notes: string | null
}

export interface SourceRef {
  key: string
  name: string
  status: SourceStatus | string
}

export interface Derived {
  code: string
  label: string
  reason: string
}

export type SubmissionPrecision = 'date' | 'datetime'

export interface OpportunityRow {
  id: string
  external_id: string
  title: string
  buyer: string
  state: string | null
  procedure_type: string | null
  families: string[]
  data_kind: DataKind
  source: SourceRef | null
  source_url: string | null
  last_checked_at: IsoDateTime | null
  submission_at: IsoDateTime | null
  submission_precision: SubmissionPrecision | string
  verification_status: string
  derived: Derived
  owner: UserRef | null
  /** Se calcula en E3 (motor de correspondencia); hoy siempre null. */
  affinity: Record<string, unknown> | null
  open_requirements: number
}

export interface VariantRef {
  id: string
  sku: string
  name: string
  attributes: Record<string, unknown>
  data_kind: DataKind
}

/** Especificación exigida por una partida: {"holes": {"value": 6, "unit": "orificios", "operator": "eq"}}. */
export interface LotSpec {
  value?: unknown
  unit?: string | null
  operator?: string | null
}

export interface LotOut {
  id: string
  number: string
  description: string
  family: string | null
  quantity: DecimalString | null
  unit: string | null
  specs: Record<string, LotSpec | unknown>
  proposed_variant: VariantRef | null
}

export interface OpportunityDetail extends OpportunityRow {
  buying_unit: string | null
  character: string | null
  reported_status: string | null
  verification_scope: string | null
  result: string
  questions_at: IsoDateTime | null
  ruling_at: IsoDateTime | null
  source_timezone: string | null
  timezone_assumed: boolean
  estimated_amount: DecimalString | null
  currency: string | null
  requires_human_review: boolean
  notes: string | null
  version: number
  lots: LotOut[]
  requirement_counts: Record<string, number>
}

export interface OpportunityPatch {
  expected_version: number
  owner_id?: string | null
  notes?: string | null
  families?: string[] | null
}

export interface OpportunityQuery {
  q?: string
  family?: string
  state?: string
  source?: string
  data_kind?: DataKind[]
  period_from?: IsoDate
  period_to?: IsoDate
  page?: number
  page_size?: number
}

// ── Documentos, requisitos y tareas ──────────────────────────────────────────

export interface DocumentVersionOut {
  id: string
  version: number
  filename: string | null
  content_type: string | null
  size_bytes: number | null
  sha256: string | null
  note: string | null
  created_at: IsoDateTime
}

export type DocumentScope = 'empresa' | 'producto' | 'expediente'

export interface DocumentOut {
  id: string
  code: string | null
  title: string
  scope: DocumentScope | string
  doc_type: string | null
  issuer_declared: string | null
  valid_until: IsoDate | null
  review_status: string
  data_kind: DataKind
  watermark: string | null
  product_id: string | null
  opportunity_id: string | null
  current_version: number
  owner: UserRef | null
  versions: DocumentVersionOut[]
}

export interface EvidenceOut {
  id: string
  document_id: string
  document_code: string | null
  document_title: string
  document_valid_until: IsoDate | null
  page: number | null
  fragment: string | null
  decision: string
}

export type RequirementStatus =
  | 'pendiente'
  | 'desconocido'
  | 'faltante'
  | 'vencido'
  | 'incumple'
  | 'en_revision'
  | 'cumple_validado'
  | 'no_aplica_justificado'

export interface RequirementLotRef {
  id: string
  number: string
  description: string
}

export interface OpenTaskRef {
  id: string
  status: string
  /** Nombre del responsable (no UserRef). */
  assignee: string | null
  due_date: IsoDate | null
}

export interface RequirementRow {
  id: string
  code: string | null
  text: string
  req_type: string | null
  /** null = no determinable desde las bases. */
  mandatory: boolean | null
  scope: string | null
  lot: RequirementLotRef | null
  attribute: string | null
  operator: string | null
  expected_value: string | null
  unit: string | null
  page: number | null
  fragment: string | null
  source_label: string | null
  bases_version: string | null
  status: RequirementStatus | string
  status_reason: string | null
  reviewer: UserRef | null
  due_date: IsoDate | null
  required_valid_until: IsoDate | null
  next_action: string | null
  data_kind: DataKind
  version: number
  evidence: EvidenceOut[]
  open_task: OpenTaskRef | null
}

export type TaskStatus = 'pendiente' | 'en_progreso' | 'hecha' | 'cancelada'

export interface TaskOut {
  id: string
  code: string | null
  title: string
  status: TaskStatus | string
  assignee: UserRef | null
  due_date: IsoDate | null
  opportunity_id: string | null
  requirement_id: string | null
  data_kind: DataKind
}

export interface AuditOut {
  id: string
  actor: UserRef | null
  action: string
  resource_type: string
  resource_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  correlation_id: string | null
  created_at: IsoDateTime
}

/** Respuesta de POST /demo/reset (dict libre del backend). */
export type DemoResetSummary = Record<string, unknown>
