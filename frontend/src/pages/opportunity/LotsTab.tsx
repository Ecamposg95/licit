import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Cpu, ExternalLink, FlaskConical, Info, Quote, RefreshCw } from 'lucide-react'
import { Badge, DataKindBadge, RequirementStatusBadge } from '@/components/badges'
import { DateTimeText } from '@/components/dates'
import { EmptyState, ErrorMeta, ErrorPanel } from '@/components/feedback'
import { toApiError, type ApiError } from '@/lib/api'
import {
  assessWorkspace,
  getRequirementMatrix,
  workspaceErrorText,
  type AssessmentOut,
  type LotPrice,
  type RequirementDetail,
  type WorkspaceView,
} from '@/lib/api-workspace'
import { formatMoney, formatQuantity, formatValue } from '@/lib/format'
import { attributeLabel, attributeUnit } from '@/lib/labels'
import { useApi, type ApiState } from '@/lib/useApi'
import type { LotOut, LotSpec } from '@/lib/types'
import { useCan } from '@/store/auth'
import { MatchResultBadge, operatorText, requiredExpression } from '@/pages/opportunity/matchLabels'

function isSpec(x: unknown): x is LotSpec {
  return typeof x === 'object' && x !== null && 'value' in x
}

const NotDeclared = ({ children = 'No declarado en el catálogo' }: { children?: string }) => (
  <span className="italic text-slate-500">{children}</span>
)

/** «Orificios = 11» a partir de las especificaciones capturadas de la partida (cuando no hay requisitos). */
function SpecList({ specs }: { specs: Record<string, unknown> }) {
  const entries = Object.entries(specs ?? {})
  if (!entries.length) return <span className="muted">Sin especificaciones capturadas</span>
  return (
    <ul className="space-y-0.5">
      {entries.map(([name, spec]) => {
        const s: LotSpec = isSpec(spec) ? spec : { value: spec }
        const unit = s.unit ?? attributeUnit(name)
        return (
          <li key={name}>
            <span className="text-slate-600">{attributeLabel(name)}</span>{' '}
            <span className="text-slate-500">{operatorText(s.operator)}</span>{' '}
            <span className="font-medium text-slate-900">
              {formatValue(s.value)}
              {unit && unit !== attributeLabel(name).toLowerCase() ? ` ${unit}` : ''}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function UnitPrice({ price, quantity, unit }: { price: LotPrice | undefined; quantity: string | null; unit: string | null }) {
  const qty = formatQuantity(quantity)
  const money = price ? formatMoney(price.unit_price, price.currency) : null
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      <dt className="text-slate-500">Cantidad</dt>
      <dd className="tabular-nums text-slate-900">
        {qty ? (
          <>
            {qty} <span className="text-slate-500">{unit ?? 'unidad no declarada'}</span>
          </>
        ) : (
          <NotDeclared>No declarada</NotDeclared>
        )}
      </dd>
      <dt className="text-slate-500">Precio unitario</dt>
      <dd>
        {money ? (
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <span className="font-medium tabular-nums text-slate-900">{money}</span>
            {price?.price_data_kind === 'SYNTHETIC' && (
              <Badge tone={{ icon: FlaskConical, className: 'border-amber-400 hatch-synthetic-soft text-amber-950' }}>
                Precio ficticio
              </Badge>
            )}
          </span>
        ) : (
          <span className="muted">Pendiente (no se inventa)</span>
        )}
      </dd>
    </dl>
  )
}

function CatalogCell({ a }: { a: AssessmentOut | undefined }) {
  if (!a) return <span className="muted">Sin evaluar</span>
  return (
    <div>
      {a.catalog_value ? <div className="font-medium text-slate-900">{a.catalog_value}</div> : <NotDeclared />}
      {a.source_text ? (
        <blockquote className="mt-1.5 flex gap-1.5 border-l-2 border-dpm-blue-200 pl-2 text-xs text-slate-700">
          <Quote aria-hidden="true" className="mt-0.5 h-3 w-3 shrink-0 text-dpm-blue-400" />
          <span>
            <span className="sr-only">Cita de la página del producto: </span>«{a.source_text}»
          </span>
        </blockquote>
      ) : (
        <p className="mt-1 text-xs text-slate-500">La página del producto no lo declara; no se infiere del nombre.</p>
      )}
    </div>
  )
}

/** La explicación guardada termina con la cita; aquí la cita ya se muestra en la columna del catálogo. */
function withoutCitation(a: AssessmentOut): string {
  if (!a.source_text) return a.explanation
  return a.explanation.replace(` Cita del catálogo: «${a.source_text}»`, '')
}

interface Props {
  lots: LotOut[]
  opportunityId: string
  workspace: ApiState<WorkspaceView>
  onAssessed?: () => void
}

/**
 * Comparador por partida: para cada requisito comparable, lo exigido, lo que declara el catálogo (con su cita
 * literal) y el resultado del motor determinista. El comparador no concede cumplimiento: eso lo decide una
 * persona en la matriz de requisitos.
 */
export default function LotsTab({ lots, opportunityId, workspace, onAssessed }: Props) {
  const canReqs = useCan('requirement.read')
  const canWrite = useCan('opportunity.write')
  const canReview = useCan('requirement.review')
  const reqs = useApi(
    () => getRequirementMatrix(opportunityId),
    [opportunityId, workspace.data?.workspace.version],
    canReqs,
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const byLot = useMemo(() => {
    const m = new Map<string, RequirementDetail[]>()
    for (const r of reqs.data ?? []) {
      if (!r.lot) continue
      m.set(r.lot.id, [...(m.get(r.lot.id) ?? []), r])
    }
    return m
  }, [reqs.data])
  const assessments = useMemo(
    () => new Map((workspace.data?.assessments ?? []).map((a) => [a.requirement_id ?? '', a])),
    [workspace.data],
  )
  const prices = useMemo(() => new Map((workspace.data?.lots ?? []).map((p) => [p.lot_id, p])), [workspace.data])

  async function assess() {
    setBusy(true)
    setError(null)
    try {
      workspace.setData(await assessWorkspace(opportunityId))
      onAssessed?.()
    } catch (e) {
      setError(toApiError(e))
    } finally {
      setBusy(false)
    }
  }

  if (lots.length === 0) {
    return (
      <div className="card">
        <EmptyState title="Sin partidas capturadas">
          La fuente no publica partidas o aún no se han extraído de las bases. No se infieren.
        </EmptyState>
      </div>
    )
  }

  const assessed = (workspace.data?.assessments.length ?? 0) > 0
  const engine = workspace.data?.assessments[0]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="flex max-w-3xl items-start gap-2 text-sm text-slate-600">
          <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
          Comparación determinista de cada requisito con lo que declara el catálogo de la variante propuesta, con la cita
          literal de su página. Un dato no declarado queda «desconocido»: nunca se infiere del nombre comercial. El
          resultado es preliminar y no cambia el estado del requisito.
        </p>
        {(canWrite || canReview) && (
          <button type="button" className={assessed ? 'btn-secondary' : 'btn-primary'} onClick={assess} disabled={busy}>
            {assessed ? <RefreshCw aria-hidden="true" className="h-4 w-4" /> : <Cpu aria-hidden="true" className="h-4 w-4" />}
            {busy ? 'Evaluando…' : assessed ? 'Reevaluar' : 'Evaluar correspondencia'}
          </button>
        )}
      </div>
      {engine && (
        <p className="text-xs text-slate-500">
          Motor determinista v{engine.engine_version} · evaluado <DateTimeText value={engine.assessed_at} />
        </p>
      )}
      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
          {workspaceErrorText(error)}
          <ErrorMeta error={error} />
        </div>
      )}
      {workspace.error && <ErrorPanel error={workspace.error} onRetry={workspace.reload} />}
      {reqs.error && <ErrorPanel error={reqs.error} onRetry={reqs.reload} />}

      {lots.map((l) => {
        const v = l.proposed_variant
        const price = prices.get(l.id)
        const lotReqs = byLot.get(l.id) ?? []
        const comparable = lotReqs.filter((r) => r.attribute)
        const others = lotReqs.filter((r) => !r.attribute)
        return (
          <section key={l.id} aria-labelledby={`lot-${l.id}`} className="card overflow-hidden">
            <div className="grid gap-4 border-b border-slate-200 bg-slate-50/60 px-4 py-3 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1.2fr)]">
              <div>
                <h3 id={`lot-${l.id}`} className="text-sm font-semibold text-slate-900">
                  Partida {l.number}
                </h3>
                <p className="mt-0.5 text-[15px] text-slate-900">{l.description}</p>
                {l.family && <p className="mt-0.5 text-xs text-slate-500">{l.family}</p>}
              </div>
              <UnitPrice price={price} quantity={l.quantity} unit={l.unit} />
              <div>
                <p className="text-xs font-medium text-slate-500">Variante propuesta</p>
                {v ? (
                  <div className="mt-0.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold tabular-nums text-slate-700">{v.sku}</span>
                      <DataKindBadge kind={v.data_kind} />
                    </div>
                    <div className="text-sm text-slate-900">{v.name}</div>
                    {price?.product_id && (
                      <Link
                        to={`/catalogo/${price.product_id}`}
                        className="link mt-0.5 inline-flex items-center gap-1 text-xs"
                      >
                        Ver ficha del producto{price.product_name ? `: ${price.product_name}` : ''}
                        <ExternalLink aria-hidden="true" className="h-3 w-3" />
                      </Link>
                    )}
                    {price?.product_review_status === 'por_revisar' && (
                      <p className="mt-0.5 text-xs text-amber-800">
                        La ficha tiene observaciones de calidad del sitio (por revisar).
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="mt-0.5 text-sm text-slate-600">Sin variante propuesta: el catálogo no cubre esta partida.</p>
                )}
              </div>
            </div>

            {comparable.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="table-base min-w-[860px]">
                  <caption className="sr-only">
                    Comparador de la partida {l.number}: exigido, catálogo con cita y resultado
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col" className="w-[30%]">
                        Exigido
                      </th>
                      <th scope="col" className="w-[36%]">
                        Catálogo (cita)
                      </th>
                      <th scope="col">Resultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparable.map((r) => {
                      const a = assessments.get(r.id)
                      return (
                        <tr key={r.id}>
                          <td>
                            {r.code && <div className="text-xs font-medium tabular-nums text-slate-500">{r.code}</div>}
                            <div className="text-slate-900">{r.text}</div>
                            <div className="mt-0.5 text-xs font-medium text-slate-700">{requiredExpression(r)}</div>
                            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                              Bases p. {r.page ?? 'no indicada'} · requisito
                              <RequirementStatusBadge status={r.status} />
                            </div>
                          </td>
                          <td>
                            <CatalogCell a={a} />
                          </td>
                          <td>
                            {a ? (
                              <div>
                                <MatchResultBadge result={a.result} />
                                <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{withoutCitation(a)}</p>
                              </div>
                            ) : (
                              <span className="muted">Sin evaluar</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="px-4 py-3 text-sm">
                <p className="text-xs font-medium text-slate-500">Especificaciones de la partida</p>
                <div className="mt-1">
                  <SpecList specs={l.specs as Record<string, unknown>} />
                </div>
                <p className="mt-2 text-xs text-slate-500">Sin requisitos comparables con el catálogo en esta partida.</p>
              </div>
            )}

            {others.length > 0 && (
              <div className="border-t border-slate-100 px-4 py-2.5 text-xs text-slate-600">
                <span className="font-medium text-slate-700">Además exige (se revisa en la matriz):</span>
                <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                  {others.map((r) => (
                    <li key={r.id} className="inline-flex items-center gap-1.5">
                      <span className="tabular-nums">{r.code}</span> {r.text}
                      <RequirementStatusBadge status={r.status} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}
