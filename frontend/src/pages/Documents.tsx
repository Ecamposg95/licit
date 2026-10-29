import { useMemo, useState } from 'react'
import { FileUp } from 'lucide-react'
import PageHeader from '@/components/PageHeader'
import DataKindChips, { usePersistentDataKinds } from '@/components/DataKindChips'
import DocumentsTable, { isDocumentExpired } from '@/components/DocumentsTable'
import { UnavailableAction } from '@/components/Tooltip'
import { EmptyState, ErrorPanel, Forbidden, TableSkeleton } from '@/components/feedback'
import { listDocuments } from '@/lib/api'
import { docTypeLabel } from '@/lib/labels'
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
  const baseDate = useAuth((s) => s.meta?.demo_base_date)
  const [kinds, setKinds] = usePersistentDataKinds('licit.documents.dataKinds')
  const [scope, setScope] = useState('')
  const [docType, setDocType] = useState('')
  const [onlyExpired, setOnlyExpired] = useState(false)

  const noKinds = kinds.length === 0
  const docs = useApi(() => listDocuments({ scope, data_kind: kinds }), [scope, kinds.join(',')], canRead && !noKinds)

  const types = useMemo(
    () => Array.from(new Set((docs.data ?? []).map((d) => d.doc_type).filter((t): t is string => !!t))).sort(),
    [docs.data],
  )
  const rows = useMemo(
    () =>
      (docs.data ?? []).filter(
        (d) => (!docType || d.doc_type === docType) && (!onlyExpired || isDocumentExpired(d, baseDate)),
      ),
    [docs.data, docType, onlyExpired, baseDate],
  )

  if (!canRead) return <Forbidden permission="document.read" />

  return (
    <div>
      <PageHeader
        title="Centro documental"
        description="Biblioteca por ámbito de empresa, producto y expediente. La vigencia de documentos simulados se evalúa contra la fecha base del demo."
        actions={
          <UnavailableAction
            label="Cargar documento"
            icon={<FileUp aria-hidden="true" className="h-4 w-4" />}
            reason="Carga con versiones y análisis: próxima entrega (E2)"
          />
        }
      />

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
                    scope === s.value ? 'bg-petrol-700 font-medium text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
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
                  {docTypeLabel(t)}
                </option>
              ))}
            </select>
          </div>
          <label className="inline-flex items-center gap-2 pb-2 text-sm text-slate-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-petrol-700 focus:ring-petrol-500"
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
            <DocumentsTable docs={rows} />
          </>
        )}
      </div>
    </div>
  )
}
