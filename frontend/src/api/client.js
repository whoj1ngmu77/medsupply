// Dev: Vite proxies /api to localhost:8000.
// Prod: VITE_API_URL points at the deployed backend.
const BASE = import.meta.env.VITE_API_URL || '/api'

let authToken = null
export const setToken = (t) => { authToken = t }
export const getToken = () => authToken

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    setToken(null)
    window.dispatchEvent(new Event('auth:expired'))
    throw new Error('Session expired. Please log in again.')
  }
  if (res.status === 204) return null

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = data.detail
    const msg = Array.isArray(detail)
      ? detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join('; ')
      : detail || `Request failed (${res.status})`
    throw new Error(msg)
  }
  return data
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: 'POST', body: JSON.stringify(body) }),
  patch: (p, body) => request(p, { method: 'PATCH', body: JSON.stringify(body) }),
  del: (p) => request(p, { method: 'DELETE' }),
}
