import { useState } from 'react'

function DCFTable({ dcfModel }) {
  const [hoveredAssumption, setHoveredAssumption] = useState(null)

  if (!dcfModel) return null

  const { assumptions, fair_value_per_share, current_price, upside_downside_pct } = dcfModel
  const isUndervalued = upside_downside_pct > 0

  const fmtB = (v) => {
    if (!v) return 'N/A'
    if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
    return `$${(v / 1e9).toFixed(1)}B`
  }

  const fmtPct = (v) => `${(v * 100).toFixed(1)}%`

  return (
    <div className="space-y-6">
      {/* Fair Value Banner */}
      <div className={`rounded-xl p-6 border-2 ${isUndervalued ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300'}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-600">DCF Fair Value</p>
            <p className={`text-3xl font-bold ${isUndervalued ? 'text-green-700' : 'text-red-700'}`}>
              ${fair_value_per_share?.toFixed(2)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium text-slate-600">Current Price</p>
            <p className="text-2xl font-semibold text-slate-800">${current_price?.toFixed(2)}</p>
          </div>
          <div className={`px-4 py-2 rounded-lg ${isUndervalued ? 'bg-green-100' : 'bg-red-100'}`}>
            <p className={`text-lg font-bold ${isUndervalued ? 'text-green-700' : 'text-red-700'}`}>
              {isUndervalued ? '+' : ''}{upside_downside_pct?.toFixed(1)}%
            </p>
            <p className="text-xs text-slate-600">{isUndervalued ? 'Upside' : 'Downside'}</p>
          </div>
        </div>
      </div>

      {/* Key Assumptions with Tooltips */}
      <div>
        <h4 className="text-lg font-semibold text-slate-700 mb-3">Key Assumptions</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            {
              label: 'Revenue Growth',
              value: assumptions?.revenue_growth_rates?.map(r => fmtPct(r)).join(', ') || 'N/A',
              rationale: assumptions?.revenue_growth_rationale,
              key: 'growth',
            },
            {
              label: 'FCF Margin',
              value: assumptions?.fcf_margin ? fmtPct(assumptions.fcf_margin) : 'N/A',
              rationale: assumptions?.fcf_margin_rationale,
              key: 'fcf',
            },
            {
              label: 'WACC',
              value: assumptions?.wacc ? fmtPct(assumptions.wacc) : 'N/A',
              rationale: assumptions?.wacc_rationale,
              key: 'wacc',
            },
            {
              label: 'Terminal Growth',
              value: assumptions?.terminal_growth_rate ? fmtPct(assumptions.terminal_growth_rate) : 'N/A',
              rationale: assumptions?.terminal_growth_rationale,
              key: 'tgr',
            },
          ].map((item) => (
            <div
              key={item.key}
              className="relative bg-slate-50 rounded-lg p-3 border border-slate-200 cursor-help"
              onMouseEnter={() => setHoveredAssumption(item.key)}
              onMouseLeave={() => setHoveredAssumption(null)}
            >
              <p className="text-xs text-slate-500">{item.label}</p>
              <p className="text-sm font-semibold text-slate-800 mt-1">{item.value}</p>
              {hoveredAssumption === item.key && item.rationale && (
                <div className="absolute z-50 bottom-full left-0 mb-2 w-64 p-3 bg-slate-800 text-white text-xs rounded-lg shadow-lg">
                  {item.rationale}
                  <div className="absolute top-full left-4 w-2 h-2 bg-slate-800 transform rotate-45 -mt-1"></div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Projection Table */}
      <div>
        <h4 className="text-lg font-semibold text-slate-700 mb-3">Cash Flow Projections</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="px-3 py-2 text-left font-semibold text-slate-700">Year</th>
                <th className="px-3 py-2 text-right font-semibold text-slate-700">Revenue</th>
                <th className="px-3 py-2 text-right font-semibold text-slate-700">FCF</th>
                <th className="px-3 py-2 text-right font-semibold text-slate-700">Discounted FCF</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {dcfModel.projected_revenues?.map((rev, i) => (
                <tr key={i}>
                  <td className="px-3 py-2 text-slate-700">Year {i + 1}</td>
                  <td className="px-3 py-2 text-right text-slate-600">{fmtB(rev)}</td>
                  <td className="px-3 py-2 text-right text-slate-600">{fmtB(dcfModel.projected_fcfs?.[i])}</td>
                  <td className="px-3 py-2 text-right text-slate-600">{fmtB(dcfModel.discounted_fcfs?.[i])}</td>
                </tr>
              ))}
              <tr className="bg-slate-50 font-medium">
                <td className="px-3 py-2 text-slate-700">Terminal Value</td>
                <td className="px-3 py-2 text-right text-slate-600"></td>
                <td className="px-3 py-2 text-right text-slate-600">{fmtB(dcfModel.terminal_value)}</td>
                <td className="px-3 py-2 text-right text-slate-600">{fmtB(dcfModel.pv_terminal_value)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Valuation Bridge */}
      <div>
        <h4 className="text-lg font-semibold text-slate-700 mb-3">Valuation Bridge</h4>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            { label: 'PV of FCFs', value: fmtB(dcfModel.discounted_fcfs?.reduce((a, b) => a + b, 0)) },
            { label: 'PV Terminal Value', value: fmtB(dcfModel.pv_terminal_value) },
            { label: 'Enterprise Value', value: fmtB(dcfModel.enterprise_value) },
            { label: 'Net Debt', value: fmtB(dcfModel.net_debt) },
            { label: 'Equity Value', value: fmtB(dcfModel.equity_value) },
            { label: 'Fair Value/Share', value: `$${fair_value_per_share?.toFixed(2)}`, highlight: true },
          ].map((item, i) => (
            <div
              key={i}
              className={`rounded-lg p-3 border ${item.highlight ? 'bg-amber-50 border-amber-300' : 'bg-slate-50 border-slate-200'}`}
            >
              <p className="text-xs text-slate-500">{item.label}</p>
              <p className={`text-sm font-semibold mt-1 ${item.highlight ? 'text-amber-700' : 'text-slate-800'}`}>{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default DCFTable
