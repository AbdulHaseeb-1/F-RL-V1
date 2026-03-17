import type { BacktestMetrics } from '../types'
import MetricCard from './MetricCard'

interface MetricsPanelProps {
  metrics: BacktestMetrics | null
}

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return (
      <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Performance Metrics</h2>
        <p className="text-sm text-gray-500">Waiting for backtest results...</p>
      </div>
    )
  }

  const metricSet = metrics
  const sharpeTrend = metricSet.sharpe && metricSet.sharpe > 1.5 ? 'up' : metricSet.sharpe && metricSet.sharpe <= 0 ? 'down' : undefined

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-white">Performance Metrics</h2>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Total Return" value={(metricSet.total_return || 0) * 100} suffix="%" trend={(metricSet.total_return || 0) > 0 ? 'up' : 'down'} />
        <MetricCard label="Sharpe Ratio" value={metricSet.sharpe} trend={sharpeTrend} />
        <MetricCard label="Max Drawdown" value={(metricSet.max_drawdown || 0) * 100} suffix="%" trend={(metricSet.max_drawdown || 0) < 0.1 ? 'up' : 'down'} />
        <MetricCard label="Win Rate" value={(metricSet.win_rate || 0) * 100} suffix="%" trend={(metricSet.win_rate || 0) > 0.5 ? 'up' : 'down'} />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <MetricCard label="Profit Factor" value={metricSet.profit_factor} small trend={(metricSet.profit_factor || 0) > 1.3 ? 'up' : 'down'} />
        <MetricCard label="# Trades" value={metricSet.n_trades} small />
        <MetricCard label="Sortino" value={metricSet.sortino} small />
        <MetricCard label="Avg Win" value={(metricSet.avg_win || 0) * 100} suffix="%" small />
        <MetricCard label="Avg Loss" value={(metricSet.avg_loss || 0) * 100} suffix="%" small />
      </div>

      {metricSet.calmar_ratio !== undefined && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Calmar Ratio" value={metricSet.calmar_ratio} small />
          <MetricCard label="Edge Ratio" value={metricSet.edge_ratio} small trend={(metricSet.edge_ratio || 0) > 1 ? 'up' : 'down'} />
          <MetricCard label="Avg MFE" value={(metricSet.avg_mfe || 0) * 100} suffix="%" small />
          <MetricCard label="Avg MAE" value={(metricSet.avg_mae || 0) * 100} suffix="%" small />
        </div>
      )}

      {metricSet.cost_drag_pct !== undefined && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Cost Drag" value={metricSet.cost_drag_pct} suffix="%" small />
          <MetricCard label="Fees ($)" value={metricSet.total_fees_usd} small />
          <MetricCard label="Slippage ($)" value={metricSet.total_slippage_usd} small />
          <MetricCard label="Funding ($)" value={metricSet.total_funding_usd} small />
        </div>
      )}

      {metricSet.n_long !== undefined && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Long Trades" value={metricSet.n_long} small />
          <MetricCard label="Short Trades" value={metricSet.n_short} small />
          <MetricCard label="Long Win %" value={(metricSet.long_win_rate || 0) * 100} suffix="%" small />
          <MetricCard label="Short Win %" value={(metricSet.short_win_rate || 0) * 100} suffix="%" small />
        </div>
      )}
    </div>
  )
}
