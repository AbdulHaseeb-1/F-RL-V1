type Trend = 'up' | 'down'

interface MetricCardProps {
  label: string
  value: number | string | null | undefined
  suffix?: string
  trend?: Trend
  small?: boolean
}

export default function MetricCard({ label, value, suffix = '', trend, small = false }: MetricCardProps) {
  const formatted = typeof value === 'number' && Number.isFinite(value)
    ? (Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(4))
    : value ?? '--'

  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400'

  return (
    <div className={`rounded-xl border border-gray-700/50 bg-gray-800/50 ${small ? 'p-3' : 'p-4'}`}>
      <p className="mb-1 text-xs uppercase tracking-wider text-gray-500">{label}</p>
      <p className={`tabular-nums font-semibold ${small ? 'text-lg' : 'text-2xl'} ${trendColor}`}>
        {formatted}
        {suffix}
      </p>
    </div>
  )
}
