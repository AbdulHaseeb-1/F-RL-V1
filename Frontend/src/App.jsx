import { useState, useEffect, useCallback } from 'react'
import { api } from './api'
import { usePolling } from './hooks/usePolling'
import StatusBadge from './components/StatusBadge'
import PipelineProgress from './components/PipelineProgress'
import MetricsPanel from './components/MetricsPanel'
import EquityChart from './components/EquityChart'
import TradeTable from './components/TradeTable'
import FoldMetrics from './components/FoldMetrics'
import RiskEvents from './components/RiskEvents'
import GateResults from './components/GateResults'

function App() {
  const [activeTab, setActiveTab] = useState('overview')
  const [backendStatus, setBackendStatus] = useState('checking')
  const [time, setTime] = useState(() => new Date().toLocaleTimeString())

  // Live clock
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Poll backend health
  const healthFetch = useCallback(() => api.health(), [])
  const { data: health } = usePolling(healthFetch, 5000)
  useEffect(() => {
    if (health) setBackendStatus(health.status || 'ok')
  }, [health])

  // Poll pipeline status (for start/stop controls)
  const statusFetch = useCallback(() => api.pipeline.status(), [])
  const { data: pipelineStatus, refetch: refetchStatus } = usePolling(statusFetch, 2000)
  const isRunning = pipelineStatus?.status === 'running'

  // Poll monitor progress (PipelineProgress component format)
  const progressFetch = useCallback(() => api.monitor.progress(), [])
  const { data: monitorProgress } = usePolling(progressFetch, 2000)

  // Poll training history: Python monitor entries [{stage, fold, metrics, …}]
  const historyFetch = useCallback(() => api.monitor.metrics('all'), [])
  const { data: history } = usePolling(historyFetch, 3000)

  // Poll backtest results
  const metricsFetch = useCallback(() => api.backtest.metrics(), [])
  const { data: btMetrics } = usePolling(metricsFetch, 5000)

  const equityFetch = useCallback(() => api.backtest.equity(), [])
  const { data: equityData } = usePolling(equityFetch, 5000)

  const tradesFetch = useCallback(() => api.backtest.trades(), [])
  const { data: tradesData } = usePolling(tradesFetch, 5000)

  const riskFetch = useCallback(() => api.backtest.riskEvents(), [])
  const { data: riskData } = usePolling(riskFetch, 5000)

  const gatesFetch = useCallback(() => api.monitor.gates(), [])
  const { data: gatesData } = usePolling(gatesFetch, 5000)

  // Pipeline controls
  const handleStart = async () => {
    try { await api.pipeline.start() } catch (err) { console.error('Start failed:', err) }
    refetchStatus()
  }
  const handleStop = async () => {
    try { await api.pipeline.stop() } catch (err) { console.error('Stop failed:', err) }
    refetchStatus()
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'training', label: 'Training' },
    { id: 'backtest', label: 'Backtest' },
    { id: 'trades', label: 'Trades' },
    { id: 'risk', label: 'Risk' },
  ]

  return (
    <div className="min-h-screen bg-[#0f1117]">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center text-white font-bold text-sm">
                BT
              </div>
              <div>
                <h1 className="text-white font-semibold text-lg leading-tight">BTC Hybrid Trader</h1>
                <p className="text-gray-500 text-xs">XGBoost + RL Pipeline</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge status={backendStatus} />
              {/* Pipeline start / stop */}
              {isRunning ? (
                <button
                  onClick={handleStop}
                  className="px-3 py-1.5 text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/30 transition-colors"
                >
                  Stop Pipeline
                </button>
              ) : (
                <button
                  onClick={handleStart}
                  className="px-3 py-1.5 text-xs font-medium bg-violet-500/20 text-violet-400 border border-violet-500/30 rounded-lg hover:bg-violet-500/30 transition-colors"
                >
                  Start Pipeline
                </button>
              )}
              <div className="text-xs text-gray-500 font-mono">{time}</div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-900/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex gap-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 text-sm font-medium transition-colors relative
                  ${activeTab === tab.id
                    ? 'text-white'
                    : 'text-gray-500 hover:text-gray-300'}`}
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

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'overview' && (
          <OverviewTab
            progress={monitorProgress}
            pipelineStatus={pipelineStatus}
            metrics={btMetrics}
            equityData={equityData}
            gates={gatesData}
            isRunning={isRunning}
            onStart={handleStart}
            onStop={handleStop}
          />
        )}
        {activeTab === 'training' && (
          <TrainingTab history={history} progress={monitorProgress} />
        )}
        {activeTab === 'backtest' && (
          <BacktestTab metrics={btMetrics} equityData={equityData} />
        )}
        {activeTab === 'trades' && (
          <TradesTab trades={tradesData} />
        )}
        {activeTab === 'risk' && (
          <RiskTab events={riskData} gates={gatesData} metrics={btMetrics} />
        )}
      </main>
    </div>
  )
}

function OverviewTab({ progress, pipelineStatus, metrics, equityData, gates, isRunning, onStart, onStop }) {
  return (
    <div className="space-y-6">
      {/* Pipeline status bar */}
      <div className="flex items-center justify-between bg-gray-800/50 border border-gray-700/50 rounded-xl px-5 py-3">
        <div className="flex items-center gap-3">
          <StatusBadge status={pipelineStatus?.status || 'idle'} />
          <span className="text-sm text-gray-400">
            {pipelineStatus?.stage ? `Stage: ${pipelineStatus.stage}` : 'No active run'}
          </span>
          {pipelineStatus?.run_name && (
            <span className="text-xs text-gray-600 font-mono">{pipelineStatus.run_name}</span>
          )}
        </div>
        {isRunning ? (
          <button
            onClick={onStop}
            className="px-3 py-1.5 text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/30 transition-colors"
          >
            Stop Pipeline
          </button>
        ) : (
          <button
            onClick={onStart}
            className="px-3 py-1.5 text-xs font-medium bg-violet-500/20 text-violet-400 border border-violet-500/30 rounded-lg hover:bg-violet-500/30 transition-colors"
          >
            Start Pipeline
          </button>
        )}
      </div>

      <PipelineProgress progress={progress} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EquityChart data={equityData} />
        <div className="space-y-4">
          {metrics && Object.keys(metrics).length > 0 ? (
            <div className="grid grid-cols-2 gap-3">
              <QuickStat label="Return" value={`${((metrics.total_return || 0) * 100).toFixed(1)}%`} positive={(metrics.total_return || 0) > 0} />
              <QuickStat label="Sharpe" value={(metrics.sharpe || 0).toFixed(2)} positive={(metrics.sharpe || 0) > 1} />
              <QuickStat label="Max DD" value={`${((metrics.max_drawdown || 0) * 100).toFixed(1)}%`} positive={(metrics.max_drawdown || 0) < 0.1} />
              <QuickStat label="Win Rate" value={`${((metrics.win_rate || 0) * 100).toFixed(1)}%`} positive={(metrics.win_rate || 0) > 0.5} />
              <QuickStat label="Trades" value={metrics.n_trades || 0} />
              <QuickStat label="Profit Factor" value={(metrics.profit_factor || 0).toFixed(2)} positive={(metrics.profit_factor || 0) > 1.3} />
            </div>
          ) : (
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-12 flex items-center justify-center text-gray-500">
              Awaiting pipeline results...
            </div>
          )}
          <GateResults gates={gates} />
        </div>
      </div>
    </div>
  )
}

function TrainingTab({ history, progress }) {
  return (
    <div className="space-y-6">
      <PipelineProgress progress={progress} />
      <FoldMetrics history={history} />

      {/* Training log */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Training Log</h2>
        <div className="space-y-1 max-h-96 overflow-y-auto font-mono text-xs">
          {(history || []).slice(-50).reverse().map((entry, i) => (
            <div key={i} className="flex items-center gap-3 py-1 border-b border-gray-800/30">
              <span className={`w-2 h-2 rounded-full shrink-0
                ${entry.status === 'passed' ? 'bg-emerald-500' :
                  entry.status === 'failed' ? 'bg-red-500' : 'bg-gray-500'}`} />
              <span className="text-gray-500 w-32 shrink-0">{entry.timestamp?.slice(11, 19) || '--'}</span>
              <span className="text-gray-400 w-20 shrink-0">{entry.stage}</span>
              <span className="text-gray-500">fold={entry.fold}</span>
              <span className="text-gray-300 ml-auto">
                {Object.entries(entry.metrics || {}).slice(0, 3).map(([k, v]) =>
                  `${k}: ${typeof v === 'number' ? v.toFixed(3) : v}`
                ).join(' | ')}
              </span>
              <span className="text-gray-600 w-16 text-right">{entry.duration_sec?.toFixed(1)}s</span>
            </div>
          ))}
          {(!history || history.length === 0) && (
            <p className="text-gray-500 py-4 text-center text-sm">No training events yet</p>
          )}
        </div>
      </div>
    </div>
  )
}

function BacktestTab({ metrics, equityData }) {
  return (
    <div className="space-y-6">
      <EquityChart data={equityData} />
      <MetricsPanel metrics={metrics} />
    </div>
  )
}

function TradesTab({ trades }) {
  return (
    <div className="space-y-6">
      <TradeTable trades={trades} />
    </div>
  )
}

function RiskTab({ events, gates, metrics }) {
  return (
    <div className="space-y-6">
      <GateResults gates={gates} />
      <RiskEvents events={events} />
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <QuickStat label="Stop Losses" value={metrics.exits_stop_loss || 0} />
          <QuickStat label="Trailing Stops" value={metrics.exits_trailing_stop || 0} />
          <QuickStat label="Time Stops" value={metrics.exits_time_stop || 0} />
          <QuickStat label="Circuit Breakers" value={metrics.exits_max_drawdown_breaker || 0} />
        </div>
      )}
    </div>
  )
}

function QuickStat({ label, value, positive }) {
  const color = positive === true ? 'text-emerald-400'
    : positive === false ? 'text-red-400'
    : 'text-white'

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-xl font-semibold ${color} tabular-nums`}>{value}</p>
    </div>
  )
}

export default App
