import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CircleCheck, FileUp, Search } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import DataKindChips, { usePersistentDataKinds } from '@/components/DataKindChips'
import { isDocumentExpired } from '@/components/DocumentsTable'
import { UnavailableAction } from '@/components/Tooltip'
import { EmptyState, ErrorPanel, Forbidden, TableSkeleton } from '@/components/feedback'
import DocumentList from '@/pages/documents/DocumentList'
import UploadDialog from '@/pages/documents/UploadDialog'
import { docTypeText, listDocuments, type DocumentRow } from '@/lib/api-documents'
import { useApi } from '@/lib/useApi'
import { useAuth, useCan } from '@/store/auth'

const SCOPES = [
  { value: '', label: 'Todos' },
  { value: 'empresa', label: 'Empresa' },
  { value: 'producto', label: 'Producto' },
  { value: 'expediente', label: 'Expediente' },
]

export default function Documents() {
  const canRead = useCan('document.read')
  const canUpload = useCan('document.upload')
  const baseDate = useAuth((s) => s.meta?.demo_base_date)
  const [kinds, setKinds] = usePersistentDataKinds('licit.documents.dataKinds')
  const [scope, setScope] = useState('')
  const [docType, setDocType] = useState('')
  const [text, setText] = useState('')
  const [onlyExpired, setOnlyExpired] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploaded, setUploaded] = useState<DocumentRow | null>(null)

  const noKinds = kinds.length === 0
  const docs = useApi(() => listDocuments({ scope, data_kind: kinds }), [scope, kinds.join(',')], canRead && !noKinds)

  const types = useMemo(
    () => Array.from(new Set((docs.data ?? []).map((d) => d.doc_type).filter((t): t is string => !!t))).sort(),
    [docs.data],
  )
  const rows = useMemo(() => {
    const q = text.trim().toLowerCase()
    return (docs.data ?? []).filter(
      (d) =>
        (!docType || d.doc_type === docType) &&
        (!onlyExpired || isDocumentExpired(d, baseDate)) &&
        (!q || d.title.toLowerCase().includes(q) || (d.code ?? '').toLowerCase().includes(q)),
    )
  }, [docs.data, docType, onlyExpired, baseDate, text])

  if (!canRead) return <Forbidden permission="document.read" />

  return (
    <div>
      <PageHeader
        title="Centro documental"
        description="Biblioteca por ámbito de empresa, producto y expediente. Cada archivo se guarda con su huella SHA-256 y sus versiones; la vigencia de documentos simulados se evalúa contra la fecha base del demo."
        actions={
          canUpload ? (
            <button type="button" className="btn-primary" onClick={() => setUploadOpen(true)}>
              <FileUp aria-hidden="true" className="h-4 w-4" />
              Cargar documento
            </button>
          ) : (
            <UnavailableAction
              label="Cargar documento"
              icon={<FileUp aria-hidden="true" className="h-4 w-4" />}
              reason="Tu rol no tiene el permiso document.upload. Pide a quien administra el demo que revise tus roles."
            />
          )
        }
      />

      {uploaded && (
        <p role="status" className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-900">
          <CircleCheck aria-hidden="true" className="h-4 w-4 shrink-0" />
          <span>
            Se cargó «{uploaded.title}» (versión {uploaded.current_version}). Queda pendiente de revisión.
          </span>
          <Link to={`/documentos/${uploaded.id}`} className="link">
            Abrir en el visor
          </Link>
        </p>
      )}

      <section aria-label="Filtros" className="card mb-4 p-4">
        <DataKindChips value={kinds} onChange={setKinds} />
        <div className="mt-4 flex flex-wrap items-end gap-4">
          <div role="group" aria-label="Ámbito">
            <span className="label">Ámbito</span>
            <div className="inline-flex overflow-hidden rounded-md border border-slate-300">
              {SCOPES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  aria-pressed={scope === s.value}
                  onClick={() => setScope(s.value)}
                  className={`border-r border-slate-300 px-3 py-1.5 text-sm last:border-r-0 ${
                    scope === s.value ? 'bg-dpm-blue-700 font-medium text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label htmlFor="d-type" className="label">
              Tipo
            </label>
            <select id="d-type" className="input w-48" value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="">Todos</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {docTypeText(t)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="d-q" className="label">
              Buscar por título o código
            </label>
            <div className="relative">
              <Search aria-hidden="true" className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
              <input id="d-q" type="search" className="input w-64 pl-8" value={text} onChange={(e) => setText(e.target.value)} />
            </div>
          </div>
          <label className="inline-flex items-center gap-2 pb-2 text-sm text-slate-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-dpm-blue focus:ring-dpm-blue"
              checked={onlyExpired}
              onChange={(e) => setOnlyExpired(e.target.checked)}
            />
            Sólo vencidos
          </label>
        </div>
      </section>

      <div className="card overflow-hidden">
        {noKinds ? (
          <EmptyState title="Activa al menos un tipo de dato">Elige REAL, HISTÓRICO o SIMULADO para ver documentos.</EmptyState>
        ) : docs.error ? (
          <div className="p-4">
            <ErrorPanel error={docs.error} onRetry={docs.reload} />
          </div>
        ) : !docs.data ? (
          <TableSkeleton cols={7} />
        ) : rows.length === 0 ? (
          <EmptyState title="Sin documentos para estos filtros">Ajusta o limpia los filtros.</EmptyState>
        ) : (
          <>
            <p className="border-b border-slate-200 px-4 py-2.5 text-sm text-slate-600" aria-live="polite">
              {rows.length} {rows.length === 1 ? 'documento' : 'documentos'}
            </p>
            <DocumentList docs={rows} />
          </>
        )}
      </div>

      {canUpload && (
        <UploadDialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onUploaded={(doc) => {
            setUploaded(doc)
            docs.reload()
          }}
        />
      )}
    </div>
  )
}
