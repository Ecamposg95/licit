import Tooltip from '@/components/Tooltip'
import { formatDate, formatDateTime, formatInstantDate, getDisplayTimeZone } from '@/lib/format'
import type { IsoDate, IsoDateTime } from '@/lib/types'

/** Instante en la zona de visualización, o el texto de ausencia indicado. */
export function DateTimeText({ value, empty = '—' }: { value: IsoDateTime | null | undefined; empty?: string }) {
  const text = formatDateTime(value)
  if (!text) return <span className="muted">{empty}</span>
  return (
    <time dateTime={value ?? undefined} className="tabular-nums">
      {text}
    </time>
  )
}

/** Fecha de calendario (vigencias, vencimientos, fecha base). */
export function CalendarDate({ value, empty = '—' }: { value: IsoDate | null | undefined; empty?: string }) {
  const text = formatDate(value)
  if (!text) return <span className="muted">{empty}</span>
  return (
    <time dateTime={value ?? undefined} className="tabular-nums">
      {text}
    </time>
  )
}

/**
 * Fecha de presentación. Con precisión "date" la fuente sólo publicó el día: se muestra la fecha
 * (en la zona de la fuente si se conoce) y la hora guardada no se presenta como dato.
 */
export function SubmissionDate({
  value,
  precision,
  sourceTimezone,
  empty = 'Sin fecha verificable',
}: {
  value: IsoDateTime | null
  precision: string
  sourceTimezone?: string | null
  empty?: string
}) {
  if (!value) return <span className="muted">{empty}</span>
  if (precision === 'date') {
    return (
      <span className="inline-flex flex-col">
        <time dateTime={value} className="tabular-nums">
          {formatInstantDate(value, sourceTimezone)}
        </time>
        <Tooltip content="La fuente publica sólo el día; la hora no se consultó." focusable>
          <span className="text-xs text-slate-500 underline decoration-dotted underline-offset-2">hora no publicada</span>
        </Tooltip>
      </span>
    )
  }
  return <DateTimeText value={value} />
}

export function TimezoneNote({ className }: { className?: string }) {
  return <span className={className}>Horario mostrado en {getDisplayTimeZone()}</span>
}
