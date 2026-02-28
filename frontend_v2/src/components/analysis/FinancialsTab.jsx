/**
 * Financial Statements tab with income statement, balance sheet, cash flow, and key ratios.
 * Each statement is rendered as a horizontal table with 5-year data.
 */

function formatBillions(value) {
  return value ? `$${(value / 1e9).toFixed(1)}B` : 'N/A'
}

function formatPercent(value) {
  return value != null ? `${(value * 100).toFixed(1)}%` : 'N/A'
}

function YoYCell({ value, yoy }) {
  return (
    <td className="px-3 py-2 text-right text-secondary">
      <div>{formatBillions(value)}</div>
      {yoy != null && (
        <div className={`text-xs font-medium ${yoy >= 0 ? 'text-accent-success' : 'text-accent-danger'}`}>
          {yoy >= 0 ? '+' : ''}{yoy.toFixed(1)}% YoY
        </div>
      )}
    </td>
  )
}

function StatementTable({ title, dotColor, headers, children }) {
  return (
    <div>
      <h4 className="text-lg font-semibold text-primary mb-3 flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${dotColor}`}></span>
        {title}
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-tertiary">
              <th className="px-3 py-2 text-left font-semibold text-primary">Metric</th>
              {headers.map((h, idx) => (
                <th key={idx} className="px-3 py-2 text-right font-semibold text-primary">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide">
            {children}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function StatRow({ label, data, accessor, className = '' }) {
  return (
    <tr className={className}>
      <td className="px-3 py-2 text-primary">{label}</td>
      {data.map((item, idx) => (
        <td key={idx} className="px-3 py-2 text-right text-secondary">
          {accessor(item)}
        </td>
      ))}
    </tr>
  )
}

function getPeriodHeaders(statements) {
  return statements.slice(0, 5).map(s => s.period?.substring(0, 7) || `FY${s.fiscal_year}`)
}

function FinancialsTab({ financialStatements, financialsLoading, companyInfo }) {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-xl font-bold text-primary">Financial Statements</h3>
          <p className="text-sm text-tertiary mt-1">5-year financial data with key ratios and highlights</p>
        </div>
        {companyInfo && (
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${companyInfo.is_us ? 'bg-accent-success-light text-accent-success-dark' : 'bg-surface-tertiary text-secondary'}`}>
            {companyInfo.is_us ? 'US Company' : 'Non-US Company'}
          </span>
        )}
      </div>

      {financialsLoading ? (
        <div className="text-center py-12">
          <div className="inline-flex items-center justify-center space-x-3 mb-4">
            <div className="w-6 h-6 border-2 spinner-brand rounded-full animate-spin"></div>
          </div>
          <p className="text-secondary">Loading financial statements...</p>
        </div>
      ) : !financialStatements?.is_available ? (
        <div className="text-center py-12 bg-surface-secondary rounded-lg">
          <svg className="w-16 h-16 mx-auto mb-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-lg font-medium text-primary">Not Available for Non-US Companies</p>
          <p className="text-sm mt-2 text-tertiary max-w-md mx-auto">
            Detailed financial statements are only available for US companies through FinancialDatasets.ai.
            {financialStatements?.error && (
              <span className="block mt-2 text-muted">{financialStatements.error}</span>
            )}
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Key Findings */}
          {financialStatements.highlights?.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-lg font-semibold text-primary flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-accent-warning"></span>
                Key Findings
              </h4>
              <div className="grid gap-3 md:grid-cols-2">
                {financialStatements.highlights.map((highlight, idx) => (
                  <div
                    key={idx}
                    className={`rounded-lg p-4 border ${
                      highlight.type === 'positive' ? 'bg-accent-success-light border-accent-success' :
                      highlight.type === 'negative' ? 'bg-accent-danger-light border-accent-danger' :
                      highlight.type === 'attention' ? 'bg-accent-warning-light border-accent-warning' :
                      'bg-surface-secondary border'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-lg ${
                        highlight.type === 'positive' ? 'bg-accent-success-light text-accent-success' :
                        highlight.type === 'negative' ? 'bg-accent-danger-light text-accent-danger' :
                        highlight.type === 'attention' ? 'bg-accent-warning-light text-accent-warning' :
                        'bg-surface-tertiary text-secondary'
                      }`}>
                        {highlight.type === 'positive' ? '✓' : highlight.type === 'negative' ? '!' : '?'}
                      </span>
                      <div className="flex-1 min-w-0">
                        <h5 className="font-semibold text-primary text-sm">{highlight.title}</h5>
                        <p className="text-sm text-secondary mt-1">{highlight.description}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Income Statement */}
          {financialStatements.income_statements?.length > 0 && (() => {
            const stmts = financialStatements.income_statements.slice(0, 5)
            return (
              <StatementTable title="Income Statement" dotColor="bg-accent-info" headers={getPeriodHeaders(stmts)}>
                <tr>
                  <td className="px-3 py-2 text-primary">Revenue</td>
                  {stmts.map((s, i) => <YoYCell key={i} value={s.revenue} yoy={s.revenue_yoy} />)}
                </tr>
                <StatRow label="Gross Profit" data={stmts} accessor={s => formatBillions(s.gross_profit)} className="bg-surface-secondary" />
                <StatRow label="Operating Income" data={stmts} accessor={s => formatBillions(s.operating_income)} />
                <tr className="bg-surface-secondary">
                  <td className="px-3 py-2 text-primary">Net Income</td>
                  {stmts.map((s, i) => <YoYCell key={i} value={s.net_income} yoy={s.net_income_yoy} />)}
                </tr>
                <tr>
                  <td className="px-3 py-2 text-primary">EPS</td>
                  {stmts.map((s, i) => (
                    <td key={i} className="px-3 py-2 text-right text-secondary">
                      <div>{s.eps ? `$${s.eps.toFixed(2)}` : 'N/A'}</div>
                      {s.eps_yoy != null && (
                        <div className={`text-xs font-medium ${s.eps_yoy >= 0 ? 'text-accent-success' : 'text-accent-danger'}`}>
                          {s.eps_yoy >= 0 ? '+' : ''}{s.eps_yoy.toFixed(1)}% YoY
                        </div>
                      )}
                    </td>
                  ))}
                </tr>
                <StatRow label="Gross Margin" data={stmts} accessor={s => formatPercent(s.gross_margin)} className="bg-accent-info-light font-medium" />
                <StatRow label="Net Margin" data={stmts} accessor={s => formatPercent(s.net_margin)} className="bg-accent-info-light font-medium" />
              </StatementTable>
            )
          })()}

          {/* Balance Sheet */}
          {financialStatements.balance_sheets?.length > 0 && (() => {
            const stmts = financialStatements.balance_sheets.slice(0, 5)
            return (
              <StatementTable title="Balance Sheet" dotColor="bg-accent-success" headers={getPeriodHeaders(stmts)}>
                <StatRow label="Total Assets" data={stmts} accessor={s => formatBillions(s.total_assets)} />
                <StatRow label="Total Equity" data={stmts} accessor={s => formatBillions(s.total_equity)} className="bg-surface-secondary" />
                <StatRow label="Cash" data={stmts} accessor={s => formatBillions(s.cash)} />
                <StatRow label="Total Debt" data={stmts} accessor={s => formatBillions(s.total_debt)} className="bg-surface-secondary" />
                <StatRow label="Debt/Equity" data={stmts} accessor={s => s.debt_to_equity ? `${s.debt_to_equity.toFixed(2)}x` : 'N/A'} className="bg-accent-success-light font-medium" />
              </StatementTable>
            )
          })()}

          {/* Cash Flow */}
          {financialStatements.cash_flows?.length > 0 && (() => {
            const stmts = financialStatements.cash_flows.slice(0, 5)
            return (
              <StatementTable title="Cash Flow Statement" dotColor="bg-chart-sma50" headers={getPeriodHeaders(stmts)}>
                <StatRow label="Operating CF" data={stmts} accessor={s => formatBillions(s.operating_cf)} />
                <StatRow label="Free Cash Flow" data={stmts} accessor={s => formatBillions(s.free_cash_flow)} className="bg-surface-secondary" />
                <StatRow label="CapEx" data={stmts} accessor={s => formatBillions(s.capex)} />
                <StatRow label="FCF Margin" data={stmts} accessor={s => formatPercent(s.fcf_margin)} className="bg-accent-info-light font-medium" />
              </StatementTable>
            )
          })()}

          {/* Key Ratios */}
          {financialStatements.ratios?.length > 0 && (() => {
            const ratios = financialStatements.ratios.slice(0, 5)
            return (
              <StatementTable title="Key Ratios" dotColor="bg-brand" headers={getPeriodHeaders(ratios)}>
                <StatRow label="ROE" data={ratios} accessor={r => formatPercent(r.profitability?.roe)} />
                <StatRow label="ROA" data={ratios} accessor={r => formatPercent(r.profitability?.roa)} className="bg-surface-secondary" />
                <StatRow label="Asset Turnover" data={ratios} accessor={r => r.efficiency?.asset_turnover ? `${r.efficiency.asset_turnover.toFixed(2)}x` : 'N/A'} />
              </StatementTable>
            )
          })()}
        </div>
      )}
    </div>
  )
}

export default FinancialsTab
