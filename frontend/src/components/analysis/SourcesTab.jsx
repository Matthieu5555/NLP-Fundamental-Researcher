import { useState } from 'react'

/**
 * Sources tab with active/excluded source lists and exclude/restore controls.
 */
function SourcesTab({ sources, excludedSourceIds, onExclude, onRestore }) {
  const [showExcluded, setShowExcluded] = useState(false)

  const isExcludable = (sourceType) => sourceType === 'news' || sourceType === 'search'

  const visibleSources = sources.filter(s => !excludedSourceIds.includes(s.id))
  const excludedSources = sources.filter(s => excludedSourceIds.includes(s.id))

  return (
    <div className="space-y-4">
      <div className="mb-6">
        <h3 className="text-xl font-bold text-slate-800">Sources</h3>
        <p className="text-sm text-slate-500 mt-1">
          Data sources used in this analysis. Click any link to view the original source.
          <span className="text-slate-400"> News sources can be excluded.</span>
        </p>
      </div>

      {sources.length === 0 ? (
        <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
          <p className="text-lg font-medium">No sources available</p>
          <p className="text-sm mt-2">Sources will appear here after analysis completes</p>
        </div>
      ) : (
        <>
          {/* Active Sources */}
          <div className="space-y-3">
            {visibleSources.map((source) => (
              <div key={source.id} className="bg-slate-50 rounded-lg p-4 border border-slate-200 hover:border-slate-300 transition-colors group">
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white" style={{ backgroundColor: 'var(--brand-primary)' }}>
                    {source.id}
                  </span>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-slate-800 text-sm">{source.title}</h4>
                    {source.url && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand hover:underline text-xs break-all block mt-1"
                      >
                        {source.url}
                      </a>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-200 text-slate-600 capitalize">
                        {source.source_type}
                      </span>
                      <span>Date: {source.date}</span>
                    </div>
                  </div>
                  {isExcludable(source.source_type) && (
                    <button
                      onClick={() => onExclude(source.id)}
                      className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-full hover:bg-accent-danger-light text-slate-400 hover:text-accent-danger"
                      title="Exclude this source"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Excluded Sources */}
          {excludedSources.length > 0 && (
            <div className="mt-6">
              <button
                onClick={() => setShowExcluded(!showExcluded)}
                className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 transition-colors"
              >
                <svg className={`w-4 h-4 transition-transform ${showExcluded ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Show excluded ({excludedSources.length})
              </button>

              {showExcluded && (
                <div className="mt-3 space-y-3">
                  {excludedSources.map((source) => (
                    <div key={source.id} className="bg-slate-100 rounded-lg p-4 border border-slate-200 opacity-60">
                      <div className="flex items-start gap-3">
                        <span className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white bg-slate-400">
                          {source.id}
                        </span>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-semibold text-slate-600 text-sm line-through">{source.title}</h4>
                          <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-200 text-slate-500 capitalize">
                              {source.source_type}
                            </span>
                            <span>Date: {source.date}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => onRestore(source.id)}
                          className="flex-shrink-0 px-3 py-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-600 hover:text-slate-800 text-xs font-medium transition-colors flex items-center gap-1"
                          title="Restore this source"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                          </svg>
                          Restore
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default SourcesTab
