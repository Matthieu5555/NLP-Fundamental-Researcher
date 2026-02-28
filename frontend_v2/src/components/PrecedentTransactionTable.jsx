import { useState } from 'react'

function PrecedentTransactionTable({ data }) {
  const [hoveredDeal, setHoveredDeal] = useState(null)

  if (!data?.deals?.length) return null

  const { deals, median_ev_revenue, median_ev_ebitda, median_premium,
          implied_value_from_revenue, implied_value_from_ebitda } = data

  const fmtX = (v) => v != null ? `${v.toFixed(1)}x` : 'N/A'
  const fmtPct = (v) => v != null ? `${(v * 100).toFixed(0)}%` : 'N/A'
  const fmtVal = (v) => {
    if (v == null) return 'N/A'
    if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
    if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
    if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`
    return `$${v.toLocaleString()}`
  }

  const summaryCards = [
    { label: 'Median EV/Revenue', value: fmtX(median_ev_revenue) },
    { label: 'Median EV/EBITDA', value: fmtX(median_ev_ebitda) },
    { label: 'Median Control Premium', value: fmtPct(median_premium) },
    ...(implied_value_from_revenue != null ? [{ label: 'Implied (EV/Rev)', value: `$${implied_value_from_revenue.toFixed(2)}`, highlight: true }] : []),
    ...(implied_value_from_ebitda != null ? [{ label: 'Implied (EV/EBITDA)', value: `$${implied_value_from_ebitda.toFixed(2)}`, highlight: true }] : []),
  ].filter(c => c.value !== 'N/A' || c.highlight)

  return (
    <div className="space-y-6">
      {/* Median Summary Cards */}
      {summaryCards.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {summaryCards.map((item, i) => (
            <div key={i} className={`rounded-lg p-3 border ${item.highlight ? 'bg-accent-warning-light border-accent-warning' : 'bg-surface-secondary border'}`}>
              <p className="text-xs text-tertiary">{item.label}</p>
              <p className={`text-sm font-semibold mt-1 ${item.highlight ? 'text-accent-warning-dark' : 'text-primary'}`}>{item.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Deal Table */}
      <div>
        <h4 className="text-lg font-semibold text-primary mb-3">Comparable Transactions</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-tertiary">
                <th className="px-3 py-2 text-left font-semibold text-primary">Date</th>
                <th className="px-3 py-2 text-left font-semibold text-primary">Acquirer</th>
                <th className="px-3 py-2 text-left font-semibold text-primary">Target</th>
                <th className="px-3 py-2 text-right font-semibold text-primary">Deal Value</th>
                <th className="px-3 py-2 text-right font-semibold text-primary">EV/Rev</th>
                <th className="px-3 py-2 text-right font-semibold text-primary">EV/EBITDA</th>
                <th className="px-3 py-2 text-right font-semibold text-primary">Premium</th>
              </tr>
            </thead>
            <tbody className="divide-y divide">
              {deals.map((deal, i) => (
                <tr
                  key={i}
                  className="hover:bg-surface-secondary cursor-help"
                  onMouseEnter={() => setHoveredDeal(i)}
                  onMouseLeave={() => setHoveredDeal(null)}
                >
                  <td className="px-3 py-2 text-secondary text-xs">{deal.date}</td>
                  <td className="px-3 py-2 text-primary font-medium">{deal.acquirer}</td>
                  <td className="px-3 py-2 text-primary">{deal.target}</td>
                  <td className="px-3 py-2 text-right text-secondary">{fmtVal(deal.deal_value_usd)}</td>
                  <td className="px-3 py-2 text-right text-secondary">{fmtX(deal.ev_to_revenue)}</td>
                  <td className="px-3 py-2 text-right text-secondary">{fmtX(deal.ev_to_ebitda)}</td>
                  <td className="px-3 py-2 text-right text-secondary">{fmtPct(deal.premium_pct)}</td>
                </tr>
              ))}
              {/* Median row */}
              <tr className="bg-surface-secondary font-medium border-t border-medium">
                <td className="px-3 py-2 text-primary font-semibold" colSpan={4}>Median</td>
                <td className="px-3 py-2 text-right text-primary font-semibold">{fmtX(median_ev_revenue)}</td>
                <td className="px-3 py-2 text-right text-primary font-semibold">{fmtX(median_ev_ebitda)}</td>
                <td className="px-3 py-2 text-right text-primary font-semibold">{fmtPct(median_premium)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Deal description on hover */}
      {hoveredDeal !== null && deals[hoveredDeal]?.description && (
        <div className="text-xs text-secondary bg-surface-secondary rounded-lg p-3">
          <span className="font-medium text-primary">{deals[hoveredDeal].acquirer} / {deals[hoveredDeal].target}:</span>{' '}
          {deals[hoveredDeal].description}
        </div>
      )}

      {/* Note */}
      <p className="text-xs text-muted italic">
        Transaction multiples include control premiums (typically 20–40%) over trading multiples.
      </p>
    </div>
  )
}

export default PrecedentTransactionTable
