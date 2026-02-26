/**
 * Tab navigation bar for analysis sections.
 * Handles amber (workflow) tabs, disabled tabs, and active indicators.
 */
function TabNavigation({ tabs, activeTab, onTabChange, sections, beliefs }) {
  return (
    <div className="border-b border-slate-200 bg-slate-50">
      <nav className="flex overflow-x-auto px-4">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id
          const hasContent = tab.id === 'all' || tab.id === 'analyst_notes' || tab.id === 'further_research' || tab.id === 'sources' || tab.id === 'charts' || tab.id === 'financials_tab' || tab.id === 'valuation' || tab.id === 'external_forces' || tab.id === 'conviction' || sections[tab.id]
          const isAmberTab = tab.special === 'amber'
          const isDisabledTab = tab.special === 'disabled'

          return (
            <button
              key={tab.id}
              onClick={() => hasContent && onTabChange(tab.id)}
              disabled={!hasContent}
              title={isDisabledTab ? 'Not available for non-US companies' : ''}
              className={`
                flex items-center space-x-2 px-5 py-4 border-b-2 font-medium text-sm whitespace-nowrap transition-all
                ${isActive
                  ? isAmberTab
                    ? 'bg-accent-warning-light border-accent-warning text-accent-warning-dark'
                    : 'bg-white border-brand text-brand'
                  : hasContent
                    ? isAmberTab
                      ? 'border-transparent text-accent-warning hover:text-accent-warning-dark hover:border-accent-warning hover:bg-accent-warning-light/50 cursor-pointer'
                      : isDisabledTab
                        ? 'border-transparent text-slate-400 hover:text-slate-500 cursor-pointer'
                        : 'border-transparent text-slate-600 hover:text-slate-800 hover:border-slate-300 cursor-pointer'
                    : 'border-transparent text-slate-400 cursor-not-allowed'
                }
                ${tab.id === 'analyst_notes' && beliefs.length > 0 ? 'font-bold' : ''}
              `}
            >
              <span>{tab.label}</span>
              {tab.id === 'analyst_notes' && beliefs.length > 0 && (
                <span className="ml-1 w-2 h-2 rounded-full bg-accent-warning animate-pulse"></span>
              )}
              {isDisabledTab && (
                <span className="ml-1 text-xs text-slate-400">(US only)</span>
              )}
            </button>
          )
        })}
      </nav>
    </div>
  )
}

export default TabNavigation
