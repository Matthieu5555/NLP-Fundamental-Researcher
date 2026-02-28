import { useState, useEffect } from 'react'
import { authFetch, API_URL } from '../utils/api'

function WatchlistDashboard({ onNavigateToSession }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadWatchlist()
  }, [])

  const loadWatchlist = async () => {
    setLoading(true)
    try {
      const response = await authFetch(`${API_URL}/api/watchlist`)
      const data = await response.json()
      setItems(data.items || [])
    } catch (err) {
      console.error('Failed to load watchlist:', err)
    } finally {
      setLoading(false)
    }
  }

  const removeItem = async (ticker) => {
    try {
      await authFetch(`${API_URL}/api/watchlist/${ticker}`, { method: 'DELETE' })
      setItems(items.filter(i => i.ticker !== ticker))
    } catch (err) {
      console.error('Failed to remove from watchlist:', err)
    }
  }

  const getGapColor = (gap) => {
    if (gap === null || gap === undefined) return 'text-tertiary'
    if (gap > 20) return 'text-accent-success-dark bg-accent-success-light'
    if (gap > 0) return 'text-accent-success'
    if (gap > -20) return 'text-accent-danger'
    return 'text-accent-danger-dark bg-accent-danger-light'
  }

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="w-6 h-6 border-2 spinner-brand rounded-full animate-spin mx-auto"></div>
        <p className="text-sm text-tertiary mt-3">Loading watchlist...</p>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-12 bg-surface-secondary rounded-lg">
        <svg className="w-12 h-12 mx-auto mb-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
        </svg>
        <p className="text-lg font-medium text-primary">Watchlist Empty</p>
        <p className="text-sm mt-2 text-tertiary">Add stocks to your watchlist from analysis results.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-bold text-primary">Watchlist</h3>
        <button
          onClick={loadWatchlist}
          className="text-sm text-tertiary hover:text-primary flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-tertiary">
              <th className="px-3 py-2 text-left font-semibold text-primary">Ticker</th>
              <th className="px-3 py-2 text-left font-semibold text-primary">Name</th>
              <th className="px-3 py-2 text-right font-semibold text-primary">Price</th>
              <th className="px-3 py-2 text-right font-semibold text-primary">Fair Value</th>
              <th className="px-3 py-2 text-right font-semibold text-primary">Gap</th>
              <th className="px-3 py-2 text-center font-semibold text-primary">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide">
            {items.map((item) => (
              <tr key={item.ticker} className="hover:bg-surface-secondary">
                <td className="px-3 py-3 font-semibold text-primary">{item.ticker}</td>
                <td className="px-3 py-3 text-secondary">{item.company_name || '-'}</td>
                <td className="px-3 py-3 text-right text-secondary">
                  {item.current_price ? `$${item.current_price.toFixed(2)}` : 'N/A'}
                </td>
                <td className="px-3 py-3 text-right text-secondary">
                  {item.last_fair_value ? `$${item.last_fair_value.toFixed(2)}` : 'N/A'}
                </td>
                <td className={`px-3 py-3 text-right font-medium ${getGapColor(item.fair_value_gap_pct)}`}>
                  {item.fair_value_gap_pct !== null ? `${item.fair_value_gap_pct > 0 ? '+' : ''}${item.fair_value_gap_pct}%` : 'N/A'}
                </td>
                <td className="px-3 py-3 text-center">
                  <div className="flex items-center justify-center gap-2">
                    {item.last_session_id && onNavigateToSession && (
                      <button
                        onClick={() => onNavigateToSession(item.last_session_id, item.ticker)}
                        className="text-xs px-2 py-1 rounded bg-surface-tertiary hover:bg-surface-card-hover text-secondary"
                        title="View analysis"
                      >
                        View
                      </button>
                    )}
                    <button
                      onClick={() => removeItem(item.ticker)}
                      className="text-xs px-2 py-1 rounded bg-accent-danger-light hover:opacity-80 text-accent-danger"
                      title="Remove from watchlist"
                    >
                      Remove
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default WatchlistDashboard
