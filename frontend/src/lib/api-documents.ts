/** Cliente del centro documental (frente D): listado, carga con versiones y descarga de archivos. */
import axios from 'axios'
import { ApiError, http, toApiError } from '@/lib/api'
import type { DataKind, DocumentOut, DocumentVersionOut, IsoDate, UserRef } from '@/lib/types'

export interface DocumentVersionRow extends DocumentVersionOut {
  /** false: versión semilla sin archivo, o documento de tercero que solo se enlaza. */
  has_file: boolean
  uploaded_by: UserRef | null
}

export interface DocumentRow extends Omit<DocumentOut, 'versions'> {
  external_url: string | null
  third_party: boolean
  page_count: number | null
  product_name: string | null
  versions: DocumentVersionRow[]
}

export interface DocumentQuery {
  scope?: string
  data_kind?: DataKind[]
  doc_type?: string
  q?: string
  product_id?: string
  opportunity_id?: string
}

/** Tipos de documento que acepta la API, con su etiqueta en español. */
export const DOC_TYPES: { value: string; label: string }[] = [
  { value: 'ficha_tecnica', label: 'Ficha técnica' },
  { value: 'certificado', label: 'Certificado' },
  { value: 'registro', label: 'Registro' },
  { value: 'constancia', label: 'Constancia' },
  { value: 'carta', label: 'Carta' },
  { value: 'catalogo', label: 'Catálogo' },
  { value: 'tecnica_quirurgica', label: 'Técnica quirúrgica' },
  { value: 'folleto', label: 'Folleto' },
  { value: 'bases', label: 'Bases' },
  { value: 'otro', label: 'Otro' },
]

export function docTypeText(code: string | null | undefined): string {
  if (!code) return ''
  return DOC_TYPES.find((t) => t.value === code)?.label ?? code.replace(/_/g, ' ')
}

export const SCOPE_OPTIONS = [
  { value: 'empresa', label: 'Empresa' },
  { value: 'producto', label: 'Producto' },
  { value: 'expediente', label: 'Expediente' },
]

/** Tope de la API (DOCUMENT_MAX_BYTES). El servidor sigue siendo la autoridad; esto solo evita una espera inútil. */
export const MAX_UPLOAD_BYTES = 15 * 1024 * 1024
export const ACCEPTED_EXTENSIONS = '.pdf,.docx,.png,.jpg,.jpeg'

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export const listDocuments = (query: DocumentQuery = {}) => {
  const params: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)) continue
    params[k] = v
  }
  return http.get<DocumentRow[]>('/documents', { params }).then((r) => r.data)
}

export const getDocument = (id: string) =>
  http.get<DocumentRow>(`/documents/${encodeURIComponent(id)}`).then((r) => r.data)

export interface NewDocumentInput {
  file: File
  title: string
  scope: string
  doc_type?: string
  data_kind: DataKind
  product_id?: string
  opportunity_id?: string
  valid_until?: IsoDate
}

export function createDocument(input: NewDocumentInput): Promise<DocumentRow> {
  const body = new FormData()
  body.append('file', input.file)
  body.append('title', input.title)
  body.append('scope', input.scope)
  body.append('data_kind', input.data_kind)
  for (const key of ['doc_type', 'product_id', 'opportunity_id', 'valid_until'] as const) {
    const value = input[key]
    if (value) body.append(key, value)
  }
  return http.post<DocumentRow>('/documents', body).then((r) => r.data)
}

export function uploadVersion(documentId: string, file: File, note?: string): Promise<DocumentVersionRow> {
  const body = new FormData()
  body.append('file', file)
  if (note?.trim()) body.append('note', note.trim())
  return http.post<DocumentVersionRow>(`/documents/${encodeURIComponent(documentId)}/versions`, body).then((r) => r.data)
}

/**
 * Descarga el archivo de una versión como blob, con el encabezado de autorización.
 * Con `responseType: 'blob'` los errores JSON del servidor llegan como Blob; aquí se vuelven a leer
 * para conservar el código (por ejemplo `external_document` y su URL).
 */
export async function fetchVersionFile(documentId: string, version: number, signal?: AbortSignal): Promise<Blob> {
  try {
    const r = await http.get<Blob>(`/documents/${encodeURIComponent(documentId)}/versions/${version}/download`, {
      responseType: 'blob',
      signal,
    })
    return r.data
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.data instanceof Blob) {
      try {
        const body: unknown = JSON.parse(await err.response.data.text())
        if (typeof body === 'object' && body !== null && 'code' in body && 'message' in body) {
          const b = body as { code: string; message: string; correlation_id?: string | null; details?: unknown }
          throw new ApiError(err.response.status, {
            code: b.code,
            message: b.message,
            correlation_id: b.correlation_id ?? null,
            details: b.details ?? null,
          })
        }
      } catch (inner) {
        if (inner instanceof ApiError) throw inner
      }
    }
    throw toApiError(err)
  }
}

/** URL externa de un error `external_document` (documento de tercero), si la hay. */
export function externalUrlOf(error: ApiError): string | null {
  const details = error.details
  if (error.code === 'external_document' && typeof details === 'object' && details !== null && 'external_url' in details) {
    const url = (details as { external_url: unknown }).external_url
    return typeof url === 'string' ? url : null
  }
  return null
}

/** Origen del documento, para mostrarlo sin confundir lo propio con lo de terceros ni lo ficticio con lo real. */
export type DocumentOrigin = 'tercero' | 'catalogo' | 'demo' | 'carga'

export function originOf(doc: Pick<DocumentRow, 'third_party' | 'external_url' | 'data_kind'>): DocumentOrigin {
  if (doc.third_party) return 'tercero'
  if (doc.data_kind === 'SYNTHETIC') return 'demo'
  if (doc.external_url) return 'catalogo'
  return 'carga'
}
