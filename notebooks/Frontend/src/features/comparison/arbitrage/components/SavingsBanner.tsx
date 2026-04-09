import type { ArbitragePlatformKey } from '../types'

export interface SavingsBannerProps {
  totalSavings: number
  percentImprovement: number
  /** Platforms included in the job (for badge row). */
  platforms: ArbitragePlatformKey[]
}

function PlatformBadge({ platform }: { platform: ArbitragePlatformKey }) {
  const initial = platform === 'instamart' ? 'I' : platform[0].toUpperCase()
  return (
    <div className={`arb-savings-badge arb-savings-badge--${platform}`} title={platform}>
      <span>{initial}</span>
    </div>
  )
}

export function SavingsBanner({ totalSavings, percentImprovement, platforms }: SavingsBannerProps) {
  const display =
    totalSavings > 0
      ? totalSavings.toLocaleString('en-IN', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      : '0.00'
  const pct =
    percentImprovement > 0.05
      ? `(-${Math.abs(Math.round(percentImprovement * 10) / 10)}%)`
      : '(—)'

  return (
    <div className="arb-savings-banner">
      <div className="arb-savings-banner__main">
        <p className="arb-savings-banner__eyebrow">OPTIMIZED TOTAL SAVINGS</p>
        <div className="arb-savings-banner__row">
          <span className="arb-savings-banner__amount">₹{display}</span>
          <span className={`arb-savings-banner__pct${pct === '(—)' ? ' arb-savings-banner__pct--muted' : ''}`}>
            {pct}
          </span>
        </div>
      </div>
      <div className="arb-savings-banner__aside">
        <div className="arb-savings-banner__badges">
          {platforms.map((p) => (
            <PlatformBadge key={p} platform={p} />
          ))}
        </div>
        <p className="arb-savings-banner__caption">Best platform mix achieved</p>
      </div>
    </div>
  )
}
