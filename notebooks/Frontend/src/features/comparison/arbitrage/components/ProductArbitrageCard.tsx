import { useEffect, useState } from 'react'
import type { ArbitragePlatformKey, ArbitrageProductRow } from '../types'
import { PlatformPricePill } from './PlatformPricePill'

const ORDER: ArbitragePlatformKey[] = ['zepto', 'blinkit', 'instamart']

function ProductThumb({ url }: { url: string }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    setFailed(false)
  }, [url])
  const src = url?.trim()
  if (!src || failed) {
    return <div className="arb-product-thumb arb-product-thumb--placeholder" aria-hidden="true" />
  }
  return (
    <img
      className="arb-product-thumb"
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
    />
  )
}

function formatBest(price: number | null) {
  if (price == null) return '—'
  return `₹${price.toFixed(price % 1 === 0 ? 0 : 2)}`
}

export interface ProductArbitrageCardProps {
  row: ArbitrageProductRow
}

export function ProductArbitrageCard({ row }: ProductArbitrageCardProps) {
  const keys = ORDER.filter((k) => row.activePlatforms.includes(k))
  const cardClass =
    'arb-product-card' + (row.comparisonMode === 'weak_partial' ? ' arb-product-card--weak' : '')

  return (
    <article className={cardClass}>
      <div className="arb-product-card__top">
        <ProductThumb url={row.imageUrl} />
        <div className="arb-product-card__info">
          <h3 className="arb-product-card__name">{row.name}</h3>
          <p className="arb-product-card__subtitle">{row.subtitle}</p>
        </div>
        <div className="arb-product-card__best">
          <span className="arb-product-card__best-label">BEST PRICE FOUND</span>
          <span className="arb-product-card__best-price">{formatBest(row.bestPrice)}</span>
        </div>
      </div>
      <div
        className={`arb-product-card__pills arb-product-card__pills--cols-${Math.min(keys.length, 3) || 1}`}
      >
        {keys.map((platform) => (
          <PlatformPricePill
            key={platform}
            platform={platform}
            price={row.platformPrices[platform]}
            isWinner={row.winningPlatform === platform}
            isActive={row.activePlatforms.includes(platform)}
            matchHint={row.platformHints?.[platform]}
          />
        ))}
      </div>
    </article>
  )
}
