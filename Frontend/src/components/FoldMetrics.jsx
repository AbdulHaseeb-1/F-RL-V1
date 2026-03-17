export default function FoldMetrics({ history }) {
  if (!history || history.length === 0) {
    return (
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">XGBoost Walk-Forward Folds</h2>
        <p className="text-gray-500 text-sm">No fold data yet</p>
      </div>
    )
  }

  const folds = history.filter(h => h.stage === 'xgb_fold' && h.status === 'passed')
  if (folds.length === 0) return null

  // Mini bar chart of win rates per fold
  const maxWR = Math.max(...folds.map(f => f.metrics?.win_rate || 0), 0.7)

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Walk-Forward Folds</h2>
        <span className="text-xs text-gray-500">{folds.length} folds</span>
      </div>

      {/* Win rate bar chart */}
      <div className="flex items-end gap-1 h-32 mb-4">
        {folds.map((f, i) => {
          const wr = f.metrics?.win_rate || 0
          const height = (wr / maxWR) * 100
          const color = wr >= 0.55 ? 'bg-emerald-500' : wr >= 0.50 ? 'bg-yellow-500' : 'bg-red-500'
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <span className="text-[9px] text-gray-500">{(wr * 100).toFixed(0)}%</span>
              <div
                className={`w-full rounded-t ${color}/60`}
                style={{ height: `${height}%`, minHeight: '2px' }}
              />
              <span className="text-[9px] text-gray-600">{i}</span>
            </div>
          )
        })}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4 text-center text-xs">
        <div>
          <p className="text-gray-500">Avg Win Rate</p>
          <p className="text-white font-mono">
            {(folds.reduce((s, f) => s + (f.metrics?.win_rate || 0), 0) / folds.length * 100).toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-gray-500">Avg Trades/Fold</p>
          <p className="text-white font-mono">
            {(folds.reduce((s, f) => s + (f.metrics?.n_trades || 0), 0) / folds.length).toFixed(0)}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Avg Profit Factor</p>
          <p className="text-white font-mono">
            {(folds.reduce((s, f) => s + (f.metrics?.profit_factor || 0), 0) / folds.length).toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  )
}
