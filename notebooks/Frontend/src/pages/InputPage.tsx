import { useState, KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { useAppStore } from '../store/appStore'

export const InputPage = () => {
  const [value, setValue] = useState('')
  const nav = useNavigate()
  const { lastPlatforms, lastLocation, addJobHistory, setToast } = useAppStore()

  const submit = async () => {
    const trimmed = value.trim()
    if (!trimmed) return

    const items = trimmed
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean)

    if (!items.length) return

    try {
      const { job_id } = await api.createJob({
        items,
        platforms: lastPlatforms,
        location: lastLocation,
      })

      addJobHistory({
        jobId: job_id,
        createdAt: new Date().toISOString(),
        items,
        platforms: lastPlatforms,
        location: lastLocation,
      })

      nav(`/compare/${job_id}`, { state: { items, platforms: lastPlatforms, location: lastLocation } })
    } catch (err: any) {
      setToast({ kind: 'error', message: err?.message ?? 'Failed to start price comparison' })
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="simple-page">
      <div className="landing-content">
        <p className="landing-subtitle">
          Paste or type all the items you need from platforms like Blinkit, Zepto and Zomato.
        </p>

        <div className="landing-input-wrapper">
          <textarea
            className="landing-textarea"
            placeholder="Example: 2L milk, brown bread, eggs, apples…"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
          />

          <button
            type="button"
            className="landing-enter-button"
            onClick={submit}
            aria-label="Enter"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  )
}

