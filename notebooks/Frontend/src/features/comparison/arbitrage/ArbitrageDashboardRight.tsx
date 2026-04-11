import { useMemo } from 'react'
import type { JobResultResponse, Platform } from '../../../services/api'
import {
  mapJobResultToArbitrageRows,
  computeSavingsSummary,
  sliceRowToPlatforms,
} from './mapResultToArbitrage'
import { ARBITRAGE_MOCK_ROWS, type ArbitragePlatformKey } from './types'
import { SavingsBanner } from './components/SavingsBanner'
import { ArbitrageGrid } from './components/ArbitrageGrid'
import { ProductArbitrageCard } from './components/ProductArbitrageCard'
import './arbitrage-dashboard.css'

const BANNER_PLATFORM_ORDER: ArbitragePlatformKey[] = ['zepto', 'blinkit', 'instamart']

export interface ArbitrageDashboardRightProps {
  result?: JobResultResponse
  /** Platforms included in comparison math and cards (subset when toggled off). */
  platforms: Platform[]
  /** Per-platform visibility for banner logo toggles (all three keys expected). */
  platformEnabled: Record<ArbitragePlatformKey, boolean>
  onTogglePlatform: (key: ArbitragePlatformKey) => void
  isRunning: boolean
  pendingQueries: string[]
}

function platformsToArbitrageKeys(platforms: Platform[]): ArbitragePlatformKey[] {
  const keys: ArbitragePlatformKey[] = []
  if (platforms.includes('zepto')) keys.push('zepto')
  if (platforms.includes('blinkit')) keys.push('blinkit')
  if (platforms.includes('zomato') || platforms.includes('instamart')) keys.push('instamart')
  return keys.length ? keys : ['zepto', 'blinkit', 'instamart']
}

function ProductArbitrageCardSkeleton({ pillCount }: { pillCount: number }) {
  const n = Math.min(Math.max(pillCount, 1), 3)
  return (
    <div className="arb-product-card arb-product-card--skeleton" aria-hidden="true">
      <div className="arb-product-card__top">
        <div className="arb-product-thumb arb-product-thumb--placeholder" />
        <div className="arb-skeleton-lines">
          <div className="arb-skeleton-line arb-skeleton-line--lg" />
          <div className="arb-skeleton-line arb-skeleton-line--sm" />
        </div>
        <div className="arb-skeleton-best">
          <div className="arb-skeleton-line arb-skeleton-line--xs" />
          <div className="arb-skeleton-line arb-skeleton-line--price" />
        </div>
      </div>
      <div className={`arb-product-card__pills arb-product-card__pills--cols-${n}`}>
        {Array.from({ length: n }).map((_, i) => (
          <div key={i} className="arb-platform-pill arb-platform-pill--skeleton" />
        ))}
      </div>
    </div>
  )
}

export function ArbitrageDashboardRight({
  result,
  platforms,
  platformEnabled,
  onTogglePlatform,
  isRunning,
  pendingQueries,
}: ArbitrageDashboardRightProps) {
  const visibleKeys = useMemo(() => platformsToArbitrageKeys(platforms), [platforms])
  const pillSkeletonCols = Math.min(Math.max(visibleKeys.length, 1), 3)

  const baseRows = useMemo(() => mapJobResultToArbitrageRows(result, platforms), [result, platforms])

  const showEmpty =
    !isRunning && Boolean(result) && result!.items.length === 0 && pendingQueries.length === 0

  const showMock =
    baseRows.length === 0 && !isRunning && !showEmpty && pendingQueries.length === 0

  const dataRows = useMemo(() => {
    if (baseRows.length > 0) return baseRows
    if (showMock) return ARBITRAGE_MOCK_ROWS.map((r) => sliceRowToPlatforms(r, visibleKeys))
    return []
  }, [baseRows, showMock, visibleKeys])

  const summary = useMemo(() => {
    if (showEmpty) return { totalSavings: 0, percentVsMax: 0, itemCount: 0 }
    return computeSavingsSummary(dataRows)
  }, [dataRows, showEmpty])

  const displayRows = useMemo(() => {
    return [...dataRows].sort((a, b) => b.savingsAmount - a.savingsAmount || a.name.localeCompare(b.name))
  }, [dataRows])

  const showGridSkeleton = isRunning && baseRows.length === 0 && !showMock

  return (
    <div className="arb-dashboard">
      {showGridSkeleton ? (
        <div className="arb-savings-banner arb-savings-banner--skeleton" aria-hidden="true">
          <div className="arb-skeleton-line arb-skeleton-line--banner-title" />
          <div className="arb-skeleton-line arb-skeleton-line--banner-amount" />
        </div>
      ) : (
        <SavingsBanner
          totalSavings={summary.totalSavings}
          percentImprovement={summary.percentVsMax}
          platformOrder={BANNER_PLATFORM_ORDER}
          enabled={platformEnabled}
          onTogglePlatform={onTogglePlatform}
        />
      )}

      <ArbitrageGrid>
        {showEmpty ? (
          <div className="arb-empty-card">
            <div className="arb-empty-card__title">No matches found</div>
            <div className="arb-empty-card__subtitle">Try specifying brand or quantity in chat.</div>
          </div>
        ) : (
          <>
            {displayRows.map((row) => (
              <ProductArbitrageCard key={row.id} row={row} />
            ))}
            {showGridSkeleton
              ? Array.from({ length: 3 }).map((_, i) => (
                  <ProductArbitrageCardSkeleton key={`sk-${i}`} pillCount={pillSkeletonCols} />
                ))
              : null}
            {!showGridSkeleton &&
              pendingQueries.map((q) => (
                <ProductArbitrageCardSkeleton key={`pending-${q}`} pillCount={pillSkeletonCols} />
              ))}
          </>
        )}
      </ArbitrageGrid>
    </div>
  )
}
