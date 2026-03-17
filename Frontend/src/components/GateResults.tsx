interface GateResultsProps {
  gates: unknown
}

interface GateEntry {
  passed?: boolean
  stage?: string
  fold?: number | string
  status?: string
  metrics?: Record<string, number | string | null>
  timestamp?: string
  [key: string]: unknown
}

export default function GateResults({ gates }: GateResultsProps) {
  const gateList = normalizeGates(gates)

  if (gateList.length === 0) {
    return null
  }

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
      <h2 className="mb-4 text-lg font-semibold text-white">Quality Gates</h2>
      <div className="space-y-2">
        {gateList.map((gate, index) => {
          const passed = Boolean(gate.passed)
          const metrics = gate.metrics && typeof gate.metrics === 'object' ? gate.metrics : {}

          return (
            <div
              key={index}
              className={`rounded-lg px-3 py-2 ${
                passed ? 'border border-emerald-500/20 bg-emerald-500/10' : 'border border-red-500/20 bg-red-500/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`text-lg ${passed ? 'text-emerald-400' : 'text-red-400'}`}>{passed ? '✓' : '✗'}</span>
                  <span className="text-sm font-medium text-gray-300">{gate.stage}</span>
                  {gate.fold != null && (
                    <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">fold {gate.fold}</span>
                  )}
                </div>
                <span className={`text-xs font-semibold uppercase ${passed ? 'text-emerald-400' : 'text-red-400'}`}>
                  {gate.status || (passed ? 'passed' : 'failed')}
                </span>
              </div>
              {Object.keys(metrics).length > 0 && (
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-xs text-gray-500">
                  {Object.entries(metrics).map(([k, v]) => (
                    <span key={k}>
                      {k}: {typeof v === 'number' && Number.isFinite(v) ? v.toFixed(4) : String(v ?? '--')}
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

function normalizeGates(input: unknown): GateEntry[] {
  const rawGates =
    Array.isArray(input) ? input
      : input && typeof input === 'object' && 'gates' in input ? (input as Record<string, unknown>).gates
      : input && typeof input === 'object' && 'data' in input ? (input as Record<string, unknown>).data
      : []

  if (!Array.isArray(rawGates)) {
    return []
  }

  return rawGates.filter((gate): gate is GateEntry => Boolean(gate) && typeof gate === 'object')
}
