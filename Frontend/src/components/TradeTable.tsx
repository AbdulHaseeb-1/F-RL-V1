import type { Trade } from '../types'

interface TradeTableProps {
  trades: unknown
}

export default function TradeTable({ trades }: TradeTableProps) {
  const tradeList = normalizeTrades(trades)

  if (tradeList.length === 0) {
    return (
      <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Recent Trades</h2>
        <p className="text-sm text-gray-500">No trades yet</p>
      </div>
    )
  }

  const recent = tradeList.slice(-20).reverse()

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Recent Trades</h2>
        <span className="text-xs text-gray-500">{tradeList.length} total</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700/50 text-xs uppercase tracking-wider text-gray-500">
              <th className="py-2 pr-3 text-left">Time</th>
              <th className="py-2 pr-3 text-left">Dir</th>
              <th className="py-2 pr-3 text-right">Entry</th>
              <th className="py-2 pr-3 text-right">Exit</th>
              <th className="py-2 pr-3 text-right">PnL</th>
              <th className="py-2 pr-3 text-right">Size</th>
              <th className="py-2 text-left">Exit Reason</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((trade, index) => {
              const pnl = trade.net_pnl_pct || trade.pnl_pct || 0
              const isWin = pnl > 0

              return (
                <tr key={index} className="border-b border-gray-800/50 hover:bg-gray-700/20">
                  <td className="py-2 pr-3 font-mono text-xs text-gray-400">{formatTs(trade.entry_ts || trade.ts)}</td>
                  <td className="py-2 pr-3">
                    <span className={`font-medium ${trade.direction === 1 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {trade.direction === 1 ? 'LONG' : 'SHORT'}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-300">
                    {Number(trade.entry_price || trade.entry || 0).toFixed(0)}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-300">
                    {Number(trade.exit_price || trade.exit || 0).toFixed(0)}
                  </td>
                  <td className={`py-2 pr-3 text-right font-mono font-medium ${isWin ? 'text-emerald-400' : 'text-red-400'}`}>
                    {(pnl * 100).toFixed(2)}%
                  </td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-400">
                    {Number(trade.position_size || trade.size || 1).toFixed(2)}
                  </td>
                  <td className="py-2 text-xs text-gray-500">{trade.exit_reason || '--'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatTs(ts: Trade['entry_ts']) {
  if (!ts) {
    return '--'
  }

  try {
    return new Date(ts).toISOString().slice(5, 16).replace('T', ' ')
  } catch {
    return String(ts).slice(0, 16)
  }
}

function normalizeTrades(input: unknown): Trade[] {
  const rawTrades =
    Array.isArray(input) ? input
      : input && typeof input === 'object' && 'trades' in input ? input.trades
      : input && typeof input === 'object' && 'data' in input ? input.data
      : []

  if (!Array.isArray(rawTrades)) {
    return []
  }

  return rawTrades.filter((trade): trade is Trade => Boolean(trade) && typeof trade === 'object')
}
