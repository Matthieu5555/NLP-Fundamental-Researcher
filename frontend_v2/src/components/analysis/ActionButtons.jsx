import { useState, useRef, useEffect } from 'react'

/**
 * Header action buttons: Update Analysis, Update Report, Download (dropdown), Add to Watchlist.
 */
function ActionButtons({
  onUpdateAnalysis, onUpdateReport, onDownloadDocx, onDownloadPptx, onDownloadExcel,
  onAddToWatchlist, reportDirty, isUpdatingReport, isUpdatingAnalysis,
  isDownloadingDocx, isDownloadingPptx, isDownloadingExcel,
  watchlistAdded,
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)

  // Close dropdown on click outside
  useEffect(() => {
    if (!dropdownOpen) return
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [dropdownOpen])

  const anyDownloading = isDownloadingDocx || isDownloadingPptx || isDownloadingExcel
  const downloadDisabled = isUpdatingReport || reportDirty || anyDownloading

  function handleDownload(fn) {
    setDropdownOpen(false)
    fn()
  }

  return (
    <div className="flex gap-2">
      {onUpdateAnalysis && (
        <button
          onClick={onUpdateAnalysis}
          disabled={!reportDirty || isUpdatingAnalysis || isUpdatingReport}
          className="px-4 py-2 text-sm font-medium border border-accent-warning text-accent-warning-dark bg-accent-warning-light rounded-lg hover:bg-accent-warning hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
          title="Re-run valuation models with analyst overrides"
        >
          {isUpdatingAnalysis ? (
            <>
              <div className="w-4 h-4 border-2 border-accent-warning-dark border-t-transparent rounded-full animate-spin"></div>
              Updating...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
              Update Models
            </>
          )}
        </button>
      )}

      {onUpdateReport && (
        <button
          onClick={onUpdateReport}
          disabled={!reportDirty || isUpdatingReport || isUpdatingAnalysis}
          className="px-4 py-2 text-sm font-medium text-white bg-brand hover:bg-brand-dark rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {isUpdatingReport ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              Updating...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Update Report
            </>
          )}
        </button>
      )}

      {/* Download dropdown */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          disabled={downloadDisabled}
          title={reportDirty ? 'Update report first to include latest insights' : ''}
          className="px-4 py-2 text-sm font-medium border border-accent-success text-accent-success-dark bg-accent-success-light rounded-lg hover:bg-accent-success hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {anyDownloading ? (
            <>
              <div className="w-4 h-4 border-2 border-accent-success-dark border-t-transparent rounded-full animate-spin"></div>
              Generating...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </>
          )}
        </button>

        {dropdownOpen && (
          <div className="absolute right-0 mt-2 w-56 bg-surface-elevated rounded-lg shadow-lg border z-50 overflow-hidden">
            <button
              onClick={() => handleDownload(onDownloadDocx)}
              disabled={isDownloadingDocx}
              className="w-full px-4 py-3 text-left text-sm hover:bg-surface-secondary transition-colors flex items-center gap-3 disabled:opacity-50"
            >
              {isDownloadingDocx ? (
                <div className="w-4 h-4 border-2 spinner-brand rounded-full animate-spin"></div>
              ) : (
                <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
              )}
              <div>
                <div className="font-medium text-primary">Word Report</div>
                <div className="text-xs text-tertiary">Full equity research report</div>
              </div>
            </button>

            <button
              onClick={() => handleDownload(onDownloadPptx)}
              disabled={isDownloadingPptx}
              className="w-full px-4 py-3 text-left text-sm hover:bg-surface-secondary transition-colors flex items-center gap-3 disabled:opacity-50 border-t"
            >
              {isDownloadingPptx ? (
                <div className="w-4 h-4 border-2 spinner-brand rounded-full animate-spin"></div>
              ) : (
                <svg className="w-4 h-4 text-accent-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              )}
              <div>
                <div className="font-medium text-primary">PowerPoint Slides</div>
                <div className="text-xs text-tertiary">Condensed presentation deck</div>
              </div>
            </button>

            <button
              onClick={() => handleDownload(onDownloadExcel)}
              disabled={isDownloadingExcel}
              className="w-full px-4 py-3 text-left text-sm hover:bg-surface-secondary transition-colors flex items-center gap-3 disabled:opacity-50 border-t"
            >
              {isDownloadingExcel ? (
                <div className="w-4 h-4 border-2 spinner-brand rounded-full animate-spin"></div>
              ) : (
                <svg className="w-4 h-4 text-accent-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2-2v8a2 2 0 002 2z" />
                </svg>
              )}
              <div>
                <div className="font-medium text-primary">Excel Model</div>
                <div className="text-xs text-tertiary">Financial model workbook</div>
              </div>
            </button>
          </div>
        )}
      </div>

      <button
        onClick={onAddToWatchlist}
        disabled={watchlistAdded}
        className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
          watchlistAdded
            ? 'bg-surface-tertiary text-tertiary cursor-not-allowed'
            : 'border border-accent-info text-accent-info-dark bg-accent-info-light hover:bg-accent-info hover:text-white'
        }`}
      >
        <svg className="w-4 h-4" fill={watchlistAdded ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
        </svg>
        {watchlistAdded ? 'Watchlisted' : 'Watchlist'}
      </button>
    </div>
  )
}

export default ActionButtons
