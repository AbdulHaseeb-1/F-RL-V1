export default function MetricCard({ label, value, suffix = '', trend, small = false }) {
  const formatted = typeof value === 'number'
    ? (Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(4))
    : value ?? '--'

  const trendColor = trend === 'up' ? 'text-emerald-400'
    : trend === 'down' ? 'text-red-400'
    : 'text-gray-400'

  return (
    <div className={`bg-gray-800/50 border border-gray-700/50 rounded-xl ${small ? 'p-3' : 'p-4'}`}>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`${small ? 'text-lg' : 'text-2xl'} font-semibold ${trendColor} tabular-nums`}>
        {formatted}{suffix}
      </p>
    </div>
  )
}
