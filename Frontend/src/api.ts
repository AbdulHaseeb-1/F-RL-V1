import type {
  BacktestMetrics,
  EquityPoint,
  GateResult,
  HealthResponse,
  HistoryEntry,
  PipelineProgressData,
  PipelineRunStatus,
  RiskEvent,
  SignalRecord,
  SignalStats,
  Trade,
} from './types'

const BASE_URL = import.meta.env.VITE_API_URL || ''

type RequestOptions = Omit<RequestInit, 'headers'> & {
  headers?: HeadersInit
}

async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })

  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }

  const json = await res.json()
  return (json.data !== undefined ? json.data : json) as T
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),

  pipeline: {
    status: () => request<PipelineRunStatus>('/api/pipeline/status'),
    start: (config?: Record<string, unknown>) =>
      request('/api/pipeline/start', {
        method: 'POST',
        body: JSON.stringify(config || {}),
      }),
    stop: () => request('/api/pipeline/stop', { method: 'POST' }),
    history: () => request<HistoryEntry[]>('/api/pipeline/history'),
  },

  monitor: {
    progress: () => request<PipelineProgressData>('/api/monitor/progress'),
    metrics: (stage?: string) => request<HistoryEntry[] | Record<string, unknown>>(`/api/monitor/metrics/${stage || 'all'}`),
    gates: () => request<GateResult[]>('/api/monitor/gates'),
  },

  backtest: {
    equity: () => request<EquityPoint[]>('/api/backtest/equity'),
    trades: () => request<Trade[]>('/api/backtest/trades'),
    metrics: () => request<BacktestMetrics>('/api/backtest/metrics'),
    riskEvents: () => request<RiskEvent[]>('/api/backtest/risk-events'),
  },

  signals: {
    recent: (n = 50) => request<SignalRecord[]>(`/api/signals/recent?n=${n}`),
    stats: () => request<SignalStats>('/api/signals/stats'),
  },
}
