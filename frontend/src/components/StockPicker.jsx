import { useState } from 'react'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

function StockPicker({ onAnalysisStart, disabled }) {
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!ticker.trim()) {
      setError('Please enter a stock ticker')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(`${API_URL}/api/analysis/start`, {
        ticker: ticker.toUpperCase(),
        options: {
          include_moat: true,
          include_swot: true,
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
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800 mb-2">
          Analyze a Stock
        </h2>
        <p className="text-slate-600">
          Get comprehensive multi-agent analysis with strategic insights
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="ticker" className="block text-sm font-semibold text-slate-700 mb-3">
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
              className="flex-1 px-5 py-4 text-lg border-2 border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-slate-100 disabled:cursor-not-allowed transition-all"
              maxLength={10}
            />
            <button
              type="submit"
              disabled={disabled || loading || !ticker.trim()}
              className="px-8 py-4 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-semibold rounded-lg shadow-md hover:shadow-lg disabled:from-slate-400 disabled:to-slate-500 disabled:cursor-not-allowed transition-all duration-200 text-lg"
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
          <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-700 font-medium">{error}</p>
          </div>
        )}
      </form>

    </div>
  )
}

export default StockPicker
