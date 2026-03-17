import { useState, useEffect, useRef, useCallback } from 'react'

export function usePolling(fetchFn, intervalMs = 3000, enabled = true) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const timerRef = useRef(null)

  const poll = useCallback(async () => {
    try {
      const result = await fetchFn()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [fetchFn])

  useEffect(() => {
    if (!enabled) return

    poll()
    timerRef.current = setInterval(poll, intervalMs)
    return () => clearInterval(timerRef.current)
  }, [poll, intervalMs, enabled])

  return { data, error, loading, refetch: poll }
}
