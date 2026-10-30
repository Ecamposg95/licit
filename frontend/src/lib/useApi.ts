import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, toApiError } from '@/lib/api'

export interface ApiState<T> {
  data: T | undefined
  error: ApiError | null
  loading: boolean
  reload: () => void
  setData: (data: T) => void
}

/**
 * Carga datos de la API y descarta respuestas obsoletas cuando cambian las dependencias.
 * `enabled = false` deja el estado en reposo (sin petición).
 */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[], enabled = true): ApiState<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState<boolean>(enabled)
  const [nonce, setNonce] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    let active = true
    setLoading(true)
    setError(null)
    fetcherRef
      .current()
      .then((d) => {
        if (active) setData(d)
      })
      .catch((e: unknown) => {
        if (active) setError(toApiError(e))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload, setData }
}
