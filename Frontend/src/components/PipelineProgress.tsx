import type { PipelineProgressData } from '../types'

interface PipelineProgressProps {
  progress: PipelineProgressData | null
}

const STAGES = [
  { key: 'data_load', label: 'Data', icon: '1' },
  { key: 'features', label: 'Features', icon: '2' },
  { key: 'xgb_train', label: 'XGBoost', icon: '3' },
  { key: 'xgb_evaluate', label: 'Evaluate', icon: '4' },
  { key: 'rl_train', label: 'RL Train', icon: '5' },
  { key: 'backtest', label: 'Backtest', icon: '6' },
  { key: 'report', label: 'Report', icon: '7' },
] as const

export default function PipelineProgress({ progress }: PipelineProgressProps) {
  const stages = progress?.stages || {}
  const current = progress?.current_stage

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Pipeline Progress</h2>
        {progress?.run_name && <span className="font-mono text-xs text-gray-500">{progress.run_name}</span>}
      </div>

      <div className="mb-6 flex items-center gap-1">
        {STAGES.map((stage, index) => {
          const info = stages[stage.key]
          const isCurrent = current === stage.key
          const status = isCurrent ? 'running' : (info?.status || 'pending')

          let backgroundClass = 'bg-gray-700/50'
          if (status === 'passed') {
            backgroundClass = 'bg-emerald-500/20'
          } else if (status === 'running') {
            backgroundClass = 'bg-blue-500/30'
          } else if (status === 'failed') {
            backgroundClass = 'bg-red-500/20'
          }

          return (
            <div key={stage.key} className="flex flex-1 items-center">
              <div className={`flex flex-1 flex-col items-center rounded-lg px-1 py-2 transition-colors duration-300 ${backgroundClass}`}>
                <div
                  className={`mb-1 flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
                    status === 'passed'
                      ? 'bg-emerald-500 text-white'
                      : status === 'running'
                        ? 'animate-pulse bg-blue-500 text-white'
                        : status === 'failed'
                          ? 'bg-red-500 text-white'
                          : 'bg-gray-600 text-gray-400'
                  }`}
                >
                  {status === 'passed' ? '✓' : stage.icon}
                </div>
                <span className="text-center text-[10px] leading-tight text-gray-400">{stage.label}</span>
              </div>
              {index < STAGES.length - 1 && (
                <div className={`h-0.5 w-4 ${info?.status === 'passed' ? 'bg-emerald-500/50' : 'bg-gray-700'}`} />
              )}
            </div>
          )
        })}
      </div>

      {progress?.total_duration_sec && progress.total_duration_sec > 0 && (
        <div className="flex justify-between text-xs text-gray-500">
          <span>Total entries: {progress.total_entries}</span>
          <span>Duration: {formatDuration(progress.total_duration_sec)}</span>
        </div>
      )}
    </div>
  )
}

function formatDuration(seconds: number) {
  if (seconds < 60) {
    return `${seconds.toFixed(0)}s`
  }

  if (seconds < 3600) {
    return `${(seconds / 60).toFixed(1)}m`
  }

  return `${(seconds / 3600).toFixed(1)}h`
}
