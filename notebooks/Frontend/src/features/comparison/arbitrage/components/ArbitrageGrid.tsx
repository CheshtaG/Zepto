import type { ReactNode } from 'react'

export interface ArbitrageGridProps {
  children: ReactNode
  progressText?: string
}

export function ArbitrageGrid({ children, progressText }: ArbitrageGridProps) {
  return (
    <section className="arb-grid-section">
      <div className="arb-grid-section__head">
        <h2 className="arb-grid-section__title">Comparison Dashboard</h2>
        {progressText ? <span className="arb-grid-section__progress">{progressText}</span> : null}
      </div>
      <div className="arb-grid-section__list">{children}</div>
    </section>
  )
}
