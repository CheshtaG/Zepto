import type { ArbitragePlatformKey } from './types'
import blinkitLogo from '../../../assets/platforms/blinkit.png'
import instamartLogo from '../../../assets/platforms/instamart.png'
import zeptoLogo from '../../../assets/platforms/zepto.webp'

/** Bundled brand marks (sources: `src/assets/platforms/`). */
export const ARBITRAGE_PLATFORM_LOGO_SRC: Record<ArbitragePlatformKey, string> = {
  zepto: zeptoLogo,
  blinkit: blinkitLogo,
  instamart: instamartLogo,
}
