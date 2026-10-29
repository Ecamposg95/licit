/**
 * Formato de fechas, dinero y cantidades.
 *
 * - Instantes (`datetime`) se muestran en la zona de visualización (meta.display_timezone,
 *   America/Mexico_City por defecto) mediante Intl; no se reinterpreta su significado.
 *   Un ISO sin zona se interpreta como UTC, que es como el backend declara guardarlos.
 * - Fechas de calendario (`date`) se muestran tal cual, sin conversión de zona.
 * - Decimales llegan como string y sólo se formatean para mostrar; no se hace aritmética.
 */
import type { DataKind, DecimalString, IsoDate, IsoDateTime } from '@/lib/types'

export const DEFAULT_TZ = 'America/Mexico_City'
const LOCALE = 'es-MX'

let displayTz = DEFAULT_TZ

export function setDisplayTimeZone(tz: string | null | undefined) {
  displayTz = tz || DEFAULT_TZ
}

export function getDisplayTimeZone() {
  return displayTz
}

const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i

export function parseInstant(value: IsoDateTime): Date | null {
  const iso = HAS_ZONE.test(value) ? value : `${value}Z`
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

function fmt(options: Intl.DateTimeFormatOptions, tz = displayTz) {
  return new Intl.DateTimeFormat(LOCALE, { timeZone: tz, ...options })
}

/** "11 nov 2026, 10:00" en la zona de visualización. */
export function formatDateTime(value: IsoDateTime | null | undefined): string | null {
  if (!value) return null
  const d = parseInstant(value)
  if (!d) return value
  return fmt({ day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(d)
}

/** Sólo el día del instante, calculado en la zona indicada (por defecto la de visualización). */
export function formatInstantDate(value: IsoDateTime | null | undefined, tz?: string | null): string | null {
  if (!value) return null
  const d = parseInstant(value)
  if (!d) return value
  return fmt({ day: 'numeric', month: 'short', year: 'numeric' }, tz || displayTz).format(d)
}

function parseCalendarDate(value: IsoDate): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!m) return null
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
}

/** Fecha de calendario "28 oct 2026" (sin conversión de zona). */
export function formatDate(value: IsoDate | null | undefined): string | null {
  if (!value) return null
  const d = parseCalendarDate(value)
  if (!d) return value
  return fmt({ day: 'numeric', month: 'short', year: 'numeric' }, 'UTC').format(d)
}

/** Fecha de calendario larga "28 de octubre de 2026". */
export function formatDateLong(value: IsoDate | null | undefined): string | null {
  if (!value) return null
  const d = parseCalendarDate(value)
  if (!d) return value
  return fmt({ day: 'numeric', month: 'long', year: 'numeric' }, 'UTC').format(d)
}

/** Hoy como "YYYY-MM-DD" en la zona de visualización. */
export function todayInDisplayTz(): IsoDate {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: displayTz,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const get = (t: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === t)?.value ?? '00'
  return `${get('year')}-${get('month')}-${get('day')}`
}

/**
 * Fecha de referencia para vigencias y vencimientos: los registros SYNTHETIC se evalúan contra
 * la fecha base del demo; los demás, contra la fecha de hoy en la zona de visualización.
 */
export function referenceDate(dataKind: DataKind, demoBaseDate: IsoDate | undefined): IsoDate {
  if (dataKind === 'SYNTHETIC' && demoBaseDate) return demoBaseDate
  return todayInDisplayTz()
}

/** Compara fechas "YYYY-MM-DD" como texto (orden lexicográfico = cronológico). */
export function isBefore(a: IsoDate, b: IsoDate): boolean {
  return a.slice(0, 10) < b.slice(0, 10)
}

const moneyFormatters = new Map<string, Intl.NumberFormat>()

/**
 * Formatea un decimal recibido como string. Se pasa el string a Intl (formato decimal exacto en
 * motores con Intl.NumberFormat v3); nunca se usa parseFloat ni se opera aritméticamente.
 */
export function formatMoney(value: DecimalString | null | undefined, currency: string | null | undefined): string | null {
  if (value === null || value === undefined || value === '') return null
  const cur = currency || 'MXN'
  let f = moneyFormatters.get(cur)
  if (!f) {
    f = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: cur, currencyDisplay: 'code', minimumFractionDigits: 2 })
    moneyFormatters.set(cur, f)
  }
  // Intl.NumberFormat v3 acepta strings decimales (precisión exacta); los tipos de TS sólo declaran number.
  return f.format(value as unknown as number)
}

/** "40.000" → "40"; "2.500" → "2.5". Sólo manipulación de texto. */
export function formatQuantity(value: DecimalString | null | undefined): string | null {
  if (value === null || value === undefined || value === '') return null
  const s = String(value)
  if (!s.includes('.')) return s
  return s.replace(/0+$/, '').replace(/\.$/, '')
}

export function formatInteger(value: number | null | undefined): string | null {
  if (value === null || value === undefined) return null
  return new Intl.NumberFormat(LOCALE).format(value)
}

/** Valor de atributo arbitrario para mostrar. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'no declarado'
  if (typeof value === 'boolean') return value ? 'sí' : 'no'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
