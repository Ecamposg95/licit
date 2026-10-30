import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  CircleCheck,
  Download,
  FilePlus,
  FileWarning,
  Info,
  LoaderCircle,
  TriangleAlert,
} from 'lucide-react'
import { Badge, RequirementStatusBadge } from '@/components/badges'
import { DateTimeText } from '@/components/dates'
import { EmptyState, ErrorPanel, Forbidden, LoadingBlock, TableSkeleton } from '@/components/feedback'
import {
  downloadArtifact,
  getGenerationPreview,
  getJob,
  getManifest,
  listArtifacts,
  newIdempotencyKey,
  startGeneration,
  type ArtifactRow,
  type JobState,
  type Manifest,
} from '@/lib/api-artifacts'
import { formatBytes } from '@/lib/api-documents'
import { DATA_KIND_CHIP_LABEL } from '@/lib/labels'
import type { DataKind } from '@/lib/types'
import { toApiError, type ApiError } from '@/lib/api'
import { useApi } from '@/lib/useApi'
import { useCan } from '@/store/auth'

const POLL_MS = 1000
const DRAFT_NOTICE = 'Borrador · no apto para presentación'

/** Huella corta con la completa al pasar el cursor o enfocarla. */
function Short({ value, size = 12 }: { value: string; size?: number }) {
  return (
    <code title={value} tabIndex={0} className="rounded bg-slate-100 px-1 py-0.5 text-xs text-slate-700">
      {value.slice(0, size)}…
    </code>
  )
}

function DraftNotice() {
  return (
    <div
      role="note"
      className="flex items-center gap-3 rounded-md border border-dpm-navy-200 bg-dpm-navy-50 px-4 py-2.5 text-sm text-dpm-navy"
    >
      <FileWarning aria-hidden="true" className="h-4 w-4 shrink-0" />
      <span>
        <strong className="font-semibold">{DRAFT_NOTICE}</strong> · los documentos llevan la marca de demostración y cada
        dato faltante aparece como <mark className="rounded bg-yellow-200 px-1 font-semibold">[PENDIENTE: …]</mark>.
      </span>
    </div>
  )
}

function ProgressBar({ job }: { job: JobState }) {
  const failed = job.status === 'failed'
  return (
    <div className="mt-3" aria-live="polite">
      <div className="mb-1 flex items-center justify-between text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5">
          {!failed && job.status !== 'done' && <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />}
          {job.message ?? (job.status === 'queued' ? 'En cola…' : 'Trabajando…')}
        </span>
        <span className="tabular-nums">{job.progress}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={job.progress}
        aria-label="Avance de la generación"
        className="h-2 overflow-hidden rounded-full bg-slate-200"
      >
        <div
          className={`h-full rounded-full transition-all ${failed ? 'bg-red-600' : 'bg-dpm-blue'}`}
          style={{ width: `${Math.max(job.progress, 3)}%` }}
        />
      </div>
    </div>
  )
}

function ManifestPreview({ artifactId }: { artifactId: string }) {
  const manifest = useApi<Manifest>(() => getManifest(artifactId), [artifactId])
  if (manifest.error) return <ErrorPanel error={manifest.error} onRetry={manifest.reload} title="No se pudo leer el manifiesto" />
  const m = manifest.data
  if (!m) return <LoadingBlock label="Leyendo manifest.json…" />
  const prov = Object.entries(m.provenance).filter(([, n]) => n > 0)
  return (
    <div className="space-y-4 text-sm">
      <p className="text-slate-600">
        Vista de <code>manifest.json</code>: cada archivo del paquete con su huella SHA-256. El manifiesto no se lista a sí
        mismo; la huella del ZIP completo está en el historial.
      </p>
      <div className="overflow-x-auto rounded-md border border-slate-200">
        <table className="table-base table-compact">
          <caption className="sr-only">Archivos del paquete</caption>
          <thead>
            <tr>
              <th scope="col">Archivo</th>
              <th scope="col" className="text-right">
                Tamaño
              </th>
              <th scope="col">SHA-256</th>
            </tr>
          </thead>
          <tbody>
            {m.files.map((f) => (
              <tr key={f.name}>
                <td className="font-medium text-slate-800">{f.name}</td>
                <td className="whitespace-nowrap text-right tabular-nums">{formatBytes(f.size_bytes)}</td>
                <td>
                  <Short value={f.sha256} size={16} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        <div>
          <dt className="inline text-slate-500">Versión de plantillas: </dt>
          <dd className="inline font-medium">{m.template_version}</dd>
        </div>
        <div>
          <dt className="inline text-slate-500">Procedencia de los datos: </dt>
          <dd className="inline font-medium">
            {prov.length ? prov.map(([k, n]) => `${DATA_KIND_CHIP_LABEL[k as DataKind] ?? k} ${n}`).join(' · ') : 'sin registros'}
          </dd>
        </div>
      </dl>
      {m.excluded_documents.length > 0 && (
        <div>
          <p className="font-medium text-slate-800">Documentos que no viajan en el paquete ({m.excluded_documents.length})</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-600">
            {m.excluded_documents.map((d, i) => (
              <li key={`${d.code}-${i}`}>
                <span className="font-medium text-slate-800">{d.code ?? 's/c'}</span> · {d.title}: {d.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      <details>
        <summary className="cursor-pointer text-slate-600 hover:text-slate-900">Ver manifest.json completo</summary>
        <pre className="mt-2 max-h-80 overflow-auto rounded-md bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
          {JSON.stringify(m, null, 2)}
        </pre>
      </details>
    </div>
  )
}

function History({
  rows,
  onDownloadError,
}: {
  rows: ArtifactRow[]
  onDownloadError: (e: ApiError | null) => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)

  const download = async (a: ArtifactRow) => {
    setDownloading(a.id)
    onDownloadError(null)
    try {
      await downloadArtifact(a.id, a.filename)
    } catch (e) {
      onDownloadError(toApiError(e))
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="card overflow-x-auto">
      <table className="table-base min-w-[860px]">
        <caption className="sr-only">Historial de borradores generados</caption>
        <thead>
          <tr>
            <th scope="col">Generado</th>
            <th scope="col">Por</th>
            <th scope="col">Versión de datos</th>
            <th scope="col">Advertencias</th>
            <th scope="col" className="text-right">
              Tamaño
            </th>
            <th scope="col">SHA-256</th>
            <th scope="col">Estado</th>
            <th scope="col">
              <span className="sr-only">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => {
            const expanded = open === a.id
            return (
              <Fragment key={a.id}>
                <tr>
                  <td className="whitespace-nowrap">
                    <DateTimeText value={a.created_at} />
                  </td>
                  <td>{a.created_by?.full_name ?? <span className="muted">—</span>}</td>
                  <td>
                    <Short value={a.data_version} />
                  </td>
                  <td className="tabular-nums">{a.warnings.length}</td>
                  <td className="whitespace-nowrap text-right tabular-nums">{formatBytes(a.size_bytes)}</td>
                  <td>
                    <Short value={a.sha256} />
                  </td>
                  <td>
                    <Badge tone={{ icon: FileWarning, className: 'border-slate-300 bg-slate-100 text-slate-700' }}>
                      Borrador
                    </Badge>
                  </td>
                  <td className="whitespace-nowrap text-right">
                    <button
                      type="button"
                      className="btn-ghost py-1.5"
                      aria-expanded={expanded}
                      aria-controls={`manifest-${a.id}`}
                      onClick={() => setOpen(expanded ? null : a.id)}
                    >
                      {expanded ? <ChevronDown aria-hidden="true" className="h-4 w-4" /> : <ChevronRight aria-hidden="true" className="h-4 w-4" />}
                      Manifiesto
                    </button>
                    <button
                      type="button"
                      className="btn-secondary ml-1 py-1.5"
                      disabled={downloading === a.id}
                      onClick={() => download(a)}
                    >
                      {downloading === a.id ? (
                        <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download aria-hidden="true" className="h-4 w-4" />
                      )}
                      Descargar ZIP
                    </button>
                  </td>
                </tr>
                {expanded && (
                  <tr>
                    <td colSpan={8} id={`manifest-${a.id}`} className="bg-slate-50">
                      <ManifestPreview artifactId={a.id} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function ExpedienteTab({ opportunityId }: { opportunityId: string }) {
  const canDownload = useCan('artifact.download')
  const canGenerate = useCan('proposal.generate')
  const preview = useApi(() => getGenerationPreview(opportunityId), [opportunityId], canDownload)
  const history = useApi(() => listArtifacts(opportunityId), [opportunityId], canDownload)

  const [selected, setSelected] = useState<Set<string> | null>(null)       // null = todas
  const [job, setJob] = useState<JobState | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [startError, setStartError] = useState<ApiError | null>(null)
  const [downloadError, setDownloadError] = useState<ApiError | null>(null)
  const [justDone, setJustDone] = useState(false)
  // La clave vive mientras el trabajo está en curso: un doble clic reutiliza el trabajo; un clic nuevo la renueva.
  const keyRef = useRef<string | null>(null)
  const starting = useRef(false)

  const templates = preview.data?.templates ?? []
  const chosen = selected ?? new Set(templates.map((t) => t.key))
  const running = jobId !== null && job?.status !== 'done' && job?.status !== 'failed'

  const toggle = (key: string) => {
    const next = new Set(chosen)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setSelected(next)
  }

  const reloadAll = useCallback(() => {
    preview.reload()
    history.reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const generate = async () => {
    if (starting.current || running) return
    starting.current = true
    setStartError(null)
    setJustDone(false)
    if (!keyRef.current) keyRef.current = newIdempotencyKey()
    try {
      const { job_id } = await startGeneration(
        opportunityId,
        templates.filter((t) => chosen.has(t.key)).map((t) => t.key),
        keyRef.current,
      )
      setJob(null)
      setJobId(job_id)
    } catch (e) {
      keyRef.current = null
      setStartError(toApiError(e))
    } finally {
      starting.current = false
    }
  }

  // Sondeo del trabajo hasta que termine.
  useEffect(() => {
    if (!jobId) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const tick = async () => {
      try {
        const state = await getJob(jobId)
        if (!active) return
        setJob(state)
        if (state.status === 'done' || state.status === 'failed') {
          keyRef.current = null
          if (state.status === 'done') {
            setJustDone(true)
            reloadAll()
          }
          return
        }
      } catch (e) {
        if (!active) return
        setStartError(toApiError(e))
        keyRef.current = null
        setJobId(null)
        return
      }
      timer = setTimeout(tick, POLL_MS)
    }
    tick()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [jobId, reloadAll])

  if (!canDownload) return <Forbidden permission="artifact.download" />

  const p = preview.data
  return (
    <div className="space-y-5">
      <DraftNotice />

      {/* ── Antes de generar ─────────────────────────────────────────────── */}
      <section aria-labelledby="exp-antes" className="card p-4">
        <h2 id="exp-antes" className="text-base font-semibold text-slate-900">
          Antes de generar
        </h2>
        {preview.error ? (
          <div className="mt-3">
            <ErrorPanel error={preview.error} onRetry={preview.reload} />
          </div>
        ) : !p ? (
          <LoadingBlock label="Calculando la versión de datos…" />
        ) : (
          <div className="mt-3 grid gap-5 lg:grid-cols-2">
            <div className="space-y-3 text-sm">
              <p>
                <span className="text-slate-500">Versión de datos: </span>
                <code title={p.data_version} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
                  {p.data_version.slice(0, 16)}…
                </code>
                {p.changed_since_last ? (
                  <span className="ml-2 inline-flex items-center gap-1 font-medium text-amber-800">
                    <TriangleAlert aria-hidden="true" className="h-3.5 w-3.5" />
                    Cambió desde la última generación
                  </span>
                ) : p.last_data_version ? (
                  <span className="ml-2 inline-flex items-center gap-1 text-slate-600">
                    <CircleCheck aria-hidden="true" className="h-3.5 w-3.5" />
                    Igual a la última generación
                  </span>
                ) : (
                  <span className="ml-2 text-slate-500">Aún no hay generaciones</span>
                )}
              </p>
              <p className="font-medium text-slate-900">{p.totals_text}</p>
              <p className="text-slate-600">{p.fiscal_text}</p>
              <fieldset>
                <legend className="mb-1 font-medium text-slate-800">Plantillas</legend>
                <ul className="space-y-1">
                  {p.templates.map((t) => (
                    <li key={t.key}>
                      <label className="inline-flex cursor-pointer items-start gap-2">
                        <input
                          type="checkbox"
                          className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-dpm-blue"
                          checked={chosen.has(t.key)}
                          disabled={running || !canGenerate}
                          onChange={() => toggle(t.key)}
                        />
                        <span>
                          {t.label} <span className="text-xs text-slate-500">({t.filename})</span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-xs text-slate-500">
                  Además siempre se incluyen la matriz en CSV y XLSX, el README de pendientes y el manifiesto.
                </p>
              </fieldset>
            </div>

            <div className="space-y-3 text-sm">
              <div>
                <p className="font-medium text-slate-800">Advertencias ({p.warnings.length})</p>
                <ul className="mt-1 max-h-44 list-disc space-y-0.5 overflow-auto pl-5 text-slate-700">
                  {p.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="font-medium text-slate-800">Pendientes abiertos ({p.open_requirements.length})</p>
                {p.open_requirements.length === 0 ? (
                  <p className="mt-1 text-slate-600">No hay requisitos abiertos.</p>
                ) : (
                  <ul className="mt-1 max-h-44 space-y-1 overflow-auto">
                    {p.open_requirements.map((r) => (
                      <li key={`${r.code}-${r.text}`} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                        <span className="font-medium tabular-nums text-slate-800">{r.code ?? 's/c'}</span>
                        <RequirementStatusBadge status={r.status} />
                        <span className="text-slate-700">{r.text}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}

        {p && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            {canGenerate ? (
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" className="btn-primary" disabled={running || chosen.size === 0} onClick={generate}>
                  {running ? (
                    <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
                  ) : (
                    <FilePlus aria-hidden="true" className="h-4 w-4" />
                  )}
                  {running ? 'Generando…' : 'Generar borrador'}
                </button>
                {chosen.size === 0 && <span className="text-sm text-slate-600">Selecciona al menos una plantilla.</span>}
                {justDone && !running && (
                  <span role="status" className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-800">
                    <CircleCheck aria-hidden="true" className="h-4 w-4" />
                    Borrador generado. Ya está en el historial.
                  </span>
                )}
              </div>
            ) : (
              <p className="flex items-start gap-2 text-sm text-slate-600">
                <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                Tu rol puede descargar los borradores existentes, pero no generar uno nuevo (permiso proposal.generate).
              </p>
            )}
            {job && <ProgressBar job={job} />}
            {job?.status === 'failed' && (
              <div role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
                <p className="font-medium">
                  No se pudo generar el expediente. Intenta de nuevo; si persiste, avisa a quien administra el demo.
                </p>
                <p className="mt-0.5 text-xs text-red-800/80">No se creó ningún borrador.</p>
                {job.error && (
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer font-medium text-red-900">Detalle técnico</summary>
                    <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-red-100 p-2 text-red-950">
                      {job.error}
                    </pre>
                  </details>
                )}
              </div>
            )}
            {startError && (
              <div className="mt-3">
                <ErrorPanel error={startError} title="No se pudo iniciar la generación" />
              </div>
            )}
          </div>
        )}
      </section>

      {/* ── Historial ────────────────────────────────────────────────────── */}
      <section aria-labelledby="exp-historial" className="space-y-3">
        <h2 id="exp-historial" className="text-base font-semibold text-slate-900">
          Historial de borradores
        </h2>
        {downloadError && <ErrorPanel error={downloadError} title="No se pudo descargar el paquete" />}
        {history.error ? (
          <ErrorPanel error={history.error} onRetry={history.reload} />
        ) : !history.data ? (
          <div className="card overflow-hidden">
            <TableSkeleton rows={2} cols={6} />
          </div>
        ) : history.data.length === 0 ? (
          <div className="card">
            <EmptyState title="Aún no se ha generado ningún borrador">
              {canGenerate
                ? 'Elige las plantillas y pulsa «Generar borrador». Cada generación conserva su paquete y su huella.'
                : 'Cuando alguien con permiso genere un borrador aparecerá aquí para descargarlo.'}
            </EmptyState>
          </div>
        ) : (
          <History rows={history.data} onDownloadError={setDownloadError} />
        )}
      </section>
    </div>
  )
}
