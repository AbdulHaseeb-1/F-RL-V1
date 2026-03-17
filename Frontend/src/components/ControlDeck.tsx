import type {
  HistoryEntry,
  PipelineProgressData,
  PipelineRunStatus,
  SignalStats,
} from '../types'
import StatusBadge from './StatusBadge'

interface ControlDeckProps {
  backendStatus: string
  pipelineRun: PipelineRunStatus | null
  progress: PipelineProgressData | null
  signalStats: SignalStats | null
  stageMetrics: unknown
  selectedStage: string
  signalLimit: number
  configText: string
  actionBusy: boolean
  actionMessage: string | null
  actionError: string | null
  onConfigChange: (value: string) => void
  onStageChange: (value: string) => void
  onSignalLimitChange: (value: number) => void
  onStart: () => void
  onStop: () => void
  onRefreshAll: () => void
  onRefreshStageMetrics: () => void
  onRefreshSignals: () => void
}

const stageOptions = [
  { value: 'all', label: 'All Stages' },
  { value: 'data_load', label: 'Data Load' },
  { value: 'features', label: 'Features' },
  { value: 'xgb_fold', label: 'XGB Fold' },
  { value: 'xgb_train', label: 'XGB Train' },
  { value: 'xgb_evaluate', label: 'XGB Evaluate' },
  { value: 'rl_train', label: 'RL Train' },
  { value: 'backtest', label: 'Backtest' },
  { value: 'report', label: 'Report' },
] as const

const signalLimitOptions = [25, 50, 100, 200] as const

export default function ControlDeck({
  backendStatus,
  pipelineRun,
  progress,
  signalStats,
  stageMetrics,
  selectedStage,
  signalLimit,
  configText,
  actionBusy,
  actionMessage,
  actionError,
  onConfigChange,
  onStageChange,
  onSignalLimitChange,
  onStart,
  onStop,
  onRefreshAll,
  onRefreshStageMetrics,
  onRefreshSignals,
}: ControlDeckProps) {
  const metricEntries = normalizeMetricEntries(stageMetrics)
  const pipelineStatus = pipelineRun?.status || 'idle'
  const runName = pipelineRun?.run_name || progress?.run_name || 'No active run'
  const currentStage = pipelineRun?.stage || progress?.current_stage || '--'
  const isRunning = pipelineStatus === 'running'

  return (
    <section className="relative overflow-hidden rounded-3xl border border-gray-700/60 bg-[radial-gradient(circle_at_top_left,_rgba(124,58,237,0.18),_transparent_35%),radial-gradient(circle_at_top_right,_rgba(16,185,129,0.12),_transparent_28%),rgba(17,24,39,0.78)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
      <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.03),transparent_45%,rgba(255,255,255,0.02))]" />
      <div className="relative space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-[11px] uppercase tracking-[0.35em] text-cyan-300/70">Operations Deck</p>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-2xl font-semibold text-white">Pipeline Control Surface</h2>
              <StatusBadge status={pipelineStatus} />
              <StatusBadge status={backendStatus} />
            </div>
            <p className="max-w-2xl text-sm text-gray-400">
              Launch, stop, refresh, inspect stages, and query signals without leaving the dashboard.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatChip label="Run" value={runName} mono />
            <StatChip label="Stage" value={currentStage} mono />
            <StatChip label="Entries" value={String(progress?.total_entries || 0)} />
            <StatChip label="Signals" value={String(signalStats?.total || 0)} />
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
          <div className="space-y-4 rounded-2xl border border-white/10 bg-black/20 p-5 backdrop-blur-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-[0.28em] text-gray-300">Pipeline Commands</h3>
                <p className="mt-1 text-sm text-gray-400">Start with optional JSON config, stop the active run, or force-refresh all views.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={onStart}
                  disabled={actionBusy || isRunning}
                  className="rounded-full border border-emerald-400/30 bg-emerald-500/15 px-4 py-2 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Start Pipeline
                </button>
                <button
                  type="button"
                  onClick={onStop}
                  disabled={actionBusy || !isRunning}
                  className="rounded-full border border-red-400/30 bg-red-500/15 px-4 py-2 text-sm font-medium text-red-300 transition hover:bg-red-500/25 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Stop Pipeline
                </button>
                <button
                  type="button"
                  onClick={onRefreshAll}
                  disabled={actionBusy}
                  className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Refresh All
                </button>
              </div>
            </div>

            <label className="block">
              <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-gray-500">Launch Config JSON</span>
              <textarea
                value={configText}
                onChange={(event) => onConfigChange(event.target.value)}
                spellCheck={false}
                className="min-h-40 w-full rounded-2xl border border-gray-700/70 bg-gray-950/70 px-4 py-3 font-mono text-sm text-gray-200 outline-none transition focus:border-cyan-400/60 focus:ring-2 focus:ring-cyan-500/20"
                placeholder={`{\n  "symbol": "BTCUSDT",\n  "timeframe": "1h"\n}`}
              />
            </label>

            {(actionMessage || actionError) && (
              <div className={`rounded-2xl border px-4 py-3 text-sm ${
                actionError
                  ? 'border-red-500/30 bg-red-500/10 text-red-200'
                  : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
              }`}>
                {actionError || actionMessage}
              </div>
            )}
          </div>

          <div className="grid gap-4">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-5 backdrop-blur-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-[0.28em] text-gray-300">Stage Inspector</h3>
                  <p className="mt-1 text-sm text-gray-400">Query the monitor feed by pipeline stage.</p>
                </div>
                <button
                  type="button"
                  onClick={onRefreshStageMetrics}
                  className="rounded-full border border-gray-600/70 px-3 py-1.5 text-xs font-medium text-gray-200 transition hover:border-cyan-400/50 hover:text-cyan-200"
                >
                  Refresh Stage
                </button>
              </div>

              <select
                value={selectedStage}
                onChange={(event) => onStageChange(event.target.value)}
                className="w-full rounded-xl border border-gray-700/70 bg-gray-950/70 px-4 py-3 text-sm text-gray-200 outline-none transition focus:border-cyan-400/60"
              >
                {stageOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              <div className="mt-4 space-y-2">
                {metricEntries.slice(-4).reverse().map((entry, index) => (
                  <div key={index} className="rounded-xl border border-gray-800/70 bg-gray-900/50 px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm text-white">{entry.stage || selectedStage}</span>
                      <span className="text-xs text-gray-500">{entry.timestamp?.slice(11, 19) || '--'}</span>
                    </div>
                    <div className="mt-1 text-xs text-gray-400">
                      {(entry.status || 'unknown').toString()} {entry.fold !== undefined ? `· fold ${entry.fold}` : ''}
                    </div>
                  </div>
                ))}
                {metricEntries.length === 0 && (
                  <div className="rounded-xl border border-dashed border-gray-700/70 px-3 py-4 text-center text-sm text-gray-500">
                    No stage entries yet
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-5 backdrop-blur-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-[0.28em] text-gray-300">Signals Explorer</h3>
                  <p className="mt-1 text-sm text-gray-400">Adjust the recent signal window and refresh the feed on demand.</p>
                </div>
                <button
                  type="button"
                  onClick={onRefreshSignals}
                  className="rounded-full border border-gray-600/70 px-3 py-1.5 text-xs font-medium text-gray-200 transition hover:border-cyan-400/50 hover:text-cyan-200"
                >
                  Refresh Signals
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                {signalLimitOptions.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => onSignalLimitChange(option)}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                      signalLimit === option
                        ? 'border border-cyan-400/40 bg-cyan-500/15 text-cyan-200'
                        : 'border border-gray-700 bg-gray-900/50 text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    Last {option}
                  </button>
                ))}
              </div>

              <div className="mt-4 grid grid-cols-4 gap-2">
                <MiniStat label="Total" value={String(signalStats?.total || 0)} />
                <MiniStat label="Long" value={String(signalStats?.long || 0)} accent="text-emerald-300" />
                <MiniStat label="Short" value={String(signalStats?.short || 0)} accent="text-red-300" />
                <MiniStat label="Skip" value={String(signalStats?.skip || 0)} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function normalizeMetricEntries(input: unknown): HistoryEntry[] {
  if (Array.isArray(input)) {
    return input.filter((entry): entry is HistoryEntry => Boolean(entry) && typeof entry === 'object')
  }

  if (input && typeof input === 'object' && 'data' in input && Array.isArray(input.data)) {
    return input.data.filter((entry): entry is HistoryEntry => Boolean(entry) && typeof entry === 'object')
  }

  return []
}

function StatChip({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.25em] text-gray-500">{label}</p>
      <p className={`mt-1 truncate text-sm text-white ${mono ? 'font-mono' : ''}`}>{value}</p>
    </div>
  )
}

function MiniStat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-gray-800/80 bg-gray-900/50 px-3 py-2 text-center">
      <p className="text-[10px] uppercase tracking-[0.2em] text-gray-500">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${accent || 'text-white'}`}>{value}</p>
    </div>
  )
}
