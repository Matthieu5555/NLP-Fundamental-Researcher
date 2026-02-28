function ScenarioAnalysis({ scenarios }) {
  if (!scenarios) return null

  const { bull, base, bear, weighted_fair_value, current_price, weighted_upside_pct } = scenarios
  const isUndervalued = weighted_upside_pct > 0

  const fmtB = (v) => {
    if (!v) return 'N/A'
    if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
    return `$${(v / 1e9).toFixed(1)}B`
  }

  const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : 'N/A'

  const scenarioCases = [
    { ...bull, color: 'success', icon: '\u25B2' },
    { ...base, color: 'warning', icon: '\u25CF' },
    { ...bear, color: 'danger', icon: '\u25BC' },
  ]

  const colorMap = {
    success: { bg: 'bg-accent-success-light', border: 'border-accent-success', text: 'text-accent-success-dark', badge: 'bg-accent-success-light' },
    warning: { bg: 'bg-accent-warning-light', border: 'border-accent-warning', text: 'text-accent-warning-dark', badge: 'bg-accent-warning-light' },
    danger: { bg: 'bg-accent-danger-light', border: 'border-accent-danger', text: 'text-accent-danger-dark', badge: 'bg-accent-danger-light' },
  }

  return (
    <div className="space-y-6">
      {/* Weighted Fair Value Banner */}
      <div className={`rounded-lg p-6 border ${isUndervalued ? 'bg-accent-success-light border-accent-success' : 'bg-accent-danger-light border-accent-danger'}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-secondary">Probability-Weighted Fair Value</p>
            <p className={`text-3xl font-bold ${isUndervalued ? 'text-accent-success-dark' : 'text-accent-danger-dark'}`}>
              ${weighted_fair_value?.toFixed(2)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium text-secondary">Current Price</p>
            <p className="text-2xl font-semibold text-primary">${current_price?.toFixed(2)}</p>
          </div>
          <div className={`px-4 py-2 rounded-lg ${isUndervalued ? 'bg-accent-success-light' : 'bg-accent-danger-light'}`}>
            <p className={`text-lg font-bold ${isUndervalued ? 'text-accent-success-dark' : 'text-accent-danger-dark'}`}>
              {isUndervalued ? '+' : ''}{weighted_upside_pct?.toFixed(1)}%
            </p>
            <p className="text-xs text-secondary">{isUndervalued ? 'Upside' : 'Downside'}</p>
          </div>
        </div>
      </div>

      {/* Scenario Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {scenarioCases.map((scenario) => {
          const c = colorMap[scenario.color]
          return (
            <div key={scenario.name} className={`rounded-lg p-4 border ${c.bg} ${c.border}`}>
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`text-lg ${c.text}`}>{scenario.icon}</span>
                  <h5 className={`text-lg font-bold ${c.text}`}>{scenario.name}</h5>
                </div>
                <span className={`px-2 py-1 rounded text-xs font-semibold ${c.badge} ${c.text}`}>
                  {(scenario.probability * 100).toFixed(0)}%
                </span>
              </div>

              {/* Fair value */}
              <div className="mb-3">
                <p className="text-xs text-tertiary">Fair Value</p>
                <p className={`text-2xl font-bold ${c.text}`}>${scenario.fair_value?.toFixed(2)}</p>
                <p className={`text-sm font-medium ${scenario.upside_pct > 0 ? 'text-accent-success' : 'text-accent-danger'}`}>
                  {scenario.upside_pct > 0 ? '+' : ''}{scenario.upside_pct?.toFixed(1)}%
                </p>
              </div>

              {/* Year 5 Revenue */}
              {scenario.revenue_yr5 > 0 && (
                <div className="mb-3">
                  <p className="text-xs text-tertiary">Year 5 Revenue</p>
                  <p className="text-sm font-semibold text-primary">{fmtB(scenario.revenue_yr5)}</p>
                </div>
              )}

              {/* Key assumptions */}
              {scenario.assumptions && (
                <div className="space-y-1 pt-2 border-t border/60">
                  <p className="text-xs font-medium text-tertiary mb-1">Key Assumptions</p>
                  {scenario.assumptions.revenue_growth_rates && (
                    <p className="text-xs text-secondary">
                      Growth: {scenario.assumptions.revenue_growth_rates.slice(0, 3).map(r => fmtPct(r)).join(' \u2192 ')}
                      {scenario.assumptions.revenue_growth_rates.length > 3 && ' \u2026'}
                    </p>
                  )}
                  {scenario.assumptions.wacc != null && (
                    <p className="text-xs text-secondary">WACC: {fmtPct(scenario.assumptions.wacc)}</p>
                  )}
                  {scenario.assumptions.terminal_growth_rate != null && (
                    <p className="text-xs text-secondary">TGR: {fmtPct(scenario.assumptions.terminal_growth_rate)}</p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default ScenarioAnalysis
