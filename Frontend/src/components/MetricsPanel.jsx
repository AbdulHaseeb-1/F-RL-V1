import MetricCard from './MetricCard'

export default function MetricsPanel({ metrics }) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return (
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Performance Metrics</h2>
        <p className="text-gray-500 text-sm">Waiting for backtest results...</p>
      </div>
    )
  }

  const m = metrics

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-white">Performance Metrics</h2>

      {/* Primary metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total Return" value={m.total_return * 100} suffix="%" trend={m.total_return > 0 ? 'up' : 'down'} />
        <MetricCard label="Sharpe Ratio" value={m.sharpe} trend={m.sharpe > 1.5 ? 'up' : m.sharpe > 0 ? '' : 'down'} />
        <MetricCard label="Max Drawdown" value={m.max_drawdown * 100} suffix="%" trend={m.max_drawdown < 0.1 ? 'up' : 'down'} />
        <MetricCard label="Win Rate" value={m.win_rate * 100} suffix="%" trend={m.win_rate > 0.5 ? 'up' : 'down'} />
      </div>

      {/* Secondary metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard label="Profit Factor" value={m.profit_factor} small trend={m.profit_factor > 1.3 ? 'up' : 'down'} />
        <MetricCard label="# Trades" value={m.n_trades} small />
        <MetricCard label="Sortino" value={m.sortino} small />
        <MetricCard label="Avg Win" value={(m.avg_win || 0) * 100} suffix="%" small />
        <MetricCard label="Avg Loss" value={(m.avg_loss || 0) * 100} suffix="%" small />
      </div>

      {/* Risk metrics */}
      {m.calmar_ratio !== undefined && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Calmar Ratio" value={m.calmar_ratio} small />
          <MetricCard label="Edge Ratio" value={m.edge_ratio} small trend={m.edge_ratio > 1 ? 'up' : 'down'} />
          <MetricCard label="Avg MFE" value={(m.avg_mfe || 0) * 100} suffix="%" small />
          <MetricCard label="Avg MAE" value={(m.avg_mae || 0) * 100} suffix="%" small />
        </div>
      )}

      {/* Cost breakdown */}
      {m.cost_drag_pct !== undefined && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Cost Drag" value={m.cost_drag_pct} suffix="%" small />
          <MetricCard label="Fees ($)" value={m.total_fees_usd} small />
          <MetricCard label="Slippage ($)" value={m.total_slippage_usd} small />
          <MetricCard label="Funding ($)" value={m.total_funding_usd} small />
        </div>
      )}

      {/* Direction breakdown */}
      {m.n_long !== undefined && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Long Trades" value={m.n_long} small />
          <MetricCard label="Short Trades" value={m.n_short} small />
          <MetricCard label="Long Win %" value={(m.long_win_rate || 0) * 100} suffix="%" small />
          <MetricCard label="Short Win %" value={(m.short_win_rate || 0) * 100} suffix="%" small />
        </div>
      )}
    </div>
  )
}
