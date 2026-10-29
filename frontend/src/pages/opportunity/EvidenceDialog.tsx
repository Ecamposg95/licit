import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Eye, FilePlus2, Link2, Search, X } from 'lucide-react'
import { DataKindBadge } from '@/components/badges'
import { ErrorMeta, ErrorPanel, LoadingBlock } from '@/components/feedback'
import { toApiError, type ApiError } from '@/lib/api'
import { docTypeText, listDocuments, type DocumentRow } from '@/lib/api-documents'
import { linkEvidence, workspaceErrorText, type RequirementDetail } from '@/lib/api-workspace'
import { useApi } from '@/lib/useApi'
import type { DataKind } from '@/lib/types'
import { useCan } from '@/store/auth'
import DocumentViewer from '@/pages/documents/DocumentViewer'
import UploadDialog from '@/pages/documents/UploadDialog'

/** <dialog> modal nativo con encabezado y cierre; el contenido lo pone quien lo usa. */
export function ModalShell({
  open,
  title,
  subtitle,
  onClose,
  busy,
  children,
  wide,
}: {
  open: boolean
  title: string
  subtitle?: ReactNode
  onClose: () => void
  busy?: boolean
  children: ReactNode
  wide?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const uid = useId()
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      aria-labelledby={`${uid}-t`}
      onCancel={(e) => {
        e.preventDefault()
        if (!busy) onClose()
      }}
      className={`${wide ? 'w-[min(60rem,calc(100vw-2rem))]' : 'w-[min(38rem,calc(100vw-2rem))]'} max-h-[calc(100vh-2rem)] rounded-xl border border-slate-200 p-0 text-slate-900 shadow-2xl backdrop:bg-slate-900/40`}
    >
      <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-6 py-4">
        <div className="min-w-0">
          <h2 id={`${uid}-t`} className="text-lg font-semibold">
            {title}
          </h2>
          {subtitle && <div className="mt-0.5 text-sm text-slate-600">{subtitle}</div>}
        </div>
        <button type="button" className="btn-ghost -mr-2 shrink-0" onClick={onClose} disabled={busy} aria-label="Cerrar">
          <X aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>
      {open && children}
    </dialog>
  )
}

/** Visor de una evidencia vinculada: el documento en la versión y página citadas. */
export function EvidenceViewerDialog({
  evidence,
  onClose,
}: {
  evidence: { document_id: string; document_title: string; document_version: number | null; page: number | null } | null
  onClose: () => void
}) {
  return (
    <ModalShell open={Boolean(evidence)} title="Evidencia vinculada" subtitle={evidence?.document_title} onClose={onClose} wide>
      {evidence && (
        <div className="p-4">
          {evidence.document_version ? (
            <DocumentViewer
              documentId={evidence.document_id}
              version={evidence.document_version}
              page={evidence.page ?? 1}
              height="60vh"
              showTitle={false}
            />
          ) : (
            <p className="text-sm text-slate-600">Esta evidencia no indica la versión del documento.</p>
          )}
        </div>
      )}
    </ModalShell>
  )
}

interface Props {
  open: boolean
  requirement: RequirementDetail | null
  opportunityId: string
  opportunityDataKind: DataKind
  onClose: () => void
  onLinked: (row: RequirementDetail) => void
}

/**
 * Vincular evidencia: un documento existente (versión, página y fragmento) o uno nuevo que se carga en el momento
 * con el diálogo del centro documental. La evidencia nueva deja el requisito «En revisión»; nunca lo valida.
 */
export default function EvidenceDialog({ open, requirement, opportunityId, opportunityDataKind, onClose, onLinked }: Props) {
  const uid = useId()
  const canUpload = useCan('document.upload')
  const docs = useApi(() => listDocuments({}), [open], open)
  const [extra, setExtra] = useState<DocumentRow[]>([])
  const [q, setQ] = useState('')
  const [docId, setDocId] = useState('')
  const [version, setVersion] = useState<number | null>(null)
  const [page, setPage] = useState('1')
  const [fragment, setFragment] = useState('')
  const [preview, setPreview] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (!open) return
    setExtra([])
    setQ('')
    setDocId('')
    setVersion(null)
    setPage('1')
    setFragment('')
    setPreview(false)
    setError(null)
  }, [open, requirement?.id])

  const realOnly = requirement?.data_kind === 'REAL'
  const all = useMemo(() => {
    const byId = new Map<string, DocumentRow>()
    for (const d of [...extra, ...(docs.data ?? [])]) if (!byId.has(d.id)) byId.set(d.id, d)
    const list = Array.from(byId.values()).filter(
      (d) => d.versions.length > 0 && (!realOnly || d.data_kind !== 'SYNTHETIC'),
    )
    // Primero los del expediente, después el resto (catálogo, empresa).
    return list.sort(
      (a, b) =>
        Number(b.opportunity_id === opportunityId) - Number(a.opportunity_id === opportunityId) ||
        (a.code ?? a.title).localeCompare(b.code ?? b.title),
    )
  }, [docs.data, extra, opportunityId, realOnly])
  const needle = q.trim().toLowerCase()
  const shown = needle
    ? all.filter((d) => `${d.code ?? ''} ${d.title} ${d.product_name ?? ''}`.toLowerCase().includes(needle))
    : all
  const selected = all.find((d) => d.id === docId)

  function pick(d: DocumentRow) {
    setDocId(d.id)
    const withFile = [...d.versions].reverse().find((v) => v.has_file) ?? d.versions[d.versions.length - 1]
    setVersion(withFile?.version ?? null)
    setPage('1')
    setPreview(false)
    setError(null)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!requirement || !selected || !version || busy) return
    setBusy(true)
    setError(null)
    try {
      const n = Number.parseInt(page, 10)
      const row = await linkEvidence(requirement.id, {
        document_id: selected.id,
        version,
        page: Number.isFinite(n) && n > 0 ? n : null,
        fragment: fragment.trim() || null,
      })
      onLinked(row)
      onClose()
    } catch (err) {
      setError(toApiError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <ModalShell
        open={open}
        busy={busy}
        onClose={onClose}
        wide={preview}
        title="Vincular evidencia"
        subtitle={
          requirement && (
            <>
              <span className="font-medium tabular-nums">{requirement.code}</span> · {requirement.text}
            </>
          )
        }
      >
        <form onSubmit={submit} noValidate>
          <div className="max-h-[62vh] space-y-4 overflow-y-auto px-6 py-4">
            <p className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900">
              Al vincularla, el requisito pasa a <strong>«En revisión»</strong>, no a validado. La valida una persona
              distinta de quien cargó o vinculó la evidencia, y cualquier aprobación del expediente queda sin efecto.
            </p>

            <div className="flex flex-wrap items-end justify-between gap-2">
              <div className="min-w-[14rem] flex-1">
                <label htmlFor={`${uid}-q`} className="label">
                  Documento existente
                </label>
                <div className="relative">
                  <Search aria-hidden="true" className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    id={`${uid}-q`}
                    className="input pl-8"
                    placeholder="Buscar por código, título o producto"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                  />
                </div>
              </div>
              {canUpload && (
                <button type="button" className="btn-secondary" onClick={() => setUploadOpen(true)}>
                  <FilePlus2 aria-hidden="true" className="h-4 w-4" />
                  Cargar documento nuevo
                </button>
              )}
            </div>

            {docs.error ? (
              <ErrorPanel error={docs.error} onRetry={docs.reload} title="No se pudo cargar la lista de documentos" />
            ) : !docs.data ? (
              <LoadingBlock label="Cargando documentos…" />
            ) : (
              <fieldset>
                <legend className="sr-only">Elige el documento</legend>
                <ul className="max-h-56 divide-y divide-slate-100 overflow-y-auto rounded-md border border-slate-200">
                  {shown.length === 0 && <li className="px-3 py-4 text-center text-sm text-slate-500">Sin coincidencias.</li>}
                  {shown.slice(0, 80).map((d) => (
                    <li key={d.id}>
                      <label
                        className={`flex cursor-pointer items-start gap-2.5 px-3 py-2 text-sm ${d.id === docId ? 'bg-dpm-blue-50' : 'hover:bg-slate-50'}`}
                      >
                        <input
                          type="radio"
                          name={`${uid}-doc`}
                          checked={d.id === docId}
                          onChange={() => pick(d)}
                          className="mt-1 h-4 w-4 border-slate-300 text-dpm-blue focus:ring-dpm-blue"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block text-slate-900">
                            {d.code && <span className="font-medium tabular-nums">{d.code} · </span>}
                            {d.title}
                          </span>
                          <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                            <DataKindBadge kind={d.data_kind} withTooltip={false} />
                            {docTypeText(d.doc_type)}
                            {d.opportunity_id === opportunityId && <span>· de este expediente</span>}
                            {d.product_name && <span>· {d.product_name}</span>}
                          </span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </fieldset>
            )}

            {selected && (
              <div className="grid gap-3 sm:grid-cols-[8rem_7rem_minmax(0,1fr)]">
                <div>
                  <label htmlFor={`${uid}-v`} className="label">
                    Versión
                  </label>
                  <select
                    id={`${uid}-v`}
                    className="input"
                    value={version ?? ''}
                    onChange={(e) => setVersion(Number(e.target.value))}
                  >
                    {selected.versions.map((v) => (
                      <option key={v.id} value={v.version}>
                        v{v.version}
                        {v.has_file ? '' : ' (sin archivo)'}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`${uid}-p`} className="label">
                    Página
                  </label>
                  <input
                    id={`${uid}-p`}
                    type="number"
                    min={1}
                    max={selected.page_count ?? undefined}
                    className="input"
                    value={page}
                    onChange={(e) => setPage(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor={`${uid}-f`} className="label">
                    Fragmento que lo sustenta (opcional)
                  </label>
                  <input
                    id={`${uid}-f`}
                    className="input"
                    maxLength={2000}
                    value={fragment}
                    onChange={(e) => setFragment(e.target.value)}
                    placeholder="Texto del documento que demuestra el requisito"
                  />
                </div>
              </div>
            )}

            {selected && version && (
              <div>
                <button type="button" className="link inline-flex items-center gap-1 text-sm" onClick={() => setPreview((p) => !p)}>
                  <Eye aria-hidden="true" className="h-4 w-4" />
                  {preview ? 'Ocultar vista previa' : 'Ver el documento en esa página'}
                </button>
                {preview && (
                  <div className="mt-2">
                    <DocumentViewer
                      documentId={selected.id}
                      version={version}
                      page={Number.parseInt(page, 10) || 1}
                      document={selected}
                      height="45vh"
                      showTitle={false}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
          {error && (
            <div className="border-t border-slate-200 px-6 py-3">
              <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
                <p className="font-medium">{workspaceErrorText(error)}</p>
                <ErrorMeta error={error} />
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={!selected || !version || busy}>
              <Link2 aria-hidden="true" className="h-4 w-4" />
              {busy ? 'Vinculando…' : 'Vincular y enviar a revisión'}
            </button>
          </div>
        </form>
      </ModalShell>

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={(doc) => {
          setExtra((prev) => [doc, ...prev])
          pick(doc)
          setQ('')
        }}
        defaults={{
          title: requirement ? `${requirement.text} · ${requirement.code ?? ''}`.trim() : undefined,
          scope: 'expediente',
          doc_type: /ficha/i.test(requirement?.text ?? '') ? 'ficha_tecnica' : undefined,
          data_kind: opportunityDataKind === 'REAL' ? 'REAL' : 'SYNTHETIC',
          opportunity_id: opportunityId,
        }}
      />
    </>
  )
}
