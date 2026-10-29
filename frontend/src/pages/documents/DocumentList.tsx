import { Link } from 'react-router-dom'
import { FileText, Globe, Link2, Upload } from 'lucide-react'
import { Badge, DataKindBadge, ExpiredBadge, ReviewStatusBadge } from '@/components/badges'
import { CalendarDate } from '@/components/dates'
import { isDocumentExpired } from '@/components/DocumentsTable'
import { docTypeText, formatBytes, originOf, type DocumentOrigin, type DocumentRow } from '@/lib/api-documents'
import { formatDateLong } from '@/lib/format'
import { scopeLabel } from '@/lib/labels'
import { useAuth } from '@/store/auth'

export function OriginBadge({ origin }: { origin: DocumentOrigin }) {
  if (origin === 'tercero')
    return (
      <Badge tone={{ icon: Link2, className: 'border-slate-400 bg-slate-100 text-slate-800' }}>
        Tercero · enlace externo
      </Badge>
    )
  if (origin === 'catalogo')
    return <Badge tone={{ icon: Globe, className: 'border-dpm-blue-300 bg-dpm-blue-50 text-dpm-blue-800' }}>Catálogo Dipromedic</Badge>
  if (origin === 'carga')
    return <Badge tone={{ icon: Upload, className: 'border-slate-300 bg-white text-slate-700' }}>Carga manual</Badge>
  return null
}

/** Tabla del centro documental: metadatos declarados; ningún documento se da por válido por su nombre. */
export default function DocumentList({ docs }: { docs: DocumentRow[] }) {
  const baseDate = useAuth((s) => s.meta?.demo_base_date)
  return (
    <div className="relative overflow-x-auto">
      <table className="table-base min-w-[1000px]">
        <thead>
          <tr>
            <th scope="col">Documento</th>
            <th scope="col">Ámbito</th>
            <th scope="col">Tipo</th>
            <th scope="col">Versión</th>
            <th scope="col">Vigencia</th>
            <th scope="col">Revisión</th>
            <th scope="col">Archivo</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => {
            const expired = isDocumentExpired(d, baseDate)
            const latest = d.versions[d.versions.length - 1]
            const origin = originOf(d)
            return (
              <tr key={d.id}>
                <td className="min-w-[300px]">
                  <div className="flex items-start gap-2">
                    <FileText aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                    <div className="min-w-0">
                      {d.code && <div className="text-xs font-medium text-slate-500 tabular-nums">{d.code}</div>}
                      <Link to={`/documentos/${d.id}`} className="link">
                        {d.title}
                      </Link>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        <DataKindBadge kind={d.data_kind} />
                        <OriginBadge origin={origin} />
                      </div>
                      {d.watermark && <p className="mt-1.5 text-[11px] font-medium text-amber-800">Marca: {d.watermark}</p>}
                    </div>
                  </div>
                </td>
                <td>
                  {scopeLabel(d.scope)}
                  {d.product_name && <div className="text-xs text-slate-500">{d.product_name}</div>}
                </td>
                <td>{d.doc_type ? docTypeText(d.doc_type) : <span className="muted">No declarado</span>}</td>
                <td className="whitespace-nowrap tabular-nums">
                  {d.versions.length === 0 ? <span className="muted">—</span> : `v${d.current_version}`}
                  {d.versions.length > 1 && <div className="text-xs text-slate-500">{d.versions.length} versiones</div>}
                </td>
                <td className="whitespace-nowrap">
                  <CalendarDate value={d.valid_until} empty="Sin vigencia declarada" />
                  {expired && (
                    <div className="mt-1">
                      <ExpiredBadge
                        hint={
                          d.data_kind === 'SYNTHETIC'
                            ? `Vigencia anterior a la fecha base del demo (${formatDateLong(baseDate) ?? '—'}).`
                            : 'Vigencia anterior a la fecha de hoy.'
                        }
                      />
                    </div>
                  )}
                </td>
                <td>
                  <ReviewStatusBadge status={d.review_status} />
                </td>
                <td className="min-w-[180px] text-xs">
                  {latest?.has_file ? (
                    <span>
                      {latest.filename}
                      <span className="block text-slate-500">{formatBytes(latest.size_bytes)}</span>
                    </span>
                  ) : d.third_party ? (
                    <span className="muted">Solo enlace</span>
                  ) : (
                    <span className="muted">{latest?.note ?? 'Sin archivo cargado'}</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
