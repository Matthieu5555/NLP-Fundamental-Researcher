import TechnicalChart from '../TechnicalChart'
import ChartErrorBoundary from '../ChartErrorBoundary'
import ConvictionScore from '../ConvictionScore'
import MarkdownSection from './MarkdownSection'
import AnalystNotesTab from './AnalystNotesTab'
import SourcesTab from './SourcesTab'
import FurtherResearchTab from './FurtherResearchTab'
import FinancialsTab from './FinancialsTab'
import ValuationTab from './ValuationTab'

/**
 * Data-driven tab definitions. Each entry declares its metadata and
 * either a render function (for special tabs) or a sectionKey (for
 * tabs that just render a markdown section with a heading).
 *
 * Ordered by analyst workflow first (workspace tabs), then analysis
 * results by importance for investment decision-making.
 *
 * ctx shape: { sections, beliefs, valuation, financialStatements,
 *              financialsLoading, companyInfo, excludedSourceIds,
 *              onExclude, onRestore, ticker }
 */
export const TAB_REGISTRY = [
  // --- Analyst workspace tabs (amber) ---
  {
    id: 'analyst_notes',
    label: 'Analyst Notes',
    special: 'amber',
    labelSuffix: (ctx) => ctx.beliefs.length > 0 ? ` (${ctx.beliefs.length})` : '',
    render: (ctx) => <AnalystNotesTab beliefs={ctx.beliefs} />,
  },
  {
    id: 'further_research',
    label: 'Further Research',
    special: 'amber',
    render: (ctx) => <FurtherResearchTab contradictions={ctx.contradictions} researchGaps={ctx.researchGaps} />,
  },
  {
    id: 'sources',
    label: 'Sources',
    special: 'amber',
    render: (ctx) => (
      <SourcesTab
        sources={ctx.allSources}
        excludedSourceIds={ctx.excludedSourceIds}
        onExclude={ctx.onExclude}
        onRestore={ctx.onRestore}
      />
    ),
  },
  // --- Analysis results by importance ---
  {
    id: 'thesis',
    label: 'Investment Thesis',
    special: 'amber',
    render: (ctx) => {
      if (ctx.sections.investment_thesis) {
        return <MarkdownSection content={ctx.sections.investment_thesis.content || 'No content available'} />
      }
      // Before investment_thesis is generated, show just the recommendation section
      if (ctx.sections.recommendation) {
        return <MarkdownSection content={ctx.sections.recommendation.content || 'No content available'} />
      }
      return renderEmpty()
    },
  },
  {
    id: 'conviction',
    label: 'Conviction',
    render: (ctx) => (
      <div className="space-y-6">
        <div>
          <h3 className="text-xl font-bold text-primary">Conviction Score</h3>
          <p className="text-sm text-tertiary mt-1">Decomposed investment conviction across key dimensions</p>
        </div>
        {ctx.valuation.conviction ? (
          <ConvictionScore data={ctx.valuation.conviction} />
        ) : ctx.sections.conviction ? (
          <MarkdownSection content={ctx.sections.conviction.content} />
        ) : (
          <div className="text-center py-12 text-tertiary bg-surface-secondary rounded-lg">
            <p className="text-lg font-medium">Conviction scoring not available</p>
          </div>
        )}
      </div>
    ),
  },
  {
    id: 'valuation',
    label: 'Financials & Valuation',
    render: (ctx) => (
      <ValuationTab
        sections={ctx.sections}
        dcf={ctx.valuation.dcf}
        sensitivity={ctx.valuation.sensitivity}
        conviction={ctx.valuation.conviction}
        scenarios={ctx.valuation.scenarios}
        footballField={ctx.valuation.footballField}
        earningsModel={ctx.valuation.earningsModel}
        precedents={ctx.valuation.precedents}
        sensitivityOperating={ctx.valuation.sensitivityOperating}
        financialStatements={ctx.financialStatements}
        financialsLoading={ctx.financialsLoading}
        companyInfo={ctx.companyInfo}
      />
    ),
  },
  {
    id: 'fundamentals_moat',
    label: 'Fundamentals & Moat',
    render: (ctx) => {
      const fundamentals = ctx.sections.fundamentals
      const moat = ctx.sections.moat
      if (!fundamentals && !moat) {
        if (Object.keys(ctx.sections).length === 0) return renderEmpty()
        return renderSectionNotAvailable({ label: 'Fundamentals & Moat', heading: 'Fundamentals & Moat' })
      }
      return (
        <div className="space-y-6">
          {fundamentals && (
            <>
              <div>
                <h3 className="text-xl font-bold text-primary">Fundamental Analysis</h3>
              </div>
              <MarkdownSection content={fundamentals.content} />
            </>
          )}
          {fundamentals && moat && (
            <hr className="border-border-light" />
          )}
          {moat && (
            <>
              <div>
                <h3 className="text-xl font-bold text-primary">Competitive Moat</h3>
              </div>
              <MarkdownSection content={moat.content} />
            </>
          )}
        </div>
      )
    },
  },
  {
    id: 'strategy',
    label: 'Industry & Strategy',
    render: (ctx) => {
      const strategy = ctx.sections.strategy
      const external = ctx.sections.industry
      if (!strategy && !external) {
        if (Object.keys(ctx.sections).length === 0) return renderEmpty()
        return renderSectionNotAvailable({ label: 'Industry & Strategy', heading: 'Industry & Strategy' })
      }
      return (
        <div className="space-y-6">
          {strategy && (
            <>
              <div>
                <h3 className="text-xl font-bold text-primary">Strategic Assessment</h3>
              </div>
              <MarkdownSection content={strategy.content} />
            </>
          )}
          {strategy && external && (
            <hr className="border-border-light" />
          )}
          {external && (
            <>
              <div>
                <h3 className="text-xl font-bold text-primary">Industry Dynamics</h3>
                <p className="text-sm text-tertiary mt-1">Regulatory environment, competitive dynamics, and addressable market</p>
              </div>
              <MarkdownSection content={external.content} />
            </>
          )}
        </div>
      )
    },
  },
  {
    id: 'bull_case',
    label: 'Bull Case',
    sectionKey: 'bull_case',
  },
  {
    id: 'bear_case',
    label: 'Bear Case',
    sectionKey: 'bear_case',
  },
  {
    id: 'charts',
    label: 'Charts',
    render: (ctx) => (
      <div className="space-y-4">
        <div className="mb-4">
          <h3 className="text-xl font-bold text-primary">Interactive Charts</h3>
          <p className="text-sm text-tertiary mt-1">Price action with technical indicators. Use the timeframe buttons to adjust the view.</p>
        </div>
        <ChartErrorBoundary>
          <TechnicalChart ticker={ctx.ticker} />
        </ChartErrorBoundary>
      </div>
    ),
  },
  {
    id: 'technicals',
    label: 'Chartism',
    sectionKey: 'technicals',
    heading: 'Chartism Analysis',
    emptyMessage: 'No chartism analysis available',
    emptySubMessage: 'Technical analysis will appear here after analysis completes',
  },
]

/**
 * Build the tabs array for TabNavigation (with dynamic labels and special flags).
 */
export function buildTabs(ctx) {
  return TAB_REGISTRY.map(tab => {
    // Tabs with custom render functions always have content (they handle empty state internally).
    // Section-key tabs have content when their key exists in the sections dict.
    const hasContent = !!tab.render || !!(tab.sectionKey && ctx.sections[tab.sectionKey])
    return {
      id: tab.id,
      label: tab.label + (tab.labelSuffix ? tab.labelSuffix(ctx) : ''),
      special: tab.specialFn ? tab.specialFn(ctx) : (tab.special || null),
      hasContent,
    }
  })
}

/**
 * Render content for the active tab using the registry.
 */
export function renderTab(tabId, ctx) {
  const tab = TAB_REGISTRY.find(t => t.id === tabId)

  if (!tab) return renderNotAvailable(ctx.sections)

  // Custom render function takes priority
  if (tab.render) return tab.render(ctx)

  // Default: render markdown section by sectionKey
  const section = ctx.sections[tab.sectionKey]
  if (!section) {
    if (Object.keys(ctx.sections).length === 0) return renderEmpty()
    return renderSectionNotAvailable(tab)
  }

  return (
    <div className="space-y-6">
      {tab.heading && (
        <div>
          <h3 className="text-xl font-bold text-primary">{tab.heading}</h3>
          {tab.subheading && <p className="text-sm text-tertiary mt-1">{tab.subheading}</p>}
        </div>
      )}
      <MarkdownSection content={section.content} />
    </div>
  )
}

// --- Shared renderers ---

function renderGenericSections(sections) {
  return (
    <div className="space-y-8">
      {Object.entries(sections).map(([sectionId, section]) => (
        <div key={sectionId} className="pb-8 last:pb-0">
          <h3 className="text-xl font-bold text-primary mb-4">
            {section?.title || 'Section'}
          </h3>
          <MarkdownSection content={section?.content || 'No content available'} />
        </div>
      ))}
    </div>
  )
}

function renderEmpty() {
  return (
    <div className="text-center py-16 text-tertiary">
      <p className="text-lg font-medium">No analysis results yet</p>
      <p className="text-sm mt-2">Results will appear here when analysis completes</p>
    </div>
  )
}

function renderNotAvailable(sections) {
  if (Object.keys(sections).length === 0) return renderEmpty()
  return (
    <div className="text-center py-16 text-tertiary">
      <p className="text-lg font-medium">Section not available</p>
      <p className="text-sm mt-2">This section may not have been generated during analysis. Try running a new analysis or check the Full Report tab.</p>
    </div>
  )
}

function renderSectionNotAvailable(tab) {
  return (
    <div className="space-y-6">
      {tab.heading && (
        <div>
          <h3 className="text-xl font-bold text-primary">{tab.heading}</h3>
          {tab.subheading && <p className="text-sm text-tertiary mt-1">{tab.subheading}</p>}
        </div>
      )}
      <div className="text-center py-12 text-tertiary bg-surface-secondary rounded-lg">
        <p className="text-lg font-medium">{tab.emptyMessage || `${tab.label} not available`}</p>
        {tab.emptySubMessage && <p className="text-sm mt-2">{tab.emptySubMessage}</p>}
      </div>
    </div>
  )
}
