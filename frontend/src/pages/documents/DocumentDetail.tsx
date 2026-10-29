import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ChevronRight, Eye, FileUp } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import { DateTimeText } from '@/components/dates'
import { ErrorPanel, Forbidden, LoadingBlock } from '@/components/feedback'
import DocumentViewer from '@/pages/documents/DocumentViewer'
import { OriginBadge } from '@/pages/documents/DocumentList'
import UploadDialog from '@/pages/documents/UploadDialog'
import { docTypeText, formatBytes, getDocument, originOf, type DocumentRow } from '@/lib/api-documents'
import { scopeLabel } from '@/lib/labels'
import { useApi } from '@/lib/useApi'
import { useCan } from '@/store/auth'

/** `/documentos/:id` — metadatos, historial de versiones y visor por página. Admite `?v=2&page=3`. */
export default function DocumentDetail() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const canRead = useCan('document.read')
  const canUpload = useCan('document.upload')
  const [uploadOpen, setUploadOpen] = useState(false)
  const doc = useApi(() => getDocument(id), [id], canRead)

  if (!canRead) return <Forbidden permission="document.read" />
  if (doc.error) return <ErrorPanel error={doc.error} onRetry={doc.reload} title="No se pudo abrir el documento" />
  if (!doc.data) return <LoadingBlock label="Cargando documento…" />

  const d: DocumentRow = doc.data
  const asked = Number(params.get('v'))
  const version = d.versions.some((v) => v.version === asked) ? asked : d.current_version
  const page = Math.max(1, Number(params.get('page')) || 1)
  const origin = originOf(d)

  function selectVersion(n: number) {
    const next = new URLSearchParams(params)
    next.set('v', String(n))
    next.delete('page')
    setParams(next, { replace: true })
  }

  return (
    <div>
      <nav aria-label="Ruta" className="mb-3 flex items-center gap-1 text-sm text-slate-600">
        <Link to="/documentos" className="link">
          Centro documental
        </Link>
        <ChevronRight aria-hidden="true" className="h-4 w-4 text-slate-400" />
        <span className="truncate" aria-current="page">
          {d.code ?? d.title}
        </span>
      </nav>

      <PageHeader
        title={d.title}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            {d.code && <span className="tabular-nums">{d.code}</span>}
            <OriginBadge origin={origin} />
          </span>
        }
        actions={
          canUpload && !(d.third_party && d.versions.length === 0) && (
            <button type="button" className="btn-primary" onClick={() => setUploadOpen(true)}>
              <FileUp aria-hidden="true" className="h-4 w-4" />
              Subir versión nueva
            </button>
          )
        }
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <DocumentViewer documentId={d.id} version={version} page={page} document={d} showTitle={false} />

        <div className="space-y-4">
          <section aria-label="Datos del documento" className="card p-4">
            <h2 className="text-sm font-semibold text-slate-900">Datos declarados</h2>
            <span aria-hidden="true" className="brand-rule mt-1.5" />
            <dl className="mt-3 space-y-2 text-sm">
              <Row label="Ámbito">{scopeLabel(d.scope)}</Row>
              <Row label="Tipo">{d.doc_type ? docTypeText(d.doc_type) : <span className="muted">No declarado</span>}</Row>
              <Row label="Producto">{d.product_name ?? <span className="muted">Sin producto vinculado</span>}</Row>
              <Row label="Procedimiento">
                {d.opportunity_id ? (
                  <Link to={`/oportunidades/${d.opportunity_id}`} className="link">
                    Abrir procedimiento
                  </Link>
                ) : (
                  <span className="muted">Sin procedimiento</span>
                )}
              </Row>
              <Row label="Emisor declarado">{d.issuer_declared ?? <span className="muted">No declarado</span>}</Row>
              <Row label="Responsable">{d.owner?.full_name ?? <span className="muted">Sin asignar</span>}</Row>
              {d.page_count && <Row label="Páginas">{d.page_count}</Row>}
            </dl>
            <p className="mt-3 text-xs text-slate-500">
              Que un archivo exista no lo valida: la revisión la hace una persona con permiso.
            </p>
          </section>
        </div>
      </div>

      <section aria-label="Historial de versiones" className="card mt-4 overflow-hidden">
        <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900">
          Historial de versiones ({d.versions.length})
        </h2>
        {d.versions.length === 0 ? (
          <p className="px-4 py-6 text-sm text-slate-600">Este documento no tiene versiones: solo se enlaza a su origen.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-base min-w-[860px]">
              <thead>
                <tr>
                  <th scope="col">Versión</th>
                  <th scope="col">Archivo</th>
                  <th scope="col">SHA-256</th>
                  <th scope="col">Nota</th>
                  <th scope="col">Cargada</th>
                  <th scope="col">
                    <span className="sr-only">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...d.versions].reverse().map((v) => (
                  <tr key={v.id} aria-current={v.version === version ? 'true' : undefined} className={v.version === version ? 'bg-dpm-blue-50' : ''}>
                    <td className="whitespace-nowrap font-medium tabular-nums">
                      v{v.version}
                      {v.version === d.current_version && <span className="ml-1.5 text-xs font-normal text-slate-500">vigente</span>}
                    </td>
                    <td className="text-xs">
                      {v.has_file ? (
                        <>
                          {v.filename}
                          <span className="block text-slate-500">{formatBytes(v.size_bytes)}</span>
                        </>
                      ) : (
                        <span className="muted">Sin archivo</span>
                      )}
                    </td>
                    <td>
                      {v.sha256 ? (
                        <code title={v.sha256} className="rounded bg-slate-100 px-1 font-mono text-[11px] text-slate-800">
                          {v.sha256.slice(0, 16)}…
                        </code>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="max-w-xs text-xs">{v.note ?? <span className="muted">—</span>}</td>
                    <td className="text-xs">
                      <DateTimeText value={v.created_at} />
                      {v.uploaded_by && <span className="block text-slate-500">{v.uploaded_by.full_name}</span>}
                    </td>
                    <td className="text-right">
                      <button
                        type="button"
                        className="btn-secondary py-1"
                        onClick={() => selectVersion(v.version)}
                        disabled={v.version === version}
                        aria-label={`Ver la versión ${v.version}`}
                      >
                        <Eye aria-hidden="true" className="h-4 w-4" />
                        {v.version === version ? 'En el visor' : 'Ver'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {canUpload && (
        <UploadDialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          documentId={d.id}
          documentTitle={d.title}
          onUploaded={(next) => {
            doc.setData(next)
            selectVersion(next.current_version)
          }}
        />
      )}
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="min-w-0 text-right text-slate-900">{children}</dd>
    </div>
  )
}
