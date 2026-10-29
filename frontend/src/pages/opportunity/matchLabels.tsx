/** Etiquetas e insignias del motor de correspondencia y del expediente (frente E). */
import { CircleCheck, CircleHelp, CircleSlash, CircleX } from 'lucide-react'
import { Badge } from '@/components/badges'
import Tooltip from '@/components/Tooltip'
import { attributeLabel } from '@/lib/labels'
import type { Validity } from '@/lib/api-workspace'

const RESULT: Record<string, { label: string; icon: typeof CircleCheck; className: string; hint: string }> = {
  coincide: {
    label: 'Coincide',
    icon: CircleCheck,
    className: 'border-emerald-300 bg-emerald-50 text-emerald-800',
    hint: 'Correspondencia técnica preliminar con lo que declara el catálogo. El cumplimiento sigue sujeto a evidencia y revisión.',
  },
  incumple: {
    label: 'Incumple',
    icon: CircleX,
    className: 'border-red-400 bg-red-50 text-red-800',
    hint: 'Lo que declara el catálogo no cumple lo exigido. No se asume equivalencia ni tolerancia no documentada.',
  },
  desconocido: {
    label: 'Desconocido',
    icon: CircleHelp,
    className: 'border-violet-300 bg-violet-50 text-violet-800',
    hint: 'El catálogo no declara el dato. No se infiere del nombre comercial.',
  },
  no_comparable: {
    label: 'No comparable',
    icon: CircleSlash,
    className: 'border-slate-300 bg-slate-50 text-slate-700',
    hint: 'Las unidades o el tipo de dato no permiten comparar sin interpretar.',
  },
}

/** Resultado del motor con texto e ícono (nunca solo color). */
export function MatchResultBadge({ result }: { result: string }) {
  const r = RESULT[result] ?? RESULT.no_comparable
  return (
    <Tooltip content={r.hint} focusable>
      <Badge tone={r}>{RESULT[result] ? r.label : result}</Badge>
    </Tooltip>
  )
}

export const matchResultLabel = (result: string) => RESULT[result]?.label ?? result

const OPERATOR: Record<string, string> = { eq: '=', gte: '≥', lte: '≤', contains: 'contiene', in: 'uno de' }
export const operatorText = (op: string | null | undefined) => (op ? OPERATOR[op] ?? op : '=')

/** «Orificios = 11», «Material contiene titanio», «Longitud = 96 mm». */
export function requiredExpression(r: {
  attribute: string | null
  operator: string | null
  expected_value: string | null
  unit: string | null
}): string | null {
  if (!r.attribute) return null
  const label = attributeLabel(r.attribute)
  const unit = r.unit && r.unit.toLowerCase() !== label.toLowerCase() ? ` ${r.unit}` : ''
  const value = r.operator === 'contains' ? `«${r.expected_value ?? ''}»` : `${r.expected_value ?? 'no declarado'}${unit}`
  return `${label} ${operatorText(r.operator)} ${value}`
}

const VALIDITY: Record<string, { label: string; className: string }> = {
  vigente: { label: 'Vigente a la fecha exigida', className: 'text-slate-600' },
  vence_antes: { label: 'Vence antes de la fecha exigida', className: 'font-medium text-rose-700' },
  vencido: { label: 'Vencido', className: 'font-medium text-rose-700' },
  sin_vigencia: { label: 'Sin vigencia declarada', className: 'text-slate-500' },
}

export function ValidityText({ validity }: { validity: Validity | string }) {
  const v = VALIDITY[validity] ?? { label: validity, className: 'text-slate-500' }
  return <span className={v.className}>{v.label}</span>
}

export const DECISION_LABEL: Record<string, string> = {
  pendiente: 'Sin decisión',
  participar: 'Participar',
  no_participar: 'No participar',
}

export const PHASE_LABEL: Record<string, string> = {
  analisis: 'Análisis',
  preparacion: 'Preparación del expediente',
  listo_revision_final: 'Listo para revisión final',
  descartada: 'Descartada (no participar)',
}

export const AFFINITY_LABEL: Record<string, string> = {
  familia: 'Familia',
  atributos: 'Atributos técnicos',
  documental: 'Cobertura documental',
  capacidad: 'Capacidad declarada',
}

export const BLOCKER_LABEL: Record<string, string> = {
  decision: 'Decisión de participar',
  aprobacion_tecnica: 'Aprobación técnica',
  aprobacion_comercial: 'Aprobación comercial',
  aprobaciones_desactualizadas: 'Aprobaciones desactualizadas',
  sin_requisitos: 'Sin requisitos obligatorios',
}

export const REVIEW_DECISIONS: { value: string; label: string; hint: string }[] = [
  { value: 'cumple_validado', label: 'Cumple · validado', hint: 'La evidencia vinculada demuestra el requisito.' },
  { value: 'incumple', label: 'Incumple', hint: 'La evidencia muestra que no se cumple.' },
  { value: 'faltante', label: 'Faltante', hint: 'La evidencia no sirve; falta el documento correcto.' },
  { value: 'vencido', label: 'Vencido', hint: 'El documento no está vigente a la fecha exigida.' },
  { value: 'desconocido', label: 'Desconocido', hint: 'No se puede determinar con lo disponible.' },
  { value: 'no_aplica_justificado', label: 'No aplica · justificado', hint: 'Las bases no lo exigen a esta oferta.' },
  { value: 'pendiente', label: 'Pendiente', hint: 'Regresa el requisito a pendiente.' },
]
