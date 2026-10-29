import { Info } from 'lucide-react'
import { DataKindBadge } from '@/components/badges'
import { EmptyState } from '@/components/feedback'
import { formatQuantity, formatValue } from '@/lib/format'
import { attributeLabel, attributeUnit, operatorSymbol } from '@/lib/labels'
import type { LotOut, LotSpec } from '@/lib/types'

function isSpec(x: unknown): x is LotSpec {
  return typeof x === 'object' && x !== null && 'value' in x
}

const NotDeclared = () => <span className="italic text-slate-500">no declarado</span>

/** "Orificios = 6 orificios" a partir de {"holes": {"value": 6, "unit": "orificios", "operator": "eq"}}. */
function SpecLine({ name, spec }: { name: string; spec: unknown }) {
  const s: LotSpec = isSpec(spec) ? spec : { value: spec }
  const unit = s.unit ?? attributeUnit(name)
  const missing = s.value === null || s.value === undefined || s.value === ''
  return (
    <li title={name}>
      <span className="text-slate-600">{attributeLabel(name)}</span>{' '}
      <span className="text-slate-500">{operatorSymbol(s.operator)}</span>{' '}
      {missing ? (
        <NotDeclared />
      ) : (
        <span className="font-medium text-slate-900">
          {formatValue(s.value)}
          {unit ? ` ${unit}` : ''}
        </span>
      )}
    </li>
  )
}

function AttributeLine({ name, value }: { name: string; value: unknown }) {
  const missing = value === null || value === undefined || value === ''
  const unit = attributeUnit(name)
  return (
    <li title={name}>
      <span className="text-slate-600">{attributeLabel(name)}:</span>{' '}
      {missing ? (
        <NotDeclared />
      ) : (
        <span className="text-slate-900">
          {formatValue(value)}
          {unit ? ` ${unit}` : ''}
        </span>
      )}
    </li>
  )
}

export default function LotsTab({ lots }: { lots: LotOut[] }) {
  if (lots.length === 0) {
    return (
      <div className="card">
        <EmptyState title="Sin partidas capturadas">
          La fuente no publica partidas o aún no se han extraído de las bases. No se infieren.
        </EmptyState>
      </div>
    )
  }
  return (
    <div className="space-y-3">
      <p className="flex items-start gap-2 text-sm text-slate-600">
        <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
        Se muestra lo que exige cada partida y lo que declara la variante propuesta. El dictamen de correspondencia se
        calcula en el motor de correspondencia (E3); esta vista no concede cumplimiento.
      </p>
      <div className="card relative overflow-x-auto">
        <table className="table-base min-w-[980px]">
          <caption className="sr-only">Partidas del procedimiento</caption>
          <thead>
            <tr>
              <th scope="col">Partida</th>
              <th scope="col">Descripción</th>
              <th scope="col" className="text-right">
                Cantidad
              </th>
              <th scope="col">Especificaciones exigidas</th>
              <th scope="col">Variante propuesta</th>
            </tr>
          </thead>
          <tbody>
            {lots.map((l) => {
              const specs = Object.entries(l.specs ?? {})
              const qty = formatQuantity(l.quantity)
              const v = l.proposed_variant
              return (
                <tr key={l.id}>
                  <th scope="row" className="whitespace-nowrap px-4 py-3 text-left align-top font-semibold tabular-nums">
                    {l.number}
                  </th>
                  <td className="min-w-[240px]">
                    <div className="text-slate-900">{l.description}</div>
                    {l.family && <div className="mt-0.5 text-xs text-slate-500">{l.family}</div>}
                  </td>
                  <td className="whitespace-nowrap text-right tabular-nums">
                    {qty ? (
                      <>
                        {qty} <span className="text-slate-500">{l.unit ?? 'unidad no declarada'}</span>
                      </>
                    ) : (
                      <NotDeclared />
                    )}
                  </td>
                  <td className="min-w-[200px]">
                    {specs.length ? (
                      <ul className="space-y-0.5">
                        {specs.map(([k, s]) => (
                          <SpecLine key={k} name={k} spec={s} />
                        ))}
                      </ul>
                    ) : (
                      <span className="muted">Sin especificaciones capturadas</span>
                    )}
                  </td>
                  <td className="min-w-[260px]">
                    {v ? (
                      <div>
                        <div className="text-xs font-medium text-slate-500 tabular-nums">{v.sku}</div>
                        <div className="text-slate-900">{v.name}</div>
                        <div className="mt-1">
                          <DataKindBadge kind={v.data_kind} />
                        </div>
                        {Object.keys(v.attributes).length > 0 && (
                          <ul className="mt-2 space-y-0.5 text-xs">
                            {Object.entries(v.attributes).map(([k, val]) => (
                              <AttributeLine key={k} name={k} value={val} />
                            ))}
                          </ul>
                        )}
                      </div>
                    ) : (
                      <span className="muted">Sin variante propuesta</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
