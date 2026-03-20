import { useState, KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Platform } from '../services/api'
import { useAppStore } from '../store/appStore'

export const InputPage = () => {
  const [value, setValue] = useState('')
  const nav = useNavigate()
  const {
    lastPlatforms,
    lastLocation,
    setLastPlatforms,
    setLastLocation,
    addJobHistory,
    setToast,
  } = useAppStore()
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>(lastPlatforms)
  const [selectedLocation, setSelectedLocation] = useState(lastLocation ?? 'Pune')

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
      setLastPlatforms(selectedPlatforms)
      setLastLocation(selectedLocation)

      const { job_id } = await api.createJob({
        items,
        platforms: selectedPlatforms,
        location: selectedLocation,
      })

      addJobHistory({
        jobId: job_id,
        createdAt: new Date().toISOString(),
        items,
        platforms: selectedPlatforms,
        location: selectedLocation,
      })

      nav(`/compare/${job_id}`, {
        state: {
          items,
          platforms: selectedPlatforms,
          location: selectedLocation,
          userInput: trimmed,
        },
      })
    } catch (err: any) {
      setToast({ kind: 'error', message: err?.message ?? 'Failed to start price comparison' })
    }
  }

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

  return (
    <div className="input-page">
      <h1 className="input-heading">What would you like to order today?</h1>

      <div className="input-textarea-wrapper">
        <textarea
          className="input-textarea"
          placeholder="Example: 2L milk, brown bread, eggs, apples…"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
        />

        <button
          type="button"
          className="input-enter-button"
          onClick={submit}
          aria-label="Enter"
        >
          ↑
        </button>
      </div>

      <div className="input-controls">
        <label className="input-label" htmlFor="location-select">
          Location
        </label>
        <select
          id="location-select"
          className="input-select"
          value={selectedLocation}
          onChange={(e) => setSelectedLocation(e.target.value)}
        >
          <option value="Pune">Pune</option>
          <option value="Delhi">Delhi</option>
        </select>

        <div className="platform-checkbox-row">
          <label className="platform-checkbox">
            <input
              type="checkbox"
              checked={selectedPlatforms.includes('zepto')}
              onChange={() => togglePlatform('zepto')}
            />
            <span>Zepto</span>
          </label>
          <label className="platform-checkbox">
            <input
              type="checkbox"
              checked={selectedPlatforms.includes('blinkit')}
              onChange={() => togglePlatform('blinkit')}
            />
            <span>Blinkit</span>
          </label>
          <label className="platform-checkbox">
            <input
              type="checkbox"
              checked={selectedPlatforms.includes('zomato')}
              onChange={() => togglePlatform('zomato')}
            />
            <span>Instamart</span>
          </label>
        </div>
      </div>
    </div>
  )
}

