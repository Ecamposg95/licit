/** Búsquedas guardadas por persona (T17). Refleja `app/schemas/saved_search.py`. */
import { http } from '@/lib/api'
import type { IsoDateTime } from '@/lib/types'

export const MAX_SAVED_TERMS = 10

export interface SavedSearchIn {
  name: string
  terms: string[]
  states: string[]
  families: string[]
  buyers: string[]
}

export interface SavedSearch extends SavedSearchIn {
  id: string
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export const listSavedSearches = () => http.get<SavedSearch[]>('/saved-searches').then((r) => r.data)

export const createSavedSearch = (body: SavedSearchIn) =>
  http.post<SavedSearch>('/saved-searches', body).then((r) => r.data)

export const updateSavedSearch = (id: string, body: SavedSearchIn) =>
  http.put<SavedSearch>(`/saved-searches/${encodeURIComponent(id)}`, body).then((r) => r.data)

export const deleteSavedSearch = (id: string) =>
  http.delete(`/saved-searches/${encodeURIComponent(id)}`).then(() => undefined)
