import type {
  JobComparisonMode,
  JobItemMatch,
  JobResultItem,
  JobResultResponse,
  Platform,
} from '../../../services/api'
import type {
  ArbitragePlatformKey,
  ArbitrageProductRow,
  ArbitrageSavingsSummary,
  PlatformSlotKind,
} from './types'
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

function hasListingSignal(m: JobItemMatch): boolean {
  return Boolean(
    (m.listing_title && m.listing_title.trim()) ||
      (m.quantity_label && m.quantity_label.trim()) ||
      (m.image_url && m.image_url.trim()) ||
      (m.screenshot_url && m.screenshot_url.trim()),
  )
}

/**
 * Map API match to pill UI: loading while job runs without usable data,
 * priced when in-stock with price, out_of_stock when listing exists but unavailable.
 */
export function derivePlatformSlot(
  m: JobItemMatch | undefined,
  opts: { jobInProgress: boolean; jobFailed: boolean; itemHasMatches: boolean },
): PlatformSlotKind {
  if (!opts.itemHasMatches) {
    return opts.jobInProgress ? 'loading' : 'unavailable'
  }
  if (!m) {
    return opts.jobInProgress ? 'loading' : 'unavailable'
  }
  if (m.price != null && m.in_stock) {
    return 'priced'
  }
  const listed = hasListingSignal(m)
  if (!m.in_stock && listed) {
    return 'out_of_stock'
  }
  if (opts.jobInProgress && !listed) {
    return 'loading'
  }
  if (!m.in_stock && !listed) {
    return 'unavailable'
  }
  if (m.in_stock && m.price == null) {
    return listed ? 'out_of_stock' : opts.jobInProgress ? 'loading' : 'unavailable'
  }
  return 'unavailable'
}

function firstMatchImage(item: JobResultItem): string {
  const fromMatches =
    item.matches.map((m) => m.image_url?.trim() || m.screenshot_url?.trim()).find(Boolean) || ''
  return fromMatches
}

/** Mirrors backend `normalize_query_title` for older API payloads. */
function normalizeQueryTitle(query: string): string {
  const s = query.trim().replace(/\s+/g, ' ')
  if (!s) return s
  return s
    .split(' ')
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : ''))
    .join(' ')
}

function pricedCountForRow(
  item: JobResultItem,
  keys: ArbitragePlatformKey[],
  selectedPlatforms: Platform[],
): number {
  let n = 0
  for (const p of selectedPlatforms) {
    const k = toArbitrageKey(p)
    if (!k || !keys.includes(k)) continue
    const m = getMatch(item, p)
    if (effectivePrice(m) != null) n += 1
  }
  return n
}

function inferComparisonMode(item: JobResultItem, priced: number): JobComparisonMode {
  if (item.comparison_mode) return item.comparison_mode
  if (priced < 2) return 'weak_partial'
  return 'exact'
}

function contributesToSavings(mode: JobComparisonMode, priced: number): boolean {
  if (mode === 'weak_partial') return false
  return priced >= 2
}

function platformForArbitrageKey(k: ArbitragePlatformKey): Platform {
  if (k === 'instamart') return 'instamart'
  return k
}

function compactMatchHint(m: JobItemMatch | undefined): string {
  if (!m) return ''
  const t = (m.listing_title || '').trim()
  const q = (m.quantity_label || '').trim()
  const s = t && q ? `${t} · ${q}` : t || q || ''
  return s.length > 58 ? `${s.slice(0, 55)}…` : s
}

export interface MapArbitrageOptions {
  jobInProgress: boolean
  jobFailed: boolean
}

/**
 * Build row-level arbitrage data from API job result.
 */
export function mapJobResultToArbitrageRows(
  result: JobResultResponse | undefined,
  selectedPlatforms: Platform[],
  options?: MapArbitrageOptions,
): ArbitrageProductRow[] {
  if (!result?.items?.length) return []

  const jobInProgress = options?.jobInProgress ?? false
  const jobFailed = options?.jobFailed ?? false

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

    const priced = pricedCountForRow(item, keys, selectedPlatforms)
    const comparisonMode = inferComparisonMode(item, priced)

    const pricedVals = keys
      .map((k) => platformPrices[k])
      .filter((v): v is number => v != null)

    let winningPlatform: ArbitragePlatformKey | null = null
    let bestPrice: number | null = null
    if (pricedVals.length) {
      const entries = keys
        .map((k) => ({ k, v: platformPrices[k] }))
        .filter((x): x is { k: ArbitragePlatformKey; v: number } => x.v != null)
      entries.sort((a, b) => a.v - b.v)
      winningPlatform = entries[0].k
      bestPrice = entries[0].v
    }

    let savingsAmount = 0
    if (contributesToSavings(comparisonMode, priced) && pricedVals.length >= 2) {
      savingsAmount = Math.max(...pricedVals) - Math.min(...pricedVals)
    }

    const name = item.canonical_title?.trim() || normalizeQueryTitle(item.query)
    const subtitle =
      item.canonical_subtitle?.trim() ||
      (comparisonMode === 'weak_partial' ? 'Limited comparable results found' : 'Compare across apps')
    const imageUrl = firstMatchImage(item)

    const platformHints: Partial<Record<ArbitragePlatformKey, string>> = {}
    for (const k of keys) {
      const hint = compactMatchHint(getMatch(item, platformForArbitrageKey(k)))
      if (hint) platformHints[k] = hint
    }

    const itemHasMatches = Array.isArray(item.matches) && item.matches.length > 0
    const platformSlots: Partial<Record<ArbitragePlatformKey, PlatformSlotKind>> = {}
    for (const k of keys) {
      const m = getMatch(item, platformForArbitrageKey(k))
      platformSlots[k] = derivePlatformSlot(m, {
        jobInProgress,
        jobFailed,
        itemHasMatches,
      })
    }

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
      comparisonMode,
      matchConfidence: item.match_confidence ?? null,
      platformHints: Object.keys(platformHints).length ? platformHints : undefined,
      platformSlots,
    })
  }

  return rows
}

/**
 * Recompute winner/savings/hints when the UI shows a subset of platforms (toggle filters).
 */
export function sliceRowToPlatforms(
  row: ArbitrageProductRow,
  keys: ArbitragePlatformKey[],
): ArbitrageProductRow {
  const platformPrices: Record<ArbitragePlatformKey, number | null> = {
    zepto: null,
    blinkit: null,
    instamart: null,
  }
  for (const k of keys) {
    platformPrices[k] = row.platformPrices[k]
  }

  const entries = keys
    .map((k) => ({ k, v: platformPrices[k] }))
    .filter((x): x is { k: ArbitragePlatformKey; v: number } => x.v != null)

  let winningPlatform: ArbitragePlatformKey | null = null
  let bestPrice: number | null = null
  if (entries.length) {
    entries.sort((a, b) => a.v - b.v)
    winningPlatform = entries[0].k
    bestPrice = entries[0].v
  }

  const priced = entries.map((e) => e.v)
  let savingsAmount = 0
  if (row.comparisonMode !== 'weak_partial' && priced.length >= 2) {
    savingsAmount = Math.max(...priced) - Math.min(...priced)
  }

  const platformHints = row.platformHints
    ? Object.fromEntries(
        Object.entries(row.platformHints).filter(([k]) =>
          keys.includes(k as ArbitragePlatformKey),
        ),
      )
    : undefined

  const platformSlots = row.platformSlots
    ? Object.fromEntries(
        Object.entries(row.platformSlots).filter(([k]) =>
          keys.includes(k as ArbitragePlatformKey),
        ),
      )
    : undefined

  return {
    ...row,
    platformPrices,
    winningPlatform,
    bestPrice,
    savingsAmount,
    activePlatforms: keys.length ? keys : row.activePlatforms,
    platformHints:
      platformHints && Object.keys(platformHints).length ? platformHints : undefined,
    platformSlots:
      platformSlots && Object.keys(platformSlots).length ? platformSlots : undefined,
  }
}

export function computeSavingsSummary(rows: ArbitrageProductRow[]): ArbitrageSavingsSummary {
  const eligible = rows.filter((r) => {
    if (r.comparisonMode === 'weak_partial') return false
    const vals = r.activePlatforms.map((k) => r.platformPrices[k]).filter((v): v is number => v != null)
    return vals.length >= 2
  })
  const totalSavings = eligible.reduce((s, r) => s + r.savingsAmount, 0)
  let sumMax = 0
  let comparable = 0
  for (const r of eligible) {
    const vals = r.activePlatforms.map((k) => r.platformPrices[k]).filter((v): v is number => v != null)
    if (vals.length >= 2) {
      sumMax += Math.max(...vals)
      comparable += 1
    }
  }
  const percentVsMax = sumMax > 0 ? Math.round((totalSavings / sumMax) * 1000) / 10 : 0
  return { totalSavings, percentVsMax, itemCount: comparable }
}
