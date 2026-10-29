/** Cliente de la generación de borradores (frente F): vista previa, trabajo, historial, manifiesto y descarga. */
import axios from 'axios'
import { ApiError, http, toApiError } from '@/lib/api'
import type { IsoDateTime, UserRef } from '@/lib/types'

export interface TemplateInfo {
  key: string
  label: string
  filename: string
}

export interface OpenRequirement {
  code: string | null
  text: string
  status: string
  mandatory: boolean | null
  lot: string | null
}

/** Lo que se generaría hoy con los datos actuales. No crea nada en el servidor. */
export interface GenerationPreview {
  data_version: string
  generated_at: IsoDateTime
  notice: string
  templates: TemplateInfo[]
  warnings: string[]
  open_requirements: OpenRequirement[]
  totals_text: string
  fiscal_text: string
  affinity_state: 'calculada' | 'no_calculada'
  last_data_version: string | null
  changed_since_last: boolean
}

export interface ArtifactRow {
  id: string
  opportunity_id: string
  created_at: IsoDateTime
  created_by: UserRef | null
  data_version: string
  template_version: string
  warnings: string[]
  sha256: string
  size_bytes: number
  status: string
  filename: string
}

export type JobStatus = 'queued' | 'running' | 'done' | 'failed'

export interface JobState {
  id: string
  kind: string
  status: JobStatus
  progress: number
  message: string | null
  result: { artifact_id?: string; sha256?: string } | null
  error: string | null
}

export interface ManifestFile {
  name: string
  sha256: string
  size_bytes: number
}

export interface ExcludedDocument {
  code: string | null
  title: string
  data_kind: string
  third_party: boolean
  external_url: string | null
  reason: string
}

export interface Manifest {
  files: ManifestFile[]
  template_version: string
  generated_at: IsoDateTime
  data_version: string
  opportunity: { external_id: string; data_kind: string }
  provenance: Record<'REAL' | 'SYNTHETIC' | 'HISTORICAL', number>
  warnings: string[]
  notice: string
  excluded_documents: ExcludedDocument[]
}

const base = (opportunityId: string) => `/workspaces/${encodeURIComponent(opportunityId)}`

export const getGenerationPreview = (opportunityId: string) =>
  http.get<GenerationPreview>(`${base(opportunityId)}/generation-preview`).then((r) => r.data)

/** La misma `idempotencyKey` devuelve el mismo trabajo (doble clic); una clave nueva encola otro. */
export const startGeneration = (opportunityId: string, templates: string[], idempotencyKey: string) =>
  http
    .post<{ job_id: string; status: JobStatus }>(
      `${base(opportunityId)}/generate`,
      { templates },
      { headers: { 'Idempotency-Key': idempotencyKey } },
    )
    .then((r) => r.data)

export const getJob = (jobId: string) => http.get<JobState>(`/jobs/${encodeURIComponent(jobId)}`).then((r) => r.data)

export const listArtifacts = (opportunityId: string) =>
  http.get<ArtifactRow[]>(`${base(opportunityId)}/artifacts`).then((r) => r.data)

export const getManifest = (artifactId: string) =>
  http.get<Manifest>(`/artifacts/${encodeURIComponent(artifactId)}/manifest`).then((r) => r.data)

/** Clave nueva por clic. `randomUUID` solo existe en contextos seguros; si falta se arma una equivalente. */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

/** Descarga el ZIP con la sesión y lo entrega al navegador. La descarga queda en la bitácora del servidor. */
export async function downloadArtifact(artifactId: string, filename: string): Promise<void> {
  try {
    const res = await http.get<Blob>(`/artifacts/${encodeURIComponent(artifactId)}/download`, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
  } catch (err) {
    // Con responseType blob el cuerpo del error también llega como Blob: se lee para conservar el mensaje del servidor.
    if (axios.isAxiosError(err) && err.response?.data instanceof Blob) {
      try {
        const body = JSON.parse(await err.response.data.text())
        if (body && typeof body === 'object' && 'code' in body && 'message' in body) {
          throw new ApiError(err.response.status, {
            code: body.code,
            message: body.message,
            correlation_id: body.correlation_id ?? null,
            details: body.details ?? null,
          })
        }
      } catch (inner) {
        if (inner instanceof ApiError) throw inner
      }
    }
    throw toApiError(err)
  }
}
