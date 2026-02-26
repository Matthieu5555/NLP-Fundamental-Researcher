/**
 * Further Research tab showing contradictions (bull vs bear cards) and research gaps.
 */
function FurtherResearchTab({ contradictions, researchGaps }) {
  const hasContent = contradictions.length > 0 || researchGaps.length > 0

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-xl font-bold text-slate-800">Further Research</h3>
        <p className="text-sm text-slate-500 mt-1">
          Key disagreements between bulls and bears that require your judgment
        </p>
      </div>

      {!hasContent ? (
        <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-xl border border-slate-200">
          <svg className="w-16 h-16 mx-auto mb-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-lg font-medium">No major contradictions found</p>
          <p className="text-sm mt-2">The analysis presents a relatively consistent view.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Contradictions */}
          {contradictions.length > 0 && (
            <>
              <h4 className="text-lg font-semibold text-slate-700 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                Key Disagreements
              </h4>
              <div className="space-y-4">
                {contradictions.map((c, idx) => (
                  <div key={idx} className="bg-white rounded-xl border-2 border-slate-200 overflow-hidden shadow-sm">
                    <div className="px-5 py-4 border-b border-slate-200 card-section-bg">
                      <div className="flex-1">
                        <h5 className="font-bold text-slate-800">{c.disputed_fact}</h5>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-2 ${c.priority === 'HIGH' ? 'badge-high' : 'bg-slate-200 text-slate-700'}`}>
                          {c.priority} PRIORITY
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 divide-x divide-slate-200">
                      <div className="p-4 bg-accent-success-light/50">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="w-3 h-3 rounded-full bg-accent-success"></span>
                          <span className="text-xs font-bold text-accent-success-dark uppercase tracking-wide">Bulls Argue</span>
                        </div>
                        <p className="text-sm text-slate-700 leading-relaxed">{c.bull_interpretation}</p>
                      </div>

                      <div className="p-4 bg-accent-danger-light/50">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="w-3 h-3 rounded-full bg-accent-danger"></span>
                          <span className="text-xs font-bold text-accent-danger-dark uppercase tracking-wide">Bears Argue</span>
                        </div>
                        <p className="text-sm text-slate-700 leading-relaxed">{c.bear_interpretation}</p>
                      </div>
                    </div>

                    <div className="px-5 py-3 border-t border-slate-200 card-section-bg">
                      <p className="text-sm text-slate-700">
                        <strong>Your call:</strong> {c.judgment_question}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Research Gaps */}
          {researchGaps.length > 0 && (
            <>
              <h4 className="text-lg font-semibold text-slate-700 flex items-center gap-2 mt-6">
                <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                Research Gaps
              </h4>
              <div className="grid gap-3">
                {researchGaps.map((g, idx) => (
                  <div key={idx} className="rounded-lg p-4 border border-slate-200 card-section-bg">
                    <div className="flex items-start gap-3">
                      <span className={`flex-shrink-0 px-2 py-1 rounded text-xs font-bold uppercase ${g.priority === 'HIGH' ? 'badge-high' : 'bg-slate-200 text-slate-700'}`}>
                        {g.priority}
                      </span>
                      <div className="flex-1">
                        <h5 className="font-semibold text-slate-800 text-sm">{g.title}</h5>
                        <p className="text-sm text-slate-600 mt-1">{g.description}</p>
                        <p className="text-xs text-slate-500 mt-2">
                          <span className="font-medium">Data source:</span> {g.data_source}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {hasContent && (
        <div className="border border-slate-200 rounded-lg p-4 card-section-bg">
          <p className="text-sm text-slate-700">
            <strong>Tip:</strong> Use the chat below to investigate these items. Ask questions like "What's the evidence for the bull case on valuation?" to gather more information.
          </p>
        </div>
      )}
    </div>
  )
}

export default FurtherResearchTab
