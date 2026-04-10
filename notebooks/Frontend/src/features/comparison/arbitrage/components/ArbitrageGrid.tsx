import type { ReactNode } from 'react'

export interface ArbitrageGridProps {
  children: ReactNode
}

export function ArbitrageGrid({ children }: ArbitrageGridProps) {
  return (
    <section className="arb-grid-section">
      <div className="arb-grid-section__head">
        <h2 className="arb-grid-section__title">Arbitrage Grid</h2>
      </div>
      <div className="arb-grid-section__list">{children}</div>
    </section>
  )
}
