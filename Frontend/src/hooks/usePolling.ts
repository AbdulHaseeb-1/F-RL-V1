import { useState, useEffect, useRef, useCallback } from 'react'

interface UsePollingResult<T> {
  data: T | null
  error: string | null
  loading: boolean
  refetch: () => Promise<void>
}

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  intervalMs = 3000,
  enabled = true,
): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const poll = useCallback(async () => {
    try {
      const result = await fetchFn()
      setData(result)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Polling failed')
    } finally {
      setLoading(false)
    }
  }, [fetchFn])

  useEffect(() => {
    if (!enabled) {
      return
    }

    void poll()
    timerRef.current = setInterval(() => {
      void poll()
    }, intervalMs)

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [poll, intervalMs, enabled])

  return { data, error, loading, refetch: poll }
}
