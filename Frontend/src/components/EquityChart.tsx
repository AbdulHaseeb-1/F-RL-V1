import { useMemo } from 'react'
import type { EquityPoint } from '../types'

interface EquityChartProps {
  data: unknown
}

export default function EquityChart({ data }: EquityChartProps) {
  const series = useMemo(() => normalizeEquityData(data), [data])

  const { points, min, max } = useMemo(() => {
    if (series.length === 0) {
      return { points: '', min: 0, max: 0 }
    }

    const values = series.map((point) => point.value)
    const minValue = Math.min(...values)
    const maxValue = Math.max(...values)
    const range = maxValue - minValue || 1
    const width = 800
    const height = 200
    const divisor = Math.max(series.length - 1, 1)

    const chartPoints = series
      .map((point, index) => {
        const x = (index / divisor) * width
        const y = height - ((point.value - minValue) / range) * height
        return `${x},${y}`
      })
      .join(' ')

    return { points: chartPoints, min: minValue, max: maxValue }
  }, [series])

  if (series.length === 0) {
    return (
      <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Equity Curve</h2>
        <div className="flex h-52 items-center justify-center text-gray-500">No equity data available</div>
      </div>
    )
  }

  const totalReturn = ((series[series.length - 1].value / series[0].value) - 1) * 100
  const isPositive = totalReturn >= 0

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Equity Curve</h2>
        <span className={`font-mono text-sm ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
          {isPositive ? '+' : ''}
          {totalReturn.toFixed(2)}%
        </span>
      </div>
      <svg viewBox="0 0 800 200" className="h-52 w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity="0.3" />
            <stop offset="100%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 50, 100, 150, 200].map((y) => (
          <line key={y} x1="0" y1={y} x2="800" y2={y} stroke="#374151" strokeWidth="0.5" />
        ))}
        <polygon points={`0,200 ${points} 800,200`} fill="url(#eqGrad)" />
        <polyline points={points} fill="none" stroke={isPositive ? '#10b981' : '#ef4444'} strokeWidth="2" />
      </svg>
      <div className="mt-2 flex justify-between text-xs text-gray-500">
        <span>${min.toLocaleString()}</span>
        <span>${max.toLocaleString()}</span>
      </div>
    </div>
  )
}

function normalizeEquityData(input: unknown): EquityPoint[] {
  const rawSeries =
    Array.isArray(input) ? input
      : input && typeof input === 'object' && 'equity_curve' in input ? input.equity_curve
      : input && typeof input === 'object' && 'data' in input ? input.data
      : []

  if (!Array.isArray(rawSeries)) {
    return []
  }

  return rawSeries
    .map((point) => {
      if (typeof point === 'number') {
        return { value: point }
      }

      if (point && typeof point === 'object') {
        if ('value' in point && typeof point.value === 'number') {
          return { ...point, value: point.value }
        }

        if ('equity' in point && typeof point.equity === 'number') {
          return { ...point, value: point.equity }
        }
      }

      return null
    })
    .filter((point): point is EquityPoint => point !== null)
}
