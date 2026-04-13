import type { ArbitragePlatformKey } from '../types'
import { platformDisplayLabel } from '../types'

export interface SavingsBannerProps {
  totalSavings: number
  percentImprovement: number
  /** Fixed order for the three toggles (logos). */
  platformOrder: ArbitragePlatformKey[]
  enabled: Record<ArbitragePlatformKey, boolean>
  onTogglePlatform: (key: ArbitragePlatformKey) => void
  /** Initial comparison fetch: same purple banner; amount row uses a subtle shimmer (no card Lottie). */
  amountLoading?: boolean
  /** Shown under toggles while `amountLoading` (keeps layout parity with live banner). */
  loadingHint?: string
  platformSavings?: Partial<Record<ArbitragePlatformKey, string>>
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
  const label = platformDisplayLabel(platform)
  const mark =
    platform === 'instamart' ? (
      <span className="arb-savings-badge__mark-stack">
        <span className="arb-savings-badge__mark-line">Insta</span>
        <span className="arb-savings-badge__mark-line">mart</span>
      </span>
    ) : (
      label
    )

  return (
    <button
      type="button"
      className={`arb-savings-badge arb-savings-badge--${platform} arb-savings-badge--toggle${
        enabled ? '' : ' arb-savings-badge--inactive'
      }`}
      aria-pressed={enabled}
      aria-label={`${label}: ${enabled ? 'shown' : 'hidden'}. Click to toggle.`}
      title={`${label} (${enabled ? 'on' : 'off'})`}
      onClick={() => onToggle(platform)}
    >
      <span className="arb-savings-badge__mark" aria-hidden="true">
        {mark}
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
  amountLoading = false,
  loadingHint = 'Fetching prices across platforms…',
  platformSavings = {},
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
    <div className={`arb-savings-banner${amountLoading ? ' arb-savings-banner--amount-loading' : ''}`}>
      <div className="arb-savings-banner__main">
        <p className="arb-savings-banner__eyebrow">OPTIMIZED TOTAL SAVINGS</p>
        <div className="arb-savings-banner__amount-block">
          {amountLoading ? (
            <div
              className="arb-savings-banner__amount-loading-wrap"
              role="status"
              aria-live="polite"
              aria-label="Loading optimized total savings"
            >
              <div className="arb-savings-banner__amount-skeleton" aria-hidden="true" />
            </div>
          ) : (
            <span className="arb-savings-banner__amount">₹{display}</span>
          )}
          <span
            className={`arb-savings-banner__pct${
              amountLoading || pct === '(—)' ? ' arb-savings-banner__pct--muted' : ''
            }`}
          >
            {pct}
          </span>
        </div>
      </div>
      <div className="arb-savings-banner__aside">
        <div className="arb-savings-banner__badges">
          {platformOrder.map((p) => (
            <div key={p} className="arb-savings-badge-stack">
              <PlatformLogoToggle
                platform={p}
                enabled={enabled[p] !== false}
                onToggle={onTogglePlatform}
              />
              <span className="arb-savings-badge-stack__metric">{platformSavings[p] ?? '—'}</span>
            </div>
          ))}
        </div>
        <p className="arb-savings-banner__caption">
          {amountLoading ? loadingHint : 'Best platform mix achieved'}
        </p>
      </div>
    </div>
  )
}
