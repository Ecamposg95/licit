import { http } from '@/lib/api'
import type { DataKind, DecimalString, DocumentOut, IsoDate } from '@/lib/types'

/** Contratos de `/api/v1/catalog` (app/schemas/catalog.py). */

/** Atributo con la cita literal de la página: `value` + `unit`, o `values` cuando sale de una fila de tabla. */
export interface CitedAttribute {
  value: unknown
  unit: string | null
  source_text: string
}
export interface CitedRowAttribute {
  values: unknown[]
  unit: string | null
  source_text: string
}

export interface CatalogLine {
  line: string
  product_count: number
  families: string[]
}

export interface ProductCard {
  id: string
  name: string
  family: string
  brand: string | null
  manufacturer: string | null
  data_kind: DataKind
  review_status: string
  description: string | null
  line: string | null
  subfamily: string | null
  source_url: string | null
  checked_on: IsoDate | null
  attribution: string | null
  images: string[]
  variant_count: number
}

export interface CatalogVariant {
  id: string
  sku: string
  name: string
  /** REAL: `{value|values, unit, source_text}` por atributo. SYNTHETIC: valores planos sin cita. */
  attributes: Record<string, unknown>
  unit: string
  price: DecimalString | null
  currency: string | null
  stock_demo: number | null
  regulatory_reference: string | null
  data_kind: DataKind
  review_status: string
  side: 'izquierda' | 'derecha' | null
  source_text: string | null
  field_provenance: Record<string, unknown>
}

export interface ProductDetail extends ProductCard {
  features: string[]
  data_quality_notes: string[]
  /** Atributos idénticos (valor y cita) en todas las variantes. */
  attributes: Record<string, unknown>
  variants: CatalogVariant[]
  documents: DocumentOut[]
}

export interface CatalogQuery {
  line?: string
  family?: string
  q?: string
  data_kind?: DataKind[]
}

function params(query: CatalogQuery) {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v) && v.length === 0) continue
    out[k] = v
  }
  return out
}

export const listCatalogLines = () => http.get<CatalogLine[]>('/catalog/lines').then((r) => r.data)

export const listCatalogProducts = (query: CatalogQuery) =>
  http.get<ProductCard[]>('/catalog/products', { params: params(query) }).then((r) => r.data)

export const getCatalogProduct = (id: string) =>
  http.get<ProductDetail>(`/catalog/products/${encodeURIComponent(id)}`).then((r) => r.data)
