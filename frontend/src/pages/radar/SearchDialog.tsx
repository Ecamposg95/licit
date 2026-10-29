import { useEffect, useRef, useState, type FormEvent } from 'react'
import { CircleAlert, CircleCheck, CircleX, FileUp, LoaderCircle, Plus, RotateCcw, Search, X } from 'lucide-react'
import { ErrorPanel } from '@/components/feedback'
import { toApiError, type ApiError } from '@/lib/api'
import {
  DEFAULT_TERMS,
  MAX_TERMS,
  getJob,
  getSearchRun,
  newIdempotencyKey,
  startSearch,
  type JobOut,
  type SearchErrorItem,
  type SearchRun,
  type SearchTerm,
} from '@/lib/api-search'
import { getDisplayTimeZone, parseInstant, todayInDisplayTz } from '@/lib/format'
import SearchRunsPanel, { SearchRunStatusBadge } from './SearchRunsPanel'

const POLL_MS = 1000
const MAX_POLL_FAILURES = 5

function hhmm(iso: string | null | undefined): string {
  const d = iso ? parseInstant(iso) : null
  if (!d) return '—'
  return new Intl.DateTimeFormat('es-MX', {
    timeZone: getDisplayTimeZone(),
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(d)
}

const fold = (s: string) =>
  s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()

interface Props {
  open: boolean
  onClose: () => void
  /** Al terminar la corrida (el radar se recarga con el filtro REAL). */
  onFinished: (run: SearchRun) => void
  /** Abre la importación manual (cuando SIDOF no responde). */
  onOpenImport: () => void
}

type Phase = 'form' | 'starting' | 'running' | 'finished'

function TermLine({ term, searchError, onOpenImport }: { term: SearchTerm; searchError?: SearchErrorItem; onOpenImport: () => void }) {
  const when = `SIDOF · ${hhmm(term.checked_at)} · «${term.term}»`
  if (term.status === 'error') {
    return (
      <li className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-900">
        <CircleX aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-red-700" />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{when}</p>
          <p>
            SIDOF no respondió: {searchError?.message ?? 'sin detalle'}. Esto no significa que no haya licitaciones. Puedes
            importar manualmente.
          </p>
        </div>
        <button type="button" className="btn-secondary shrink-0 px-3 py-1 text-xs" onClick={onOpenImport}>
          <FileUp aria-hidden="true" className="h-3.5 w-3.5" />
          Importar
        </button>
      </li>
    )
  }
  if (term.status === 'unconfirmed') {
    return (
      <li className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-amber-950">
        <CircleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
        <div>
          <p className="font-medium">{when}</p>
          <p>Sin resultados confirmados (la fuente no confirmó la respuesta)</p>
        </div>
      </li>
    )
  }
  if (term.status === 'pendiente' || term.status === 'buscando') {
    return (
      <li className="flex items-center gap-2 px-3 py-2 text-slate-500">
        <LoaderCircle aria-hidden="true" className={`h-4 w-4 ${term.status === 'buscando' ? 'animate-spin' : ''}`} />
        «{term.term}» · {term.status === 'buscando' ? 'buscando en SIDOF…' : 'en espera'}
      </li>
    )
  }
  // «buscado» con notas pendientes también está en curso: la palomita solo aparece al terminar de leerlas.
  const reading = term.status === 'leyendo' || (term.status === 'buscado' && term.read < term.notes)
  return (
    <li className="flex items-start gap-2 px-3 py-2 text-slate-700">
      {reading ? (
        <LoaderCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-dpm-blue" />
      ) : (
        <CircleCheck aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
      )}
      <div>
        <p className="font-medium text-slate-900">
          {when} · {term.total ?? 0} notas · {term.new} {term.new === 1 ? 'nueva' : 'nuevas'}
        </p>
        <p className="text-xs text-slate-500">
          {term.notes} de convocatorias por leer ({term.read} leídas)
          {term.seen_other_term > 0 && ` · ${term.seen_other_term} ya encontradas por otro término`}
          {term.skipped_non_cv > 0 && ` · ${term.skipped_non_cv} fuera de convocatorias`}
          {` · ${term.procedures} procedimientos del objeto`}
          {term.discarded > 0 && ` · ${term.discarded} descartados por objeto`}
          {term.updated + term.unchanged > 0 && ` · ${term.updated} actualizados, ${term.unchanged} sin cambios`}
        </p>
      </div>
    </li>
  )
}

function Summary({ run, job, onOpenImport }: { run: SearchRun; job: JobOut | null; onOpenImport: () => void }) {
  const c = run.counts
  if (run.status === 'failed') {
    return (
      <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
        <p className="font-medium">La búsqueda no se completó.</p>
        <p className="mt-0.5">
          {job?.status === 'failed' && job.error ? `${job.error}. ` : ''}
          Esto no significa que no haya licitaciones. Puedes importar manualmente una nota o un procedimiento.
        </p>
        <button type="button" className="btn-secondary mt-2 px-3 py-1 text-xs" onClick={onOpenImport}>
          <FileUp aria-hidden="true" className="h-3.5 w-3.5" />
          Importar manualmente
        </button>
      </div>
    )
  }
  if (run.status === 'done' && c.new === 0) {
    return (
      <p role="status" className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800">
        La búsqueda terminó sin procedimientos nuevos
        {c.updated + c.unchanged > 0 && ` (${c.updated} actualizados, ${c.unchanged} sin cambios)`}.
      </p>
    )
  }
  return (
    <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
      {run.status === 'partial' ? 'La búsqueda terminó con avisos: ' : 'Búsqueda terminada: '}
      {c.new} {c.new === 1 ? 'procedimiento nuevo' : 'procedimientos nuevos'}, {c.updated} actualizados y {c.unchanged} sin
      cambios, de {c.notes} notas leídas. El radar muestra ahora los datos REAL.
    </p>
  )
}

/** «Buscar ahora»: corrida real en SIDOF como trabajo asíncrono, con avance y conteos por término. */
export default function SearchDialog({ open, onClose, onFinished, onOpenImport }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const today = todayInDisplayTz()
  const [terms, setTerms] = useState<string[]>(DEFAULT_TERMS)
  const [draft, setDraft] = useState('')
  const [draftError, setDraftError] = useState<string | null>(null)
  const [from, setFrom] = useState(`${today.slice(0, 4)}-01-01`)
  const [to, setTo] = useState(today)
  const [phase, setPhase] = useState<Phase>('form')
  const [ids, setIds] = useState<{ run: string; job: string } | null>(null)
  const [job, setJob] = useState<JobOut | null>(null)
  const [run, setRun] = useState<SearchRun | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [pollWarning, setPollWarning] = useState<string | null>(null)
  const [historyKey, setHistoryKey] = useState(0)
  // Una clave por intento: un doble clic reutiliza el trabajo; tras terminar o fallar se genera otra.
  const keyRef = useRef(newIdempotencyKey())
  const inFlight = useRef(false)
  const onFinishedRef = useRef(onFinished)
  onFinishedRef.current = onFinished

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  // Consulta el trabajo y la corrida cada segundo hasta que termine (sigue aunque se cierre el diálogo).
  useEffect(() => {
    if (!ids || phase !== 'running') return
    let stopped = false
    let failures = 0
    let timer: number | undefined
    const tick = async () => {
      try {
        const [j, r] = await Promise.all([getJob(ids.job), getSearchRun(ids.run)])
        if (stopped) return
        failures = 0
        setPollWarning(null)
        setJob(j)
        setRun(r)
        if (j.status === 'done' || j.status === 'failed') {
          const final = r.status === 'queued' || r.status === 'running' ? await getSearchRun(ids.run) : r
          if (stopped) return
          setRun(final)
          setPhase('finished')
          setHistoryKey((k) => k + 1)
          keyRef.current = newIdempotencyKey()
          onFinishedRef.current(final)
          return
        }
      } catch (e) {
        if (stopped) return
        failures += 1
        if (failures >= MAX_POLL_FAILURES) {
          setError(toApiError(e))
          setPhase('finished')
          keyRef.current = newIdempotencyKey()
          return
        }
        setPollWarning('No se pudo consultar el avance; reintentando…')
      }
      timer = window.setTimeout(tick, POLL_MS)
    }
    tick()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [ids, phase])

  const addTerm = () => {
    const t = draft.replace(/\s+/g, ' ').trim()
    if (t.length < 2 || t.length > 80) return setDraftError('Cada término debe tener entre 2 y 80 caracteres.')
    if (terms.some((x) => fold(x) === fold(t))) return setDraftError('Ese término ya está en la lista.')
    if (terms.length >= MAX_TERMS) return setDraftError(`Máximo ${MAX_TERMS} términos por búsqueda.`)
    setTerms([...terms, t])
    setDraft('')
    setDraftError(null)
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (inFlight.current || terms.length === 0) return
    inFlight.current = true
    setPhase('starting')
    setError(null)
    setJob(null)
    setRun(null)
    try {
      const r = await startSearch({ terms, date_from: from, date_to: to }, keyRef.current)
      setIds({ run: r.search_run_id, job: r.job_id })
      setPhase('running')
    } catch (err) {
      setError(toApiError(err))
      setPhase('form')
      keyRef.current = newIdempotencyKey()
    } finally {
      inFlight.current = false
    }
  }

  const reset = () => {
    setPhase('form')
    setIds(null)
    setJob(null)
    setRun(null)
    setError(null)
  }

  const busy = phase === 'starting' || phase === 'running'
  const searchErrors = new Map<string, SearchErrorItem>()
  const usedErrors = new Set<SearchErrorItem>()
  for (const t of run?.terms ?? []) {
    const code = t.status === 'error' ? 'source_unavailable' : t.status === 'unconfirmed' ? 'zero_unconfirmed' : null
    const found = code ? run?.errors.find((x) => x.term === t.term && x.code === code && !usedErrors.has(x)) : undefined
    if (found) {
      usedErrors.add(found)
      if (code === 'source_unavailable') searchErrors.set(t.term, found)
    }
  }
  const otherErrors = (run?.errors ?? []).filter((x) => !usedErrors.has(x))
  const progress = phase === 'finished' ? 100 : (job?.progress ?? 0)

  return (
    <dialog
      ref={ref}
      aria-labelledby="search-dialog-title"
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      className="w-[min(46rem,calc(100vw-2rem))] rounded-xl border border-slate-200 p-0 text-slate-900 shadow-2xl backdrop:bg-slate-900/40"
    >
      <form onSubmit={submit}>
        <div className="max-h-[calc(100vh-10rem)] overflow-y-auto p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 id="search-dialog-title" className="text-lg font-semibold">
                Buscar ahora en el DOF (SIDOF)
              </h2>
              <span aria-hidden="true" className="brand-rule mt-2" />
            </div>
            <button type="button" className="btn-ghost -mr-2 -mt-1 p-1.5" onClick={onClose} aria-label="Cerrar">
              <X aria-hidden="true" className="h-5 w-5" />
            </button>
          </div>
          <p className="mt-3 text-sm text-slate-600">
            Consulta real desde el servidor: búsqueda por palabra de SIDOF (no documentada) y lectura de cada nota con su
            servicio oficial, a una petición por segundo. Cada procedimiento queda con su enlace a la nota oficial y su
            huella SHA-256. El DOF puede publicar después que Compras MX.
          </p>

          {phase === 'form' || phase === 'starting' ? (
            <fieldset disabled={busy} className="mt-5 space-y-4">
              <div>
                <span className="label" id="terms-label">
                  Términos ({terms.length} de {MAX_TERMS})
                </span>
                <ul aria-labelledby="terms-label" className="flex flex-wrap gap-2">
                  {terms.map((t) => (
                    <li
                      key={t}
                      className="inline-flex items-center gap-1 rounded-full border border-dpm-blue-200 bg-dpm-blue-50 py-1 pl-3 pr-1 text-sm text-dpm-blue-800"
                    >
                      {t}
                      <button
                        type="button"
                        className="rounded-full p-0.5 hover:bg-dpm-blue-100"
                        aria-label={`Quitar «${t}»`}
                        onClick={() => setTerms(terms.filter((x) => x !== t))}
                      >
                        <X aria-hidden="true" className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                  {terms.length === 0 && <li className="text-sm text-slate-500">Agrega al menos un término.</li>}
                </ul>
                <div className="mt-2 flex gap-2">
                  <label htmlFor="new-term" className="sr-only">
                    Nuevo término
                  </label>
                  <input
                    id="new-term"
                    className="input"
                    placeholder="Otro término (p. ej. clavo intramedular)"
                    value={draft}
                    onChange={(e) => {
                      setDraft(e.target.value)
                      setDraftError(null)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addTerm()
                      }
                    }}
                    aria-invalid={!!draftError}
                    aria-describedby={draftError ? 'new-term-error' : undefined}
                  />
                  <button type="button" className="btn-secondary shrink-0" onClick={addTerm}>
                    <Plus aria-hidden="true" className="h-4 w-4" />
                    Agregar
                  </button>
                </div>
                {draftError && (
                  <p id="new-term-error" className="mt-1 text-xs text-red-700">
                    {draftError}
                  </p>
                )}
                <button type="button" className="btn-ghost mt-1 py-1 text-xs" onClick={() => setTerms(DEFAULT_TERMS)}>
                  <RotateCcw aria-hidden="true" className="h-3.5 w-3.5" />
                  Restaurar diccionario
                </button>
                <p className="mt-1 text-xs text-slate-500">
                  SIDOF ignora acentos y busca palabras completas («protesis» no encuentra «endoprotesis»).
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="search-from" className="label">
                    Publicadas desde
                  </label>
                  <input id="search-from" type="date" className="input" value={from} max={to} required
                    onChange={(e) => setFrom(e.target.value)} />
                </div>
                <div>
                  <label htmlFor="search-to" className="label">
                    Hasta
                  </label>
                  <input id="search-to" type="date" className="input" value={to} min={from} max={today} required
                    onChange={(e) => setTo(e.target.value)} />
                </div>
              </div>
              <p className="text-xs text-slate-500">
                Fechas de publicación en el DOF (máximo un año). Cada nota se lee por separado; un año completo puede tardar
                unos minutos y se puede cerrar esta ventana mientras tanto.
              </p>
              {error && <ErrorPanel error={error} title="No se pudo iniciar la búsqueda" />}
            </fieldset>
          ) : (
            <div className="mt-5 space-y-4" aria-live="polite">
              <div>
                <div className="mb-1 flex items-center justify-between gap-3 text-xs text-slate-600">
                  <span className="flex items-center gap-2">
                    {run && <SearchRunStatusBadge status={run.status} />}
                    {phase === 'running' ? (job?.message ?? 'En cola…') : 'Terminada'}
                  </span>
                  <span className="tabular-nums">{progress}%</span>
                </div>
                <div
                  role="progressbar"
                  aria-label="Avance de la búsqueda"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progress}
                  className="h-2 overflow-hidden rounded-full bg-slate-200"
                >
                  <div className="h-full rounded-full bg-dpm-blue transition-[width] duration-500" style={{ width: `${progress}%` }} />
                </div>
                {pollWarning && <p className="mt-1 text-xs text-amber-900">{pollWarning}</p>}
              </div>
              {run && (
                <ul className="space-y-1 text-sm">
                  {run.terms.map((t) => (
                    <TermLine key={t.term} term={t} searchError={searchErrors.get(t.term)} onOpenImport={onOpenImport} />
                  ))}
                </ul>
              )}
              {otherErrors.length > 0 && (
                <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-950">
                  <p className="font-medium">Avisos de la corrida ({otherErrors.length})</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4">
                    {otherErrors.slice(0, 8).map((x, i) => (
                      <li key={i}>{x.message}</li>
                    ))}
                    {otherErrors.length > 8 && <li>… y {otherErrors.length - 8} más (ver historial).</li>}
                  </ul>
                </div>
              )}
              {phase === 'finished' && run && <Summary run={run} job={job} onOpenImport={onOpenImport} />}
              {phase === 'finished' && error && (
                <ErrorPanel error={error} title="Se perdió el seguimiento de la búsqueda; revisa el historial" />
              )}
            </div>
          )}

          <div className="mt-5">
            <SearchRunsPanel refreshKey={historyKey} />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          {phase === 'running' && (
            <span className="mr-auto text-xs text-slate-500">La búsqueda sigue en el servidor aunque cierres la ventana.</span>
          )}
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cerrar
          </button>
          {phase === 'finished' ? (
            <button type="button" className="btn-primary" onClick={reset}>
              <Search aria-hidden="true" className="h-4 w-4" />
              Nueva búsqueda
            </button>
          ) : (
            <button type="submit" className="btn-primary" disabled={busy || terms.length === 0}>
              {busy ? <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Search aria-hidden="true" className="h-4 w-4" />}
              {phase === 'starting' ? 'Iniciando…' : phase === 'running' ? 'Buscando…' : 'Buscar en SIDOF'}
            </button>
          )}
        </div>
      </form>
    </dialog>
  )
}
