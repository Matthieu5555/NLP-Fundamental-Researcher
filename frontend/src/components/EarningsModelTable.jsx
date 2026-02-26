function EarningsModelTable({ earningsModelData }) {
  if (!earningsModelData?.rows?.length) return null

  const { rows } = earningsModelData

  // Separate historical and forecast for visual emphasis
  const historicalRows = rows.filter(r => !r.is_estimate)
  const forecastRows = rows.filter(r => r.is_estimate)

  const fmtRev = (v) => {
    if (v == null) return 'N/A'
    if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
    if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
    return `$${(v / 1e6).toFixed(0)}M`
  }

  const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : 'N/A'
  const fmtEps = (v) => v != null ? `$${v.toFixed(2)}` : 'N/A'

  const renderRow = (row, i) => (
    <tr key={i} className={row.is_estimate ? 'bg-accent-warning-light/40' : 'text-slate-400'}>
      <td className={`px-3 py-2 font-medium ${row.is_estimate ? 'text-slate-800' : 'text-slate-400'}`}>
        FY{row.fiscal_year}{row.is_estimate ? 'E' : ''}
      </td>
      <td className={`px-3 py-2 text-right ${row.is_estimate ? 'text-slate-700 font-medium' : 'text-slate-400'}`}>
        {fmtRev(row.revenue)}
      </td>
      <td className={`px-3 py-2 text-right ${
        row.revenue_growth != null
          ? (row.revenue_growth >= 0 ? 'text-accent-success' : 'text-accent-danger')
          : 'text-slate-300'
      } ${row.is_estimate ? 'font-medium' : ''}`}>
        {fmtPct(row.revenue_growth)}
      </td>
      <td className={`px-3 py-2 text-right ${row.is_estimate ? 'text-slate-700' : 'text-slate-400'}`}>
        {fmtRev(row.ebitda)}
      </td>
      <td className={`px-3 py-2 text-right ${row.is_estimate ? 'text-slate-700' : 'text-slate-400'}`}>
        {fmtPct(row.ebitda_margin)}
      </td>
      <td className={`px-3 py-2 text-right ${row.is_estimate ? 'text-slate-700 font-medium' : 'text-slate-400'}`}>
        {fmtEps(row.eps)}
      </td>
      <td className="px-3 py-2 text-center">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
          row.is_estimate ? 'bg-accent-warning-light text-accent-warning-dark' : 'bg-slate-100 text-slate-500'
        }`}>
          {row.is_estimate ? 'Forecast' : 'Actual'}
        </span>
      </td>
    </tr>
  )

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-100">
              <th className="px-3 py-2 text-left font-semibold text-slate-700">Fiscal Year</th>
              <th className="px-3 py-2 text-right font-semibold text-slate-700">Revenue</th>
              <th className="px-3 py-2 text-right font-semibold text-slate-700">Rev Growth</th>
              <th className="px-3 py-2 text-right font-semibold text-slate-700">EBITDA</th>
              <th className="px-3 py-2 text-right font-semibold text-slate-700">EBITDA Margin</th>
              <th className="px-3 py-2 text-right font-semibold text-slate-700">EPS</th>
              <th className="px-3 py-2 text-center font-semibold text-slate-700">Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {/* Historical rows - muted styling */}
            {historicalRows.map((row, i) => renderRow(row, `h-${i}`))}
            {/* Divider between historical and forecast */}
            {historicalRows.length > 0 && forecastRows.length > 0 && (
              <tr>
                <td colSpan={7} className="py-0">
                  <div className="border-t-2 border-accent-warning"></div>
                </td>
              </tr>
            )}
            {/* Forecast rows - emphasized */}
            {forecastRows.map((row, i) => renderRow(row, `f-${i}`))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-2.5 bg-slate-100 rounded-sm"></div>
          <span>Historical</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-2.5 bg-accent-warning-light rounded-sm border border-accent-warning"></div>
          <span>Analyst Forecast</span>
        </div>
      </div>
    </div>
  )
}

export default EarningsModelTable
