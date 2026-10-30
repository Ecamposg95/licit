import type { ComponentType, ReactNode } from 'react'
import {
  Archive,
  Ban,
  CalendarClock,
  CalendarX,
  CircleCheck,
  CircleDashed,
  CircleMinus,
  CircleQuestionMark,
  CircleX,
  Clock,
  CloudOff,
  Eye,
  FileX,
  FlaskConical,
  Globe,
  Hourglass,
  Lock,
  ShieldCheck,
  type LucideProps,
} from 'lucide-react'
import Tooltip from '@/components/Tooltip'
import { DATA_KIND_HINT, DATA_KIND_LABEL, humanize } from '@/lib/labels'
import type { DataKind, Derived } from '@/lib/types'

type Icon = ComponentType<LucideProps>

interface Tone {
  label: string
  icon: Icon
  className: string
}

export function Badge({
  tone,
  children,
  title,
  wrap,
}: {
  tone: Omit<Tone, 'label'>
  children: ReactNode
  title?: string
  /** Permite varias líneas (columnas angostas) en lugar de recortar el texto. */
  wrap?: boolean
}) {
  const Ico = tone.icon
  return (
    <span
      title={title}
      className={`inline-flex max-w-full gap-1 border px-2 py-0.5 text-xs font-medium ${
        wrap ? 'items-start rounded-md' : 'items-center whitespace-nowrap rounded-full'
      } ${tone.className}`}
    >
      <Ico aria-hidden="true" className={`h-3.5 w-3.5 shrink-0 ${wrap ? 'mt-px' : ''}`} strokeWidth={2.25} />
      <span className={wrap ? '' : 'truncate'}>{children}</span>
    </span>
  )
}

// ── Tipo de dato ─────────────────────────────────────────────────────────────

const DATA_KIND_TONE: Record<DataKind, Omit<Tone, 'label'>> = {
  REAL: { icon: Globe, className: 'border-petrol-300 bg-petrol-50 text-petrol-800' },
  HISTORICAL: { icon: Archive, className: 'border-slate-300 bg-slate-100 text-slate-700' },
  SYNTHETIC: { icon: FlaskConical, className: 'border-amber-400 hatch-synthetic-soft text-amber-950' },
}

/** Insignia de data_kind. SYNTHETIC siempre se rotula "Simulado · ficticio". */
export function DataKindBadge({ kind, withTooltip = true }: { kind: DataKind; withTooltip?: boolean }) {
  const text = kind === 'SYNTHETIC' ? 'Simulado · ficticio' : DATA_KIND_LABEL[kind] ?? kind
  const badge = <Badge tone={DATA_KIND_TONE[kind] ?? DATA_KIND_TONE.HISTORICAL}>{text}</Badge>
  if (!withTooltip) return badge
  return (
    <Tooltip content={DATA_KIND_HINT[kind] ?? kind} focusable>
      {badge}
    </Tooltip>
  )
}

// ── Estado derivado de la oportunidad ────────────────────────────────────────

const DERIVED_TONE: Record<string, Omit<Tone, 'label'>> = {
  abierta_verificada: { icon: ShieldCheck, className: 'border-emerald-300 bg-emerald-50 text-emerald-800' },
  por_verificar: { icon: CircleQuestionMark, className: 'border-amber-300 bg-amber-50 text-amber-900' },
  desactualizada: { icon: Hourglass, className: 'border-orange-300 bg-orange-50 text-orange-900' },
  fuente_inaccesible: { icon: CloudOff, className: 'border-red-300 bg-red-50 text-red-800' },
  fecha_transcurrida: { icon: CalendarX, className: 'border-slate-300 bg-slate-100 text-slate-700' },
  historica: { icon: Archive, className: 'border-slate-300 bg-slate-100 text-slate-700' },
  simulada: { icon: FlaskConical, className: 'border-amber-300 bg-white text-amber-900' },
}

/** Estado de verificación derivado (icono + texto); el motivo va en el tooltip. */
export function DerivedBadge({ derived, wrap }: { derived: Derived; wrap?: boolean }) {
  const tone = DERIVED_TONE[derived.code] ?? { icon: CircleQuestionMark, className: 'border-slate-300 bg-white text-slate-700' }
  return (
    <Tooltip content={derived.reason} focusable>
      <Badge tone={tone} wrap={wrap}>
        {derived.label}
      </Badge>
    </Tooltip>
  )
}

// ── Estado de requisito (semáforo con texto e icono, §5 Matriz) ──────────────

export const REQUIREMENT_STATUS: Record<string, Tone & { group: 'verde' | 'ambar' | 'rojo' | 'neutro' }> = {
  cumple_validado: {
    label: 'Cumple · validado',
    icon: CircleCheck,
    className: 'border-emerald-300 bg-emerald-50 text-emerald-800',
    group: 'verde',
  },
  no_aplica_justificado: {
    label: 'No aplica · justificado',
    icon: CircleMinus,
    className: 'border-slate-300 bg-slate-50 text-slate-700',
    group: 'neutro',
  },
  en_revision: {
    label: 'En revisión',
    icon: Eye,
    className: 'border-sky-300 bg-sky-50 text-sky-800',
    group: 'ambar',
  },
  pendiente: {
    label: 'Pendiente',
    icon: Clock,
    className: 'border-amber-300 bg-amber-50 text-amber-900',
    group: 'ambar',
  },
  desconocido: {
    label: 'Desconocido',
    icon: CircleQuestionMark,
    className: 'border-violet-300 bg-violet-50 text-violet-800',
    group: 'ambar',
  },
  faltante: {
    label: 'Faltante',
    icon: FileX,
    className: 'border-orange-300 bg-orange-50 text-orange-900',
    group: 'rojo',
  },
  vencido: {
    label: 'Vencido',
    icon: CalendarClock,
    className: 'border-rose-300 bg-rose-50 text-rose-800',
    group: 'rojo',
  },
  incumple: {
    label: 'Incumple',
    icon: CircleX,
    className: 'border-red-400 bg-red-50 text-red-800',
    group: 'rojo',
  },
}

export const REQUIREMENT_STATUS_ORDER = [
  'incumple',
  'faltante',
  'vencido',
  'desconocido',
  'pendiente',
  'en_revision',
  'cumple_validado',
  'no_aplica_justificado',
]

const SEMAPHORE_DOT: Record<string, string> = {
  verde: 'bg-emerald-500',
  ambar: 'bg-amber-400',
  rojo: 'bg-red-600',
  neutro: 'bg-slate-400',
}

export function RequirementStatusBadge({ status }: { status: string }) {
  const s = REQUIREMENT_STATUS[status]
  if (!s) return <Badge tone={{ icon: CircleDashed, className: 'border-slate-300 bg-white text-slate-700' }}>{humanize(status)}</Badge>
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden="true" className={`h-2.5 w-2.5 shrink-0 rounded-full ${SEMAPHORE_DOT[s.group]}`} />
      <Badge tone={s}>{s.label}</Badge>
    </span>
  )
}

// ── Fuentes ──────────────────────────────────────────────────────────────────

const SOURCE_STATUS: Record<string, Tone & { hint: string }> = {
  activa: {
    label: 'Activa',
    icon: CircleCheck,
    className: 'border-emerald-300 bg-emerald-50 text-emerald-800',
    hint: 'La última consulta a la fuente funcionó.',
  },
  no_probada: {
    label: 'No probada',
    icon: CircleDashed,
    className: 'border-slate-300 bg-white text-slate-700',
    hint: 'Aún no se ha ejecutado una consulta real contra esta fuente.',
  },
  bloqueada: {
    label: 'Bloqueada',
    icon: Lock,
    className: 'border-red-300 bg-red-50 text-red-800',
    hint: 'CAPTCHA, autenticación o restricción de la fuente: se usa carga manual.',
  },
  inaccesible: {
    label: 'Inaccesible',
    icon: CloudOff,
    className: 'border-red-300 bg-red-50 text-red-800',
    hint: 'La última consulta falló por red o por el portal; no implica ausencia de procedimientos.',
  },
}

export function SourceStatusBadge({ status }: { status: string }) {
  const s = SOURCE_STATUS[status]
  if (!s) return <Badge tone={{ icon: CircleDashed, className: 'border-slate-300 bg-white text-slate-700' }}>{humanize(status)}</Badge>
  return (
    <Tooltip content={s.hint} focusable>
      <Badge tone={s}>{s.label}</Badge>
    </Tooltip>
  )
}

// ── Actividades y revisión ───────────────────────────────────────────────────

const TASK_STATUS: Record<string, Tone> = {
  pendiente: { label: 'Pendiente', icon: Clock, className: 'border-amber-300 bg-amber-50 text-amber-900' },
  en_progreso: { label: 'En progreso', icon: Eye, className: 'border-sky-300 bg-sky-50 text-sky-800' },
  hecha: { label: 'Hecha', icon: CircleCheck, className: 'border-emerald-300 bg-emerald-50 text-emerald-800' },
  cancelada: { label: 'Cancelada', icon: Ban, className: 'border-slate-300 bg-slate-100 text-slate-600' },
}

export function TaskStatusBadge({ status }: { status: string }) {
  const s = TASK_STATUS[status] ?? { label: humanize(status), icon: CircleDashed, className: 'border-slate-300 bg-white text-slate-700' }
  return <Badge tone={s}>{s.label}</Badge>
}

const REVIEW_STATUS: Record<string, Tone> = {
  pendiente: { label: 'Revisión pendiente', icon: Clock, className: 'border-amber-300 bg-amber-50 text-amber-900' },
  en_revision: { label: 'En revisión', icon: Eye, className: 'border-sky-300 bg-sky-50 text-sky-800' },
  validado: { label: 'Validado', icon: CircleCheck, className: 'border-emerald-300 bg-emerald-50 text-emerald-800' },
  aprobado: { label: 'Aprobado', icon: CircleCheck, className: 'border-emerald-300 bg-emerald-50 text-emerald-800' },
  rechazado: { label: 'Rechazado', icon: CircleX, className: 'border-red-300 bg-red-50 text-red-800' },
}

export function ReviewStatusBadge({ status }: { status: string }) {
  const s = REVIEW_STATUS[status] ?? { label: humanize(status), icon: CircleDashed, className: 'border-slate-300 bg-white text-slate-700' }
  return <Badge tone={s}>{s.label}</Badge>
}

export function ExpiredBadge({ label = 'Vencido', hint }: { label?: string; hint: string }) {
  return (
    <Tooltip content={hint} focusable>
      <Badge tone={{ icon: CalendarX, className: 'border-rose-300 bg-rose-50 text-rose-800' }}>{label}</Badge>
    </Tooltip>
  )
}
