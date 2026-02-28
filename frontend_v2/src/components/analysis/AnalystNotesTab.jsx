/**
 * Displays analyst beliefs grouped by section with badges and confidence bars.
 */
function AnalystNotesTab({ beliefs }) {
  // Group beliefs by section
  const beliefsBySection = beliefs.reduce((acc, belief) => {
    const section = belief.section || 'general'
    if (!acc[section]) acc[section] = []
    acc[section].push(belief)
    return acc
  }, {})

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-xl font-bold text-primary">Analyst Notes</h3>
          <p className="text-sm text-tertiary mt-1">
            Your insights and conclusions from the analysis conversation
          </p>
        </div>
      </div>

      {beliefs.length === 0 ? (
        <div className="text-center py-12 text-tertiary bg-surface-secondary rounded-lg">
          <svg className="w-12 h-12 mx-auto mb-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-lg font-medium text-primary">No analyst notes yet</p>
          <p className="text-sm mt-2 text-tertiary max-w-md mx-auto">
            Express your views in chat to capture insights here.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(beliefsBySection).map(([sectionName, sectionBeliefs]) => (
            <div key={sectionName} className="rounded-lg overflow-hidden card-section-bg">
              <div className="border-b bg-surface-tertiary px-4 py-3">
                <h4 className="font-semibold text-primary capitalize text-sm tracking-wide">
                  {sectionName.replace(/_/g, ' ')}
                </h4>
              </div>
              <div className="divide-y divide">
                {sectionBeliefs.map((belief, idx) => (
                  <div key={idx} className="px-4 py-4 hover:bg-surface-secondary transition-colors">
                    <div className="flex items-start gap-3">
                      <span className="flex-shrink-0 px-2 py-1 rounded text-xs font-bold uppercase tracking-wide belief-badge">
                        {belief.badge || belief.type?.replace(/_/g, ' ') || 'NOTE'}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-primary leading-relaxed">{belief.content}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs text-tertiary">Confidence:</span>
                          <div className="flex-1 max-w-[100px] h-1.5 bg-surface-card-hover rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${(belief.confidence || 0.7) * 100}%`,
                                backgroundColor: belief.badge_color || 'var(--accent-warning-dark)'
                              }}
                            />
                          </div>
                          <span className="text-xs text-tertiary">{Math.round((belief.confidence || 0.7) * 100)}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {beliefs.length > 0 && (
        <div className="rounded-lg p-4 mt-4 card-section-bg">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-tertiary flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-primary">
              <strong>Tip:</strong> Click "UPDATE MODELS" to recalculate valuations and re-run analysis with your overrides, or "UPDATE REPORT" to just rewrite the narrative.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default AnalystNotesTab
