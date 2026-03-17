import type { HistoryEntry } from '../types'

interface FoldMetricsProps {
  history: HistoryEntry[] | null
}

function toNumber(value: unknown) {
  return typeof value === 'number' ? value : 0
}

export default function FoldMetrics({ history }: FoldMetricsProps) {
  if (!history || history.length === 0) {
    return (
      <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">XGBoost Walk-Forward Folds</h2>
        <p className="text-sm text-gray-500">No fold data yet</p>
      </div>
    )
  }

  const folds = history.filter((entry) => entry.stage === 'xgb_fold' && entry.status === 'passed')

  if (folds.length === 0) {
    return null
  }

  const maxWinRate = Math.max(...folds.map((fold) => toNumber(fold.metrics?.win_rate)), 0.7)

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Walk-Forward Folds</h2>
        <span className="text-xs text-gray-500">{folds.length} folds</span>
      </div>

      <div className="mb-4 flex h-32 items-end gap-1">
        {folds.map((fold, index) => {
          const winRate = toNumber(fold.metrics?.win_rate)
          const height = (winRate / maxWinRate) * 100
          const color = winRate >= 0.55 ? 'bg-emerald-500' : winRate >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'

          return (
            <div key={index} className="flex flex-1 flex-col items-center gap-1">
              <span className="text-[9px] text-gray-500">{(winRate * 100).toFixed(0)}%</span>
              <div className={`w-full rounded-t ${color}/60`} style={{ height: `${height}%`, minHeight: '2px' }} />
              <span className="text-[9px] text-gray-600">{index}</span>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-3 gap-4 text-center text-xs">
        <div>
          <p className="text-gray-500">Avg Win Rate</p>
          <p className="font-mono text-white">
            {((folds.reduce((sum, fold) => sum + toNumber(fold.metrics?.win_rate), 0) / folds.length) * 100).toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-gray-500">Avg Trades/Fold</p>
          <p className="font-mono text-white">
            {(folds.reduce((sum, fold) => sum + toNumber(fold.metrics?.n_trades), 0) / folds.length).toFixed(0)}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Avg Profit Factor</p>
          <p className="font-mono text-white">
            {(folds.reduce((sum, fold) => sum + toNumber(fold.metrics?.profit_factor), 0) / folds.length).toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  )
}
