/**
 * UsageStats Component
 *
 * Displays user's API usage statistics including:
 * - Total requests and costs
 * - Usage breakdown by category
 * - Recent activity summary
 */

import { useState, useEffect } from 'react'
import api from '../utils/api'

export default function UsageStats({ isOpen, onClose }) {
  const [stats, setStats] = useState(null)
  const [daily, setDaily] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!isOpen) return

    const fetchUsage = async () => {
      setLoading(true)
      setError(null)

      try {
        const [statsRes, dailyRes] = await Promise.all([
          api.get('/api/usage/stats'),
          api.get('/api/usage/daily?days=7'),
        ])

        setStats(statsRes.data)
        setDaily(dailyRes.data.daily || [])
      } catch (err) {
        console.error('Failed to fetch usage:', err)
        setError('Failed to load usage data')
      } finally {
        setLoading(false)
      }
    }

    fetchUsage()
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-surface-elevated rounded-lg shadow-lg border w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="border-b bg-surface-secondary px-6 py-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-primary">Usage Statistics</h2>
            <button
              onClick={onClose}
              className="text-muted hover:text-secondary transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
            </div>
          ) : error ? (
            <div className="text-center py-8 text-accent-danger">{error}</div>
          ) : stats ? (
            <div className="space-y-6">
              {/* Current Month Summary */}
              <div>
                <h3 className="text-sm font-medium text-tertiary uppercase tracking-wide mb-3">
                  Last 30 Days
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-surface-secondary rounded-lg p-4">
                    <p className="text-2xl font-bold text-primary">
                      {stats.current_month.requests}
                    </p>
                    <p className="text-sm text-secondary">API Requests</p>
                  </div>
                  <div className="bg-surface-secondary rounded-lg p-4">
                    <p className="text-2xl font-bold text-brand">
                      ${stats.current_month.cost_usd.toFixed(2)}
                    </p>
                    <p className="text-sm text-secondary">Total Cost</p>
                  </div>
                  <div className="bg-surface-secondary rounded-lg p-4">
                    <p className="text-2xl font-bold text-primary">
                      {(stats.current_month.tokens / 1000).toFixed(1)}k
                    </p>
                    <p className="text-sm text-secondary">Tokens Used</p>
                  </div>
                  <div className="bg-surface-secondary rounded-lg p-4">
                    <p className="text-2xl font-bold text-accent-success">
                      {stats.current_month.cache_hit_rate}%
                    </p>
                    <p className="text-sm text-secondary">Cache Hit Rate</p>
                  </div>
                </div>
              </div>

              {/* All Time Summary */}
              <div>
                <h3 className="text-sm font-medium text-tertiary uppercase tracking-wide mb-3">
                  All Time
                </h3>
                <div className="bg-surface-secondary rounded-lg p-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="text-lg font-semibold text-primary">
                        {stats.all_time.requests} requests
                      </p>
                      <p className="text-sm text-secondary">
                        ${stats.all_time.cost_usd.toFixed(2)} total cost
                      </p>
                    </div>
                    {stats.all_time.top_tickers?.length > 0 && (
                      <div className="text-right">
                        <p className="text-xs text-tertiary mb-1">Top Tickers</p>
                        <div className="flex gap-1 flex-wrap justify-end">
                          {stats.all_time.top_tickers.slice(0, 3).map((ticker) => (
                            <span
                              key={ticker}
                              className="px-2 py-0.5 text-xs font-medium bg-accent-warning-light text-accent-warning-dark rounded"
                            >
                              {ticker}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Daily Activity */}
              {daily.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-tertiary uppercase tracking-wide mb-3">
                    Recent Activity
                  </h3>
                  <div className="space-y-2">
                    {daily.slice(0, 5).map((day) => (
                      <div
                        key={day.date}
                        className="flex justify-between items-center py-2"
                      >
                        <span className="text-sm text-secondary">
                          {new Date(day.date).toLocaleDateString('en-US', {
                            weekday: 'short',
                            month: 'short',
                            day: 'numeric',
                          })}
                        </span>
                        <div className="flex gap-4 text-sm">
                          <span className="text-primary">
                            {day.requests} requests
                          </span>
                          <span className="text-brand font-medium">
                            ${day.cost_usd.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-tertiary">
              No usage data available yet
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t bg-surface-secondary px-6 py-4">
          <p className="text-xs text-tertiary text-center">
            Usage data is tracked for cost attribution and monitoring
          </p>
        </div>
      </div>
    </div>
  )
}
