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
        <h3 className="text-xl font-bold text-primary">Sources</h3>
        <p className="text-sm text-tertiary mt-1">
          Data sources used in this analysis. Click any link to view the original source.
          <span className="text-muted"> News sources can be excluded.</span>
        </p>
      </div>

      {sources.length === 0 ? (
        <div className="text-center py-12 text-tertiary bg-surface-secondary rounded-lg">
          <p className="text-lg font-medium">No sources available</p>
          <p className="text-sm mt-2">Sources will appear here after analysis completes</p>
        </div>
      ) : (
        <>
          {/* Active Sources */}
          <div className="space-y-3">
            {visibleSources.map((source) => (
              <div key={source.id} className="bg-surface-secondary rounded-lg p-4 hover:bg-surface-tertiary transition-colors group">
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white bg-brand">
                    {source.id}
                  </span>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-primary text-sm">{source.title}</h4>
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
                    <div className="flex items-center gap-3 mt-2 text-xs text-tertiary">
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-card-hover text-secondary capitalize">
                        {source.source_type}
                      </span>
                      <span>Date: {source.date}</span>
                    </div>
                  </div>
                  {isExcludable(source.source_type) && (
                    <button
                      onClick={() => onExclude(source.id)}
                      className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-full hover:bg-accent-danger-light text-muted hover:text-accent-danger"
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
                className="flex items-center gap-2 text-sm text-tertiary hover:text-primary transition-colors"
              >
                <svg className={`w-4 h-4 transition-transform ${showExcluded ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Show excluded ({excludedSources.length})
              </button>

              {showExcluded && (
                <div className="mt-3 space-y-3">
                  {excludedSources.map((source) => (
                    <div key={source.id} className="bg-surface-tertiary rounded-lg p-4 opacity-60">
                      <div className="flex items-start gap-3">
                        <span className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white bg-surface-card-hover">
                          {source.id}
                        </span>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-semibold text-secondary text-sm line-through">{source.title}</h4>
                          <div className="flex items-center gap-3 mt-2 text-xs text-muted">
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-card-hover text-tertiary capitalize">
                              {source.source_type}
                            </span>
                            <span>Date: {source.date}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => onRestore(source.id)}
                          className="flex-shrink-0 px-3 py-1.5 rounded-lg bg-surface-card-hover hover:bg-surface-card-hover text-secondary hover:text-primary text-xs font-medium transition-colors flex items-center gap-1"
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
