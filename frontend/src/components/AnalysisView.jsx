import { useState, useEffect, useRef, useCallback } from 'react'
import TechnicalChart from './TechnicalChart'
import ChartErrorBoundary from './ChartErrorBoundary'
import DataAvailabilityBanner from './DataAvailabilityBanner'
import ConvictionScore from './ConvictionScore'
import { authFetch, API_URL } from '../utils/api'
import { parseSSEStream } from '../hooks/useSSEStream'

// Extracted sub-components
import AnalysisProgress from './analysis/AnalysisProgress'
import CostBreakdown from './analysis/CostBreakdown'
import ActionButtons from './analysis/ActionButtons'
import TabNavigation from './analysis/TabNavigation'
import MarkdownSection from './analysis/MarkdownSection'
import AnalystNotesTab from './analysis/AnalystNotesTab'
import SourcesTab from './analysis/SourcesTab'
import FurtherResearchTab from './analysis/FurtherResearchTab'
import FinancialsTab from './analysis/FinancialsTab'
import ValuationTab from './analysis/ValuationTab'

function AnalysisView({ sessionId, ticker, onAnalysisComplete, reportVersion = 0, beliefs = [], isResumed = false, reportDirty = false, onUpdateReport, isUpdatingReport = false, chatCost = 0 }) {
  const [activeTab, setActiveTab] = useState('all')
  const [analysisRunning, setAnalysisRunning] = useState(false)
  const [sectionsLoading, setSectionsLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [progressStep, setProgressStep] = useState(0)
  const [progressTotal, setProgressTotal] = useState(10)
  const [sections, setSections] = useState({})
  const [contradictions, setContradictions] = useState([])
  const [researchGaps, setResearchGaps] = useState([])
  const [excludedSourceIds, setExcludedSourceIds] = useState([])
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false)
  const [error, setError] = useState(null)
  const [costUsd, setCostUsd] = useState(null)
  const [costBreakdown, setCostBreakdown] = useState(null)
  const [financialStatements, setFinancialStatements] = useState(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)
  const [companyInfo, setCompanyInfo] = useState(null)
  const [dcfModel, setDcfModel] = useState(null)
  const [sensitivityData, setSensitivityData] = useState(null)
  const [convictionData, setConvictionData] = useState(null)
  const [scenarioData, setScenarioData] = useState(null)
  const [footballFieldData, setFootballFieldData] = useState(null)
  const [earningsModelData, setEarningsModelData] = useState(null)
  const [precedentData, setPrecedentData] = useState(null)
  const [growthMarginSensitivityData, setGrowthMarginSensitivityData] = useState(null)
  const [watchlistAdded, setWatchlistAdded] = useState(false)
  const initRef = useRef({ sessionId: null, started: false })
  const analysisRunningRef = useRef(false)

  // --- Effects ---

  useEffect(() => {
    if (!sessionId) return
    if (initRef.current.sessionId === sessionId && initRef.current.started) return
    initRef.current = { sessionId, started: true }

    if (isResumed) {
      setAnalysisRunning(false)
      loadSections()
      onAnalysisComplete()
    } else {
      runAnalysis()
    }
  }, [sessionId])

  useEffect(() => {
    if (reportVersion > 0 && !analysisRunning) {
      loadSections()
    }
  }, [reportVersion])

  // --- Data Loading ---

  const runAnalysis = async () => {
    setAnalysisRunning(true)
    analysisRunningRef.current = true
    setError(null)

    try {
      const startResponse = await authFetch(`${API_URL}/api/analysis/${sessionId}/run`, { method: 'POST' })
      if (!startResponse.ok) throw new Error('Failed to start analysis')

      const finishStream = () => {
        if (analysisRunningRef.current) {
          analysisRunningRef.current = false
          setAnalysisRunning(false)
          loadSections()
        }
      }

      await parseSSEStream(startResponse, {
        onJSON(parsed) {
          if (parsed.status === 'error') {
            setError(parsed.message)
            analysisRunningRef.current = false
            setAnalysisRunning(false)
            return
          }
          setProgress(parsed.message || '')
          if (parsed.step !== undefined) setProgressStep(parsed.step)
          if (parsed.total !== undefined) setProgressTotal(parsed.total)
          if (parsed.cost_usd !== undefined) setCostUsd(parsed.cost_usd)
          if (parsed.cost_breakdown) setCostBreakdown(parsed.cost_breakdown)
        },
        onDone: finishStream,
        onError(err) {
          console.error('Stream processing error:', err)
          setError('Analysis stream interrupted. Try refreshing the page.')
          analysisRunningRef.current = false
          setAnalysisRunning(false)
        },
      })
    } catch (err) {
      console.error('Analysis error:', err)
      setError('Failed to run analysis')
      analysisRunningRef.current = false
      setAnalysisRunning(false)
    }
  }

  const loadSections = async () => {
    setSectionsLoading(true)
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sections`)
      const data = await response.json()
      setSections(data.sections || {})
      setContradictions(data.contradictions || [])
      setResearchGaps(data.research_gaps || [])
      setExcludedSourceIds(data.excluded_source_ids || [])
      setSectionsLoading(false)
      onAnalysisComplete()

      loadCompanyInfo()
      loadFinancialStatements()
      loadValuationData()
    } catch (err) {
      console.error('Load sections error:', err)
      setError('Failed to load analysis results')
      setSectionsLoading(false)
    }
  }

  const loadCompanyInfo = async () => {
    try {
      const response = await authFetch(`${API_URL}/api/analysis/${sessionId}/company-info`)
      setCompanyInfo(await response.json())
    } catch (err) {
      console.error('Load company info error:', err)
    }
  }

  const loadFinancialStatements = async () => {
    setFinancialsLoading(true)
    try {
      const response = await authFetch(`${API_URL}/api/analysis/${sessionId}/financial-statements`)
      setFinancialStatements(await response.json())
    } catch (err) {
      console.error('Load financial statements error:', err)
      setFinancialStatements({ is_available: false, error: err.message })
    } finally {
      setFinancialsLoading(false)
    }
  }

  const loadValuationData = async () => {
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/valuation-data`)
      const data = await response.json()
      if (data.dcf_model) setDcfModel(data.dcf_model)
      if (data.sensitivity_data) setSensitivityData(data.sensitivity_data)
      if (data.conviction_data) setConvictionData(data.conviction_data)
      if (data.scenario_data) setScenarioData(data.scenario_data)
      if (data.football_field_data) setFootballFieldData(data.football_field_data)
      if (data.earnings_model_data) setEarningsModelData(data.earnings_model_data)
      if (data.precedent_data) setPrecedentData(data.precedent_data)
      if (data.growth_margin_sensitivity_data) setGrowthMarginSensitivityData(data.growth_margin_sensitivity_data)
    } catch (err) {
      console.error('Load valuation data error:', err)
    }
  }

  // --- Actions ---

  const handleExcludeSource = async (sourceId) => {
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sources/${sourceId}/exclude`, { method: 'POST' })
      const data = await response.json()
      if (data.success) setExcludedSourceIds(data.excluded_source_ids)
    } catch (err) {
      console.error('Exclude source error:', err)
    }
  }

  const handleRestoreSource = async (sourceId) => {
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sources/${sourceId}/restore`, { method: 'POST' })
      const data = await response.json()
      if (data.success) setExcludedSourceIds(data.excluded_source_ids)
    } catch (err) {
      console.error('Restore source error:', err)
    }
  }

  const addToWatchlist = async () => {
    try {
      const response = await authFetch(`${API_URL}/api/watchlist/${ticker}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
      if (response.ok) setWatchlistAdded(true)
    } catch (err) {
      console.error('Failed to add to watchlist:', err)
    }
  }

  const downloadReport = async () => {
    setIsDownloadingPdf(true)
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/export/pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })

      const contentType = response.headers.get('content-type')
      if (!response.ok || contentType?.includes('application/json')) {
        const errorData = await response.json()
        throw new Error(errorData.details || errorData.error || 'PDF export failed')
      }

      const blob = await response.blob()
      if (blob.size < 1000) throw new Error('Generated PDF is too small - report may be empty')

      const downloadUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `${ticker}_analysis_${new Date().toISOString().split('T')[0]}.pdf`
      a.click()
      window.URL.revokeObjectURL(downloadUrl)
    } catch (err) {
      console.error('Download error:', err)
      alert(`PDF download failed: ${err.message}`)
    } finally {
      setIsDownloadingPdf(false)
    }
  }

  // --- Derived Data ---

  const getAllSources = () => {
    const sourcesSection = sections.sources
    return (sourcesSection?.sources && Array.isArray(sourcesSection.sources)) ? sourcesSection.sources : []
  }

  const tabs = [
    { id: 'analyst_notes', label: `Analyst Notes${beliefs.length > 0 ? ` (${beliefs.length})` : ''}`, special: 'amber' },
    { id: 'further_research', label: 'Further Research', special: 'amber' },
    { id: 'sources', label: 'Sources', special: 'amber' },
    { id: 'all', label: 'Investment Thesis', special: 'amber' },
    { id: 'valuation', label: 'Valuation' },
    { id: 'conviction', label: 'Conviction' },
    { id: 'strategy', label: 'Strategy' },
    { id: 'moat', label: 'Moat' },
    { id: 'fundamentals', label: 'Fundamentals' },
    { id: 'financials_tab', label: 'Financials', special: financialStatements?.is_available ? null : 'disabled' },
    { id: 'bull_case', label: 'Bull Case' },
    { id: 'bear_case', label: 'Bear Case' },
    { id: 'external_forces', label: 'External Forces' },
    { id: 'charts', label: 'Charts' },
    { id: 'technicals', label: 'Chartism' },
  ]

  const getVisibleSections = () => {
    if (activeTab === 'all') return sections
    const section = sections[activeTab]
    return section ? { [activeTab]: section } : {}
  }

  const hasSections = Object.keys(sections).length > 0
  const showContent = !analysisRunning && !sectionsLoading && !error

  // --- Render ---

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-50 to-slate-100 border-b border-slate-200 px-6 py-5">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Analysis Results</h2>
            <div className="flex items-center gap-4 mt-1">
              <p className="text-sm text-slate-600">Multi-agent analysis for {ticker}</p>
              <CostBreakdown costUsd={costUsd} chatCost={chatCost} costBreakdown={costBreakdown} />
            </div>
          </div>
          {!analysisRunning && !sectionsLoading && hasSections && (
            <ActionButtons
              onUpdateReport={onUpdateReport}
              onDownloadReport={downloadReport}
              onAddToWatchlist={addToWatchlist}
              reportDirty={reportDirty}
              isUpdatingReport={isUpdatingReport}
              isDownloadingPdf={isDownloadingPdf}
              watchlistAdded={watchlistAdded}
            />
          )}
        </div>
      </div>

      {/* Data Availability Banner */}
      {companyInfo && !companyInfo.is_us && !analysisRunning && (
        <div className="px-6 pt-4">
          <DataAvailabilityBanner companyInfo={companyInfo} />
        </div>
      )}

      {/* Analysis Running */}
      {analysisRunning && (
        <AnalysisProgress progress={progress} progressStep={progressStep} progressTotal={progressTotal} />
      )}

      {/* Sections Loading */}
      {!analysisRunning && sectionsLoading && (
        <div className="px-6 py-12 text-center bg-white">
          <div className="inline-flex items-center justify-center space-x-3 mb-4">
            <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--brand-primary)', borderTopColor: 'transparent' }}></div>
          </div>
          <p className="text-slate-600">Loading analysis results...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="px-6 py-8 bg-white">
          <div className="bg-accent-danger-light border-2 border-accent-danger rounded-lg p-6 text-center">
            <p className="text-sm text-accent-danger-dark font-medium mb-4">{error}</p>
            <button onClick={runAnalysis} className="px-4 py-2 bg-accent-danger text-white rounded-lg hover:bg-accent-danger-dark">
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* Tabs and Content */}
      {showContent && (
        <>
          <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} sections={sections} beliefs={beliefs} />

          <div className="px-6 py-6 min-h-[400px] max-h-[600px] overflow-y-auto bg-white">
            {renderTabContent()}
          </div>

          {hasSections && (
            <div className="border-t border-slate-200 px-4 py-1 text-center" style={{ background: 'linear-gradient(to right, var(--brand-gradient-from), var(--brand-gradient-to))' }}>
              <p className="text-xs font-medium" style={{ color: 'var(--brand-primary)' }}>
                Scroll down to ask questions about this analysis
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )

  function renderTabContent() {
    switch (activeTab) {
      case 'analyst_notes':
        return <AnalystNotesTab beliefs={beliefs} />

      case 'sources':
        return (
          <SourcesTab
            sources={getAllSources()}
            excludedSourceIds={excludedSourceIds}
            onExclude={handleExcludeSource}
            onRestore={handleRestoreSource}
          />
        )

      case 'further_research':
        return <FurtherResearchTab contradictions={contradictions} researchGaps={researchGaps} />

      case 'financials_tab':
        return (
          <FinancialsTab
            financialStatements={financialStatements}
            financialsLoading={financialsLoading}
            companyInfo={companyInfo}
          />
        )

      case 'external_forces':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-bold text-slate-800">External Forces</h3>
              <p className="text-sm text-slate-500 mt-1">PESTEL analysis, Porter's Five Forces, and TAM/SAM/SOM</p>
            </div>
            {sections.external_forces ? (
              <MarkdownSection content={sections.external_forces.content} />
            ) : (
              <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                <p className="text-lg font-medium">External forces analysis not available</p>
              </div>
            )}
          </div>
        )

      case 'valuation':
        return (
          <ValuationTab
            sections={sections}
            dcfModel={dcfModel}
            sensitivityData={sensitivityData}
            convictionData={convictionData}
            scenarioData={scenarioData}
            footballFieldData={footballFieldData}
            earningsModelData={earningsModelData}
            precedentData={precedentData}
            growthMarginSensitivityData={growthMarginSensitivityData}
          />
        )

      case 'conviction':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-bold text-slate-800">Conviction Score</h3>
              <p className="text-sm text-slate-500 mt-1">Decomposed investment conviction across key dimensions</p>
            </div>
            {convictionData ? (
              <ConvictionScore convictionData={convictionData} />
            ) : sections.conviction ? (
              <MarkdownSection content={sections.conviction.content} />
            ) : (
              <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                <p className="text-lg font-medium">Conviction scoring not available</p>
              </div>
            )}
          </div>
        )

      case 'charts':
        return (
          <div className="space-y-4">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-slate-800">Interactive Charts</h3>
              <p className="text-sm text-slate-500 mt-1">Price action with technical indicators. Use the timeframe buttons to adjust the view.</p>
            </div>
            <ChartErrorBoundary>
              <TechnicalChart ticker={ticker} />
            </ChartErrorBoundary>
          </div>
        )

      case 'technicals':
        return (
          <div className="space-y-6">
            {sections.technicals ? (
              <div>
                <h3 className="text-xl font-bold text-slate-800 mb-4">Chartism Analysis</h3>
                <MarkdownSection content={sections.technicals.content} />
              </div>
            ) : (
              <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                <p className="text-lg font-medium">No chartism analysis available</p>
                <p className="text-sm mt-2">Technical analysis will appear here after analysis completes</p>
              </div>
            )}
          </div>
        )

      case 'all':
        if (sections.full_report) {
          return <MarkdownSection content={sections.full_report.content || 'No content available'} />
        }
        if (!hasSections) {
          return (
            <div className="text-center py-16 text-slate-500">
              <p className="text-lg font-medium">No analysis results yet</p>
              <p className="text-sm mt-2">Results will appear here when analysis completes</p>
            </div>
          )
        }
        return renderGenericSections()

      default: {
        const visibleSections = getVisibleSections()
        if (Object.keys(visibleSections).length === 0) {
          if (!hasSections) {
            return (
              <div className="text-center py-16 text-slate-500">
                <p className="text-lg font-medium">No analysis results yet</p>
                <p className="text-sm mt-2">Results will appear here when analysis completes</p>
              </div>
            )
          }
          return (
            <div className="text-center py-16 text-slate-500">
              <p className="text-lg font-medium">Section not available</p>
              <p className="text-sm mt-2">This section may not have been generated during analysis. Try running a new analysis or check the Full Report tab.</p>
            </div>
          )
        }
        return renderGenericSections()
      }
    }
  }

  function renderGenericSections() {
    return (
      <div className="space-y-8">
        {Object.entries(getVisibleSections()).map(([sectionId, section]) => (
          <div key={sectionId} className="border-b border-slate-100 pb-8 last:border-0">
            <h3 className="text-xl font-bold text-slate-800 mb-4">
              {section?.title || 'Section'}
            </h3>
            <MarkdownSection content={section?.content || 'No content available'} />
          </div>
        ))}
      </div>
    )
  }
}

export default AnalysisView
