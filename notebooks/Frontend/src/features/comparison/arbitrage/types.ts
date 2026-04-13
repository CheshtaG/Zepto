import type { JobComparisonMode, Platform } from '../../../services/api'

/** Canonical keys for the three-column UI (Instamart only, not zomato alias). */
export type ArbitragePlatformKey = 'zepto' | 'blinkit' | 'instamart'

/** Per-column UI state for a platform (VDOM/API lifecycle). */
export type PlatformSlotKind = 'loading' | 'priced' | 'out_of_stock' | 'unavailable'

export interface ArbitrageProductRow {
  id: string
  name: string
  subtitle: string
  imageUrl: string
  bestPrice: number | null
  winningPlatform: ArbitragePlatformKey | null
  platformPrices: Record<ArbitragePlatformKey, number | null>
  /** Rupee saving vs worst in-stock price on this row (0 if not comparable). */
  savingsAmount: number
  /** Selected platforms for this job (subset of three). */
  activePlatforms: ArbitragePlatformKey[]
  comparisonMode: JobComparisonMode
  matchConfidence?: number | null
  /** Matched listing title · quantity per column (from API matches). */
  platformHints?: Partial<Record<ArbitragePlatformKey, string>>
  /** Per-platform display: loading (Lottie), priced, out of stock, or unavailable. */
  platformSlots?: Partial<Record<ArbitragePlatformKey, PlatformSlotKind>>
}

export interface ArbitrageSavingsSummary {
  totalSavings: number
  percentVsMax: number
  itemCount: number
}

const allPricedSlots: Partial<Record<ArbitragePlatformKey, PlatformSlotKind>> = {
  zepto: 'priced',
  blinkit: 'priced',
  instamart: 'priced',
}

export const ARBITRAGE_MOCK_ROWS: ArbitrageProductRow[] = [
  {
    id: 'mock-1',
    name: 'Amul Taaza Toned Milk',
    subtitle: '500 ml · Amul',
    imageUrl: '',
    bestPrice: 28,
    winningPlatform: 'zepto',
    platformPrices: { zepto: 28, blinkit: 32, instamart: 31 },
    savingsAmount: 4,
    activePlatforms: ['zepto', 'blinkit', 'instamart'],
    comparisonMode: 'exact',
    platformSlots: { ...allPricedSlots },
  },
  {
    id: 'mock-2',
    name: 'Harvest Gold Brown Bread',
    subtitle: '400 g · Harvest Gold',
    imageUrl: '',
    bestPrice: 45,
    winningPlatform: 'blinkit',
    platformPrices: { zepto: 48, blinkit: 45, instamart: 47 },
    savingsAmount: 3,
    activePlatforms: ['zepto', 'blinkit', 'instamart'],
    comparisonMode: 'exact',
    platformSlots: { ...allPricedSlots },
  },
]

/** Map UI Platform to arbitrage column key */
export function toArbitrageKey(p: Platform): ArbitragePlatformKey | null {
  if (p === 'zomato' || p === 'instamart') return 'instamart'
  if (p === 'zepto') return 'zepto'
  if (p === 'blinkit') return 'blinkit'
  return null
}

export function platformDisplayLabel(key: ArbitragePlatformKey): string {
  switch (key) {
    case 'zepto':
      return 'Zepto'
    case 'blinkit':
      return 'Blinkit'
    case 'instamart':
      return 'Instamart'
    default:
      return key
  }
}
