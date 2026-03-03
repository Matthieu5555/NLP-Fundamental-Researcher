function SensitivityGrid({ data, title, subtitle, rowLabel, colLabel }) {
  if (!data) return null

  // Support both WACC x TGR and Growth x Margin grid shapes
  const rowValues = data.wacc_values || data.growth_values
  const colValues = data.terminal_growth_values || data.margin_values
  const grid = data.fair_value_grid
  const baseRowIdx = data.base_wacc_idx ?? data.base_growth_idx
  const baseColIdx = data.base_tgr_idx ?? data.base_margin_idx
  const currentPrice = data.current_price

  if (!rowValues || !colValues || !grid) return null

  const gridTitle = title || 'WACC vs Terminal Growth Rate'
  const gridSubtitle = subtitle || 'Fair value per share across different assumptions'
  const gridRowLabel = rowLabel || 'WACC'
  const gridColLabel = colLabel || 'TGR'

  const getColor = (fv) => {
    if (!fv || fv <= 0) return 'bg-surface-tertiary text-muted'
    const upside = ((fv / currentPrice) - 1) * 100
    if (upside > 30) return 'bg-accent-success-muted text-accent-success-dark font-semibold'
    if (upside > 15) return 'bg-accent-success-light text-accent-success-dark font-semibold'
    if (upside > 0) return 'bg-accent-success-light text-accent-success'
    if (upside > -15) return 'bg-accent-danger-light text-accent-danger'
    if (upside > -30) return 'bg-accent-danger-light text-accent-danger-dark font-semibold'
    return 'bg-accent-danger-muted text-accent-danger-dark font-semibold'
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-lg font-semibold text-primary">{gridTitle}</h4>
          <p className="text-sm text-tertiary">{gridSubtitle}</p>
        </div>
        <div className="text-sm text-secondary">
          Current Price: <span className="font-semibold">${currentPrice?.toFixed(2)}</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-tertiary">
              <th className="px-3 py-2 text-left font-semibold text-primary">{gridRowLabel} \ {gridColLabel}</th>
              {colValues.map((val, j) => (
                <th key={j} className={`px-3 py-2 text-center font-semibold ${j === baseColIdx ? 'text-accent-warning-dark bg-accent-warning-light' : 'text-primary'}`}>
                  {(val * 100).toFixed(1)}%
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.map((row, i) => (
              <tr key={i}>
                <td className={`px-3 py-2 font-semibold ${i === baseRowIdx ? 'text-accent-warning-dark bg-accent-warning-light' : 'text-primary bg-surface-secondary'}`}>
                  {(rowValues[i] * 100).toFixed(1)}%
                </td>
                {row.map((fv, j) => {
                  const isBase = i === baseRowIdx && j === baseColIdx
                  const pctChange = fv > 0 && currentPrice > 0 ? ((fv / currentPrice - 1) * 100) : null
                  return (
                    <td
                      key={j}
                      className={`px-2 py-1.5 text-center font-medium ${getColor(fv)} ${isBase ? 'ring-2 ring-accent-warning ring-inset' : ''}`}
                    >
                      {fv > 0 ? (
                        <>
                          <div>${fv.toFixed(0)}</div>
                          {pctChange !== null && (
                            <div className="text-[10px] opacity-75">
                              {pctChange >= 0 ? '+' : ''}{pctChange.toFixed(1)}%
                            </div>
                          )}
                        </>
                      ) : 'N/A'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-tertiary">
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-accent-success-muted rounded"></div>
          <span>&gt;30% upside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-accent-success-light rounded"></div>
          <span>0–30% upside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-accent-danger-light rounded"></div>
          <span>0–30% downside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-accent-danger-muted rounded"></div>
          <span>&gt;30% downside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 ring-2 ring-accent-warning rounded"></div>
          <span>Base case</span>
        </div>
      </div>
    </div>
  )
}

export default SensitivityGrid
