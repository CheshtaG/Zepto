type FrontendLogRecord = {
  ts: string
  event: string
  payload?: Record<string, unknown>
}

const STORAGE_KEY = 'frontend-event-logs'
const MAX_LOGS = 300

export function logFrontendEvent(event: string, payload?: Record<string, unknown>) {
  const record: FrontendLogRecord = {
    ts: new Date().toISOString(),
    event,
    payload,
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const existing = raw ? (JSON.parse(raw) as FrontendLogRecord[]) : []
    const next = [...existing, record].slice(-MAX_LOGS)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // Ignore localStorage failures.
  }

  // Keep dev-console visibility for debugging sessions.
  // eslint-disable-next-line no-console
  console.log('[frontend-log]', record)
}

