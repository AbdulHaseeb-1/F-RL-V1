export default function GateResults({ gates }) {
  if (!gates || gates.length === 0) return null

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Quality Gates</h2>
      <div className="space-y-2">
        {gates.map((g, i) => {
          const passed = g.passed
          return (
            <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-lg
              ${passed ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'}`}>
              <div className="flex items-center gap-2">
                <span className={`text-lg ${passed ? 'text-emerald-400' : 'text-red-400'}`}>
                  {passed ? '\u2713' : '\u2717'}
                </span>
                <span className="text-sm text-gray-300">{g.stage} / {g.metric}</span>
              </div>
              <div className="text-right">
                <span className="text-sm font-mono text-gray-400">
                  {g.value?.toFixed(4)} {g.direction} {g.threshold}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
