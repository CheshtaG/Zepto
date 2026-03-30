import { useState, useCallback, useEffect, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Platform, type LocationPayload, type ClarificationQuestion } from '../services/api'
import { useAppStore } from '../store/appStore'
import quiksaveLogo from '../../Images/quiksave logo.png'
import locationChevron from '../assets/location-chevron.svg'
import { AnimatedBackground } from '../components/AnimatedBackground/AnimatedBackground'

export const InputPage = () => {
  const [value, setValue] = useState('')
  const [isMenuOpen, setIsMenuOpen] = useState(true)
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false)
  const [locationSearch, setLocationSearch] = useState('')
  const nav = useNavigate()
  const {
    lastPlatforms,
    lastLocation,
    jobHistory,
    setLastPlatforms,
    setLastLocation,
    addJobHistory,
    setToast,
  } = useAppStore()
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>(lastPlatforms)
  const [selectedLocation, setSelectedLocation] = useState(lastLocation ?? 'Detecting...')
  const [locationPayload, setLocationPayload] = useState<LocationPayload | undefined>(undefined)
  const [isDetectingLocation, setIsDetectingLocation] = useState(true)
  const [clarificationQueue, setClarificationQueue] = useState<ClarificationQuestion[]>([])
  const [pendingSubmitItems, setPendingSubmitItems] = useState<string[] | null>(null)
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({})
  const [isClarifying, setIsClarifying] = useState(false)

  const detectLocation = useCallback(async () => {
    setIsDetectingLocation(true)
    try {
      if (typeof navigator !== 'undefined' && navigator.geolocation) {
        const coords = await new Promise<GeolocationCoordinates>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(
            (pos) => resolve(pos.coords),
            (err) => reject(err),
            { enableHighAccuracy: true, timeout: 8000, maximumAge: 5 * 60 * 1000 },
          )
        })

        let city: string | undefined
        let pincode: string | undefined
        try {
          const rev = await fetch(
            `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${coords.latitude}&longitude=${coords.longitude}&localityLanguage=en`,
          )
          if (rev.ok) {
            const data = await rev.json()
            city = data?.city || data?.locality || data?.principalSubdivision
            pincode = data?.postcode
          }
        } catch {
          // Reverse geocode can fail; coordinates are still useful for backend.
        }

        const label = [city, pincode].filter(Boolean).join(', ') || 'Detected from your device'
        const payload: LocationPayload = {
          name: label,
          city,
          pincode,
          lat: coords.latitude,
          lng: coords.longitude,
          source: 'geolocation',
        }
        setLocationPayload(payload)
        setSelectedLocation(label)
        setLastLocation(label)
        setIsDetectingLocation(false)
        return
      }
    } catch {
      // fall through to IP fallback
    }

    try {
      const detected = await api.detectLocation()
      if (detected.location) {
        const payload = detected.location
        const label =
          payload.name || [payload.city, payload.pincode].filter(Boolean).join(', ') || 'Auto-detected'
        setLocationPayload(payload)
        setSelectedLocation(label)
        setLastLocation(label)
      } else {
        setSelectedLocation(lastLocation ?? 'Location unavailable')
      }
    } catch {
      setSelectedLocation(lastLocation ?? 'Location unavailable')
    } finally {
      setIsDetectingLocation(false)
    }
  }, [lastLocation, setLastLocation])

  useEffect(() => {
    detectLocation()
  }, [detectLocation])

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
      setLastLocation(selectedLocation)

      const { job_id } = await api.createJob({
        items: finalItems,
        platforms: selectedPlatforms,
        location: locationPayload ?? selectedLocation,
      })

      addJobHistory({
        jobId: job_id,
        createdAt: new Date().toISOString(),
        items: finalItems,
        platforms: selectedPlatforms,
        location: selectedLocation,
      })

      nav(`/compare/${job_id}`, {
        state: {
          items: finalItems,
          platforms: selectedPlatforms,
          location: selectedLocation,
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

  const handleEnableCurrentLocation = async () => {
    await detectLocation()
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
        <div className="input-top-row">
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
              placeholder="Example: 2L milk, brown bread, eggs, apples..."
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
                    {isDetectingLocation
                      ? 'Detecting your location...'
                      : `Current: ${selectedLocation || 'Unavailable'} `}
                    <span className="location-current-dot" aria-hidden="true" />
                  </p>
                </div>
                <button
                  type="button"
                  className="location-enable-button"
                  onClick={handleEnableCurrentLocation}
                  disabled={isDetectingLocation}
                >
                  {isDetectingLocation ? 'Enabling...' : 'Enable'}
                </button>
              </div>

            </div>
          </div>
        </div>
      ) : null}

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

