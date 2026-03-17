type LogLevel = 'debug' | 'info' | 'warn' | 'error'

const log = (level: LogLevel, message: string, meta?: unknown) => {
  // Central place to plug in real telemetry later (Sentry, Datadog, etc.)
  // eslint-disable-next-line no-console
  console[level](
    `[frontend] ${message}`,
    meta && typeof meta === 'object' ? meta : meta ?? '',
  )
}

export const logger = {
  debug: (message: string, meta?: unknown) => log('debug', message, meta),
  info: (message: string, meta?: unknown) => log('info', message, meta),
  warn: (message: string, meta?: unknown) => log('warn', message, meta),
  error: (message: string, meta?: unknown) => log('error', message, meta),
}

