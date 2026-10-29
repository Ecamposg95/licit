import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Download, ExternalLink, FileWarning, Link2, TriangleAlert } from 'lucide-react'
import { DataKindBadge, ReviewStatusBadge } from '@/components/badges'
import { CalendarDate, DateTimeText } from '@/components/dates'
import { CatalogCredit } from '@/components/brand/Footer'
import { ErrorPanel, LoadingBlock } from '@/components/feedback'
import {
  docTypeText,
  externalUrlOf,
  fetchVersionFile,
  formatBytes,
  getDocument,
  type DocumentRow,
  type DocumentVersionRow,
} from '@/lib/api-documents'
import { ApiError, toApiError } from '@/lib/api'
import { useApi } from '@/lib/useApi'
import { useAuth } from '@/store/auth'

const FALLBACK_WATERMARK = 'DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN'

interface Props {
  documentId: string
  /** Número de versión a mostrar (no el id). */
  version: number
  /** Página inicial del PDF (1 por omisión). Al cambiarla desde fuera, el visor salta a esa página. */
  page?: number
  /** Si ya se tiene el documento cargado, evita pedirlo otra vez. */
  document?: DocumentRow
  /** Alto del visor en CSS. */
  height?: string
  /** Muestra la cabecera de título (se apaga cuando la pantalla ya la presenta). */
  showTitle?: boolean
}

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

/** Fecha de consulta de un documento importado del catálogo: el día en que se guardó (UTC → día calendario). */
function consultedOn(version: DocumentVersionRow | undefined): string | null {
  return version?.created_at ? version.created_at.slice(0, 10) : null
}

/**
 * Visor por página: descarga la versión como blob con el encabezado de autorización y la muestra en un
 * <iframe> con `#page=N`. Un documento SYNTHETIC lleva la marca DEMO; uno de tercero no se descarga:
 * se muestra como enlace externo. Las URLs de objeto se revocan al cambiar de versión y al desmontar.
 */
export default function DocumentViewer({ documentId, version, page = 1, document: provided, height = '70vh', showTitle = true }: Props) {
  const watermark = useAuth((s) => s.meta?.watermark) ?? FALLBACK_WATERMARK
  const loaded = useApi(() => getDocument(documentId), [documentId], !provided)
  const doc = provided ?? loaded.data
  const row = doc?.versions.find((v) => v.version === version)

  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [fileError, setFileError] = useState<ApiError | null>(null)
  const [fileLoading, setFileLoading] = useState(false)
  const [currentPage, setCurrentPage] = useState(Math.max(1, page))

  useEffect(() => setCurrentPage(Math.max(1, page)), [page, documentId, version])

  const wantsFile = Boolean(doc && row?.has_file)
  useEffect(() => {
    if (!wantsFile) {
      setObjectUrl(null)
      return
    }
    const controller = new AbortController()
    let created: string | null = null
    setFileLoading(true)
    setFileError(null)
    setObjectUrl(null)
    fetchVersionFile(documentId, version, controller.signal)
      .then((blob) => {
        created = URL.createObjectURL(blob)
        setObjectUrl(created)
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setFileError(toApiError(e))
      })
      .finally(() => {
        if (!controller.signal.aborted) setFileLoading(false)
      })
    return () => {
      controller.abort()
      if (created) URL.revokeObjectURL(created)
    }
  }, [documentId, version, wantsFile])

  if (loaded.error && !provided) return <ErrorPanel error={loaded.error} onRetry={loaded.reload} />
  if (!doc) return <LoadingBlock label="Cargando documento…" />

  const externalUrl = (fileError && externalUrlOf(fileError)) || (doc.third_party && !row?.has_file ? doc.external_url : null)
  const contentType = row?.content_type ?? ''
  const isPdf = contentType === 'application/pdf'
  const isImage = contentType.startsWith('image/')
  const pageCount = doc.page_count && isPdf ? doc.page_count : null
  const clamp = (n: number) => Math.min(Math.max(1, Math.round(n) || 1), pageCount ?? 9999)

  return (
    <section aria-label={`Visor de ${doc.title}`} className="card overflow-hidden">
      <header className="space-y-2 border-b border-slate-200 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          {showTitle && <h2 className="min-w-0 flex-1 text-base font-semibold text-slate-900">{doc.title}</h2>}
          <DataKindBadge kind={doc.data_kind} />
          <ReviewStatusBadge status={doc.review_status} />
        </div>
        <dl className="grid gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="inline font-medium text-slate-500">Versión </dt>
            <dd className="inline tabular-nums">
              {doc.versions.length === 0 ? 'solo enlace, sin archivo' : `v${version} de ${doc.versions.length}`}
            </dd>
          </div>
          <div>
            <dt className="inline font-medium text-slate-500">Vigencia </dt>
            <dd className="inline">
              <CalendarDate value={doc.valid_until} empty="sin vigencia declarada" />
            </dd>
          </div>
          {doc.versions.length > 0 && (
            <>
              <div className="min-w-0">
                <dt className="inline font-medium text-slate-500">SHA-256 </dt>
                <dd className="inline">
                  {row?.sha256 ? (
                    <code title={row.sha256} className="rounded bg-slate-100 px-1 font-mono text-[11px] text-slate-800">
                      {row.sha256.slice(0, 16)}…
                    </code>
                  ) : (
                    <span className="muted">sin archivo</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="inline font-medium text-slate-500">Archivo </dt>
                <dd className="inline">
                  {row?.filename ? `${row.filename} · ${formatBytes(row.size_bytes)}` : <span className="muted">sin archivo</span>}
                </dd>
              </div>
            </>
          )}
          <div>
            <dt className="inline font-medium text-slate-500">Tipo </dt>
            <dd className="inline">{docTypeText(doc.doc_type) || 'no declarado'}</dd>
          </div>
          {row && (
            <div>
              <dt className="inline font-medium text-slate-500">Cargada </dt>
              <dd className="inline">
                <DateTimeText value={row.created_at} />
              </dd>
            </div>
          )}
        </dl>
      </header>

      {doc.data_kind === 'SYNTHETIC' && (
        <p
          role="note"
          className="hatch-synthetic-soft flex items-center gap-2 border-b border-amber-300 px-4 py-2 text-xs font-semibold tracking-wide text-amber-950"
        >
          <TriangleAlert aria-hidden="true" className="h-4 w-4 shrink-0" />
          {watermark}
        </p>
      )}

      {externalUrl ? (
        <div className="px-4 py-8">
          <div className="mx-auto max-w-xl rounded-lg border border-slate-300 bg-slate-50 p-5 text-center">
            <Link2 aria-hidden="true" className="mx-auto h-7 w-7 text-slate-500" />
            <h3 className="mt-2 text-base font-semibold text-slate-900">Documento de tercero · enlace externo</h3>
            <p className="mt-1 text-sm text-slate-600">
              Este archivo pertenece a otra marca o fabricante y no se guarda en la plataforma. Su reutilización no está
              cubierta por el aviso de Dipromedic, por eso solo se enlaza a su origen ({host(externalUrl)}).
            </p>
            <a href={externalUrl} target="_blank" rel="noopener noreferrer" className="btn-primary mt-4">
              <ExternalLink aria-hidden="true" className="h-4 w-4" />
              Abrir en {host(externalUrl)}
            </a>
          </div>
        </div>
      ) : !row ? (
        <p className="px-4 py-10 text-center text-sm text-slate-600">La versión {version} no existe en este documento.</p>
      ) : !row.has_file ? (
        <div className="px-4 py-10 text-center text-sm text-slate-600">
          <FileWarning aria-hidden="true" className="mx-auto mb-2 h-6 w-6 text-slate-400" />
          Esta versión no tiene un archivo adjunto.
          {row.note && <p className="mt-1 text-xs text-slate-500">{row.note}</p>}
        </div>
      ) : fileError ? (
        <div className="p-4">
          <ErrorPanel error={fileError} title="No se pudo abrir el archivo" />
        </div>
      ) : fileLoading || !objectUrl ? (
        <LoadingBlock label="Descargando archivo…" />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2">
            {isPdf ? (
              <div className="flex items-center gap-1" role="group" aria-label="Página">
                <button
                  type="button"
                  className="btn-ghost p-1.5"
                  aria-label="Página anterior"
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((p) => clamp(p - 1))}
                >
                  <ChevronLeft aria-hidden="true" className="h-4 w-4" />
                </button>
                <label className="flex items-center gap-1.5 text-xs text-slate-600">
                  Página
                  <input
                    type="number"
                    min={1}
                    max={pageCount ?? undefined}
                    value={currentPage}
                    onChange={(e) => setCurrentPage(clamp(Number(e.target.value)))}
                    className="input w-16 py-1 text-center tabular-nums"
                  />
                  {pageCount && <span className="tabular-nums">de {pageCount}</span>}
                </label>
                <button
                  type="button"
                  className="btn-ghost p-1.5"
                  aria-label="Página siguiente"
                  disabled={pageCount !== null && currentPage >= pageCount}
                  onClick={() => setCurrentPage((p) => clamp(p + 1))}
                >
                  <ChevronRight aria-hidden="true" className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <span className="text-xs text-slate-600">{contentType || 'Archivo'}</span>
            )}
            <a href={objectUrl} download={row.filename ?? 'documento'} className="btn-secondary py-1.5">
              <Download aria-hidden="true" className="h-4 w-4" />
              Descargar
            </a>
          </div>
          {isPdf || isImage ? (
            <iframe
              title={`${doc.title} · versión ${version}${isPdf ? ` · página ${currentPage}` : ''}`}
              src={isPdf ? `${objectUrl}#page=${currentPage}&view=FitH&navpanes=0` : objectUrl}
              className="block w-full border-0 bg-slate-200"
              style={{ height }}
            />
          ) : (
            <p className="px-4 py-10 text-center text-sm text-slate-600">
              Este formato no se puede previsualizar en el navegador. Usa «Descargar» para abrirlo.
            </p>
          )}
        </>
      )}

      {doc.external_url && !doc.third_party && doc.data_kind === 'REAL' && (
        <footer className="border-t border-slate-200 px-4 py-2 text-xs text-slate-600">
          {consultedOn(row) && <CatalogCredit checkedOn={consultedOn(row)!} />}
          {' · '}
          <a href={doc.external_url} target="_blank" rel="noopener noreferrer" className="link">
            Ver en {host(doc.external_url)}
          </a>
        </footer>
      )}
    </section>
  )
}
