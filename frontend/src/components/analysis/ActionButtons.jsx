/**
 * Header action buttons: Update Report, Download PDF, Add to Watchlist.
 */
function ActionButtons({ onUpdateReport, onDownloadReport, onAddToWatchlist, reportDirty, isUpdatingReport, isDownloadingPdf, watchlistAdded }) {
  return (
    <div className="flex gap-3">
      {onUpdateReport && (
        <button
          onClick={onUpdateReport}
          disabled={!reportDirty || isUpdatingReport}
          className="px-6 py-3 text-sm font-semibold text-white bg-brand-gradient hover:opacity-90 rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-md flex items-center gap-2"
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
              UPDATE REPORT
            </>
          )}
        </button>
      )}

      <button
        onClick={onDownloadReport}
        disabled={isUpdatingReport || reportDirty || isDownloadingPdf}
        title={reportDirty ? 'Update report first to include latest insights' : ''}
        className="px-6 py-3 text-sm font-semibold text-white bg-accent-success-gradient hover:opacity-90 rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
      >
        {isDownloadingPdf ? (
          <>
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            Generating PDF...
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            DOWNLOAD PDF
          </>
        )}
      </button>

      <button
        onClick={onAddToWatchlist}
        disabled={watchlistAdded}
        className={`px-4 py-3 text-sm font-semibold rounded-lg shadow-md transition-all flex items-center gap-2 ${
          watchlistAdded
            ? 'bg-slate-100 text-slate-500 cursor-not-allowed'
            : 'text-white bg-accent-info-gradient hover:opacity-90 hover:shadow-lg'
        }`}
      >
        <svg className="w-4 h-4" fill={watchlistAdded ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
        </svg>
        {watchlistAdded ? 'WATCHLISTED' : 'WATCHLIST'}
      </button>
    </div>
  )
}

export default ActionButtons
