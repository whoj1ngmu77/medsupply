import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'

export function useFetch(path, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await api.get(path))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => { reload() }, deps.length ? deps : [path])

  return { data, loading, error, reload }
}
