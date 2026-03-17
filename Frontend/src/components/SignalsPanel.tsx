import type { SignalRecord, SignalStats } from '../types'

interface SignalsPanelProps {
  signals: unknown
  stats: SignalStats | null
  signalLimit: number
  onRefresh: () => void
}

export default function SignalsPanel({ signals, stats, signalLimit, onRefresh }: SignalsPanelProps) {
  const signalList = normalizeSignals(signals)

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-gray-700/50 bg-gray-800/50 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Signal Stream</h2>
            <p className="mt-1 text-sm text-gray-400">Recent model outputs from the active or latest run.</p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20"
          >
            Refresh Signals
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <SignalStat label="Window" value={String(signalLimit)} />
          <SignalStat label="Total" value={String(stats?.total || 0)} />
          <SignalStat label="Long" value={String(stats?.long || 0)} accent="text-emerald-300" />
          <SignalStat label="Short" value={String(stats?.short || 0)} accent="text-red-300" />
        </div>
      </div>

      <div className="rounded-2xl border border-gray-700/50 bg-gray-800/50 p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold text-white">Recent Signals</h3>
          <span className="text-xs text-gray-500">{signalList.length} rows</span>
        </div>

        {signalList.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-700/70 px-4 py-10 text-center text-sm text-gray-500">
            No signals available yet
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700/50 text-xs uppercase tracking-wider text-gray-500">
                  <th className="py-2 pr-3 text-left">Time</th>
                  <th className="py-2 pr-3 text-left">Signal</th>
                  <th className="py-2 pr-3 text-right">Price</th>
                  <th className="py-2 pr-3 text-right">Confidence</th>
                  <th className="py-2 text-left">Raw</th>
                </tr>
              </thead>
              <tbody>
                {signalList.slice().reverse().map((signal, index) => (
                  <tr key={index} className="border-b border-gray-800/50 hover:bg-gray-700/20">
                    <td className="py-2 pr-3 font-mono text-xs text-gray-400">{formatTs(signal.timestamp || signal.ts)}</td>
                    <td className="py-2 pr-3">
                      <span className={signalClass(signal.signal)}>
                        {formatSignal(signal.signal)}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right font-mono text-gray-300">
                      {formatNumber(signal.price ?? signal.close)}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono text-gray-300">
                      {formatPercent(signal.confidence ?? signal.probability)}
                    </td>
                    <td className="max-w-64 truncate py-2 text-xs text-gray-500">
                      {JSON.stringify(signal)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function normalizeSignals(input: unknown): SignalRecord[] {
  const rawSignals =
    Array.isArray(input) ? input
      : input && typeof input === 'object' && 'signals' in input ? input.signals
      : input && typeof input === 'object' && 'data' in input ? input.data
      : []

  if (!Array.isArray(rawSignals)) {
    return []
  }

  return rawSignals.filter((signal): signal is SignalRecord => Boolean(signal) && typeof signal === 'object')
}

function formatTs(value: SignalRecord['timestamp']) {
  if (!value) {
    return '--'
  }

  try {
    return new Date(value).toISOString().slice(5, 16).replace('T', ' ')
  } catch {
    return String(value).slice(0, 16)
  }
}

function formatSignal(signal: SignalRecord['signal']) {
  if (signal === 1 || signal === '1' || signal === 'long' || signal === 'Long') {
    return 'LONG'
  }

  if (signal === -1 || signal === '-1' || signal === 'short' || signal === 'Short') {
    return 'SHORT'
  }

  return String(signal ?? 'SKIP').toUpperCase()
}

function signalClass(signal: SignalRecord['signal']) {
  const text = formatSignal(signal)

  if (text === 'LONG') {
    return 'font-medium text-emerald-300'
  }

  if (text === 'SHORT') {
    return 'font-medium text-red-300'
  }

  return 'font-medium text-gray-300'
}

function formatNumber(value: unknown) {
  return typeof value === 'number' ? value.toFixed(2) : '--'
}

function formatPercent(value: unknown) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '--'
}

function SignalStat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-gray-800/80 bg-gray-900/50 px-4 py-3">
      <p className="text-[10px] uppercase tracking-[0.25em] text-gray-500">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${accent || 'text-white'}`}>{value}</p>
    </div>
  )
}
