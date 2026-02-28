function FootballField({ data }) {
  if (!data) return null

  const { ranges, current_price, weighted_fair_value, consensus_target } = data

  if (!ranges || ranges.length === 0) return null

  // Calculate global min/max across all ranges for consistent scaling
  const allValues = ranges.flatMap(r => [r.low, r.mid, r.high]).filter(v => v > 0)
  if (current_price) allValues.push(current_price)
  if (weighted_fair_value) allValues.push(weighted_fair_value)
  if (consensus_target) allValues.push(consensus_target)
  const globalMin = Math.min(...allValues) * 0.85
  const globalMax = Math.max(...allValues) * 1.15
  const scale = (v) => Math.max(0, Math.min(100, ((v - globalMin) / (globalMax - globalMin)) * 100))

  const isUndervalued = weighted_fair_value && weighted_fair_value > current_price

  return (
    <div className="space-y-6">
      {/* Summary Banner */}
      {weighted_fair_value && current_price && (
        <div className={`rounded-lg p-6 border ${isUndervalued ? 'bg-accent-success-light border-accent-success' : 'bg-accent-danger-light border-accent-danger'}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-secondary">Weighted Fair Value</p>
              <p className={`text-3xl font-bold ${isUndervalued ? 'text-accent-success-dark' : 'text-accent-danger-dark'}`}>
                ${weighted_fair_value.toFixed(2)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-secondary">Current Price</p>
              <p className="text-2xl font-semibold text-primary">${current_price.toFixed(2)}</p>
            </div>
            {consensus_target && (
              <div className="text-right">
                <p className="text-sm font-medium text-secondary">Analyst Consensus</p>
                <p className="text-2xl font-semibold text-secondary">${consensus_target.toFixed(2)}</p>
              </div>
            )}
            <div className={`px-4 py-2 rounded-lg ${isUndervalued ? 'bg-accent-success-light' : 'bg-accent-danger-light'}`}>
              <p className={`text-lg font-bold ${isUndervalued ? 'text-accent-success-dark' : 'text-accent-danger-dark'}`}>
                {((weighted_fair_value / current_price - 1) * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-secondary">{isUndervalued ? 'Upside' : 'Downside'}</p>
            </div>
          </div>
        </div>
      )}

      {/* Football Field Chart */}
      <div>
        <h4 className="text-lg font-semibold text-primary mb-4">Valuation Range Comparison</h4>
        <div className="space-y-2">
          {ranges.map((range, i) => (
            <div key={i} className="flex items-center gap-3">
              {/* Method label */}
              <div className="w-32 flex-shrink-0 text-right">
                <p className="text-xs font-medium text-primary leading-tight">{range.method}</p>
                {range.source && <p className="text-[10px] text-muted">{range.source}</p>}
              </div>
              {/* Bar area */}
              <div className="flex-1 relative h-7 bg-surface-secondary rounded">
                {/* Range bar (low to high) */}
                <div
                  className="absolute top-1 bottom-1 rounded-sm bg-accent-info-light border border-accent-info"
                  style={{
                    left: `${scale(range.low)}%`,
                    width: `${Math.max(1, scale(range.high) - scale(range.low))}%`,
                  }}
                />
                {/* Mid marker */}
                <div
                  className="absolute top-0.5 bottom-0.5 w-0.5 bg-accent-info-dark z-10"
                  style={{ left: `${scale(range.mid)}%` }}
                />
                {/* Current price line */}
                {current_price && (
                  <div
                    className="absolute top-0 bottom-0 w-px z-20"
                    style={{
                      left: `${scale(current_price)}%`,
                      borderLeft: '1px dashed var(--text-primary)',
                    }}
                  />
                )}
              </div>
              {/* Value labels */}
              <div className="w-24 flex-shrink-0 text-right">
                <p className="text-xs font-semibold text-primary">${range.mid.toFixed(0)}</p>
                <p className="text-[10px] text-muted">${range.low.toFixed(0)} – ${range.high.toFixed(0)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 text-xs text-tertiary pt-2">
        <div className="flex items-center gap-1.5">
          <div className="w-5 h-2.5 bg-accent-info-light border border-accent-info rounded-sm"></div>
          <span>Valuation range</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-0.5 h-3 bg-accent-info-dark"></div>
          <span>Midpoint</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-px h-3 border-l border-dashed border-heavy"></div>
          <span>Current (${current_price?.toFixed(0)})</span>
        </div>
      </div>
    </div>
  )
}

export default FootballField
