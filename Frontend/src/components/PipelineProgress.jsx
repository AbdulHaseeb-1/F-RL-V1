import StatusBadge from './StatusBadge'

const STAGES = [
  { key: 'data_load', label: 'Data', icon: '1' },
  { key: 'features', label: 'Features', icon: '2' },
  { key: 'xgb_train', label: 'XGBoost', icon: '3' },
  { key: 'xgb_evaluate', label: 'Evaluate', icon: '4' },
  { key: 'rl_train', label: 'RL Train', icon: '5' },
  { key: 'backtest', label: 'Backtest', icon: '6' },
  { key: 'report', label: 'Report', icon: '7' },
]

export default function PipelineProgress({ progress }) {
  const stages = progress?.stages || {}
  const current = progress?.current_stage

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Pipeline Progress</h2>
        {progress?.run_name && (
          <span className="text-xs text-gray-500 font-mono">{progress.run_name}</span>
        )}
      </div>

      <div className="flex items-center gap-1 mb-6">
        {STAGES.map((stage, i) => {
          const info = stages[stage.key]
          const isCurrent = current === stage.key
          const status = isCurrent ? 'running' : (info?.status || 'pending')

          let bgClass = 'bg-gray-700/50'
          if (status === 'passed') bgClass = 'bg-emerald-500/20'
          else if (status === 'running') bgClass = 'bg-blue-500/30'
          else if (status === 'failed') bgClass = 'bg-red-500/20'

          return (
            <div key={stage.key} className="flex items-center flex-1">
              <div className={`flex flex-col items-center flex-1 py-2 px-1 rounded-lg ${bgClass} transition-colors duration-300`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold mb-1
                  ${status === 'passed' ? 'bg-emerald-500 text-white' :
                    status === 'running' ? 'bg-blue-500 text-white animate-pulse' :
                    status === 'failed' ? 'bg-red-500 text-white' :
                    'bg-gray-600 text-gray-400'}`}>
                  {status === 'passed' ? '\u2713' : stage.icon}
                </div>
                <span className="text-[10px] text-gray-400 text-center leading-tight">{stage.label}</span>
              </div>
              {i < STAGES.length - 1 && (
                <div className={`w-4 h-0.5 ${info?.status === 'passed' ? 'bg-emerald-500/50' : 'bg-gray-700'}`} />
              )}
            </div>
          )
        })}
      </div>

      {progress?.total_duration_sec > 0 && (
        <div className="flex justify-between text-xs text-gray-500">
          <span>Total entries: {progress.total_entries}</span>
          <span>Duration: {formatDuration(progress.total_duration_sec)}</span>
        </div>
      )}
    </div>
  )
}

function formatDuration(sec) {
  if (sec < 60) return `${sec.toFixed(0)}s`
  if (sec < 3600) return `${(sec / 60).toFixed(1)}m`
  return `${(sec / 3600).toFixed(1)}h`
}
