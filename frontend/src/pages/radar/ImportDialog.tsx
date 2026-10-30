import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { CircleCheck, ExternalLink, FileUp, Info, LoaderCircle, X } from 'lucide-react'
import { ErrorPanel } from '@/components/feedback'
import { toApiError, type ApiError } from '@/lib/api'
import {
  COMPRASMX_URL,
  importOpportunity,
  type ImportOutcome,
  type ManualMetadata,
  type ProcedureChoice,
} from '@/lib/api-search'
import type { OpportunityRow } from '@/lib/types'

type Tab = 'sidof' | 'comprasmx'
const TABS: { id: Tab; label: string }[] = [
  { id: 'sidof', label: 'URL de nota DOF (SIDOF)' },
  { id: 'comprasmx', label: 'Procedimiento de Compras MX (captura)' },
]

const EMPTY_META: ManualMetadata = { external_id: '', title: '', buyer: '', source_url: '', submission_at: '', notes: '' }

const OUTCOME_TEXT: Record<ImportOutcome, string> = {
  new: 'Se registró como oportunidad REAL con su evidencia.',
  updated: 'Ya existía: se agregó la nota como nueva evidencia y se actualizaron los datos.',
  unchanged: 'Ya existía y la nota no cambió: se registró una nueva comprobación.',
}

interface Props {
  open: boolean
  onClose: () => void
  /** Tras importar (el radar se recarga). */
  onImported: (row: OpportunityRow) => void
}

function isChoiceList(x: unknown): x is ProcedureChoice[] {
  return Array.isArray(x) && x.every((d) => typeof d === 'object' && d !== null && 'external_id' in d)
}

/** «Importar»: nota oficial de SIDOF por URL o captura manual de un procedimiento visto en Compras MX. */
export default function ImportDialog({ open, onClose, onImported }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ sidof: null, comprasmx: null })
  const [tab, setTab] = useState<Tab>('sidof')
  const [url, setUrl] = useState('')
  const [choices, setChoices] = useState<ProcedureChoice[] | null>(null)
  const [chosen, setChosen] = useState('')
  const [meta, setMeta] = useState<ManualMetadata>(EMPTY_META)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [done, setDone] = useState<{ row: OpportunityRow; outcome: ImportOutcome } | null>(null)

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  const switchTab = (next: Tab) => {
    setTab(next)
    setError(null)
    setDone(null)
  }

  const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const next: Tab = tab === 'sidof' ? 'comprasmx' : 'sidof'
    switchTab(next)
    tabRefs.current[next]?.focus()
  }

  const run = async (body: Parameters<typeof importOpportunity>[0]) => {
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      const result = await importOpportunity(body)
      setDone(result)
      setChoices(null)
      setChosen('')
      onImported(result.row)
    } catch (err) {
      const apiErr = toApiError(err)
      if (apiErr.code === 'procedure_choice_required' && isChoiceList(apiErr.details)) {
        setChoices(apiErr.details)
        setChosen(apiErr.details[0]?.external_id ?? '')
      } else {
        setError(apiErr)
      }
    } finally {
      setBusy(false)
    }
  }

  const submitUrl = (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    run(choices && chosen ? { url: url.trim(), external_id: chosen } : { url: url.trim() })
  }

  const submitMeta = (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    run({
      metadata: {
        ...meta,
        submission_at: meta.submission_at ? meta.submission_at : null,
        notes: meta.notes?.trim() ? meta.notes.trim() : null,
      },
    })
  }

  const setField = (k: keyof ManualMetadata) => (e: { target: { value: string } }) =>
    setMeta((m) => ({ ...m, [k]: e.target.value }))

  const close = () => {
    if (!busy) onClose()
  }

  const duplicateId =
    error?.code === 'duplicate_opportunity' && typeof error.details === 'object' && error.details !== null
      ? ((error.details as { opportunity_id?: string }).opportunity_id ?? null)
      : null

  return (
    <dialog
      ref={ref}
      aria-labelledby="import-dialog-title"
      onCancel={(e) => {
        e.preventDefault()
        close()
      }}
      className="w-[min(40rem,calc(100vw-2rem))] rounded-xl border border-slate-200 p-0 text-slate-900 shadow-2xl backdrop:bg-slate-900/40"
    >
      <div className="max-h-[calc(100vh-8rem)] overflow-y-auto p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="import-dialog-title" className="text-lg font-semibold">
              Importar procedimiento
            </h2>
            <span aria-hidden="true" className="brand-rule mt-2" />
          </div>
          <button type="button" className="btn-ghost -mr-2 -mt-1 p-1.5" onClick={close} aria-label="Cerrar">
            <X aria-hidden="true" className="h-5 w-5" />
          </button>
        </div>

        <div role="tablist" aria-label="Forma de importación" onKeyDown={onTabKey} className="mt-4 flex gap-1 overflow-x-auto border-b border-slate-200">
          {TABS.map((t) => {
            const selected = t.id === tab
            return (
              <button
                key={t.id}
                ref={(el) => (tabRefs.current[t.id] = el)}
                role="tab"
                type="button"
                id={`import-tab-${t.id}`}
                aria-selected={selected}
                aria-controls={`import-panel-${t.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => switchTab(t.id)}
                className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                  selected
                    ? 'border-dpm-blue text-dpm-blue-800'
                    : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900'
                }`}
              >
                {t.label}
              </button>
            )
          })}
        </div>

        {tab === 'sidof' ? (
          <form id="import-panel-sidof" role="tabpanel" aria-labelledby="import-tab-sidof" onSubmit={submitUrl} className="mt-4 space-y-3">
            <p className="text-sm text-slate-600">
              Pega el enlace de una nota del Diario Oficial publicada en SIDOF. El servidor la lee con el servicio oficial,
              extrae el procedimiento y guarda la nota como evidencia (enlace, hora y SHA-256).
            </p>
            <div>
              <label htmlFor="import-url" className="label">
                URL de la nota
              </label>
              <input
                id="import-url"
                type="url"
                inputMode="url"
                required
                className="input"
                placeholder="https://sidof.segob.gob.mx/notas/docFuente/5801639"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value)
                  setChoices(null)
                }}
                disabled={busy}
              />
            </div>
            {choices && (
              <fieldset className="rounded-md border border-slate-200 p-3">
                <legend className="px-1 text-xs font-medium text-slate-700">
                  La nota trae {choices.length} procedimientos; elige cuál importar
                </legend>
                <div className="max-h-56 space-y-1 overflow-y-auto">
                  {choices.map((c) => (
                    <label key={c.external_id} className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 text-sm hover:bg-slate-50">
                      <input
                        type="radio"
                        name="procedure-choice"
                        className="mt-1"
                        value={c.external_id}
                        checked={chosen === c.external_id}
                        onChange={() => setChosen(c.external_id)}
                      />
                      <span>
                        <span className="font-medium tabular-nums text-slate-900">{c.external_id}</span>
                        <span className="block text-xs text-slate-600">{c.title ?? 'Objeto no identificado en la nota'}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            <div className="flex justify-end">
              <button type="submit" className="btn-primary" disabled={busy || !url.trim()}>
                {busy ? <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" /> : <FileUp aria-hidden="true" className="h-4 w-4" />}
                {busy ? 'Leyendo la nota…' : choices ? 'Importar el seleccionado' : 'Leer e importar'}
              </button>
            </div>
          </form>
        ) : (
          <form id="import-panel-comprasmx" role="tabpanel" aria-labelledby="import-tab-comprasmx" onSubmit={submitMeta} className="mt-4 space-y-3">
            <p className="flex items-start gap-2 rounded-md border border-dpm-blue-200 bg-dpm-blue-50 px-3 py-2 text-sm text-dpm-blue-900">
              <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Compras MX bloquea la consulta automatizada; se registra como por verificar.{' '}
                <a href={COMPRASMX_URL} target="_blank" rel="noopener noreferrer" className="link inline-flex items-center gap-1">
                  Abrir Compras MX
                  <ExternalLink aria-hidden="true" className="h-3 w-3" />
                  <span className="sr-only">(se abre en una pestaña nueva)</span>
                </a>
              </span>
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="meta-id" className="label">
                  Número de procedimiento
                </label>
                <input id="meta-id" required minLength={3} maxLength={120} className="input" placeholder="LA-50-GYR-…-2026"
                  value={meta.external_id} onChange={setField('external_id')} disabled={busy} />
              </div>
              <div>
                <label htmlFor="meta-buyer" className="label">
                  Convocante
                </label>
                <input id="meta-buyer" required minLength={2} maxLength={255} className="input" value={meta.buyer}
                  onChange={setField('buyer')} disabled={busy} />
              </div>
            </div>
            <div>
              <label htmlFor="meta-title" className="label">
                Objeto del procedimiento
              </label>
              <input id="meta-title" required minLength={3} maxLength={500} className="input" value={meta.title}
                onChange={setField('title')} disabled={busy} />
            </div>
            <div>
              <label htmlFor="meta-url" className="label">
                URL del procedimiento en Compras MX
              </label>
              <input id="meta-url" type="url" required className="input"
                placeholder="https://comprasmx.buengobierno.gob.mx/sitiopublico/#/sitiopublico/detalle/…"
                value={meta.source_url} onChange={setField('source_url')} disabled={busy} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="meta-submission" className="label">
                  Presentación de proposiciones (hora de Ciudad de México)
                </label>
                <input id="meta-submission" type="datetime-local" className="input" value={meta.submission_at ?? ''}
                  onChange={setField('submission_at')} disabled={busy} />
                <p className="mt-1 text-xs text-slate-500">Opcional. Si no la conoces, déjala vacía.</p>
              </div>
              <div>
                <label htmlFor="meta-notes" className="label">
                  Notas
                </label>
                <textarea id="meta-notes" rows={2} maxLength={2000} className="input" value={meta.notes ?? ''}
                  onChange={setField('notes')} disabled={busy} />
              </div>
            </div>
            <div className="flex justify-end">
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" /> : <FileUp aria-hidden="true" className="h-4 w-4" />}
                {busy ? 'Registrando…' : 'Registrar por verificar'}
              </button>
            </div>
          </form>
        )}

        <div className="mt-4 space-y-2" aria-live="polite">
          {error && (
            <>
              <ErrorPanel error={error} title="No se pudo importar" />
              {duplicateId && (
                <Link to={`/oportunidades/${duplicateId}`} className="link text-sm" onClick={onClose}>
                  Abrir el procedimiento existente
                </Link>
              )}
            </>
          )}
          {done && (
            <div role="status" className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              <CircleCheck aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
              <div>
                <p className="font-medium">{done.row.external_id}</p>
                <p>{OUTCOME_TEXT[done.outcome]}</p>
                <Link to={`/oportunidades/${done.row.id}`} className="link" onClick={onClose}>
                  Abrir la oportunidad
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="flex justify-end border-t border-slate-200 bg-slate-50 px-6 py-3">
        <button type="button" className="btn-secondary" onClick={close} disabled={busy}>
          Cerrar
        </button>
      </div>
    </dialog>
  )
}
