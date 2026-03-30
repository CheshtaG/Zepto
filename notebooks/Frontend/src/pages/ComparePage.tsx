import { useState, useRef, useCallback, useEffect, type KeyboardEvent } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { useComparisonJob } from '../features/comparison/hooks/useComparisonJob'
import { PlatformResults } from '../features/comparison/components/PlatformResults'
import { api, type ChatMessage, type Platform, type LocationPayload } from '../services/api'
import { HttpError } from '../lib/http'
import { useAppStore } from '../store/appStore'
import quiksaveLogo from '../assets/quiksave-logo-transparent.png'
import locationChevron from '../assets/location-chevron.svg'

interface LocationState {
  userInput?: string
  items?: string[]
  platforms?: Platform[]
  location?: string | LocationPayload
}

export const ComparePage = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const state = (location.state || {}) as LocationState
  const { result, status, isRunning } = useComparisonJob(jobId)
  const { setToast, setResult, setPollingState } = useAppStore()

  const [chatInput, setChatInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [additionalItems, setAdditionalItems] = useState<string[]>([])
  const [isSending, setIsSending] = useState(false)
  const [splitPercent, setSplitPercent] = useState(30)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null)
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false)
  const [locationSearch, setLocationSearch] = useState('')
  const [isDetectingLocation, setIsDetectingLocation] = useState(false)
  const isDragging = useRef(false)
  const chatAreaRef = useRef<HTMLDivElement>(null)
  const selectedPlatforms: Platform[] = state.platforms?.length
    ? state.platforms
    : ['zepto', 'blinkit', 'zomato']
  const selectedLocationPayload = state.location
  const selectedLocation =
    typeof state.location === 'string'
      ? state.location
      : state.location?.name || [state.location?.city, state.location?.pincode].filter(Boolean).join(', ') || 'Unknown'
  const [displayLocation, setDisplayLocation] = useState(selectedLocation)

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
    setDisplayLocation(selectedLocation)
  }, [selectedLocation])

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

  useEffect(() => {
    if (result) setLastUpdatedAt(Date.now())
  }, [result])

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
              platforms: selectedPlatforms,
              location: selectedLocationPayload ?? selectedLocation,
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
                platforms: selectedPlatforms,
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
        platforms: selectedPlatforms,
        location: selectedLocationPayload ?? selectedLocation,
      })

      navigate(`/compare/${job_id}`, {
        state: {
          userInput: mergedItems.join(', '),
          items: mergedItems,
          platforms: selectedPlatforms,
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
    selectedPlatforms,
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

  const detectLocation = useCallback(async () => {
    setIsDetectingLocation(true)
    try {
      const detected = await api.detectLocation()
      if (detected.location) {
        const payload = detected.location
        const label =
          payload.name || [payload.city, payload.pincode].filter(Boolean).join(', ') || 'Auto-detected'
        setDisplayLocation(label)
      }
    } finally {
      setIsDetectingLocation(false)
    }
  }, [])

  if (!jobId) {
    return null
  }

  return (
    <div className="compare-screen">
      <header className="compare-top-row">
        <div className="compare-top-row-inner">
          <div className="input-logo-wrap">
            <img src={quiksaveLogo} alt="Quiksave" className="input-logo-img" />
          </div>
          <button
            type="button"
            className="input-location-button"
            aria-label="Select location"
            onClick={() => setIsLocationModalOpen(true)}
          >
            <span className="input-location-label">Select Location</span>
            <img src={locationChevron} alt="" className="input-location-caret-img" aria-hidden="true" />
          </button>
        </div>
        <div className="compare-gradient-rule" aria-hidden="true" />
      </header>

      <div className="compare-page">
      {/* Left side: chat area + textbox */}
      <section className="compare-left" style={{ width: `${splitPercent}%` }}>
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

      {/* Right side: comparison table */}
      <section className="compare-right" style={{ width: `${100 - splitPercent}%` }}>
        <div className="compare-studio-header">
          <div className="compare-studio-summary-card">
            <div className="compare-studio-summary-platforms">
              {selectedPlatforms.map((p) => (
                <span key={p} className={`compare-studio-platform-chip ${p}`}>
                  {p === 'zomato' ? 'Instamart' : p[0].toUpperCase() + p.slice(1)}
                </span>
              ))}
            </div>

            <div className="compare-studio-summary-bottom">
              <span className="compare-studio-last-updated">
                Last updated:{' '}
                {lastUpdatedAt
                  ? `${Math.max(0, Math.round((Date.now() - lastUpdatedAt) / 60000))} min ago`
                  : '—'}
              </span>

              <span className="compare-studio-status">
                {isRunning ? 'Fetching latest prices…' : status?.status === 'failed' ? 'Job failed' : 'Comparison ready.'}
              </span>
            </div>
          </div>
        </div>

        <PlatformResults
          result={result}
          additionalItems={additionalItems}
          platforms={selectedPlatforms}
          isRunning={isRunning}
        />
      </section>
      </div>

      {isLocationModalOpen ? (
        <div
          className="location-modal-backdrop"
          onClick={() => setIsLocationModalOpen(false)}
          role="presentation"
        >
          <div
            className="location-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Select your location"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="location-modal-header">
              <h2>
                <span className="location-title-pin" aria-hidden="true">
                  📍
                </span>
                Your Location
              </h2>
              <button
                type="button"
                className="location-modal-close"
                onClick={() => setIsLocationModalOpen(false)}
                aria-label="Close location modal"
              >
                ×
              </button>
            </div>

            <div className="location-modal-body">
              <div className="location-search-row">
                <span className="location-search-icon" aria-hidden="true">
                  🔍
                </span>
                <input
                  type="text"
                  value={locationSearch}
                  onChange={(e) => setLocationSearch(e.target.value)}
                  placeholder="Search a new address"
                  className="location-search-input"
                />
              </div>

              <div className="location-current-card">
                <div className="location-current-text">
                  <p className="location-current-title">Use My Current Location</p>
                  <p className="location-current-subtitle">
                    {isDetectingLocation ? 'Detecting your location...' : `Current: ${displayLocation || 'Unavailable'} `}
                    <span className="location-current-dot" aria-hidden="true" />
                  </p>
                </div>
                <button
                  type="button"
                  className="location-enable-button"
                  onClick={detectLocation}
                  disabled={isDetectingLocation}
                >
                  {isDetectingLocation ? 'Enabling...' : 'Enable'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

