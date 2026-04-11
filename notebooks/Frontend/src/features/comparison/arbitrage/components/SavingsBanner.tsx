import type { ArbitragePlatformKey } from '../types'
import { ARBITRAGE_PLATFORM_LOGO_SRC } from '../platformLogos'
import { platformDisplayLabel } from '../types'

export interface SavingsBannerProps {
  totalSavings: number
  percentImprovement: number
  /** Fixed order for the three toggles (logos). */
  platformOrder: ArbitragePlatformKey[]
  enabled: Record<ArbitragePlatformKey, boolean>
  onTogglePlatform: (key: ArbitragePlatformKey) => void
}

function PlatformLogoToggle({
  platform,
  enabled,
  onToggle,
}: {
  platform: ArbitragePlatformKey
  enabled: boolean
  onToggle: (key: ArbitragePlatformKey) => void
}) {
  const src = ARBITRAGE_PLATFORM_LOGO_SRC[platform]

  return (
    <button
      type="button"
      className={`arb-savings-badge arb-savings-badge--${platform} arb-savings-badge--toggle${
        enabled ? '' : ' arb-savings-badge--inactive'
      }`}
      aria-pressed={enabled}
      aria-label={`${platformDisplayLabel(platform)}: ${enabled ? 'shown' : 'hidden'}. Click to toggle.`}
      title={`${platformDisplayLabel(platform)} (${enabled ? 'on' : 'off'})`}
      onClick={() => onToggle(platform)}
    >
      <span className="arb-savings-badge__logo-wrap" aria-hidden="true">
        <img src={src} alt="" className="arb-savings-badge__logo" />
      </span>
    </button>
  )
}

export function SavingsBanner({
  totalSavings,
  percentImprovement,
  platformOrder,
  enabled,
  onTogglePlatform,
}: SavingsBannerProps) {
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
          {platformOrder.map((p) => (
            <PlatformLogoToggle
              key={p}
              platform={p}
              enabled={enabled[p] !== false}
              onToggle={onTogglePlatform}
            />
          ))}
        </div>
        <p className="arb-savings-banner__caption">Best platform mix achieved</p>
      </div>
    </div>
  )
}
