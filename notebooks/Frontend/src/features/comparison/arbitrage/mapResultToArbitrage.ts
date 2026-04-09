import type { JobItemMatch, JobResultItem, JobResultResponse, Platform } from '../../../services/api'
import type { ArbitragePlatformKey, ArbitrageProductRow, ArbitrageSavingsSummary } from './types'
import { toArbitrageKey } from './types'

function getMatch(item: JobResultItem, platform: Platform): JobItemMatch | undefined {
  const backendKey: Platform = platform === 'zomato' ? 'instamart' : platform
  return (
    item.matches.find((m) => m.platform === backendKey) ||
    (platform === 'zomato' ? item.matches.find((m) => m.platform === 'zomato') : undefined)
  )
}

function effectivePrice(m: JobItemMatch | undefined): number | null {
  if (!m || !m.in_stock || m.price == null) return null
  return m.price
}

/**
 * Build row-level arbitrage data from API job result.
 */
export function mapJobResultToArbitrageRows(
  result: JobResultResponse | undefined,
  selectedPlatforms: Platform[],
): ArbitrageProductRow[] {
  if (!result?.items?.length) return []

  const keys: ArbitragePlatformKey[] = []
  if (selectedPlatforms.includes('zepto')) keys.push('zepto')
  if (selectedPlatforms.includes('blinkit')) keys.push('blinkit')
  if (selectedPlatforms.includes('zomato') || selectedPlatforms.includes('instamart')) keys.push('instamart')

  const rows: ArbitrageProductRow[] = []

  for (const item of result.items) {
    const platformPrices: Record<ArbitragePlatformKey, number | null> = {
      zepto: null,
      blinkit: null,
      instamart: null,
    }

    for (const p of selectedPlatforms) {
      const k = toArbitrageKey(p)
      if (!k) continue
      const m = getMatch(item, p)
      platformPrices[k] = effectivePrice(m)
    }

    const priced = keys
      .map((k) => ({ k, v: platformPrices[k] }))
      .filter((x): x is { k: ArbitragePlatformKey; v: number } => x.v != null)

    let winningPlatform: ArbitragePlatformKey | null = null
    let bestPrice: number | null = null
    if (priced.length) {
      priced.sort((a, b) => a.v - b.v)
      winningPlatform = priced[0].k
      bestPrice = priced[0].v
    }

    const values = keys.map((k) => platformPrices[k]).filter((v): v is number => v != null)
    let savingsAmount = 0
    if (values.length >= 2) {
      savingsAmount = Math.max(...values) - Math.min(...values)
    }

    const winnerUiPlatform: Platform | undefined = winningPlatform
      ? winningPlatform === 'instamart'
        ? selectedPlatforms.includes('zomato')
          ? 'zomato'
          : selectedPlatforms.includes('instamart')
            ? 'instamart'
            : 'zomato'
        : winningPlatform
      : undefined
    const winnerMatch = winnerUiPlatform ? getMatch(item, winnerUiPlatform) : undefined

    const titleFromWinner = winnerMatch?.listing_title?.trim()
    const anyTitle = item.matches.map((m) => m.listing_title?.trim()).find(Boolean)
    const name = titleFromWinner || anyTitle || item.query

    const subtitleParts = [winnerMatch?.quantity_label].filter(Boolean)
    const subtitle = subtitleParts.length ? String(subtitleParts[0]) : 'Compare across apps'

    const imageUrl =
      winnerMatch?.image_url?.trim() ||
      winnerMatch?.screenshot_url?.trim() ||
      item.matches.map((m) => m.image_url || m.screenshot_url).find(Boolean) ||
      ''

    rows.push({
      id: item.query,
      name,
      subtitle,
      imageUrl,
      bestPrice,
      winningPlatform,
      platformPrices,
      savingsAmount,
      activePlatforms: keys.length ? keys : ['zepto', 'blinkit', 'instamart'],
    })
  }

  return rows
}

export function computeSavingsSummary(rows: ArbitrageProductRow[]): ArbitrageSavingsSummary {
  const totalSavings = rows.reduce((s, r) => s + r.savingsAmount, 0)
  let sumMax = 0
  let comparable = 0
  for (const r of rows) {
    const vals = r.activePlatforms.map((k) => r.platformPrices[k]).filter((v): v is number => v != null)
    if (vals.length >= 2) {
      sumMax += Math.max(...vals)
      comparable += 1
    }
  }
  const percentVsMax = sumMax > 0 ? Math.round((totalSavings / sumMax) * 1000) / 10 : 0
  return { totalSavings, percentVsMax, itemCount: comparable }
}
