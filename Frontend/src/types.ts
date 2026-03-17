export interface HealthResponse {
  status?: string
  data?: {
    status?: string
    [key: string]: unknown
  }
  [key: string]: unknown
}

export interface PipelineStageInfo {
  status?: string
  [key: string]: unknown
}

export interface PipelineProgressData {
  stages?: Record<string, PipelineStageInfo>
  current_stage?: string
  run_name?: string
  total_duration_sec?: number
  total_entries?: number
  [key: string]: unknown
}

export interface PipelineRunStatus {
  id?: string
  status?: string
  stage?: string
  started_at?: string
  ended_at?: string
  run_name?: string
  config?: Record<string, unknown>
  error?: string
  [key: string]: unknown
}

export interface EquityPoint {
  value: number
  [key: string]: unknown
}

export interface GateResult {
  passed?: boolean
  stage?: string
  metric?: string
  value?: number
  direction?: string
  threshold?: number | string
  [key: string]: unknown
}

export interface HistoryEntry {
  stage?: string
  status?: string
  timestamp?: string
  fold?: number | string
  metrics?: Record<string, number | string | null | undefined>
  duration_sec?: number
  [key: string]: unknown
}

export interface BacktestMetrics {
  total_return?: number
  sharpe?: number
  max_drawdown?: number
  win_rate?: number
  n_trades?: number
  profit_factor?: number
  sortino?: number
  avg_win?: number
  avg_loss?: number
  calmar_ratio?: number
  edge_ratio?: number
  avg_mfe?: number
  avg_mae?: number
  cost_drag_pct?: number
  total_fees_usd?: number
  total_slippage_usd?: number
  total_funding_usd?: number
  n_long?: number
  n_short?: number
  long_win_rate?: number
  short_win_rate?: number
  exits_stop_loss?: number
  exits_trailing_stop?: number
  exits_time_stop?: number
  exits_max_drawdown_breaker?: number
  [key: string]: number | string | boolean | null | undefined
}

export interface Trade {
  entry_ts?: string | number | Date
  ts?: string | number | Date
  direction?: number
  entry_price?: number
  entry?: number
  exit_price?: number
  exit?: number
  net_pnl_pct?: number
  pnl_pct?: number
  position_size?: number
  size?: number
  exit_reason?: string
  [key: string]: unknown
}

export interface RiskEvent {
  ts?: string | number | Date
  event?: string
  dd?: number
  pnl?: number
  [key: string]: unknown
}

export interface SignalStats {
  total?: number
  long?: number
  short?: number
  skip?: number
  [key: string]: unknown
}

export interface SignalRecord {
  ts?: string | number | Date
  timestamp?: string | number | Date
  signal?: number | string
  price?: number
  close?: number
  probability?: number
  confidence?: number
  [key: string]: unknown
}
