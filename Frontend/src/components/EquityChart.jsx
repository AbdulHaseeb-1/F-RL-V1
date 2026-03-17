import { useMemo } from 'react'

export default function EquityChart({ data }) {
  const { points, min, max, drawdownPoints } = useMemo(() => {
    if (!data || data.length === 0) return { points: '', min: 0, max: 0, drawdownPoints: '' }

    const values = data.map(d => d.value)
    const mn = Math.min(...values)
    const mx = Math.max(...values)
    const range = mx - mn || 1
    const w = 800
    const h = 200

    const pts = data.map((d, i) => {
      const x = (i / (data.length - 1)) * w
      const y = h - ((d.value - mn) / range) * h
      return `${x},${y}`
    }).join(' ')

    // Drawdown line
    let peak = data[0].value
    const ddPts = data.map((d, i) => {
      peak = Math.max(peak, d.value)
      const dd = (peak - d.value) / peak
      const x = (i / (data.length - 1)) * w
      const y = dd * 100 // scale to 0-100 range
      return `${x},${y}`
    }).join(' ')

    return { points: pts, min: mn, max: mx, drawdownPoints: ddPts }
  }, [data])

  if (!data || data.length === 0) {
    return (
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Equity Curve</h2>
        <div className="h-52 flex items-center justify-center text-gray-500">
          No equity data available
        </div>
      </div>
    )
  }

  const totalReturn = ((data[data.length - 1].value / data[0].value) - 1) * 100
  const isPositive = totalReturn >= 0

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Equity Curve</h2>
        <span className={`text-sm font-mono ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
          {isPositive ? '+' : ''}{totalReturn.toFixed(2)}%
        </span>
      </div>
      <svg viewBox="0 0 800 200" className="w-full h-52" preserveAspectRatio="none">
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity="0.3" />
            <stop offset="100%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Grid lines */}
        {[0, 50, 100, 150, 200].map(y => (
          <line key={y} x1="0" y1={y} x2="800" y2={y} stroke="#374151" strokeWidth="0.5" />
        ))}
        {/* Fill area */}
        <polygon
          points={`0,200 ${points} 800,200`}
          fill="url(#eqGrad)"
        />
        {/* Equity line */}
        <polyline
          points={points}
          fill="none"
          stroke={isPositive ? '#10b981' : '#ef4444'}
          strokeWidth="2"
        />
      </svg>
      <div className="flex justify-between text-xs text-gray-500 mt-2">
        <span>${min.toLocaleString()}</span>
        <span>${max.toLocaleString()}</span>
      </div>
    </div>
  )
}
