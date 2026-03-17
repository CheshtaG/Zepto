import { useState, type KeyboardEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useComparisonJob } from '../features/comparison/hooks/useComparisonJob'
import { ComparisonTable } from '../features/comparison/components/ComparisonTable'

export const ComparePage = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const { result, status, isRunning, derivedProgress } = useComparisonJob(jobId)
  const [extraItems, setExtraItems] = useState('')

  if (!jobId) {
    return null
  }

  return (
    <div className="compare-page">
      {/* Left side: full-height textbox for extra items */}
      <section className="compare-left">
        <div className="compare-left-inner">
          <p className="compare-label">Add more items to compare:</p>
          <div className="compare-textarea-wrapper">
            <textarea
              className="compare-textarea"
              placeholder="Type new items here…"
              value={extraItems}
              onChange={(e) => setExtraItems(e.target.value)}
              onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  // future: hook this up to extend the comparison
                }
              }}
            />
            <button
              type="button"
              className="compare-enter-button"
              aria-label="Add items"
            >
              ↑
            </button>
          </div>
        </div>
      </section>

      {/* Right side: comparison table */}
      <section className="compare-right">
          <header style={{ marginBottom: 16 }}>
            <h2 style={{ color: '#000000' }}>Price comparison</h2>
            <p className="landing-subtitle" style={{ color: '#000000' }}>
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

          {!result && (
            <div className="results-empty">
              <div>
                <div>Waiting for results…</div>
                <div>Capturing screenshots &amp; extracting prices in the background.</div>
              </div>
            </div>
          )}

          {result && <ComparisonTable result={result} />}
        </section>
    </div>
  )
}

