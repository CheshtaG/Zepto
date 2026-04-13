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

function formatInr(value: number): string {
  const rounded = Math.round(value * 100) / 100
  return rounded.toLocaleString('en-IN', {
    minimumFractionDigits: rounded % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  })
}

export interface ArbitrageDashboardRightProps {
  result?: JobResultResponse
  /** Platforms included in comparison math and cards (subset when toggled off). */
  platforms: Platform[]
  /** Per-platform visibility for banner logo toggles (all three keys expected). */
  platformEnabled: Record<ArbitragePlatformKey, boolean>
  onTogglePlatform: (key: ArbitragePlatformKey) => void
  isRunning: boolean
  /** Job finished with error — slots show unavailable instead of endless loading. */
  jobFailed?: boolean
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
        <div className="arb-product-card__best">
          <span className="arb-product-card__best-label">BEST PRICE FOUND</span>
          <span className="arb-product-card__best-price">
            <div className="arb-skeleton-line arb-skeleton-line--price arb-skeleton-line--in-card" />
          </span>
        </div>
      </div>
      <div className={`arb-product-card__pills arb-product-card__pills--cols-${n}`}>
        {Array.from({ length: n }).map((_, i) => (
          <div
            key={i}
            className="arb-platform-pill arb-platform-pill--skeleton"
            role="status"
            aria-label="Loading prices"
          >
            <div className="arb-platform-pill__label arb-skeleton-line arb-skeleton-line--xs" />
          </div>
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
  jobFailed = false,
  pendingQueries,
}: ArbitrageDashboardRightProps) {
  const visibleKeys = useMemo(() => platformsToArbitrageKeys(platforms), [platforms])
  const pillSkeletonCols = Math.min(Math.max(visibleKeys.length, 1), 3)

  const baseRows = useMemo(
    () =>
      mapJobResultToArbitrageRows(result, platforms, {
        jobInProgress: isRunning,
        jobFailed,
      }),
    [result, platforms, isRunning, jobFailed],
  )

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

  const platformSavingsText = useMemo(() => {
    const sourceRows = baseRows.length > 0 ? baseRows : dataRows
    if (!sourceRows.length) {
      return {
        zepto: '—',
        blinkit: '—',
        instamart: '—',
      } as Record<ArbitragePlatformKey, string>
    }

    const expectedRows = sourceRows.length
    const stats: Record<ArbitragePlatformKey, { total: number; covered: number }> = {
      zepto: { total: 0, covered: 0 },
      blinkit: { total: 0, covered: 0 },
      instamart: { total: 0, covered: 0 },
    }

    let bestBasketTotal = 0
    for (const row of sourceRows) {
      let rowMin: number | null = null
      for (const k of BANNER_PLATFORM_ORDER) {
        const price = row.platformPrices[k]
        if (price == null) continue
        if (rowMin == null || price < rowMin) rowMin = price
        stats[k].total += price
        stats[k].covered += 1
      }
      if (rowMin != null) bestBasketTotal += rowMin
    }

    const labels: Record<ArbitragePlatformKey, string> = {
      zepto: '—',
      blinkit: '—',
      instamart: '—',
    }
    for (const k of BANNER_PLATFORM_ORDER) {
      if (stats[k].covered < expectedRows) {
        labels[k] = `${stats[k].covered}/${expectedRows} priced`
        continue
      }
      // Requested basis: platform total - best-price basket total.
      const delta = stats[k].total - bestBasketTotal
      if (delta > 0) {
        labels[k] = `₹${formatInr(delta)} extra`
      } else if (delta < 0) {
        labels[k] = `₹${formatInr(Math.abs(delta))} saved`
      } else {
        labels[k] = '₹0'
      }
    }
    return labels
  }, [baseRows, dataRows])

  const totalItems = baseRows.length + pendingQueries.length
  const readyItems = baseRows.filter((row) => {
    const keys = row.activePlatforms.length ? row.activePlatforms : visibleKeys
    if (keys.length === 0) return false
    return keys.some((k) => {
      const slot = row.platformSlots?.[k]
      if (slot && slot !== 'loading') return true
      return row.platformPrices[k] != null
    })
  }).length
  const progressText = totalItems > 0 ? `${Math.min(readyItems, totalItems)} of ${totalItems}` : undefined

  return (
    <div className="arb-dashboard">
      <div className="arb-dashboard__sticky-head">
        <SavingsBanner
          amountLoading={showGridSkeleton}
          totalSavings={summary.totalSavings}
          percentImprovement={summary.percentVsMax}
          platformOrder={BANNER_PLATFORM_ORDER}
          enabled={platformEnabled}
          onTogglePlatform={onTogglePlatform}
          platformSavings={platformSavingsText}
        />
      </div>

      <ArbitrageGrid progressText={progressText}>
        {showEmpty ? (
          <div className="arb-empty-card">
            <div className="arb-empty-card__title">No matches found</div>
            <div className="arb-empty-card__subtitle">Try specifying brand or quantity in chat.</div>
          </div>
        ) : (
          <>
            {displayRows.map((row) => (
              <ProductArbitrageCard
                key={row.id}
                row={row}
                jobInProgress={isRunning}
                jobFailed={jobFailed}
              />
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
