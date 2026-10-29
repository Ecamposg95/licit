import { useState } from 'react'
import { Quote } from 'lucide-react'
import Tooltip from '@/components/Tooltip'
import { attributeLabel } from '@/lib/labels'

/** Etiquetas de los atributos del catálogo de Dipromedic; si falta una, se muestra la clave legible. */
const LABELS: Record<string, string> = {
  material: 'Material',
  norma_material: 'Norma del material',
  diametro: 'Diámetro',
  diametros: 'Diámetros',
  longitud: 'Longitud',
  region_anatomica: 'Región anatómica',
  lateralidad: 'Lateralidad',
  orificios_disponibles: 'Orificios disponibles',
  orificios_poliaxiales: 'Orificios poliaxiales',
  orificios_poliaxiales_distales: 'Orificios poliaxiales distales',
  orificios_monoaxiales: 'Orificios monoaxiales',
  orificios_bloqueo: 'Orificios de bloqueo',
  orificios_lisos: 'Orificios lisos',
  diametros_disponibles: 'Diámetros disponibles',
  longitudes_disponibles: 'Longitudes disponibles',
  perfil_proximal: 'Perfil proximal',
  perfil_distal: 'Perfil distal',
  angulo_variable: 'Ángulo variable',
  angulos: 'Ángulos',
  recubrimiento: 'Recubrimiento',
  porosidad_minima: 'Porosidad mínima',
  medidas: 'Medidas',
  cono: 'Cono',
  fijacion: 'Fijación',
  variantes_fijacion: 'Variantes de fijación',
  tipo_orificio: 'Tipo de orificio',
  esterilidad: 'Esterilidad',
  inserto: 'Inserto',
  espesor: 'Espesor',
  holes: 'Orificios',
  diameter_mm: 'Diámetro',
  length_mm: 'Longitud',
}
export const catalogAttributeLabel = (key: string) => LABELS[key] ?? attributeLabel(key)

export interface AttributeView {
  text: string
  /** Texto literal de la página que respalda el valor; `null` si el dato no trae cita (datos ficticios). */
  quote: string | null
}

const NUMBER = new Intl.NumberFormat('es-MX', { maximumFractionDigits: 3 })

function scalar(v: unknown): string {
  if (v === null || v === undefined || v === '') return 'no declarado'
  if (typeof v === 'number') return NUMBER.format(v)
  if (typeof v === 'boolean') return v ? 'sí' : 'no'
  return String(v)
}

function joinList(items: string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} y ${items[items.length - 1]}`
}

/** Unidades que van pegadas al número (±15°, 30%). */
function withUnit(text: string, unit: string | null | undefined): string {
  if (!unit) return text
  return unit === '°' || unit === '%' ? `${text}${unit}` : `${text} ${unit}`
}

function valueText(v: unknown, unit: string | null | undefined): string {
  if (Array.isArray(v)) return withUnit(joinList(v.map(scalar)), unit)
  if (v !== null && typeof v === 'object') {
    const o = v as Record<string, unknown>
    if ('min' in o && 'max' in o) return withUnit(`${scalar(o.min)}–${scalar(o.max)}`, unit)
    return Object.entries(o)
      .map(([k, x]) => `${k}: ${withUnit(scalar(x), unit)}`)
      .join('; ')
  }
  return withUnit(scalar(v), unit)
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v)
}

/** Valor legible y cita de un atributo, sea de una ficha (`value`), de una fila de tabla (`values`) o un dato plano. */
export function attributeView(raw: unknown): AttributeView {
  if (isRecord(raw) && typeof raw.source_text === 'string') {
    const unit = typeof raw.unit === 'string' ? raw.unit : null
    if ('values' in raw) return { text: valueText(raw.values, unit), quote: raw.source_text }
    if ('value' in raw) return { text: valueText(raw.value, unit), quote: raw.source_text }
  }
  return { text: valueText(raw, null), quote: null }
}

/** Valor con la cita en un tooltip (pasar el cursor o enfocar). */
export function CitedValue({ raw }: { raw: unknown }) {
  const { text, quote } = attributeView(raw)
  if (!quote) return <span>{text}</span>
  return (
    <Tooltip
      focusable
      content={
        <>
          <span className="block italic">«{quote}»</span>
          <span className="mt-1 block text-[11px] text-slate-300">Fuente: página del producto</span>
        </>
      }
    >
      <span className="cursor-help border-b border-dotted border-dpm-blue-400">{text}</span>
    </Tooltip>
  )
}

/**
 * Atributos técnicos con su valor y unidad. La cita textual de la página sale en un tooltip y,
 * con «Mostrar citas», en una columna visible. Un atributo sin cita se rotula como tal.
 */
export default function AttributeTable({ attributes, caption }: { attributes: Record<string, unknown>; caption?: string }) {
  const [showQuotes, setShowQuotes] = useState(false)
  const entries = Object.entries(attributes)
  if (entries.length === 0) return <p className="text-sm muted">Sin atributos técnicos publicados.</p>
  const anyQuote = entries.some(([, v]) => attributeView(v).quote)

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-600">
          {anyQuote ? (
            <>
              <strong className="font-semibold text-slate-700">Fuente: página del producto.</strong> Pasa el cursor o
              enfoca un valor para ver la cita textual.
            </>
          ) : (
            'Datos de demostración: no tienen cita de ninguna página.'
          )}
        </p>
        {anyQuote && (
          <button
            type="button"
            aria-pressed={showQuotes}
            onClick={() => setShowQuotes((s) => !s)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
              showQuotes
                ? 'border-dpm-blue bg-dpm-blue-50 text-dpm-blue-800'
                : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
            }`}
          >
            <Quote aria-hidden="true" className="h-3.5 w-3.5" />
            {showQuotes ? 'Ocultar citas' : 'Mostrar citas'}
          </button>
        )}
      </div>
      <div className="relative overflow-x-auto rounded-md border border-slate-200">
        <table className="table-base table-compact">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr>
              <th scope="col">Atributo</th>
              <th scope="col">Valor</th>
              {showQuotes && <th scope="col">Cita textual de la página</th>}
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, raw]) => {
              const { quote } = attributeView(raw)
              return (
                <tr key={key}>
                  <th scope="row" className="whitespace-nowrap px-3 py-2.5 pl-4 text-left align-top font-medium text-slate-700">
                    {catalogAttributeLabel(key)}
                  </th>
                  <td className="min-w-[160px] text-slate-900">
                    <CitedValue raw={raw} />
                    {!quote && <span className="ml-2 text-[11px] text-amber-800">sin cita</span>}
                  </td>
                  {showQuotes && (
                    <td className="max-w-md text-xs italic text-slate-600">{quote ? `«${quote}»` : '—'}</td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
