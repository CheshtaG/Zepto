import { useState, useEffect, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Platform, type ClarificationQuestion } from '../services/api'
import { useAppStore } from '../store/appStore'
import { AnimatedBackground } from '../components/AnimatedBackground/AnimatedBackground'
import { logFrontendEvent } from '../lib/frontendLogger'

export const Onboarding = () => {
  const [value, setValue] = useState('')
  const [isMenuOpen, setIsMenuOpen] = useState(true)
  const nav = useNavigate()
  const {
    lastPlatforms,
    lastLocation,
    lastLocationPayload,
    jobHistory,
    setLastPlatforms,
    addJobHistory,
    setToast,
  } = useAppStore()
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>(lastPlatforms)
  const [clarificationQueue, setClarificationQueue] = useState<ClarificationQuestion[]>([])
  const [pendingSubmitItems, setPendingSubmitItems] = useState<string[] | null>(null)
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({})
  const [isClarifying, setIsClarifying] = useState(false)

  const submit = async () => {
    const trimmed = value.trim()
    if (!trimmed) return
    if (!selectedPlatforms.length) {
      setToast({ kind: 'error', message: 'Select at least one platform.' })
      return
    }

    const items = trimmed
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean)

    if (!items.length) return

    try {
      if (!pendingSubmitItems) {
        const clarification = await api.clarifyItems(items)
        if (clarification.questions?.length) {
          setPendingSubmitItems(items)
          setClarificationQueue(clarification.questions)
          setIsClarifying(true)
          return
        }
      }

      const finalItems = (() => {
        const base = pendingSubmitItems ?? items
        if (!Object.keys(clarificationAnswers).length) return base
        return base.map((it) => clarificationAnswers[it.toLowerCase()] ?? it)
      })()

      setLastPlatforms(selectedPlatforms)

      const { job_id } = await api.createJob({
        items: finalItems,
        platforms: selectedPlatforms,
        metadata: {
          location:
            lastLocationPayload ??
            (lastLocation ? { name: lastLocation, source: 'manual' } : undefined),
          history: jobHistory.slice(0, 5),
        },
      })
      logFrontendEvent('job_created_from_input', {
        jobId: job_id,
        itemsCount: finalItems.length,
        platforms: selectedPlatforms,
        location: lastLocation,
      })

      addJobHistory({
        jobId: job_id,
        createdAt: new Date().toISOString(),
        items: finalItems,
        platforms: selectedPlatforms,
        location: lastLocation,
      })

      nav(`/compare/${job_id}`, {
        state: {
          items: finalItems,
          platforms: selectedPlatforms,
          location: lastLocation,
          userInput: finalItems.join(', '),
        },
      })
      setPendingSubmitItems(null)
      setClarificationQueue([])
      setClarificationAnswers({})
      setIsClarifying(false)
    } catch (err: any) {
      setToast({ kind: 'error', message: err?.message ?? 'Failed to start price comparison' })
    }
  }

  const currentQuestion = clarificationQueue[0]
  const handlePickClarification = (opt: string) => {
    if (!currentQuestion) return
    setClarificationAnswers((prev) => ({
      ...prev,
      [currentQuestion.item.toLowerCase()]: opt,
    }))
    setClarificationQueue((prev) => prev.slice(1))
  }

  useEffect(() => {
    if (isClarifying && clarificationQueue.length === 0 && pendingSubmitItems?.length) {
      // Auto-continue after all clarification answers.
      submit()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClarifying, clarificationQueue.length])

  const togglePlatform = (platform: Platform) => {
    setSelectedPlatforms((prev) =>
      prev.includes(platform) ? prev.filter((p) => p !== platform) : [...prev, platform],
    )
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const formatHistoryTime = (iso: string) =>
    new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

  return (
    <div className="input-page">
      <AnimatedBackground intensity="low" />
      <aside className={`side-menu ${isMenuOpen ? 'open' : 'closed'}`}>
        <button
          type="button"
          className="side-menu-toggle"
          onClick={() => setIsMenuOpen((prev) => !prev)}
          aria-label={isMenuOpen ? 'Collapse side menu' : 'Expand side menu'}
        >
          {isMenuOpen ? '‹' : '›'}
        </button>
        {isMenuOpen ? (
          <div className="side-menu-content">
            <h3 className="side-menu-title">Old comparisons</h3>
            <div className="side-menu-list">
              {jobHistory.length ? (
                jobHistory.map((entry) => (
                  <button key={entry.jobId} type="button" className="side-menu-item">
                    <span className="side-menu-item-title">{entry.items.slice(0, 2).join(', ')}</span>
                    <span className="side-menu-item-meta">{formatHistoryTime(entry.createdAt)}</span>
                  </button>
                ))
              ) : (
                <p className="side-menu-empty">Your recent comparisons will show here.</p>
              )}
            </div>
          </div>
        ) : null}
      </aside>

      <div className="input-content">
        <div className="input-main-block">
          <div className="input-heading-row">
            <div className="input-heading-block">
              <h1 className="input-heading">
                What would you like to <span className="input-heading-accent">order</span> today?
              </h1>
              <p className="input-subheading">Paste your list. We'll compare prices across apps.</p>
            </div>
            <div className="platform-checkbox-row">
              <label className={`platform-chip zepto ${selectedPlatforms.includes('zepto') ? 'selected' : ''}`}>
                <input
                  type="checkbox"
                  checked={selectedPlatforms.includes('zepto')}
                  onChange={() => togglePlatform('zepto')}
                />
                <span>Z</span>
              </label>
              <label className={`platform-chip blinkit ${selectedPlatforms.includes('blinkit') ? 'selected' : ''}`}>
                <input
                  type="checkbox"
                  checked={selectedPlatforms.includes('blinkit')}
                  onChange={() => togglePlatform('blinkit')}
                />
                <span>B</span>
              </label>
              <label className={`platform-chip instamart ${selectedPlatforms.includes('zomato') ? 'selected' : ''}`}>
                <input
                  type="checkbox"
                  checked={selectedPlatforms.includes('zomato')}
                  onChange={() => togglePlatform('zomato')}
                />
                <span>I</span>
              </label>
            </div>
          </div>

          <div className="input-textarea-wrapper">
            <textarea
              className="input-textarea"
              placeholder="Example; toned milk, brown bread, eggs, apples"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
            />

            <button
              type="button"
              className="input-enter-button"
              onClick={submit}
              aria-label="Enter"
              title="Compare prices"
            >
              ↑
              <span className="input-enter-tooltip">Compare prices</span>
            </button>
          </div>
        </div>
      </div>

      {isClarifying && currentQuestion ? (
        <div className="clarify-modal-backdrop" role="presentation">
          <div className="clarify-modal" role="dialog" aria-modal="true" aria-label="Clarify product">
            <h3>Quick clarification</h3>
            <p>{currentQuestion.prompt}</p>
            <div className="clarify-options">
              {currentQuestion.options.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  className="clarify-option-btn"
                  onClick={() => handlePickClarification(opt)}
                >
                  {opt}
                </button>
              ))}
              <button
                type="button"
                className="clarify-option-btn secondary"
                onClick={() => handlePickClarification(currentQuestion.item)}
              >
                Any works for me
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
