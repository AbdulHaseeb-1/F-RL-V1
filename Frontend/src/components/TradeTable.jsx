export default function TradeTable({ trades }) {
  if (!trades || trades.length === 0) {
    return (
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Recent Trades</h2>
        <p className="text-gray-500 text-sm">No trades yet</p>
      </div>
    )
  }

  const recent = trades.slice(-20).reverse()

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Recent Trades</h2>
        <span className="text-xs text-gray-500">{trades.length} total</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-700/50">
              <th className="text-left py-2 pr-3">Time</th>
              <th className="text-left py-2 pr-3">Dir</th>
              <th className="text-right py-2 pr-3">Entry</th>
              <th className="text-right py-2 pr-3">Exit</th>
              <th className="text-right py-2 pr-3">PnL</th>
              <th className="text-right py-2 pr-3">Size</th>
              <th className="text-left py-2">Exit Reason</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((t, i) => {
              const isWin = (t.net_pnl_pct || t.pnl_pct || 0) > 0
              return (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-700/20">
                  <td className="py-2 pr-3 text-gray-400 font-mono text-xs">
                    {formatTs(t.entry_ts || t.ts)}
                  </td>
                  <td className="py-2 pr-3">
                    <span className={`font-medium ${t.direction === 1 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {t.direction === 1 ? 'LONG' : 'SHORT'}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-300">
                    {Number(t.entry_price || t.entry || 0).toFixed(0)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-300">
                    {Number(t.exit_price || t.exit || 0).toFixed(0)}
                  </td>
                  <td className={`py-2 pr-3 text-right font-mono font-medium ${isWin ? 'text-emerald-400' : 'text-red-400'}`}>
                    {((t.net_pnl_pct || t.pnl_pct || 0) * 100).toFixed(2)}%
                  </td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-400">
                    {(t.position_size || t.size || 1).toFixed(2)}
                  </td>
                  <td className="py-2 text-xs text-gray-500">
                    {t.exit_reason || '--'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatTs(ts) {
  if (!ts) return '--'
  try {
    const d = new Date(ts)
    return d.toISOString().slice(5, 16).replace('T', ' ')
  } catch {
    return String(ts).slice(0, 16)
  }
}
