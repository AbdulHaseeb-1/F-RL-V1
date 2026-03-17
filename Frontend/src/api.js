const BASE_URL = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  const json = await res.json()
  // Unwrap the backend envelope {success, data} → data
  return json.data !== undefined ? json.data : json
}

export const api = {
  health: () => request('/api/health'),

  pipeline: {
    status: () => request('/api/pipeline/status'),
    start: (config) => request('/api/pipeline/start', {
      method: 'POST', body: JSON.stringify(config || {}),
    }),
    stop: () => request('/api/pipeline/stop', { method: 'POST' }),
    history: () => request('/api/pipeline/history'),
  },

  monitor: {
    progress: () => request('/api/monitor/progress'),
    metrics: (stage) => request(`/api/monitor/metrics/${stage || 'all'}`),
    gates: () => request('/api/monitor/gates'),
  },

  backtest: {
    equity: () => request('/api/backtest/equity'),
    trades: () => request('/api/backtest/trades'),
    metrics: () => request('/api/backtest/metrics'),
    riskEvents: () => request('/api/backtest/risk-events'),
  },

  signals: {
    recent: (n = 50) => request(`/api/signals/recent?n=${n}`),
    stats: () => request('/api/signals/stats'),
  },
}
