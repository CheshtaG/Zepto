import type { ReactNode } from 'react'

export type ArbitrageSortMode = 'savings' | 'name'

export interface ArbitrageGridProps {
  sortMode: ArbitrageSortMode
  onSortModeChange: (mode: ArbitrageSortMode) => void
  children: ReactNode
}

export function ArbitrageGrid({ sortMode, onSortModeChange, children }: ArbitrageGridProps) {
  return (
    <section className="arb-grid-section">
      <div className="arb-grid-section__head">
        <h2 className="arb-grid-section__title">Arbitrage Grid</h2>
        <button
          type="button"
          className="arb-sort-pill"
          onClick={() => onSortModeChange(sortMode === 'savings' ? 'name' : 'savings')}
        >
          Sort by {sortMode === 'savings' ? 'Savings' : 'Name'}
        </button>
      </div>
      <div className="arb-grid-section__list">{children}</div>
    </section>
  )
}
