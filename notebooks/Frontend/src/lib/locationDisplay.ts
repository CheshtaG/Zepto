import type { LocationPayload } from '../services/api'

/**
 * Single label for the header pill: store string, then payload name / city+pincode.
 */
export function formatLocationHeaderLabel(
  lastLocation?: string | null,
  payload?: LocationPayload | null,
): string {
  const trimmed = lastLocation?.trim()
  if (trimmed) return trimmed

  if (payload) {
    const name = payload.name?.trim()
    if (name) return name
    const city = payload.city?.trim()
    const pc = payload.pincode?.trim()
    const cityPin = [city, pc].filter(Boolean).join(', ')
    if (cityPin) return cityPin
    if (city) return city
    if (pc) return pc
  }

  return ''
}
