function SensitivityGrid({ sensitivityData }) {
  if (!sensitivityData) return null

  const { wacc_values, terminal_growth_values, fair_value_grid, base_wacc_idx, base_tgr_idx, current_price } = sensitivityData

  const getColor = (fv) => {
    if (!fv || fv <= 0) return 'bg-slate-100 text-slate-400'
    const upside = ((fv / current_price) - 1) * 100
    if (upside > 30) return 'bg-green-200 text-green-900'
    if (upside > 15) return 'bg-green-100 text-green-800'
    if (upside > 0) return 'bg-green-50 text-green-700'
    if (upside > -15) return 'bg-red-50 text-red-700'
    if (upside > -30) return 'bg-red-100 text-red-800'
    return 'bg-red-200 text-red-900'
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-lg font-semibold text-slate-700">WACC vs Terminal Growth Rate</h4>
          <p className="text-sm text-slate-500">Fair value per share across different assumptions</p>
        </div>
        <div className="text-sm text-slate-600">
          Current Price: <span className="font-semibold">${current_price?.toFixed(2)}</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-100">
              <th className="px-3 py-2 text-left font-semibold text-slate-700">WACC \ TGR</th>
              {terminal_growth_values?.map((tgr, j) => (
                <th key={j} className={`px-3 py-2 text-center font-semibold ${j === base_tgr_idx ? 'text-amber-700 bg-amber-50' : 'text-slate-700'}`}>
                  {(tgr * 100).toFixed(1)}%
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {fair_value_grid?.map((row, i) => (
              <tr key={i}>
                <td className={`px-3 py-2 font-semibold ${i === base_wacc_idx ? 'text-amber-700 bg-amber-50' : 'text-slate-700 bg-slate-50'}`}>
                  {(wacc_values[i] * 100).toFixed(1)}%
                </td>
                {row.map((fv, j) => {
                  const isBase = i === base_wacc_idx && j === base_tgr_idx
                  return (
                    <td
                      key={j}
                      className={`px-3 py-2 text-center font-medium ${getColor(fv)} ${isBase ? 'ring-2 ring-amber-500 ring-inset' : ''}`}
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
          <div className="w-4 h-3 bg-green-200 rounded"></div>
          <span>Strong upside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-green-50 rounded"></div>
          <span>Modest upside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-red-50 rounded"></div>
          <span>Modest downside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 bg-red-200 rounded"></div>
          <span>Strong downside</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 ring-2 ring-amber-500 rounded"></div>
          <span>Base case</span>
        </div>
      </div>
    </div>
  )
}

export default SensitivityGrid
