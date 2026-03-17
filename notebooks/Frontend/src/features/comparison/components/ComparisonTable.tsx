import type { JobResultResponse } from '../../../services/api'

interface Props {
  result: JobResultResponse
}

export const ComparisonTable = ({ result }: Props) => {
  const getPrice = (item: (typeof result.items)[number], platform: 'zepto' | 'blinkit' | 'zomato') => {
    const match = item.matches.find((m) => m.platform === platform)
    return match && match.price != null ? `₹${match.price}` : '—'
  }

  return (
    <table className="comparison-table">
      <thead>
        <tr>
          <th rowSpan={2}>Product</th>
          <th colSpan={3}>Platform</th>
        </tr>
        <tr>
          <th>Zepto</th>
          <th>Blinkit</th>
          <th>Instamart</th>
        </tr>
      </thead>
      <tbody>
        {result.items.map((item) => (
          <tr key={item.query}>
            <td>{item.query}</td>
            <td>{getPrice(item, 'zepto')}</td>
            <td>{getPrice(item, 'blinkit')}</td>
            {/* Backend platform is "zomato", we label it as Instamart in UI for now */}
            <td>{getPrice(item, 'zomato')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

