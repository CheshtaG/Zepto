import { useState, useRef, useCallback, useEffect, useMemo, type KeyboardEvent } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { useComparisonJob } from '../features/comparison/hooks/useComparisonJob'
import { ArbitrageDashboardRight } from '../features/comparison/arbitrage/ArbitrageDashboardRight'
import type { ArbitragePlatformKey } from '../features/comparison/arbitrage/types'
import { api, type ChatMessage, type Platform, type LocationPayload } from '../services/api'
import { HttpError } from '../lib/http'
import { useAppStore } from '../store/appStore'

interface LocationState {
  userInput?: string
  items?: string[]
  platforms?: Platform[]
  location?: string | LocationPayload
}

const ARB_PLATFORM_KEYS: ArbitragePlatformKey[] = ['zepto', 'blinkit', 'instamart']

export const ComparePage = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const state = (location.state || {}) as LocationState
  const { result, isRunning, status } = useComparisonJob(jobId)
  const { setToast, setResult, setPollingState, jobHistory } = useAppStore()

  const [chatInput, setChatInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [additionalItems, setAdditionalItems] = useState<string[]>([])
  const [isSending, setIsSending] = useState(false)
  const [splitPercent, setSplitPercent] = useState(30)
  const isDragging = useRef(false)
  const chatAreaRef = useRef<HTMLDivElement>(null)
  const jobPlatforms: Platform[] = state.platforms?.length
    ? state.platforms
    : ['zepto', 'blinkit', 'zomato']

  const statePlatformsKey = useMemo(() => JSON.stringify(state.platforms ?? []), [state.platforms])

  const [platformEnabled, setPlatformEnabled] = useState<Record<ArbitragePlatformKey, boolean>>({
    zepto: true,
    blinkit: true,
    instamart: true,
  })

  useEffect(() => {
    const sp = state.platforms?.length ? state.platforms : (['zepto', 'blinkit', 'zomato'] as Platform[])
    setPlatformEnabled({
      zepto: sp.includes('zepto'),
      blinkit: sp.includes('blinkit'),
      instamart: sp.includes('zomato') || sp.includes('instamart'),
    })
  }, [jobId, statePlatformsKey])

  const visiblePlatforms = useMemo((): Platform[] => {
    const o: Platform[] = []
    if (platformEnabled.zepto) o.push('zepto')
    if (platformEnabled.blinkit) o.push('blinkit')
    if (platformEnabled.instamart) o.push('zomato')
    if (o.length === 0) o.push('zepto')
    return o
  }, [platformEnabled])

  const togglePlatform = useCallback((key: ArbitragePlatformKey) => {
    setPlatformEnabled((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      const on = ARB_PLATFORM_KEYS.filter((k) => next[k]).length
      if (on === 0) return prev
      return next
    })
  }, [])

  const selectedLocationPayload = state.location
  const selectedLocation =
    typeof state.location === 'string'
      ? state.location
      : state.location?.name || [state.location?.city, state.location?.pincode].filter(Boolean).join(', ') || 'Unknown'
  const extractItems = useCallback((content: string) => {
    return content
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean)
  }, [])

  const mergeUniqueItems = useCallback((existing: string[], incoming: string[]) => {
    const byLower = new Map<string, string>()
    for (const item of existing) {
      if (!item.trim()) continue
      byLower.set(item.trim().toLowerCase(), item.trim())
    }
    for (const item of incoming) {
      if (!item.trim()) continue
      byLower.set(item.trim().toLowerCase(), item.trim())
    }
    return Array.from(byLower.values())
  }, [])

  useEffect(() => {
    if (state.userInput && messages.length === 0) {
      setMessages([{ role: 'user', content: state.userInput }])
      setAdditionalItems(extractItems(state.userInput))
    }
  }, [state.userInput, messages.length, extractItems])

  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight
    }
  }, [messages])

  const knownItemQueries = useMemo(() => {
    const s = new Set<string>()
    if (!result) return s
    for (const it of result.items) s.add(it.query.trim().toLowerCase())
    return s
  }, [result])

  const pendingOnlyQueries = useMemo(() => {
    return additionalItems.filter((item) => !knownItemQueries.has(item.trim().toLowerCase()))
  }, [additionalItems, knownItemQueries])

  const handleSendMessage = useCallback(async () => {
    if (!chatInput.trim() || !jobId || isSending) return

    const userMessage: ChatMessage = { role: 'user', content: chatInput.trim() }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    const newItems = extractItems(userMessage.content)
    setAdditionalItems((prev) => mergeUniqueItems(prev, newItems))
    setChatInput('')
    setIsSending(true)

    try {
      const baseItems = result?.items.map((item) => item.query) ?? state.items ?? []
      const baseLower = new Set(baseItems.map((it) => it.trim().toLowerCase()))
      const itemsToAdd = newItems.filter((it) => !baseLower.has(it.trim().toLowerCase()))

      // If we already have a running/finished job, only fetch comparisons for the new items
      // so the existing table doesn't go blank.
      if (jobId && result?.items && itemsToAdd.length > 0) {
        try {
          await api.addJobItems(jobId, itemsToAdd)
          try {
            const st = await api.getJobStatus(jobId)
            setPollingState(jobId, {
              status: st,
              isPolling: st.status !== 'done' && st.status !== 'failed',
            })
            const res = await api.getJobResult(jobId)
            setResult(jobId, res)
          } catch {
            setToast({ kind: 'error', message: 'Added items but could not refresh the table. It will update shortly.' })
          }
          return
        } catch (err: unknown) {
          // In-memory jobs disappear after an API restart; recreate a job with the merged list.
          if (err instanceof HttpError && err.status === 404) {
            const mergedItems = mergeUniqueItems(baseItems, newItems)
            if (!mergedItems.length) return
            const { job_id } = await api.createJob({
              items: mergedItems,
              platforms: jobPlatforms,
              metadata: {
                location:
                  typeof (selectedLocationPayload ?? selectedLocation) === 'string'
                    ? { name: String(selectedLocationPayload ?? selectedLocation), source: 'manual' }
                    : (selectedLocationPayload as LocationPayload | undefined),
                history: jobHistory.slice(0, 5),
              },
            })
            setToast({
              kind: 'info',
              message: 'Previous session expired (e.g. server restarted). Started a fresh comparison.',
            })
            navigate(`/compare/${job_id}`, {
              replace: true,
              state: {
                userInput: mergedItems.join(', '),
                items: mergedItems,
                platforms: jobPlatforms,
                location: selectedLocationPayload ?? selectedLocation,
              },
            })
            return
          }
          throw err
        }
      }

      const mergedItems = mergeUniqueItems(baseItems, newItems)
      if (!mergedItems.length) return

      const { job_id } = await api.createJob({
        items: mergedItems,
        platforms: jobPlatforms,
        metadata: {
          location:
            typeof (selectedLocationPayload ?? selectedLocation) === 'string'
              ? { name: String(selectedLocationPayload ?? selectedLocation), source: 'manual' }
              : (selectedLocationPayload as LocationPayload | undefined),
          history: jobHistory.slice(0, 5),
        },
      })

      navigate(`/compare/${job_id}`, {
        state: {
          userInput: mergedItems.join(', '),
          items: mergedItems,
          platforms: jobPlatforms,
          location: selectedLocationPayload ?? selectedLocation,
        },
      })
    } catch (err) {
      setToast({ kind: 'error', message: 'Failed to fetch comparison for new items' })
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Could not fetch data for the new items. Please try again.',
      }
      setMessages([...updatedMessages, errorMessage])
    } finally {
      setIsSending(false)
    }
  }, [
    chatInput,
    jobId,
    isSending,
    messages,
    extractItems,
    mergeUniqueItems,
    result?.items,
    jobPlatforms,
    selectedLocation,
    selectedLocationPayload,
    state.items,
    navigate,
    setToast,
    setResult,
    setPollingState,
  ])

  const handleMouseDown = useCallback(() => {
    isDragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const handleMouseMove = useCallback((e: globalThis.MouseEvent) => {
    if (!isDragging.current) return
    const newPercent = (e.clientX / window.innerWidth) * 100
    const clamped = Math.min(70, Math.max(25, newPercent))
    setSplitPercent(clamped)
  }, [])

  const handleMouseUp = useCallback(() => {
    isDragging.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [])

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [handleMouseMove, handleMouseUp])

  if (!jobId) {
    return null
  }

  return (
    <div className="compare-screen">
      <div className="compare-page">
      {/* Left side: chat area + textbox */}
      <section className="compare-left" style={{ width: `${splitPercent}%` }}>
        <div className="compare-left-scroll">
          <div className="compare-chat-area" ref={chatAreaRef}>
          {messages.length === 0 && (
            <div className="chat-empty-state">
              <p>Ask me about:</p>
              <ul>
                <li>Which platform has the best prices</li>
                <li>Recommendations for your shopping list</li>
                <li>Availability across platforms</li>
              </ul>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`chat-bubble ${msg.role === 'user' ? 'user-bubble' : 'assistant-bubble'}`}
            >
              {msg.content}
            </div>
          ))}
          {isSending && (
            <div className="chat-bubble assistant-bubble typing-indicator">
              <span></span><span></span><span></span>
            </div>
          )}
          </div>
        </div>

        <div className="compare-textarea-wrapper">
          <textarea
            className="compare-textarea"
            placeholder="Ask about prices, recommendations..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSendMessage()
              }
            }}
            disabled={isSending}
          />
          <button
            type="button"
            className="compare-enter-button"
            aria-label="Send message"
            onClick={handleSendMessage}
            disabled={isSending || !chatInput.trim()}
          >
            ↑
          </button>
        </div>
      </section>

      {/* Resizable divider */}
      <div
        className="compare-divider"
        onMouseDown={handleMouseDown}
      />

      {/* Right side: arbitrage dashboard */}
      <section className="compare-right" style={{ width: `${100 - splitPercent}%` }}>
        <ArbitrageDashboardRight
          result={result}
          platforms={visiblePlatforms}
          platformEnabled={platformEnabled}
          onTogglePlatform={togglePlatform}
          isRunning={Boolean(isRunning)}
          jobFailed={status?.status === 'failed'}
          pendingQueries={pendingOnlyQueries}
        />
      </section>
      </div>
    </div>
  )
}

