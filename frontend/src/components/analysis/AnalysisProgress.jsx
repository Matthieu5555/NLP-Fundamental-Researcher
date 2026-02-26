/**
 * Displays analysis progress with a step counter, progress bar, and status message.
 * Also handles the SSE stream connection and parsing.
 */
function AnalysisProgress({ progress, progressStep, progressTotal }) {
  return (
    <div className="px-6 py-12 bg-white">
      <div className="max-w-md mx-auto">
        {/* Progress bar */}
        <div className="mb-4">
          <div className="flex justify-between text-sm text-slate-600 mb-2">
            <span>Step {Math.min(progressStep, progressTotal)} of {progressTotal}</span>
            <span>{Math.min(100, Math.round((progressStep / progressTotal) * 100))}%</span>
          </div>
          <div className="w-full h-3 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500 ease-out bg-brand-gradient"
              style={{ width: `${Math.min(100, (progressStep / progressTotal) * 100)}%` }}
            />
          </div>
        </div>

        {/* Status message */}
        <div className="text-center">
          <div className="inline-flex items-center justify-center space-x-3 mb-3">
            <div className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--brand-primary)', borderTopColor: 'transparent' }}></div>
            <p className="text-lg text-slate-700 font-medium">{progress || 'Initializing analysis...'}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AnalysisProgress
