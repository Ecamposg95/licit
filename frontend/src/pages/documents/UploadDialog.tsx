import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { FileUp, TriangleAlert } from 'lucide-react'
import { ErrorPanel } from '@/components/feedback'
import {
  ACCEPTED_EXTENSIONS,
  DOC_TYPES,
  MAX_UPLOAD_BYTES,
  SCOPE_OPTIONS,
  createDocument,
  formatBytes,
  getDocument,
  uploadVersion,
  type DocumentRow,
} from '@/lib/api-documents'
import { ApiError, toApiError } from '@/lib/api'
import type { DataKind } from '@/lib/types'
import { useAuth } from '@/store/auth'

export interface UploadDefaults {
  title?: string
  scope?: string
  doc_type?: string
  data_kind?: DataKind
  product_id?: string
  opportunity_id?: string
}

interface Props {
  open: boolean
  onClose: () => void
  /** Recibe el documento completo (con todas sus versiones) cuando la carga termina. */
  onUploaded: (doc: DocumentRow) => void
  /** Si se indica, el archivo se agrega como versión nueva de ese documento en vez de crear uno. */
  documentId?: string
  documentTitle?: string
  defaults?: UploadDefaults
}

const KIND_OPTIONS: { value: DataKind; label: string; hint: string }[] = [
  { value: 'REAL', label: 'Real', hint: 'Documento auténtico de la empresa o del fabricante.' },
  {
    value: 'SYNTHETIC',
    label: 'Simulado (prueba)',
    hint: 'Archivo de demostración con marca DEMO. El reinicio del demo lo borra.',
  },
]

/**
 * Diálogo de carga: documento nuevo (título, ámbito, tipo, vigencia) o versión nueva de uno existente.
 * El tipo de dato se elige a propósito: un archivo ficticio nunca debe quedar como REAL por descuido.
 * Reutilizable por otras pantallas (por ejemplo, la matriz de requisitos) con `defaults`.
 */
export default function UploadDialog({ open, onClose, onUploaded, documentId, documentTitle, defaults }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const uid = useId()
  const watermark = useAuth((s) => s.meta?.watermark)
  const isVersion = Boolean(documentId)

  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [scope, setScope] = useState('empresa')
  const [docType, setDocType] = useState('')
  const [dataKind, setDataKind] = useState<DataKind | ''>('')
  const [validUntil, setValidUntil] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  // Cada apertura parte de cero (con los valores por omisión que dé quien lo monta).
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) {
      setFile(null)
      setTitle(defaults?.title ?? '')
      setScope(defaults?.scope ?? 'empresa')
      setDocType(defaults?.doc_type ?? '')
      setDataKind(defaults?.data_kind ?? '')
      setValidUntil('')
      setNote('')
      setError(null)
      setLocalError(null)
      setBusy(false)
      d.showModal()
    }
    if (!open && d.open) d.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  function pickFile(f: File | null) {
    setFile(f)
    setError(null)
    if (f && f.size > MAX_UPLOAD_BYTES) {
      setLocalError(`El archivo pesa ${formatBytes(f.size)} y el máximo es ${formatBytes(MAX_UPLOAD_BYTES)}.`)
    } else if (f && f.size === 0) {
      setLocalError('El archivo está vacío (0 bytes).')
    } else {
      setLocalError(null)
    }
    // El título se propone a partir del nombre, sin extensión; la persona puede cambiarlo.
    if (f && !isVersion && !title.trim()) setTitle(f.name.replace(/\.[^.]+$/, '').replace(/[_]+/g, ' '))
  }

  const ready =
    file !== null && !localError && (isVersion || (title.trim().length > 0 && dataKind !== '' && scope !== ''))

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file || !ready || busy) return
    setBusy(true)
    setError(null)
    try {
      let doc: DocumentRow
      if (documentId) {
        await uploadVersion(documentId, file, note)
        doc = await getDocument(documentId)
      } else {
        doc = await createDocument({
          file,
          title: title.trim(),
          scope,
          doc_type: docType || undefined,
          data_kind: dataKind as DataKind,
          valid_until: validUntil || undefined,
          product_id: defaults?.product_id,
          opportunity_id: defaults?.opportunity_id,
        })
      }
      onUploaded(doc)
      onClose()
    } catch (err) {
      setError(toApiError(err))
    } finally {
      setBusy(false)
    }
  }

  const heading = isVersion ? 'Subir una versión nueva' : 'Cargar documento'
  return (
    <dialog
      ref={ref}
      aria-labelledby={`${uid}-title`}
      onCancel={(e) => {
        e.preventDefault()
        if (!busy) onClose()
      }}
      className="w-[min(36rem,calc(100vw-2rem))] rounded-xl border border-slate-200 p-0 text-slate-900 shadow-2xl backdrop:bg-slate-900/40"
    >
      <form onSubmit={submit} noValidate>
        <div className="space-y-4 p-6">
          <div>
            <h2 id={`${uid}-title`} className="text-lg font-semibold">
              {heading}
            </h2>
            {isVersion && documentTitle && (
              <p className="mt-0.5 text-sm text-slate-600">
                {documentTitle}. La versión anterior se conserva y se puede consultar.
              </p>
            )}
          </div>

          <div>
            <label htmlFor={`${uid}-file`} className="label">
              Archivo
            </label>
            <input
              ref={fileRef}
              id={`${uid}-file`}
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              className="input file:mr-3 file:rounded-full file:border-0 file:bg-dpm-blue-50 file:px-3 file:py-1 file:text-sm file:font-semibold file:text-dpm-blue-800"
              onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
              aria-describedby={`${uid}-file-help`}
            />
            <p id={`${uid}-file-help`} className="mt-1 text-xs text-slate-500">
              PDF, DOCX (sin macros), PNG o JPEG. Máximo {formatBytes(MAX_UPLOAD_BYTES)}. Se guarda con su huella SHA-256.
            </p>
            {file && !localError && (
              <p className="mt-1 text-xs text-slate-600">
                {file.name} · {formatBytes(file.size)}
              </p>
            )}
            {localError && (
              <p role="alert" className="mt-1 text-xs font-medium text-red-700">
                {localError}
              </p>
            )}
          </div>

          {isVersion ? (
            <div>
              <label htmlFor={`${uid}-note`} className="label">
                Nota de la versión (opcional)
              </label>
              <input
                id={`${uid}-note`}
                className="input"
                maxLength={500}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Qué cambia respecto a la versión anterior"
              />
              <p className="mt-1 text-xs text-slate-500">
                Al subir una versión nueva, la revisión del documento vuelve a quedar pendiente.
              </p>
            </div>
          ) : (
            <>
              <div>
                <label htmlFor={`${uid}-title-input`} className="label">
                  Título
                </label>
                <input
                  id={`${uid}-title-input`}
                  className="input"
                  maxLength={500}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor={`${uid}-scope`} className="label">
                    Ámbito
                  </label>
                  <select id={`${uid}-scope`} className="input" value={scope} onChange={(e) => setScope(e.target.value)}>
                    {SCOPE_OPTIONS.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`${uid}-type`} className="label">
                    Tipo de documento
                  </label>
                  <select id={`${uid}-type`} className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
                    <option value="">Sin especificar</option>
                    {DOC_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label htmlFor={`${uid}-valid`} className="label">
                  Vigencia declarada (opcional)
                </label>
                <input
                  id={`${uid}-valid`}
                  type="date"
                  className="input sm:w-56"
                  value={validUntil}
                  onChange={(e) => setValidUntil(e.target.value)}
                />
              </div>
              <fieldset>
                <legend className="label">Tipo de dato</legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  {KIND_OPTIONS.map((k) => (
                    <label
                      key={k.value}
                      className={`flex cursor-pointer items-start gap-2 rounded-md border p-2.5 text-sm ${
                        dataKind === k.value ? 'border-dpm-blue bg-dpm-blue-50' : 'border-slate-300 bg-white'
                      }`}
                    >
                      <input
                        type="radio"
                        name={`${uid}-kind`}
                        value={k.value}
                        checked={dataKind === k.value}
                        onChange={() => setDataKind(k.value)}
                        className="mt-1 h-4 w-4 border-slate-300 text-dpm-blue focus:ring-dpm-blue"
                      />
                      <span>
                        <span className="block font-medium text-slate-900">{k.label}</span>
                        <span className="block text-xs text-slate-600">{k.hint}</span>
                      </span>
                    </label>
                  ))}
                </div>
                {dataKind === 'SYNTHETIC' && (
                  <p className="hatch-synthetic-soft mt-2 flex items-start gap-2 rounded-md border border-amber-300 px-3 py-2 text-xs font-medium text-amber-950">
                    <TriangleAlert aria-hidden="true" className="mt-px h-4 w-4 shrink-0" />
                    <span>
                      Quedará marcado como ficticio: {watermark ?? 'DEMOSTRACIÓN · DATOS FICTICIOS · SIN VALIDEZ PARA PRESENTACIÓN'}
                    </span>
                  </p>
                )}
              </fieldset>
            </>
          )}

          {error && <ErrorPanel error={error} title="No se pudo cargar el archivo" />}
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" className="btn-primary" disabled={!ready || busy}>
            <FileUp aria-hidden="true" className="h-4 w-4" />
            {busy ? 'Subiendo…' : isVersion ? 'Subir versión' : 'Cargar documento'}
          </button>
        </div>
      </form>
    </dialog>
  )
}
