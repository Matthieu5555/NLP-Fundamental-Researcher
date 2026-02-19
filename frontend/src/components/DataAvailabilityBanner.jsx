/**
 * DataAvailabilityBanner Component
 *
 * Displays a prominent warning banner for non-US companies,
 * showing which features are unavailable due to data limitations.
 */

export default function DataAvailabilityBanner({ companyInfo }) {
  // Don't show for US companies or if no info yet
  if (!companyInfo || companyInfo.is_us) {
    return null
  }

  const unavailable = companyInfo.unavailable_features || []

  if (unavailable.length === 0) {
    return null
  }

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-amber-800">
            Limited Data Available for Non-US Company
          </h4>
          <p className="text-sm text-amber-700 mt-1">
            {companyInfo.company_name || companyInfo.ticker} is classified as a non-US company.
            Some premium data sources are not available:
          </p>
          <ul className="mt-2 text-sm text-amber-700 space-y-1">
            {unavailable.map((feature, idx) => (
              <li key={idx} className="flex items-center gap-2">
                <svg className="w-4 h-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                {feature}
              </li>
            ))}
          </ul>
          <p className="text-xs text-amber-600 mt-3">
            Analysis will use publicly available data from Yahoo Finance and web research.
          </p>
        </div>
        <div className="flex-shrink-0">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
            {companyInfo.region?.toUpperCase() || 'NON-US'}
          </span>
        </div>
      </div>
    </div>
  )
}
