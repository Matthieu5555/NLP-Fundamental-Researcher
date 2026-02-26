function SensitivityGrid({ sensitivityData, title, subtitle, rowLabel, colLabel }) {
  if (!sensitivityData) return null

  // Support both WACC x TGR and Growth x Margin grid shapes
  const rowValues = sensitivityData.wacc_values || sensitivityData.growth_values
  const colValues = sensitivityData.terminal_growth_values || sensitivityData.margin_values
  const grid = sensitivityData.fair_value_grid
  const baseRowIdx = sensitivityData.base_wacc_idx ?? sensitivityData.base_growth_idx
  const baseColIdx = sensitivityData.base_tgr_idx ?? sensitivityData.base_margin_idx
  const currentPrice = sensitivityData.current_price

  if (!rowValues || !colValues || !grid) return null

  const gridTitle = title || 'WACC vs Terminal Growth Rate'
  const gridSubtitle = subtitle || 'Fair value per share across different assumptions'
  const gridRowLabel = rowLabel || 'WACC'
  const gridColLabel = colLabel || 'TGR'

  const getColor = (fv) => {
    if (!fv || fv <= 0) return 'bg-slate-100 text-slate-400'
    const upside = ((fv / currentPrice) - 1) * 100
    if (upside > 30) return 'bg-accent-success-muted text-accent-success-dark'
    if (upside > 15) return 'bg-accent-success-light text-accent-success-dark'
    if (upside > 0) return 'bg-accent-success-light text-accent-success-dark'
    if (upside > -15) return 'bg-accent-danger-light text-accent-danger-dark'
    if (upside > -30) return 'bg-accent-danger-light text-accent-danger-dark'
    return 'bg-accent-danger-muted text-accent-danger-dark'
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-lg font-semibold text-slate-700">{gridTitle}</h4>
          <p className="text-sm text-slate-500">{gridSubtitle}</p>
        </div>
        <div className="text-sm text-slate-600">
          Current Price: <span className="font-semibold">${currentPrice?.toFixed(2)}</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-100">
              <th className="px-3 py-2 text-left font-semibold text-slate-700">{gridRowLabel} \ {gridColLabel}</th>
              {colValues.map((val, j) => (
                <th key={j} className={`px-3 py-2 text-center font-semibold ${j === baseColIdx ? 'text-accent-warning-dark bg-accent-warning-light' : 'text-slate-700'}`}>
                  {(val * 100).toFixed(1)}%
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.map((row, i) => (
              <tr key={i}>
                <td className={`px-3 py-2 font-semibold ${i === baseRowIdx ? 'text-accent-warning-dark bg-accent-warning-light' : 'text-slate-700 bg-slate-50'}`}>
                  {(rowValues[i] * 100).toFixed(1)}%
                </td>
                {row.map((fv, j) => {
                  const isBase = i === baseRowIdx && j === baseColIdx
                  return (
                    <td
                      key={j}
                      className={`px-3 py-2 text-center font-medium ${getColor(fv)} ${isBase ? 'ring-2 ring-accent-warning ring-inset' : ''}`}
                    >
                      {fv > 0 ? `$${fv.toFixed(0)}` : 'N/A'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-accent-success-muted rounded"></div>
          <span>Strong upside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-accent-success-light rounded"></div>
          <span>Modest upside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-accent-danger-light rounded"></div>
          <span>Modest downside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-accent-danger-muted rounded"></div>
          <span>Strong downside</span>
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
