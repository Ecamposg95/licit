import { FileText } from 'lucide-react'
import { DataKindBadge, ExpiredBadge, ReviewStatusBadge } from '@/components/badges'
import { CalendarDate } from '@/components/dates'
import { docTypeLabel, scopeLabel } from '@/lib/labels'
import { formatDateLong, isBefore, referenceDate } from '@/lib/format'
import type { DocumentOut } from '@/lib/types'
import { useAuth } from '@/store/auth'

export function isDocumentExpired(doc: DocumentOut, demoBaseDate: string | undefined) {
  if (!doc.valid_until) return false
  return isBefore(doc.valid_until, referenceDate(doc.data_kind, demoBaseDate))
}

/** Tabla de documentos: metadatos declarados; ningún documento se da por válido por su nombre. */
export default function DocumentsTable({ docs }: { docs: DocumentOut[] }) {
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
            <th scope="col">Emisor declarado</th>
            <th scope="col">Vigencia</th>
            <th scope="col">Revisión</th>
            <th scope="col">Responsable</th>
            <th scope="col">Archivo</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => {
            const expired = isDocumentExpired(d, baseDate)
            const latest = d.versions[d.versions.length - 1]
            return (
              <tr key={d.id}>
                <td className="min-w-[280px]">
                  <div className="flex items-start gap-2">
                    <FileText aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                    <div className="min-w-0">
                      {d.code && <div className="text-xs font-medium text-slate-500 tabular-nums">{d.code}</div>}
                      <div className="font-medium text-slate-900">{d.title}</div>
                      <div className="mt-1">
                        <DataKindBadge kind={d.data_kind} />
                      </div>
                      {d.watermark && (
                        <p className="mt-1.5 text-[11px] font-medium text-amber-800">Marca: {d.watermark}</p>
                      )}
                    </div>
                  </div>
                </td>
                <td>{scopeLabel(d.scope)}</td>
                <td>{d.doc_type ? docTypeLabel(d.doc_type) : <span className="muted">No declarado</span>}</td>
                <td className="tabular-nums">v{d.current_version}</td>
                <td>{d.issuer_declared ?? <span className="muted">No declarado</span>}</td>
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
                <td>{d.owner?.full_name ?? <span className="muted">Sin asignar</span>}</td>
                <td className="min-w-[160px] text-xs">
                  {latest?.filename ? (
                    <span>{latest.filename}</span>
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
