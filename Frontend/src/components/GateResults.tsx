import type { GateResult } from '../types'

interface GateResultsProps {
  gates: unknown
}

function formatGateValue(value: GateResult['value']) {
  if (typeof value === 'number') {
    return value.toFixed(4)
  }

  return value ?? '--'
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

          return (
            <div
              key={index}
              className={`flex items-center justify-between rounded-lg px-3 py-2 ${
                passed ? 'border border-emerald-500/20 bg-emerald-500/10' : 'border border-red-500/20 bg-red-500/10'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`text-lg ${passed ? 'text-emerald-400' : 'text-red-400'}`}>{passed ? '✓' : '✗'}</span>
                <span className="text-sm text-gray-300">
                  {gate.stage} / {gate.metric}
                </span>
              </div>
              <div className="text-right">
                <span className="font-mono text-sm text-gray-400">
                  {formatGateValue(gate.value)} {gate.direction} {gate.threshold}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function normalizeGates(input: unknown): GateResult[] {
  const rawGates =
    Array.isArray(input) ? input
      : input && typeof input === 'object' && 'gates' in input ? input.gates
      : input && typeof input === 'object' && 'data' in input ? input.data
      : []

  if (!Array.isArray(rawGates)) {
    return []
  }

  return rawGates.filter((gate): gate is GateResult => Boolean(gate) && typeof gate === 'object')
}
