import { LoadingDotsBlue } from '../../../../components/LoadingDotsBlue'
import type { ArbitragePlatformKey, PlatformSlotKind } from '../types'
import { platformDisplayLabel } from '../types'

export interface PlatformPricePillProps {
  platform: ArbitragePlatformKey
  price: number | null
  isWinner: boolean
  isActive: boolean
  /** Matched listing snippet (title · qty) for transparency. */
  matchHint?: string
  slot: PlatformSlotKind
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
  slot,
}: PlatformPricePillProps) {
  const label = platformDisplayLabel(platform)
  const showWinnerTag = isWinner && slot === 'priced'
  const classes = [
    'arb-platform-pill',
    isWinner && slot === 'priced' ? 'arb-platform-pill--winner' : '',
    !isActive ? 'arb-platform-pill--inactive' : '',
    slot === 'out_of_stock' ? 'arb-platform-pill--oos' : '',
    slot === 'unavailable' ? 'arb-platform-pill--na' : '',
    slot === 'loading' ? 'arb-platform-pill--loading' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={classes}>
      <div className="arb-platform-pill__label">
        {label}
        {showWinnerTag ? <span className="arb-platform-pill__winner-tag"> (WINNER)</span> : null}
      </div>
      <div
        className="arb-platform-pill__price"
        role={slot === 'loading' ? 'status' : undefined}
        aria-label={slot === 'loading' ? 'Loading price' : undefined}
      >
        {slot === 'loading' ? (
          <LoadingDotsBlue
            className="arb-platform-pill__lottie"
            width={96}
            height={36}
            visualScale={4}
          />
        ) : slot === 'out_of_stock' ? (
          <span className="arb-platform-pill__status-text">Out of stock</span>
        ) : slot === 'unavailable' ? (
          <span className="arb-platform-pill__status-text arb-platform-pill__status-text--unavailable">
            No price
          </span>
        ) : (
          formatPrice(price)
        )}
      </div>
      {matchHint && slot === 'priced' ? (
        <div className="arb-platform-pill__hint" title={matchHint}>
          {matchHint}
        </div>
      ) : matchHint && (slot === 'out_of_stock' || slot === 'unavailable') ? (
        <div className="arb-platform-pill__hint" title={matchHint}>
          {matchHint}
        </div>
      ) : null}
    </div>
  )
}
