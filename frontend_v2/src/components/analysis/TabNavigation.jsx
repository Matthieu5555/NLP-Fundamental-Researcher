/**
 * Tab navigation bar for analysis sections.
 * Handles amber (workflow) tabs, disabled tabs, and active indicators.
 */
function TabNavigation({ tabs, activeTab, onTabChange, sections, beliefs }) {
  return (
    <div className="border-b bg-surface-secondary">
      <nav className="flex overflow-x-auto px-4">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id
          const hasContent = tab.hasContent
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
                    : 'bg-surface-elevated border-brand text-brand'
                  : hasContent
                    ? isAmberTab
                      ? 'border-transparent text-accent-warning hover:text-accent-warning-dark hover:border-accent-warning hover:bg-accent-warning-light cursor-pointer'
                      : isDisabledTab
                        ? 'border-transparent text-muted hover:text-tertiary cursor-pointer'
                        : 'border-transparent text-secondary hover:text-primary hover:border-medium cursor-pointer'
                    : 'border-transparent text-muted cursor-not-allowed'
                }
                ${tab.id === 'analyst_notes' && beliefs.length > 0 ? 'font-bold' : ''}
              `}
            >
              <span>{tab.label}</span>
              {tab.id === 'analyst_notes' && beliefs.length > 0 && (
                <span className="ml-1 w-2 h-2 rounded-full bg-accent-warning animate-pulse"></span>
              )}
              {isDisabledTab && (
                <span className="ml-1 text-xs text-muted">(US only)</span>
              )}
            </button>
          )
        })}
      </nav>
    </div>
  )
}

export default TabNavigation
