const colors: Record<string, string> = {
  idle: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
  passed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  running: 'bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse',
  completed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  pending: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  skipped: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  ok: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  unreachable: 'bg-red-500/20 text-red-400 border-red-500/30',
}

interface StatusBadgeProps {
  status: string
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const cls = colors[status] || colors.pending

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${cls}`}>
      {status}
    </span>
  )
}
