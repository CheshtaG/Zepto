import { useEffect } from 'react'
import { api } from '../../../services/api'
import { useAppStore } from '../../../store/appStore'
import { logger } from '../../../lib/logger'

export const useComparisonJob = (jobId: string | undefined) => {
  const { resultsByJobId, pollingByJobId, setResult, setPollingState, setToast } =
    useAppStore()

  const result = jobId ? resultsByJobId[jobId] : undefined
  const polling = jobId ? pollingByJobId[jobId] : undefined

  useEffect(() => {
    if (!jobId) return

    let cancelled = false
    let lastProgress = -1

    async function ensureStatusAndResult() {
      try {
        setPollingState(jobId, { isPolling: true })
        const status = await api.getJobStatus(jobId)
        if (cancelled) return
        setPollingState(jobId, {
          status,
          isPolling: status.status !== 'done' && status.status !== 'failed',
        })
        lastProgress = status.progress ?? 0
        const res = await api.getJobResult(jobId)
        if (cancelled) return
        setResult(jobId, res)
      } catch (err: any) {
        if (cancelled) return
        logger.error('Failed to ensure job status/result', err)
        setPollingState(jobId, { isPolling: false })
        setToast({ kind: 'error', message: err?.message ?? 'Failed to fetch job status' })
      }
    }

    ensureStatusAndResult()

    const interval = setInterval(async () => {
      if (cancelled || !jobId) return
      try {
        const status = await api.getJobStatus(jobId)
        if (cancelled) return
        setPollingState(jobId, {
          status,
          isPolling: status.status !== 'done' && status.status !== 'failed',
        })
        // Fetch partial rows whenever the job is still running (each platform can finish separately).
        if (
          status.status === 'done' ||
          status.status === 'failed' ||
          status.status === 'capturing' ||
          status.progress > lastProgress
        ) {
          lastProgress = status.progress ?? lastProgress
          const res = await api.getJobResult(jobId)
          if (cancelled) return
          setResult(jobId, res)
        }
        // Do not stop polling on `done`: add-items reuses the same jobId and sets status back to
        // capturing; if we clearInterval here, the UI never updates until navigation/refresh.
        if (status.status === 'failed') clearInterval(interval)
      } catch (err: any) {
        if (!cancelled) {
          logger.error('Error while polling job status', err)
          setPollingState(jobId, { isPolling: false })
          setToast({ kind: 'error', message: err?.message ?? 'Error polling job status' })
        }
        clearInterval(interval)
      }
    }, 2500)

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [jobId, setPollingState, setResult, setToast])

  const status = polling?.status
  const isRunning = polling?.isPolling && status !== 'done' && status !== 'failed'

  const derivedProgress = (() => {
    if (!status) return 10
    if (status.status === 'capturing') return Math.max(15, status.progress)
    if (status.status === 'extracting') return Math.max(45, status.progress)
    if (status.status === 'done') return 100
    if (status.status === 'failed') return 0
    return status.progress
  })()

  return { result, status, polling, isRunning, derivedProgress }
}

