import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import ControlDeck from './components/ControlDeck'
import EquityChart from './components/EquityChart'
import FoldMetrics from './components/FoldMetrics'
import GateResults from './components/GateResults'
import MetricsPanel from './components/MetricsPanel'
import PipelineProgress from './components/PipelineProgress'
import RiskEvents from './components/RiskEvents'
import SignalsPanel from './components/SignalsPanel'
import StatusBadge from './components/StatusBadge'
import TradeTable from './components/TradeTable'
import { usePolling } from './hooks/usePolling'
import type {
  BacktestMetrics,
  EquityPoint,
  GateResult,
  HistoryEntry,
  PipelineProgressData,
  PipelineRunStatus,
  RiskEvent,
  SignalRecord,
  SignalStats,
  Trade,
} from './types'

type TabId = 'overview' | 'training' | 'backtest' | 'trades' | 'risk' | 'signals'

interface OverviewTabProps {
  progress: PipelineProgressData | null
  metrics: BacktestMetrics | null
  equityData: EquityPoint[] | null
  gates: GateResult[] | null
}

interface TrainingTabProps {
  history: unknown
  progress: PipelineProgressData | null
}

interface BacktestTabProps {
  metrics: BacktestMetrics | null
  equityData: EquityPoint[] | null
}

interface TradesTabProps {
  trades: Trade[] | null
}

interface RiskTabProps {
  events: RiskEvent[] | null
  gates: GateResult[] | null
  metrics: BacktestMetrics | null
}

interface SignalsTabProps {
  signals: SignalRecord[] | null
  stats: SignalStats | null
  signalLimit: number
  onRefresh: () => void
}

interface QuickStatProps {
  label: string
  value: string | number
  positive?: boolean
}

const tabs: Array<{ id: TabId; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'training', label: 'Training' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'trades', label: 'Trades' },
  { id: 'risk', label: 'Risk' },
  { id: 'signals', label: 'Signals' },
]

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [backendStatus, setBackendStatus] = useState('checking')
  const [configText, setConfigText] = useState('{\n  "symbol": "BTCUSDT",\n  "timeframe": "1h"\n}')
  const [selectedStage, setSelectedStage] = useState('all')
  const [signalLimit, setSignalLimit] = useState(50)
  const [actionBusy, setActionBusy] = useState(false)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const healthFetch = useCallback(() => api.health(), [])
  const { data: health } = usePolling(healthFetch, 5000)

  useEffect(() => {
    if (health) {
      setBackendStatus(health.status || health.data?.status || 'ok')
    }
  }, [health])

  const pipelineStatusFetch = useCallback(() => api.pipeline.status(), [])
  const { data: pipelineRun, refetch: refetchPipelineRun } = usePolling(pipelineStatusFetch, 2000)

  const progressFetch = useCallback(() => api.monitor.progress(), [])
  const { data: progress, refetch: refetchProgress } = usePolling(progressFetch, 2000)

  const historyFetch = useCallback(() => api.pipeline.history(), [])
  const { data: history, refetch: refetchHistory } = usePolling(historyFetch, 3000)

  const metricsFetch = useCallback(() => api.backtest.metrics(), [])
  const { data: btMetrics, refetch: refetchBacktestMetrics } = usePolling(metricsFetch, 5000)

  const equityFetch = useCallback(() => api.backtest.equity(), [])
  const { data: equityData, refetch: refetchEquity } = usePolling(equityFetch, 5000)

  const tradesFetch = useCallback(() => api.backtest.trades(), [])
  const { data: tradesData, refetch: refetchTrades } = usePolling(tradesFetch, 5000)

  const riskFetch = useCallback(() => api.backtest.riskEvents(), [])
  const { data: riskData, refetch: refetchRisk } = usePolling(riskFetch, 5000)

  const gatesFetch = useCallback(() => api.monitor.gates(), [])
  const { data: gatesData, refetch: refetchGates } = usePolling(gatesFetch, 5000)

  const stageMetricsFetch = useCallback(() => api.monitor.metrics(selectedStage), [selectedStage])
  const { data: stageMetrics, refetch: refetchStageMetrics } = usePolling(stageMetricsFetch, 5000)

  const signalStatsFetch = useCallback(() => api.signals.stats(), [])
  const { data: signalStats, refetch: refetchSignalStats } = usePolling(signalStatsFetch, 5000)

  const signalsFetch = useCallback(() => api.signals.recent(signalLimit), [signalLimit])
  const { data: signalsData, refetch: refetchSignals } = usePolling(signalsFetch, 5000)

  const refreshAll = useCallback(async () => {
    setActionBusy(true)
    setActionError(null)

    try {
      await Promise.all([
        refetchPipelineRun(),
        refetchProgress(),
        refetchHistory(),
        refetchBacktestMetrics(),
        refetchEquity(),
        refetchTrades(),
        refetchRisk(),
        refetchGates(),
        refetchStageMetrics(),
        refetchSignalStats(),
        refetchSignals(),
      ])
      setActionMessage(`Telemetry refreshed at ${new Date().toLocaleTimeString()}`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to refresh dashboard')
    } finally {
      setActionBusy(false)
    }
  }, [
    refetchBacktestMetrics,
    refetchEquity,
    refetchGates,
    refetchHistory,
    refetchPipelineRun,
    refetchProgress,
    refetchRisk,
    refetchSignalStats,
    refetchSignals,
    refetchStageMetrics,
    refetchTrades,
  ])

  const handleStartPipeline = useCallback(async () => {
    let parsedConfig: Record<string, unknown> = {}

    try {
      parsedConfig = configText.trim() ? JSON.parse(configText) : {}
    } catch {
      setActionError('Launch config must be valid JSON')
      setActionMessage(null)
      return
    }

    setActionBusy(true)
    setActionError(null)

    try {
      const run = await api.pipeline.start(parsedConfig)
      await Promise.all([refetchPipelineRun(), refetchProgress(), refetchHistory()])
      const runName = (run as PipelineRunStatus | null)?.run_name || 'new run'
      setActionMessage(`Pipeline started: ${runName}`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to start pipeline')
      setActionMessage(null)
    } finally {
      setActionBusy(false)
    }
  }, [configText, refetchHistory, refetchPipelineRun, refetchProgress])

  const handleStopPipeline = useCallback(async () => {
    setActionBusy(true)
    setActionError(null)

    try {
      await api.pipeline.stop()
      await Promise.all([refetchPipelineRun(), refetchProgress(), refetchHistory()])
      setActionMessage('Pipeline stop requested')
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to stop pipeline')
      setActionMessage(null)
    } finally {
      setActionBusy(false)
    }
  }, [refetchHistory, refetchPipelineRun, refetchProgress])

  const handleRefreshStageMetrics = useCallback(async () => {
    setActionError(null)
    try {
      await refetchStageMetrics()
      setActionMessage(`Stage feed refreshed: ${selectedStage}`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to refresh stage metrics')
    }
  }, [refetchStageMetrics, selectedStage])

  const handleRefreshSignals = useCallback(async () => {
    setActionError(null)
    try {
      await Promise.all([refetchSignals(), refetchSignalStats()])
      setActionMessage(`Signal feed refreshed: last ${signalLimit}`)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to refresh signals')
    }
  }, [refetchSignalStats, refetchSignals, signalLimit])

  return (
    <div className="min-h-screen bg-[#0f1117]">
      <header className="sticky top-0 z-50 border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm">
        <div className="mx-auto h-16 max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-full items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-blue-500 text-sm font-bold text-white">
                BT
              </div>
              <div>
                <h1 className="text-lg font-semibold leading-tight text-white">BTC Hybrid Trader</h1>
                <p className="text-xs text-gray-500">XGBoost + RL Pipeline</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <StatusBadge status={backendStatus} />
              <div className="font-mono text-xs text-gray-500">{new Date().toLocaleTimeString()}</div>
            </div>
          </div>
        </div>
      </header>

      <nav className="border-b border-gray-800 bg-gray-900/30">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === tab.id ? 'text-white' : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {tab.label}
                {activeTab === tab.id && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-violet-500" />
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-6">
          <ControlDeck
            backendStatus={backendStatus}
            pipelineRun={pipelineRun}
            progress={progress}
            signalStats={signalStats}
            stageMetrics={stageMetrics}
            selectedStage={selectedStage}
            signalLimit={signalLimit}
            configText={configText}
            actionBusy={actionBusy}
            actionMessage={actionMessage}
            actionError={actionError}
            onConfigChange={setConfigText}
            onStageChange={setSelectedStage}
            onSignalLimitChange={setSignalLimit}
            onStart={handleStartPipeline}
            onStop={handleStopPipeline}
            onRefreshAll={refreshAll}
            onRefreshStageMetrics={handleRefreshStageMetrics}
            onRefreshSignals={handleRefreshSignals}
          />
        </div>

        {activeTab === 'overview' && (
          <OverviewTab
            progress={progress}
            metrics={btMetrics}
            equityData={equityData}
            gates={gatesData}
          />
        )}
        {activeTab === 'training' && <TrainingTab history={history} progress={progress} />}
        {activeTab === 'backtest' && <BacktestTab metrics={btMetrics} equityData={equityData} />}
        {activeTab === 'trades' && <TradesTab trades={tradesData} />}
        {activeTab === 'risk' && <RiskTab events={riskData} gates={gatesData} metrics={btMetrics} />}
        {activeTab === 'signals' && (
          <SignalsTab
            signals={signalsData}
            stats={signalStats}
            signalLimit={signalLimit}
            onRefresh={handleRefreshSignals}
          />
        )}
      </main>
    </div>
  )
}

function OverviewTab({ progress, metrics, equityData, gates }: OverviewTabProps) {
  return (
    <div className="space-y-6">
      <PipelineProgress progress={progress} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <EquityChart data={equityData} />
        <div className="space-y-4">
          {metrics && Object.keys(metrics).length > 0 ? (
            <div className="grid grid-cols-2 gap-3">
              <QuickStat
                label="Return"
                value={`${((metrics.total_return || 0) * 100).toFixed(1)}%`}
                positive={(metrics.total_return || 0) > 0}
              />
              <QuickStat
                label="Sharpe"
                value={(metrics.sharpe || 0).toFixed(2)}
                positive={(metrics.sharpe || 0) > 1}
              />
              <QuickStat
                label="Max DD"
                value={`${((metrics.max_drawdown || 0) * 100).toFixed(1)}%`}
                positive={(metrics.max_drawdown || 0) < 0.1}
              />
              <QuickStat
                label="Win Rate"
                value={`${((metrics.win_rate || 0) * 100).toFixed(1)}%`}
                positive={(metrics.win_rate || 0) > 0.5}
              />
              <QuickStat label="Trades" value={metrics.n_trades || 0} />
              <QuickStat
                label="Profit Factor"
                value={(metrics.profit_factor || 0).toFixed(2)}
                positive={(metrics.profit_factor || 0) > 1.3}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center rounded-xl border border-gray-700/50 bg-gray-800/50 p-12 text-gray-500">
              Awaiting pipeline results...
            </div>
          )}
          <GateResults gates={gates} />
        </div>
      </div>
    </div>
  )
}

function TrainingTab({ history, progress }: TrainingTabProps) {
  const historyList = normalizeHistory(history)

  return (
    <div className="space-y-6">
      <PipelineProgress progress={progress} />
      <FoldMetrics history={historyList} />

      <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Training Log</h2>
        <div className="max-h-96 space-y-1 overflow-y-auto font-mono text-xs">
          {historyList.slice(-50).reverse().map((entry, index) => (
            <div key={index} className="flex items-center gap-3 border-b border-gray-800/30 py-1">
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${
                  entry.status === 'passed'
                    ? 'bg-emerald-500'
                    : entry.status === 'failed'
                      ? 'bg-red-500'
                      : 'bg-gray-500'
                }`}
              />
              <span className="w-32 shrink-0 text-gray-500">{entry.timestamp?.slice(11, 19) || '--'}</span>
              <span className="w-20 shrink-0 text-gray-400">{entry.stage}</span>
              <span className="text-gray-500">fold={entry.fold}</span>
              <span className="ml-auto text-gray-300">
                {Object.entries(entry.metrics || {})
                  .slice(0, 3)
                  .map(([key, value]) => `${key}: ${typeof value === 'number' ? value.toFixed(3) : value}`)
                  .join(' | ')}
              </span>
              <span className="w-16 text-right text-gray-600">
                {entry.duration_sec?.toFixed(1)}
                s
              </span>
            </div>
          ))}
          {historyList.length === 0 && (
            <p className="py-4 text-center text-sm text-gray-500">No training events yet</p>
          )}
        </div>
      </div>
    </div>
  )
}

function BacktestTab({ metrics, equityData }: BacktestTabProps) {
  return (
    <div className="space-y-6">
      <EquityChart data={equityData} />
      <MetricsPanel metrics={metrics} />
    </div>
  )
}

function TradesTab({ trades }: TradesTabProps) {
  return (
    <div className="space-y-6">
      <TradeTable trades={trades} />
    </div>
  )
}

function RiskTab({ events, gates, metrics }: RiskTabProps) {
  return (
    <div className="space-y-6">
      <GateResults gates={gates} />
      <RiskEvents events={events} />
      {metrics && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <QuickStat label="Stop Losses" value={metrics.exits_stop_loss || 0} />
          <QuickStat label="Trailing Stops" value={metrics.exits_trailing_stop || 0} />
          <QuickStat label="Time Stops" value={metrics.exits_time_stop || 0} />
          <QuickStat label="Circuit Breakers" value={metrics.exits_max_drawdown_breaker || 0} />
        </div>
      )}
    </div>
  )
}

function SignalsTab({ signals, stats, signalLimit, onRefresh }: SignalsTabProps) {
  return (
    <SignalsPanel
      signals={signals}
      stats={stats}
      signalLimit={signalLimit}
      onRefresh={onRefresh}
    />
  )
}

function QuickStat({ label, value, positive }: QuickStatProps) {
  const color = positive === true ? 'text-emerald-400' : positive === false ? 'text-red-400' : 'text-white'

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-4">
      <p className="mb-1 text-xs uppercase tracking-wider text-gray-500">{label}</p>
      <p className={`text-xl font-semibold tabular-nums ${color}`}>{value}</p>
    </div>
  )
}

function normalizeHistory(input: unknown): HistoryEntry[] {
  const rawHistory =
    Array.isArray(input) ? input
      : input && typeof input === 'object' && 'history' in input ? input.history
      : input && typeof input === 'object' && 'events' in input ? input.events
      : input && typeof input === 'object' && 'data' in input ? input.data
      : []

  if (!Array.isArray(rawHistory)) {
    return []
  }

  return rawHistory.filter((entry): entry is HistoryEntry => Boolean(entry) && typeof entry === 'object')
}

export default App
