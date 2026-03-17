import { env } from '../config/env'
import { logger } from './logger'

export class HttpError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

interface RequestOptions extends RequestInit {
  path: string
}

export async function request<T>({ path, ...init }: RequestOptions): Promise<T> {
  const url = `${env.apiBaseUrl}${path}`

  try {
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(init.headers ?? {}),
      },
      ...init,
    })

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      const message = text || `Request failed with status ${res.status}`
      logger.warn('HTTP request failed', { url, status: res.status, message })
      throw new HttpError(res.status, message)
    }

    const data = (await res.json()) as T
    return data
  } catch (err: any) {
    if (!(err instanceof HttpError)) {
      logger.error('HTTP request threw', { url, error: err?.message ?? String(err) })
    }
    throw err
  }
}

