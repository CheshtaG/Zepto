import type { ArbitragePlatformKey } from '../types'
import { platformDisplayLabel } from '../types'

export interface PlatformPricePillProps {
  platform: ArbitragePlatformKey
  price: number | null
  isWinner: boolean
  isActive: boolean
  /** Matched listing snippet (title · qty) for transparency. */
  matchHint?: string
}

function formatPrice(price: number | null) {
  if (price == null) return '—'
  return `₹${price}`
}

export function PlatformPricePill({
  platform,
  price,
  isWinner,
  isActive,
  matchHint,
}: PlatformPricePillProps) {
  const label = platformDisplayLabel(platform)
  const classes = [
    'arb-platform-pill',
    isWinner ? 'arb-platform-pill--winner' : '',
    !isActive ? 'arb-platform-pill--inactive' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={classes}>
      <div className="arb-platform-pill__label">
        {label}
        {isWinner ? <span className="arb-platform-pill__winner-tag"> (WINNER)</span> : null}
      </div>
      <div className="arb-platform-pill__price">{formatPrice(price)}</div>
      {matchHint ? (
        <div className="arb-platform-pill__hint" title={matchHint}>
          {matchHint}
        </div>
      ) : null}
    </div>
  )
}
