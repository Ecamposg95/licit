/** Cliente del expediente (frente E): motor de correspondencia, matriz interactiva, decisión y aprobaciones. */
import { http, type ApiError } from '@/lib/api'
import type {
  DataKind,
  DecimalString,
  EvidenceOut,
  IsoDate,
  IsoDateTime,
  OpenTaskRef,
  RequirementRow,
  TaskOut,
  UserRef,
} from '@/lib/types'

// ── Tipos ────────────────────────────────────────────────────────────────────

export type MatchResult = 'coincide' | 'incumple' | 'desconocido' | 'no_comparable'
export type Validity = 'vigente' | 'vence_antes' | 'vencido' | 'sin_vigencia'

/** Evaluación del motor guardada para un requisito (también llega dentro de la fila de la matriz). */
export interface RequirementAssessment {
  result: MatchResult | string
  explanation: string
  rule: string
  engine_version: string
  catalog_value: string | null
  source_text: string | null
  variant_sku: string | null
  assessed_at: IsoDateTime
}

export interface EvidenceDetail extends EvidenceOut {
  document_version_id: string | null
  document_version: number | null
  document_data_kind: DataKind | null
  document_page_count: number | null
  /** Quién vinculó la evidencia. */
  created_by: UserRef | null
  /** Quién subió la versión del documento. */
  uploaded_by: UserRef | null
  reviewer: UserRef | null
  reviewed_at: IsoDateTime | null
  reason: string | null
  validity: Validity | string
}

export interface MatrixTaskRef extends OpenTaskRef {
  assignee_id?: string | null
}

export interface RequirementDetail extends Omit<RequirementRow, 'evidence' | 'open_task'> {
  evidence: EvidenceDetail[]
  open_task: MatrixTaskRef | null
  assessment: RequirementAssessment | null
  /** Fecha contra la que se revisa la vigencia de la evidencia (la del requisito o la de presentación). */
  required_by: IsoDate | null
}

export interface AffinityComponent {
  weight: number
  score: number | null
  known: number
  total: number
}

export type AffinityKey = 'familia' | 'atributos' | 'documental' | 'capacidad'

export interface Affinity {
  components: Record<AffinityKey, AffinityComponent>
  /** null = cobertura incompleta (algún componente sin datos). */
  total: number | null
  coverage_complete: boolean
  blocking: string[]
}

export interface WorkspaceOut {
  /** null mientras el expediente no se ha abierto (sin decisión, aprobaciones ni evaluación). */
  id: string | null
  opportunity_id: string
  decision: 'pendiente' | 'participar' | 'no_participar' | string
  decision_by: UserRef | null
  decision_at: IsoDateTime | null
  decision_reason: string | null
  technical_approval_by: UserRef | null
  technical_approval_at: IsoDateTime | null
  commercial_approval_by: UserRef | null
  commercial_approval_at: IsoDateTime | null
  approvals_stale: boolean
  phase: 'analisis' | 'preparacion' | 'listo_revision_final' | 'descartada' | string
  version: number
}

export interface AssessmentOut {
  id: string
  lot_id: string
  lot_number: string | null
  requirement_id: string | null
  requirement_code: string | null
  variant_id: string | null
  variant_sku: string | null
  variant_name: string | null
  variant_data_kind: DataKind | null
  product_id: string | null
  result: MatchResult | string
  explanation: string
  rule: string
  engine_version: string
  catalog_value: string | null
  source_text: string | null
  assessed_at: IsoDateTime
}

export interface LotPrice {
  lot_id: string
  number: string
  unit_price: DecimalString | null
  currency: string | null
  /** Procedencia del precio, independiente del producto (en los escenarios siempre SYNTHETIC). */
  price_data_kind: DataKind | null
  /** Ficha del producto propuesto (para enlazar a /catalogo/:id). */
  product_id: string | null
  product_name: string | null
  product_review_status: string | null
}

export interface WorkspaceView {
  workspace: WorkspaceOut
  affinity: Affinity | null
  assessments: AssessmentOut[]
  lots: LotPrice[]
}

export interface ReadinessItem {
  code: string
  kind: 'decision' | 'requisito' | 'vigencia' | 'conflicto' | 'aprobacion' | string
  message: string
  status?: string
}

export type ReviewDecision =
  | 'cumple_validado'
  | 'incumple'
  | 'faltante'
  | 'vencido'
  | 'desconocido'
  | 'pendiente'
  | 'no_aplica_justificado'

// ── Llamadas ─────────────────────────────────────────────────────────────────

const enc = encodeURIComponent

export const getRequirementMatrix = (opportunityId: string) =>
  http.get<RequirementDetail[]>(`/opportunities/${enc(opportunityId)}/requirements`).then((r) => r.data)

export const getWorkspace = (opportunityId: string) =>
  http.get<WorkspaceView>(`/workspaces/${enc(opportunityId)}`).then((r) => r.data)

export const assessWorkspace = (opportunityId: string) =>
  http.post<WorkspaceView>(`/workspaces/${enc(opportunityId)}/assess`).then((r) => r.data)

export const decideWorkspace = (opportunityId: string, decision: 'participar' | 'no_participar', reason: string) =>
  http.post<WorkspaceView>(`/workspaces/${enc(opportunityId)}/decision`, { decision, reason }).then((r) => r.data)

export const approveWorkspace = (opportunityId: string, kind: 'tecnica' | 'comercial') =>
  http.post<WorkspaceView>(`/workspaces/${enc(opportunityId)}/approvals`, { kind }).then((r) => r.data)

export const markWorkspaceReady = (opportunityId: string) =>
  http.post<WorkspaceView>(`/workspaces/${enc(opportunityId)}/ready`).then((r) => r.data)

export interface EvidenceInput {
  document_id: string
  version: number
  page?: number | null
  fragment?: string | null
}

export const linkEvidence = (requirementId: string, input: EvidenceInput) =>
  http.post<RequirementDetail>(`/requirements/${enc(requirementId)}/evidence`, input).then((r) => r.data)

export const reviewRequirement = (
  requirementId: string,
  input: { decision: ReviewDecision; reason: string; expected_version: number },
) => http.patch<RequirementDetail>(`/requirements/${enc(requirementId)}/review`, input).then((r) => r.data)

export const assignRequirementTask = (
  requirementId: string,
  input: { assignee_id: string; due_date?: IsoDate | null; title?: string | null },
) => http.post<TaskOut>(`/requirements/${enc(requirementId)}/tasks`, input).then((r) => r.data)

export const updateTaskStatus = (taskId: string, status: string) =>
  http.patch<TaskOut>(`/tasks/${enc(taskId)}`, { status }).then((r) => r.data)

// ── Mensajes de error en español ─────────────────────────────────────────────

/** Texto exacto acordado para la autoaprobación (spec §2.3). */
export const SELF_APPROVAL_TEXT = 'No puedes aprobar evidencia que tú cargaste. Cambia a la cuenta del revisor'

const ERROR_TEXT: Record<string, string> = {
  self_approval: SELF_APPROVAL_TEXT,
  evidence_expired:
    'La evidencia está vencida o vence antes de la fecha exigida. No se puede validar: incorpora un documento vigente.',
  version_conflict: 'El requisito cambió desde que lo abriste. Recarga la matriz y revisa la versión actual.',
  segregation:
    'La aprobación técnica y la comercial deben darlas personas distintas. Cambia a otra cuenta para dar la otra aprobación.',
  reason_required: 'Escribe el motivo: queda en la bitácora.',
  evidence_required: 'No se valida un requisito sin evidencia vinculada.',
  evidence_already_linked: 'Esa versión del documento ya es evidencia de este requisito.',
  synthetic_evidence: 'Un documento ficticio no puede ser evidencia de un procedimiento real.',
  page_out_of_range: 'Esa página no existe en el documento.',
  forbidden: 'Tu rol no tiene permiso para esta acción.',
  not_ready: 'El expediente aún no puede pasar a revisión final. Atiende los bloqueantes.',
}

export function workspaceErrorText(error: ApiError): string {
  return ERROR_TEXT[error.code] ?? error.message
}

export function readinessItems(error: ApiError): ReadinessItem[] {
  const d = error.details as { items?: ReadinessItem[]; blockers?: string[] } | null
  if (error.code !== 'not_ready' || !d) return []
  if (Array.isArray(d.items)) return d.items
  return (d.blockers ?? []).map((code) => ({ code, kind: 'requisito', message: '' }))
}
