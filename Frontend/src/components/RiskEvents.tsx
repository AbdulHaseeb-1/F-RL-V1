import type { RiskEvent } from '../types'

interface RiskEventsProps {
  events: unknown
}

const eventColors: Record<string, string> = {
  stop_loss: 'text-red-400',
  trailing_stop: 'text-yellow-400',
  time_stop: 'text-blue-400',
  circuit_breaker: 'font-bold text-red-500',
}

export default function RiskEvents({ events }: RiskEventsProps) {
  const eventList = normalizeEvents(events)

  if (eventList.length === 0) {
    return null
  }

  const recent = eventList.slice(-15).reverse()

  return (
    <div className="rounded-xl border border-gray-700/50 bg-gray-800/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Risk Events</h2>
        <span className="text-xs text-gray-500">{eventList.length} total</span>
      </div>
      <div className="max-h-60 space-y-2 overflow-y-auto">
        {recent.map((event, index) => (
          <div key={index} className="flex items-center gap-3 border-b border-gray-800/30 py-1 text-sm">
            <span className="w-24 shrink-0 font-mono text-xs text-gray-500">{formatTs(event.ts)}</span>
            <span className={eventColors[event.event || ''] || 'text-gray-400'}>
              {event.event?.replace(/_/g, ' ').toUpperCase()}
            </span>
            {event.dd !== undefined && <span className="ml-auto text-xs text-gray-500">DD: {(event.dd * 100).toFixed(1)}%</span>}
            {event.pnl !== undefined && <span className="ml-auto text-xs text-gray-500">PnL: {(event.pnl * 100).toFixed(2)}%</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

function formatTs(ts: RiskEvent['ts']) {
  if (!ts) {
    return '--'
  }

  try {
    return new Date(ts).toISOString().slice(5, 16).replace('T', ' ')
  } catch {
    return String(ts).slice(0, 16)
  }
}

function normalizeEvents(input: unknown): RiskEvent[] {
  const rawEvents =
    Array.isArray(input) ? input
      : input && typeof input === 'object' && 'events' in input ? input.events
      : input && typeof input === 'object' && 'risk_events' in input ? input.risk_events
      : input && typeof input === 'object' && 'data' in input ? input.data
      : []

  if (!Array.isArray(rawEvents)) {
    return []
  }

  return rawEvents.filter((event): event is RiskEvent => Boolean(event) && typeof event === 'object')
}
