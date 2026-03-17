export default function RiskEvents({ events }) {
  if (!events || events.length === 0) return null

  const eventColors = {
    stop_loss: 'text-red-400',
    trailing_stop: 'text-yellow-400',
    time_stop: 'text-blue-400',
    circuit_breaker: 'text-red-500 font-bold',
  }

  const recent = events.slice(-15).reverse()

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Risk Events</h2>
        <span className="text-xs text-gray-500">{events.length} total</span>
      </div>
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {recent.map((e, i) => (
          <div key={i} className="flex items-center gap-3 text-sm py-1 border-b border-gray-800/30">
            <span className="text-xs text-gray-500 font-mono w-24 shrink-0">
              {formatTs(e.ts)}
            </span>
            <span className={`${eventColors[e.event] || 'text-gray-400'}`}>
              {e.event?.replace(/_/g, ' ').toUpperCase()}
            </span>
            {e.dd && <span className="text-xs text-gray-500 ml-auto">DD: {(e.dd * 100).toFixed(1)}%</span>}
            {e.pnl && <span className="text-xs text-gray-500 ml-auto">PnL: {(e.pnl * 100).toFixed(2)}%</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

function formatTs(ts) {
  if (!ts) return '--'
  try { return new Date(ts).toISOString().slice(5, 16).replace('T', ' ') }
  catch { return String(ts).slice(0, 16) }
}
