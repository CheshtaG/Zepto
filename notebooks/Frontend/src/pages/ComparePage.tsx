import { useState, useRef, useCallback, useEffect, type KeyboardEvent } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { useComparisonJob } from '../features/comparison/hooks/useComparisonJob'
import { ComparisonTable } from '../features/comparison/components/ComparisonTable'
import { api, type ChatMessage, type Platform } from '../services/api'
import { useAppStore } from '../store/appStore'

interface LocationState {
  userInput?: string
  items?: string[]
  platforms?: Platform[]
  location?: string
}

export const ComparePage = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const state = (location.state || {}) as LocationState
  const { result, status, isRunning, derivedProgress } = useComparisonJob(jobId)
  const { setToast } = useAppStore()

  const [chatInput, setChatInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [additionalItems, setAdditionalItems] = useState<string[]>([])
  const [isSending, setIsSending] = useState(false)
  const [splitPercent, setSplitPercent] = useState(50)
  const isDragging = useRef(false)
  const chatAreaRef = useRef<HTMLDivElement>(null)
  const selectedPlatforms: Platform[] = state.platforms?.length
    ? state.platforms
    : ['zepto', 'blinkit', 'zomato']
  const selectedLocation = state.location ?? 'Pune'

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
      const mergedItems = mergeUniqueItems(baseItems, newItems)
      if (!mergedItems.length) return

      const { job_id } = await api.createJob({
        items: mergedItems,
        platforms: selectedPlatforms,
        location: selectedLocation,
      })

      navigate(`/compare/${job_id}`, {
        state: {
          userInput: mergedItems.join(', '),
          items: mergedItems,
          platforms: selectedPlatforms,
          location: selectedLocation,
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
    state.items,
    navigate,
    setToast,
  ])

  const handleMouseDown = useCallback(() => {
    isDragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const handleMouseMove = useCallback((e: globalThis.MouseEvent) => {
    if (!isDragging.current) return
    const newPercent = (e.clientX / window.innerWidth) * 100
    const clamped = Math.min(70, Math.max(30, newPercent))
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
    <div className="compare-page">
      {/* Left side: chat area + textbox */}
      <section className="compare-left" style={{ width: `${splitPercent}%` }}>
        <div className="compare-chat-header">
          <h3>Shopping Assistant</h3>
          <p>Ask questions about your comparison</p>
        </div>

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
        <header style={{ marginBottom: 16 }}>
          <h2 style={{ color: '#000000' }}>Price comparison</h2>
          <p className="compare-status-text">
            Location: <strong>{selectedLocation}</strong>
          </p>
          <p className="compare-status-text">
            Platforms: <strong>{selectedPlatforms.map((p) => (p === 'zomato' ? 'Instamart' : p)).join(', ')}</strong>
          </p>
          <p className="compare-status-text">
            {isRunning
              ? 'Fetching latest prices…'
              : status?.status === 'failed'
                ? 'Job failed – try again.'
                : 'Comparison ready.'}
          </p>
          <div className="progress-track" style={{ maxWidth: 260, marginTop: 8 }}>
            <div className="progress-bar" style={{ width: `${derivedProgress}%` }} />
          </div>
        </header>

        {!result && additionalItems.length === 0 && (
          <div className="results-empty">
            <div>
              <div>Waiting for results…</div>
              <div>Capturing screenshots &amp; extracting prices in the background.</div>
            </div>
          </div>
        )}

        {result && (
          <ComparisonTable
            result={result}
            additionalItems={additionalItems}
            platforms={selectedPlatforms}
          />
        )}
        {!result && additionalItems.length > 0 && (
          <table className="comparison-table">
            <thead>
              <tr>
                <th rowSpan={2}>Product</th>
                <th colSpan={selectedPlatforms.length}>Platform</th>
              </tr>
              <tr>
                {selectedPlatforms.map((platform) => (
                  <th key={`pending-header-${platform}`}>
                    {platform === 'zomato' ? 'Instamart' : platform[0].toUpperCase() + platform.slice(1)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {additionalItems.map((item) => (
                <tr key={`pending-only-${item}`}>
                  <td>{item}</td>
                  {selectedPlatforms.map((platform) => (
                    <td key={`pending-only-${item}-${platform}`}>—</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

