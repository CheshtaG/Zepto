import { useEffect, useMemo, useState } from 'react'
import type { JobItemMatch, JobResultResponse, Platform } from '../../../services/api'

type Props = {
  result?: JobResultResponse
  additionalItems?: string[]
  platforms: Platform[]
  isRunning: boolean
}

const platformLabel: Record<Platform, string> = {
  zepto: 'Zepto',
  blinkit: 'Blinkit',
  zomato: 'Instamart',
  instamart: 'Instamart',
}

const platformAccents: Record<Platform, 'mint' | 'purple' | 'gradient'> = {
  blinkit: 'mint',
  zepto: 'purple',
  zomato: 'gradient',
  instamart: 'gradient',
}

function formatPrice(price: number | null) {
  if (price == null) return '—'
  return `₹${price}`
}

function ProductListingImage({ url }: { url: string | undefined }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    setFailed(false)
  }, [url])
  const src = url?.trim()
  if (!src || failed) {
    return <div className="compare-product-image-placeholder" aria-hidden="true" />
  }
  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
    />
  )
}

function getMatchForPlatform(item: JobResultResponse['items'][number], platform: Platform): JobItemMatch | undefined {
  const backendKey: Platform = platform === 'zomato' ? 'instamart' : platform
  return (
    item.matches.find((m) => m.platform === backendKey) ||
    (platform === 'zomato' ? item.matches.find((m) => m.platform === 'zomato') : undefined)
  )
}

function getBestPlatformForItem(item: JobResultResponse['items'][number], platforms: Platform[]) {
  const priced = platforms
    .map((p) => {
      const m = getMatchForPlatform(item, p)
      return { p, m }
    })
    .filter((x) => x.m && x.m.price != null && x.m.in_stock)

  if (!priced.length) return undefined
  priced.sort((a, b) => (a.m?.price ?? 0) - (b.m?.price ?? 0))
  return priced[0]?.p
}

export function PlatformResults({ result, additionalItems = [], platforms, isRunning }: Props) {
  const known = useMemo(() => {
    const s = new Set<string>()
    if (!result) return s
    for (const it of result.items) s.add(it.query.trim().toLowerCase())
    return s
  }, [result])

  const pendingOnly = useMemo(() => {
    return additionalItems.filter((item) => !known.has(item.trim().toLowerCase()))
  }, [additionalItems, known])

  const orderedPlatforms: Platform[] = (() => {
    const out: Platform[] = []
    if (platforms.includes('blinkit')) out.push('blinkit')
    if (platforms.includes('zepto')) out.push('zepto')
    if (platforms.includes('zomato')) out.push('zomato')
    else if (platforms.includes('instamart')) out.push('instamart')
    return out
  })()
  const cheapestPlatform = result?.summary?.cheapest_platform

  const isCheapestForSection = (sectionPlatform: Platform) => {
    if (!cheapestPlatform) return false
    // backend may return instamart while UI uses zomato alias
    if (sectionPlatform === 'zomato') return cheapestPlatform === 'instamart' || cheapestPlatform === 'zomato'
    return cheapestPlatform === sectionPlatform
  }

  return (
    <div
      className="compare-results-studio"
      style={{ gridTemplateColumns: `repeat(${Math.max(1, orderedPlatforms.length)}, minmax(0, 1fr))` }}
    >
      {orderedPlatforms.map((platform) => {
        const items = result?.items ?? []

        const matchesCount = items.reduce((acc, it) => {
          const m = getMatchForPlatform(it, platform)
          if (!m) return acc
          if (m.in_stock) return acc + 1
          return acc
        }, 0)

        const foundCount = items.reduce((acc, it) => {
          const m = getMatchForPlatform(it, platform)
          return m ? acc + 1 : acc
        }, 0)

        const badgeText =
          foundCount === 0 ? '—' : matchesCount === 0 ? 'Out of stock' : `${matchesCount} items found`

        const accent = platformAccents[platform]

        const bestByItem = new Map<string, Platform | undefined>()
        if (result) {
          for (const it of result.items) bestByItem.set(it.query, getBestPlatformForItem(it, platforms))
        }

        const hasAnyCard = Boolean(result) && (items.length > 0 || pendingOnly.length > 0)

        return (
          <section key={platform} className={`compare-platform-section ${accent}`}>
            <header className="compare-platform-header">
              <div className="compare-platform-header-left">
                <span className={`platform-accent-dot ${accent}`} aria-hidden="true" />
                <h3 className="compare-platform-title">{platformLabel[platform]}</h3>
              </div>
              <div className="compare-platform-badge">{badgeText}</div>
            </header>

            <div className="compare-platform-products">
              {isRunning && !result ? (
                <div className="compare-skeleton-list">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="compare-product-card skeleton" />
                  ))}
                </div>
              ) : result && items.length === 0 && pendingOnly.length === 0 ? (
                <div className="compare-empty-card">
                  <div className="compare-empty-title">No matches found</div>
                  <div className="compare-empty-subtitle">Try specifying brand/quantity</div>
                </div>
              ) : result && foundCount === 0 ? (
                <div className="compare-empty-card">
                  <div className="compare-empty-title">No matches found</div>
                  <div className="compare-empty-subtitle">Try specifying brand/quantity</div>
                </div>
              ) : (
                <>
                  {result?.items.map((it) => {
                    const m = getMatchForPlatform(it, platform)
                    const inStock = Boolean(m?.in_stock)
                    const price = m?.price ?? null
                    const isOutOfStock = !m || !inStock || price == null
                    const isCheapest = isCheapestForSection(platform)
                    const best = bestByItem.get(it.query)
                    const isBestMatch = best === platform && !isOutOfStock

                    const cardTone = isOutOfStock ? 'card--out-of-stock' : isBestMatch ? 'card--best-match' : ''

                    let badgeLabel: string | null = null
                    let badgeKind: 'oos' | 'best' | 'cheap' | null = null
                    if (isOutOfStock) {
                      badgeLabel = 'Out of stock'
                      badgeKind = 'oos'
                    } else if (isBestMatch) {
                      badgeLabel = 'Best match'
                      badgeKind = 'best'
                    } else if (isCheapest) {
                      badgeLabel = 'Cheapest'
                      badgeKind = 'cheap'
                    }

                    return (
                      <div key={it.query} className={`compare-product-card${cardTone ? ` ${cardTone}` : ''}`}>
                        <div
                          className="compare-product-name"
                          title={m?.listing_title?.trim() || it.query}
                        >
                          {(m?.listing_title && m.listing_title.trim()) || it.query}
                        </div>
                        <div className="compare-product-meta">{m?.quantity_label ?? '—'}</div>
                        <div className="compare-product-price-row">
                          <span className="compare-product-price">{formatPrice(price)}</span>
                        </div>
                        <div className="compare-product-image">
                          <ProductListingImage url={m?.image_url ?? m?.screenshot_url} />
                        </div>
                        <div className="compare-product-card-badge">
                          {badgeLabel ? (
                            <span
                              className={
                                badgeKind === 'oos'
                                  ? 'compare-product-badge-text compare-product-badge-text--oos'
                                  : badgeKind === 'best'
                                    ? 'compare-product-badge-text compare-product-badge-text--best'
                                    : 'compare-product-badge-text compare-product-badge-text--cheap'
                              }
                            >
                              {badgeLabel}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}

                  {pendingOnly.map((item) => (
                    <div key={`pending-${item}-${platform}`} className="compare-product-card skeleton">
                      <div className="compare-product-skeleton-lines" />
                    </div>
                  ))}

                  {!result && !isRunning && hasAnyCard && items.length === 0 && pendingOnly.length > 0 && (
                    <div className="compare-empty-card">
                      <div className="compare-empty-title">No matches found</div>
                      <div className="compare-empty-subtitle">Try specifying brand/quantity</div>
                    </div>
                  )}
                </>
              )}
            </div>
          </section>
        )
      })}
    </div>
  )
}

