const BASE_URL = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  health: () => request('/api/health'),
  items: {
    list: () => request('/api/v1/items'),
    create: (body) => request('/api/v1/items', { method: 'POST', body: JSON.stringify(body) }),
  },
}
