import { useState, useEffect } from 'react'
import api from '../utils/api'

function StockPicker({ onAnalysisStart, disabled }) {
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Reset loading state when component becomes enabled again (after New Analysis)
  useEffect(() => {
    if (!disabled) {
      setLoading(false)
      setTicker('')
      setError(null)
    }
  }, [disabled])

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!ticker.trim()) {
      setError('Please enter a stock ticker')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await api.post('/api/analysis/start', {
        ticker: ticker.toUpperCase(),
        options: {
          include_moat: true,
          include_strategy: true,
          debate_rounds: 2
        }
      })

      const { session_id, ticker: confirmedTicker } = response.data
      onAnalysisStart(session_id, confirmedTicker)

      setTimeout(() => {
        window.scrollTo({ top: 400, behavior: 'smooth' })
      }, 100)

    } catch (err) {
      console.error('Analysis start error:', err)
      setError(err.response?.data?.error || 'Failed to start analysis')
      setLoading(false)
    }
  }

  return (
    <div className="bg-surface-elevated rounded-lg border p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-primary mb-2">
          Analyze a Stock
        </h2>
        <p className="text-secondary">
          Get comprehensive multi-agent analysis with strategic insights
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="ticker" className="block text-sm font-semibold text-primary mb-3">
            Stock Ticker Symbol
          </label>
          <div className="flex space-x-3">
            <input
              type="text"
              id="ticker"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              disabled={disabled || loading}
              placeholder="e.g., AAPL, MSFT, GOOGL"
              className="flex-1 px-5 py-4 text-lg border border-medium rounded-lg focus:ring-2 focus:ring-brand focus:border-brand disabled:bg-surface-tertiary disabled:cursor-not-allowed transition-colors"
              maxLength={10}
            />
            <button
              type="submit"
              disabled={disabled || loading || !ticker.trim()}
              className="px-8 py-4 text-white font-semibold rounded-lg disabled:bg-surface-tertiary disabled:text-muted disabled:cursor-not-allowed transition-colors text-lg bg-brand hover:bg-brand-dark"
            >
              {loading ? (
                <div className="flex items-center space-x-2">
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Analyzing...</span>
                </div>
              ) : disabled ? 'In Progress' : 'Analyze'}
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-accent-danger-light border border-accent-danger rounded-lg p-4">
            <p className="text-sm text-accent-danger-dark font-medium">{error}</p>
          </div>
        )}
      </form>

    </div>
  )
}

export default StockPicker
