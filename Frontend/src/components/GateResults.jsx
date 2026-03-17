export default function GateResults({ gates }) {
  if (!gates || gates.length === 0) return null

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Quality Gates</h2>
      <div className="space-y-2">
        {gates.map((g, i) => {
          const passed = g.passed ?? (g.status === 'passed')
          const metrics = g.metrics || {}
          const metricEntries = Object.entries(metrics).slice(0, 4)
          return (
            <div key={i} className={`px-3 py-2 rounded-lg
              ${passed ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`text-lg ${passed ? 'text-emerald-400' : 'text-red-400'}`}>
                    {passed ? '\u2713' : '\u2717'}
                  </span>
                  <span className="text-sm text-gray-300 font-medium">{g.stage}</span>
                  {g.fold >= 0 && (
                    <span className="text-xs text-gray-500">fold {g.fold}</span>
                  )}
                </div>
                <span className="text-xs text-gray-500 font-mono">
                  {g.timestamp ? String(g.timestamp).slice(11, 19) : ''}
                </span>
              </div>
              {metricEntries.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 ml-7">
                  {metricEntries.map(([k, v]) => (
                    <span key={k} className="text-xs text-gray-500 font-mono">
                      {k}: <span className="text-gray-300">
                        {typeof v === 'number' ? v.toFixed(4) : String(v)}
                      </span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
