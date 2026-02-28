import { useState } from 'react'

/**
 * Cost badge with expandable breakdown dropdown.
 * Shows total analysis + chat cost, with per-agent detail on click.
 */
function CostBreakdown({ costUsd, chatCost, costBreakdown }) {
  const [showBreakdown, setShowBreakdown] = useState(false)

  const total = (costUsd || 0) + chatCost
  if (total === 0) return null

  return (
    <div className="relative">
      <button
        onClick={() => setShowBreakdown(!showBreakdown)}
        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-accent-success-light text-accent-success-dark hover:opacity-80 transition-colors cursor-pointer"
      >
        Cost: ${total.toFixed(4)}
        {costBreakdown && (
          <svg className={`w-3 h-3 ml-1 transition-transform ${showBreakdown ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {showBreakdown && costBreakdown && (
        <div className="absolute right-0 mt-2 w-64 bg-surface-elevated rounded-lg shadow-lg border z-50 p-3">
          <h4 className="text-xs font-semibold text-secondary uppercase tracking-wide mb-2">Cost Breakdown</h4>
          <div className="space-y-1.5">
            {Object.entries(costBreakdown).map(([name, cost]) => (
              <div key={name} className="flex justify-between items-center text-xs">
                <span className="text-secondary">{name}</span>
                <span className="font-medium text-primary">${cost.toFixed(4)}</span>
              </div>
            ))}
            {chatCost > 0 && (
              <div className="flex justify-between items-center text-xs">
                <span className="text-secondary">Chat Conversations</span>
                <span className="font-medium text-primary">${chatCost.toFixed(4)}</span>
              </div>
            )}
            <div className="border-t mt-2 pt-2 flex justify-between items-center text-xs font-semibold">
              <span className="text-primary">Total</span>
              <span className="text-accent-success-dark">${total.toFixed(4)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CostBreakdown
