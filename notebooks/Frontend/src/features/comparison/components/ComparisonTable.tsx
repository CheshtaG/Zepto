import type { JobResultResponse, Platform } from '../../../services/api'

interface Props {
  result: JobResultResponse
  additionalItems?: string[]
  platforms?: Platform[]
}

const platformLabel: Record<Platform, string> = {
  zepto: 'Zepto',
  blinkit: 'Blinkit',
  zomato: 'Instamart',
}

export const ComparisonTable = ({ result, additionalItems = [], platforms }: Props) => {
  const selectedPlatforms: Platform[] = platforms?.length ? platforms : ['zepto', 'blinkit', 'zomato']

  const getPrice = (item: (typeof result.items)[number], platform: Platform) => {
    const match = item.matches.find((m) => m.platform === platform)
    return match && match.price != null ? `₹${match.price}` : '—'
  }

  const known = new Set(result.items.map((item) => item.query.trim().toLowerCase()))
  const pendingOnly = additionalItems.filter((item) => !known.has(item.trim().toLowerCase()))

  return (
    <table className="comparison-table">
      <thead>
        <tr>
          <th rowSpan={2}>Product</th>
          <th colSpan={selectedPlatforms.length}>Platform</th>
        </tr>
        <tr>
          {selectedPlatforms.map((platform) => (
            <th key={platform}>{platformLabel[platform]}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {result.items.map((item) => (
          <tr key={item.query}>
            <td>{item.query}</td>
            {selectedPlatforms.map((platform) => (
              <td key={`${item.query}-${platform}`}>{getPrice(item, platform)}</td>
            ))}
          </tr>
        ))}
        {pendingOnly.map((item) => (
          <tr key={`pending-${item}`}>
            <td>{item}</td>
            {selectedPlatforms.map((platform) => (
              <td key={`pending-${item}-${platform}`}>—</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

