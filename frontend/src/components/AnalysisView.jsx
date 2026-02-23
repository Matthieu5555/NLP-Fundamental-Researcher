import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import TechnicalChart from './TechnicalChart'
import ChartErrorBoundary from './ChartErrorBoundary'
import DataAvailabilityBanner from './DataAvailabilityBanner'
import DCFTable from './DCFTable'
import CompTable from './CompTable'
import SensitivityGrid from './SensitivityGrid'
import ConvictionScore from './ConvictionScore'
import { getAccessToken } from '../utils/api'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

// Helper for authenticated fetch requests
const authFetch = (url, options = {}) => {
  const token = getAccessToken()
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  })
}

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
  const [showExcluded, setShowExcluded] = useState(false)
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false)
  const [error, setError] = useState(null)
  const [costUsd, setCostUsd] = useState(null)
  const [costBreakdown, setCostBreakdown] = useState(null)
  const [showCostBreakdown, setShowCostBreakdown] = useState(false)
  const [financialStatements, setFinancialStatements] = useState(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)
  const [companyInfo, setCompanyInfo] = useState(null)
  const [dcfModel, setDcfModel] = useState(null)
  const [sensitivityData, setSensitivityData] = useState(null)
  const [convictionData, setConvictionData] = useState(null)
  const [scenarioData, setScenarioData] = useState(null)
  const [footballFieldData, setFootballFieldData] = useState(null)
  const [watchlistAdded, setWatchlistAdded] = useState(false)
  const initRef = useRef({ sessionId: null, started: false })

  useEffect(() => {
    // Guard against double-run and resumed sessions
    if (!sessionId) return

    // If this is the same session we already processed, skip
    if (initRef.current.sessionId === sessionId && initRef.current.started) {
      console.log('Skipping duplicate analysis trigger for:', sessionId)
      return
    }

    // Mark this session as being processed
    initRef.current = { sessionId, started: true }

    if (isResumed) {
      // For resumed sessions, just load existing sections
      console.log('Resuming session, loading existing sections for:', ticker)
      setAnalysisRunning(false)
      loadSections()
      onAnalysisComplete() // Mark as complete immediately for chat
    } else {
      // For new sessions, run the full analysis
      console.log('Starting new analysis for:', ticker)
      runAnalysis()
    }
  }, [sessionId]) // Only depend on sessionId, isResumed is already set by the time this runs

  // Reload sections when report is updated from chat
  useEffect(() => {
    if (reportVersion > 0 && !analysisRunning) {
      console.log('Report updated, reloading sections...')
      loadSections()
    }
  }, [reportVersion])

  const runAnalysis = async () => {
    console.log('Starting analysis for session:', sessionId)
    setAnalysisRunning(true)
    setError(null)

    try {
      // First, trigger the analysis with a POST request
      const startResponse = await authFetch(`${API_URL}/api/analysis/${sessionId}/run`, {
        method: 'POST',
      })

      if (!startResponse.ok) {
        throw new Error('Failed to start analysis')
      }

      // Use fetch with ReadableStream for SSE (EventSource only supports GET)
      const reader = startResponse.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const processStream = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read()

            if (done) {
              console.log('Stream ended')
              // Stream ended without [DONE] - load sections anyway
              if (analysisRunning) {
                setAnalysisRunning(false)
                loadSections()
              }
              break
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')

            // Keep the last incomplete line in the buffer
            buffer = lines.pop() || ''

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.substring(6).trim()

                if (data === '[DONE]') {
                  console.log('Analysis stream complete, loading sections...')
                  setAnalysisRunning(false)
                  loadSections()
                  return
                }

                try {
                  const parsed = JSON.parse(data)
                  if (parsed.status === 'error') {
                    console.error('Analysis error:', parsed.message)
                    setError(parsed.message)
                    setAnalysisRunning(false)
                    return
                  }
                  setProgress(parsed.message || '')
                  // Capture step progress
                  if (parsed.step !== undefined) {
                    setProgressStep(parsed.step)
                  }
                  if (parsed.total !== undefined) {
                    setProgressTotal(parsed.total)
                  }
                  // Capture cost from completion message
                  if (parsed.cost_usd !== undefined) {
                    setCostUsd(parsed.cost_usd)
                  }
                  // Capture cost breakdown if available
                  if (parsed.cost_breakdown) {
                    setCostBreakdown(parsed.cost_breakdown)
                  }
                } catch (e) {
                  // Not JSON, ignore
                }
              }
            }
          }
        } catch (err) {
          console.error('Stream processing error:', err)
          setError('Analysis stream interrupted. Try refreshing the page.')
          setAnalysisRunning(false)
        }
      }

      processStream()

    } catch (err) {
      console.error('Analysis error:', err)
      setError('Failed to run analysis')
      setAnalysisRunning(false)
    }
  }

  const loadSections = async () => {
    setSectionsLoading(true)
    try {
      console.log('Fetching sections for session:', sessionId)
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sections`)
      const data = await response.json()
      console.log('Sections loaded:', Object.keys(data.sections || {}))
      console.log('Section data:', data.sections)
      setSections(data.sections || {})
      setContradictions(data.contradictions || [])
      setResearchGaps(data.research_gaps || [])
      setExcludedSourceIds(data.excluded_source_ids || [])
      setSectionsLoading(false)
      onAnalysisComplete()

      // Also load company info, financial statements, and valuation data
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
      const data = await response.json()
      setCompanyInfo(data)
      console.log('Company info loaded:', data)
    } catch (err) {
      console.error('Load company info error:', err)
    }
  }

  const loadFinancialStatements = async () => {
    setFinancialsLoading(true)
    try {
      const response = await authFetch(`${API_URL}/api/analysis/${sessionId}/financial-statements`)
      const data = await response.json()
      setFinancialStatements(data)
      console.log('Financial statements loaded:', data.is_available)
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
      console.log('Valuation data loaded:', { dcf: !!data.dcf_model, sensitivity: !!data.sensitivity_data, conviction: !!data.conviction_data, scenarios: !!data.scenario_data, footballField: !!data.football_field_data })
    } catch (err) {
      console.error('Load valuation data error:', err)
    }
  }

  // Tabs: Special amber tabs first (Analyst Notes, Further Research, Sources, Full Report), then content tabs
  // Order: Strategy > Moat > Financials > Fundamental > Bull > Bear > Technicals
  const tabs = [
    { id: 'analyst_notes', label: `Analyst Notes${beliefs.length > 0 ? ` (${beliefs.length})` : ''}`, special: 'amber' },
    { id: 'further_research', label: 'Further Research', special: 'amber' },
    { id: 'sources', label: 'Sources', special: 'amber' },
    { id: 'all', label: 'Full Report' },
    { id: 'conviction', label: 'Conviction' },
    { id: 'dcf_valuation', label: 'DCF Valuation' },
    { id: 'comp_table', label: 'Comparables' },
    { id: 'earnings_model', label: 'Earnings Model' },
    { id: 'sensitivity', label: 'Sensitivity' },
    { id: 'scenario_analysis', label: 'Scenarios' },
    { id: 'football_field', label: 'Football Field' },
    { id: 'strategic_assessment', label: 'Strategic Assessment' },
    { id: 'precedent_transactions', label: 'Precedent M&A' },
    { id: 'strategy', label: 'Strategy' },
    { id: 'moat', label: 'Moat' },
    { id: 'financials_tab', label: 'Financials', special: financialStatements?.is_available ? null : 'disabled' },
    { id: 'fundamentals', label: 'Fundamentals' },
    { id: 'bull_case', label: 'Bull Case' },
    { id: 'bear_case', label: 'Bear Case' },
    { id: 'charts', label: 'Charts' },
    { id: 'technicals', label: 'Chartism' },
  ]

  // Get all sources from metadata or sources section
  const getAllSources = () => {
    const sourcesSection = sections.sources
    if (sourcesSection?.sources && Array.isArray(sourcesSection.sources)) {
      return sourcesSection.sources
    }
    return []
  }

  // Check if a source type can be excluded
  const isExcludable = (sourceType) => {
    return sourceType === 'news' || sourceType === 'search'
  }

  // Exclude a source
  const handleExcludeSource = async (sourceId) => {
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sources/${sourceId}/exclude`, {
        method: 'POST'
      })
      const data = await response.json()
      if (data.success) {
        setExcludedSourceIds(data.excluded_source_ids)
      } else {
        console.error('Failed to exclude source:', data.error)
      }
    } catch (err) {
      console.error('Exclude source error:', err)
    }
  }

  // Restore a source
  const handleRestoreSource = async (sourceId) => {
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sources/${sourceId}/restore`, {
        method: 'POST'
      })
      const data = await response.json()
      if (data.success) {
        setExcludedSourceIds(data.excluded_source_ids)
      } else {
        console.error('Failed to restore source:', data.error)
      }
    } catch (err) {
      console.error('Restore source error:', err)
    }
  }

  // Filter sources by excluded status
  const getVisibleSources = () => {
    return getAllSources().filter(source => !excludedSourceIds.includes(source.id))
  }

  const getExcludedSources = () => {
    return getAllSources().filter(source => excludedSourceIds.includes(source.id))
  }

  // Group beliefs by section for display
  const beliefsBySection = beliefs.reduce((acc, belief) => {
    const section = belief.section || 'general'
    if (!acc[section]) acc[section] = []
    acc[section].push(belief)
    return acc
  }, {})

  const getVisibleSections = () => {
    if (activeTab === 'all') {
      return sections
    }
    const section = sections[activeTab]
    return section ? { [activeTab]: section } : {}
  }

  const addToWatchlist = async () => {
    try {
      const response = await authFetch(`${API_URL}/api/watchlist/${ticker}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
      if (response.ok) {
        setWatchlistAdded(true)
      }
    } catch (err) {
      console.error('Failed to add to watchlist:', err)
    }
  }

  const downloadReport = async () => {
    setIsDownloadingPdf(true)
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/export/pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
      })

      // Check if response is JSON (error) or blob (success)
      const contentType = response.headers.get('content-type')

      if (!response.ok || contentType?.includes('application/json')) {
        const errorData = await response.json()
        throw new Error(errorData.details || errorData.error || 'PDF export failed')
      }

      const blob = await response.blob()

      if (blob.size < 1000) {
        throw new Error('Generated PDF is too small - report may be empty')
      }

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

  console.log('AnalysisView render - analysisRunning:', analysisRunning, 'sectionsLoading:', sectionsLoading, 'sections count:', Object.keys(sections).length, 'error:', error)

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
      {/* Header - Always visible */}
      <div className="bg-gradient-to-r from-slate-50 to-slate-100 border-b border-slate-200 px-6 py-5">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Analysis Results</h2>
            <div className="flex items-center gap-4 mt-1">
              <p className="text-sm text-slate-600">Multi-agent analysis for {ticker}</p>
              {(costUsd !== null || chatCost > 0) && (
                <div className="relative">
                  <button
                    onClick={() => setShowCostBreakdown(!showCostBreakdown)}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 hover:bg-green-200 transition-colors cursor-pointer"
                  >
                    Cost: ${((costUsd || 0) + chatCost).toFixed(4)}
                    {costBreakdown && (
                      <svg className={`w-3 h-3 ml-1 transition-transform ${showCostBreakdown ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    )}
                  </button>
                  {/* Cost Breakdown Dropdown */}
                  {showCostBreakdown && costBreakdown && (
                    <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-slate-200 z-50 p-3">
                      <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Cost Breakdown</h4>
                      <div className="space-y-1.5">
                        {Object.entries(costBreakdown).map(([name, cost]) => (
                          <div key={name} className="flex justify-between items-center text-xs">
                            <span className="text-slate-600">{name}</span>
                            <span className="font-medium text-slate-800">${cost.toFixed(4)}</span>
                          </div>
                        ))}
                        {chatCost > 0 && (
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-slate-600">Chat Conversations</span>
                            <span className="font-medium text-slate-800">${chatCost.toFixed(4)}</span>
                          </div>
                        )}
                        <div className="border-t border-slate-200 mt-2 pt-2 flex justify-between items-center text-xs font-semibold">
                          <span className="text-slate-700">Total</span>
                          <span className="text-green-700">${((costUsd || 0) + chatCost).toFixed(4)}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          {!analysisRunning && !sectionsLoading && Object.keys(sections).length > 0 && (
            <div className="flex gap-3">
              {onUpdateReport && (
                <button
                  onClick={onUpdateReport}
                  disabled={!reportDirty || isUpdatingReport}
                  className="px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-md flex items-center gap-2"
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
                onClick={downloadReport}
                disabled={isUpdatingReport || reportDirty || isDownloadingPdf}
                title={reportDirty ? 'Update report first to include latest insights' : ''}
                className="px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
                onClick={addToWatchlist}
                disabled={watchlistAdded}
                className={`px-4 py-3 text-sm font-semibold rounded-lg shadow-md transition-all flex items-center gap-2 ${
                  watchlistAdded
                    ? 'bg-slate-100 text-slate-500 cursor-not-allowed'
                    : 'text-white bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 hover:shadow-lg'
                }`}
              >
                <svg className="w-4 h-4" fill={watchlistAdded ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                </svg>
                {watchlistAdded ? 'WATCHLISTED' : 'WATCHLIST'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Data Availability Banner for Non-US Companies */}
      {companyInfo && !companyInfo.is_us && !analysisRunning && (
        <div className="px-6 pt-4">
          <DataAvailabilityBanner companyInfo={companyInfo} />
        </div>
      )}

      {/* Analysis Running State */}
      {analysisRunning && (
        <div className="px-6 py-12 bg-white">
          <div className="max-w-md mx-auto">
            {/* Progress bar */}
            <div className="mb-4">
              <div className="flex justify-between text-sm text-slate-600 mb-2">
                <span>Step {progressStep} of {progressTotal}</span>
                <span>{Math.round((progressStep / progressTotal) * 100)}%</span>
              </div>
              <div className="w-full h-3 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{
                    width: `${(progressStep / progressTotal) * 100}%`,
                    background: 'linear-gradient(to right, #C87A23, #E8A040)'
                  }}
                />
              </div>
            </div>

            {/* Status message */}
            <div className="text-center">
              <div className="inline-flex items-center justify-center space-x-3 mb-3">
                <div className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: '#C87A23', borderTopColor: 'transparent' }}></div>
                <p className="text-lg text-slate-700 font-medium">{progress || 'Initializing analysis...'}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sections Loading State */}
      {!analysisRunning && sectionsLoading && (
        <div className="px-6 py-12 text-center bg-white">
          <div className="inline-flex items-center justify-center space-x-3 mb-4">
            <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin" style={{ borderColor: '#C87A23', borderTopColor: 'transparent' }}></div>
          </div>
          <p className="text-slate-600">Loading analysis results...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="px-6 py-8 bg-white">
          <div className="bg-red-50 border-2 border-red-200 rounded-lg p-6 text-center">
            <p className="text-sm text-red-700 font-medium mb-4">{error}</p>
            <button
              onClick={runAnalysis}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* Tabs and Content - Always show when analysis is done */}
      {!analysisRunning && !sectionsLoading && !error && (
        <>
          {/* Tabs */}
          <div className="border-b border-slate-200 bg-slate-50">
            <nav className="flex overflow-x-auto px-4">
              {tabs.map((tab, idx) => {
                const isActive = activeTab === tab.id
                const hasContent = tab.id === 'all' || tab.id === 'analyst_notes' || tab.id === 'further_research' || tab.id === 'sources' || tab.id === 'charts' || tab.id === 'financials_tab' || tab.id === 'dcf_valuation' || tab.id === 'comp_table' || tab.id === 'earnings_model' || tab.id === 'sensitivity' || tab.id === 'conviction' || tab.id === 'scenario_analysis' || tab.id === 'football_field' || tab.id === 'strategic_assessment' || tab.id === 'precedent_transactions' || sections[tab.id]
                const isAmberTab = tab.special === 'amber'
                const isDisabledTab = tab.special === 'disabled'

                return (
                  <button
                    key={tab.id}
                    onClick={() => hasContent && setActiveTab(tab.id)}
                    disabled={!hasContent}
                    title={isDisabledTab ? 'Not available for non-US companies' : ''}
                    className={`
                      flex items-center space-x-2 px-5 py-4 border-b-2 font-medium text-sm whitespace-nowrap transition-all
                      ${isActive
                        ? isAmberTab
                          ? 'bg-amber-50 border-amber-500 text-amber-700'
                          : 'bg-white border-[#C87A23] text-[#C87A23]'
                        : hasContent
                          ? isAmberTab
                            ? 'border-transparent text-amber-600 hover:text-amber-700 hover:border-amber-300 hover:bg-amber-50/50 cursor-pointer'
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
                      <span className="ml-1 w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
                    )}
                    {isDisabledTab && (
                      <span className="ml-1 text-xs text-slate-400">(US only)</span>
                    )}
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Content Area */}
          <div className="px-6 py-6 min-h-[400px] max-h-[600px] overflow-y-auto bg-white">
            {/* Analyst Notes Tab - Redesigned with badges */}
            {activeTab === 'analyst_notes' ? (
              <div className="space-y-6">
                {/* Header */}
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-xl font-bold text-slate-800">Analyst Notes</h3>
                    <p className="text-sm text-slate-500 mt-1">
                      Your insights and conclusions from the analysis conversation
                    </p>
                  </div>
                </div>

                {beliefs.length === 0 ? (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-xl border border-slate-200">
                    <svg className="w-12 h-12 mx-auto mb-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p className="text-lg font-medium text-slate-700">No analyst notes yet</p>
                    <p className="text-sm mt-2 text-slate-500 max-w-md mx-auto">
                      Express your views in chat to capture insights here.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(beliefsBySection).map(([sectionName, sectionBeliefs]) => (
                      <div key={sectionName} className="rounded-xl border border-slate-200 overflow-hidden card-section-bg">
                        <div className="bg-slate-100 px-4 py-3 border-b border-slate-200">
                          <h4 className="font-semibold text-slate-700 capitalize text-sm tracking-wide">
                            {sectionName.replace(/_/g, ' ')}
                          </h4>
                        </div>
                        <div className="divide-y divide-slate-100">
                          {sectionBeliefs.map((belief, idx) => (
                            <div key={idx} className="px-4 py-4 hover:bg-slate-50 transition-colors">
                              <div className="flex items-start gap-3">
                                {/* Badge */}
                                <span
                                  className="flex-shrink-0 px-2 py-1 rounded text-xs font-bold uppercase tracking-wide belief-badge"
                                >
                                  {belief.badge || belief.type?.replace(/_/g, ' ') || 'NOTE'}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm text-slate-700 leading-relaxed">{belief.content}</p>
                                  {/* Confidence bar */}
                                  <div className="flex items-center gap-2 mt-2">
                                    <span className="text-xs text-slate-500">Confidence:</span>
                                    <div className="flex-1 max-w-[100px] h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                      <div
                                        className="h-full rounded-full transition-all"
                                        style={{
                                          width: `${(belief.confidence || 0.7) * 100}%`,
                                          backgroundColor: belief.badge_color || '#D97706'
                                        }}
                                      />
                                    </div>
                                    <span className="text-xs text-slate-500">{Math.round((belief.confidence || 0.7) * 100)}%</span>
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
                  <div className="border border-slate-200 rounded-lg p-4 mt-4 card-section-bg">
                    <div className="flex items-start gap-3">
                      <svg className="w-5 h-5 text-slate-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <p className="text-sm text-slate-700">
                        <strong>Tip:</strong> Click "UPDATE REPORT" in the header to regenerate the report with your analyst notes elegantly woven into the narrative.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ) : activeTab === 'sources' ? (
              /* Sources Tab - Special rendering with exclude/restore */
              <div className="space-y-4">
                <div className="mb-6">
                  <h3 className="text-xl font-bold text-slate-800">Sources</h3>
                  <p className="text-sm text-slate-500 mt-1">
                    Data sources used in this analysis. Click any link to view the original source.
                    {isExcludable('news') && <span className="text-slate-400"> News sources can be excluded.</span>}
                  </p>
                </div>
                {getAllSources().length === 0 ? (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">No sources available</p>
                    <p className="text-sm mt-2">Sources will appear here after analysis completes</p>
                  </div>
                ) : (
                  <>
                    {/* Active Sources */}
                    <div className="space-y-3">
                      {getVisibleSources().map((source) => (
                        <div key={source.id} className="bg-slate-50 rounded-lg p-4 border border-slate-200 hover:border-slate-300 transition-colors group">
                          <div className="flex items-start gap-3">
                            <span className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white" style={{ backgroundColor: '#C87A23' }}>
                              {source.id}
                            </span>
                            <div className="flex-1 min-w-0">
                              <h4 className="font-semibold text-slate-800 text-sm">{source.title}</h4>
                              {source.url && (
                                <a
                                  href={source.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-[#C87A23] hover:underline text-xs break-all block mt-1"
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
                            {/* Exclude button - only for news/search sources */}
                            {isExcludable(source.source_type) && (
                              <button
                                onClick={() => handleExcludeSource(source.id)}
                                className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-full hover:bg-red-100 text-slate-400 hover:text-red-600"
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

                    {/* Excluded Sources Section */}
                    {getExcludedSources().length > 0 && (
                      <div className="mt-6">
                        <button
                          onClick={() => setShowExcluded(!showExcluded)}
                          className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 transition-colors"
                        >
                          <svg className={`w-4 h-4 transition-transform ${showExcluded ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                          Show excluded ({getExcludedSources().length})
                        </button>

                        {showExcluded && (
                          <div className="mt-3 space-y-3">
                            {getExcludedSources().map((source) => (
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
                                  {/* Restore button */}
                                  <button
                                    onClick={() => handleRestoreSource(source.id)}
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
            ) : activeTab === 'further_research' ? (
              /* Further Research Tab - Card-based contradiction display */
              <div className="space-y-6">
                {/* Header */}
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Further Research</h3>
                  <p className="text-sm text-slate-500 mt-1">
                    Key disagreements between bulls and bears that require your judgment
                  </p>
                </div>

                {/* Contradictions Cards */}
                {contradictions.length === 0 && researchGaps.length === 0 ? (
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
                              {/* Card Header */}
                              <div className="px-5 py-4 border-b border-slate-200 card-section-bg">
                                <div className="flex-1">
                                  <h5 className="font-bold text-slate-800">{c.disputed_fact}</h5>
                                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-2 ${c.priority === 'HIGH' ? 'bg-red-100 text-red-700' : 'bg-slate-200 text-slate-700'}`}>
                                    {c.priority} PRIORITY
                                  </span>
                                </div>
                              </div>

                              {/* Bull vs Bear Grid */}
                              <div className="grid grid-cols-2 divide-x divide-slate-200">
                                {/* Bulls Column */}
                                <div className="p-4 bg-green-50/50">
                                  <div className="flex items-center gap-2 mb-2">
                                    <span className="w-3 h-3 rounded-full bg-green-500"></span>
                                    <span className="text-xs font-bold text-green-700 uppercase tracking-wide">Bulls Argue</span>
                                  </div>
                                  <p className="text-sm text-slate-700 leading-relaxed">{c.bull_interpretation}</p>
                                </div>

                                {/* Bears Column */}
                                <div className="p-4 bg-red-50/50">
                                  <div className="flex items-center gap-2 mb-2">
                                    <span className="w-3 h-3 rounded-full bg-red-500"></span>
                                    <span className="text-xs font-bold text-red-700 uppercase tracking-wide">Bears Argue</span>
                                  </div>
                                  <p className="text-sm text-slate-700 leading-relaxed">{c.bear_interpretation}</p>
                                </div>
                              </div>

                              {/* Your Call Footer */}
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
                                <span className={`flex-shrink-0 px-2 py-1 rounded text-xs font-bold uppercase ${g.priority === 'HIGH' ? 'bg-red-100 text-red-700' : 'bg-slate-200 text-slate-700'}`}>
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

                {/* CTA */}
                {(contradictions.length > 0 || researchGaps.length > 0) && (
                  <div className="border border-slate-200 rounded-lg p-4 card-section-bg">
                    <p className="text-sm text-slate-700">
                      <strong>Tip:</strong> Use the chat below to investigate these items. Ask questions like "What's the evidence for the bull case on valuation?" to gather more information.
                    </p>
                  </div>
                )}
              </div>
            ) : activeTab === 'financials_tab' ? (
              /* Financial Statements Tab */
              <div className="space-y-6">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-xl font-bold text-slate-800">Financial Statements</h3>
                    <p className="text-sm text-slate-500 mt-1">
                      5-year financial data with key ratios and highlights
                    </p>
                  </div>
                  {companyInfo && (
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${companyInfo.is_us ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                      {companyInfo.is_us ? 'US Company' : 'Non-US Company'}
                    </span>
                  )}
                </div>

                {financialsLoading ? (
                  <div className="text-center py-12">
                    <div className="inline-flex items-center justify-center space-x-3 mb-4">
                      <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: '#C87A23', borderTopColor: 'transparent' }}></div>
                    </div>
                    <p className="text-slate-600">Loading financial statements...</p>
                  </div>
                ) : !financialStatements?.is_available ? (
                  <div className="text-center py-12 bg-slate-50 rounded-xl border border-slate-200">
                    <svg className="w-16 h-16 mx-auto mb-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p className="text-lg font-medium text-slate-700">Not Available for Non-US Companies</p>
                    <p className="text-sm mt-2 text-slate-500 max-w-md mx-auto">
                      Detailed financial statements are only available for US companies through FinancialDatasets.ai.
                      {financialStatements?.error && (
                        <span className="block mt-2 text-slate-400">{financialStatements.error}</span>
                      )}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-8">
                    {/* Highlights Section */}
                    {financialStatements.highlights?.length > 0 && (
                      <div className="space-y-3">
                        <h4 className="text-lg font-semibold text-slate-700 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                          Key Findings
                        </h4>
                        <div className="grid gap-3 md:grid-cols-2">
                          {financialStatements.highlights.map((highlight, idx) => (
                            <div
                              key={idx}
                              className={`rounded-lg p-4 border ${
                                highlight.type === 'positive' ? 'bg-green-50 border-green-200' :
                                highlight.type === 'negative' ? 'bg-red-50 border-red-200' :
                                highlight.type === 'attention' ? 'bg-amber-50 border-amber-200' :
                                'bg-slate-50 border-slate-200'
                              }`}
                            >
                              <div className="flex items-start gap-3">
                                <span className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-lg ${
                                  highlight.type === 'positive' ? 'bg-green-100 text-green-600' :
                                  highlight.type === 'negative' ? 'bg-red-100 text-red-600' :
                                  highlight.type === 'attention' ? 'bg-amber-100 text-amber-600' :
                                  'bg-slate-100 text-slate-600'
                                }`}>
                                  {highlight.type === 'positive' ? '✓' : highlight.type === 'negative' ? '!' : '?'}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <h5 className="font-semibold text-slate-800 text-sm">{highlight.title}</h5>
                                  <p className="text-sm text-slate-600 mt-1">{highlight.description}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Income Statement */}
                    {financialStatements.income_statements?.length > 0 && (
                      <div>
                        <h4 className="text-lg font-semibold text-slate-700 mb-3 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                          Income Statement
                        </h4>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-slate-100">
                                <th className="px-3 py-2 text-left font-semibold text-slate-700">Metric</th>
                                {financialStatements.income_statements.slice(0, 5).map((stmt, idx) => (
                                  <th key={idx} className="px-3 py-2 text-right font-semibold text-slate-700">
                                    {stmt.period?.substring(0, 7) || `FY${stmt.fiscal_year}`}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              <tr>
                                <td className="px-3 py-2 text-slate-700">Revenue</td>
                                {financialStatements.income_statements.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    <div>{stmt.revenue ? `$${(stmt.revenue / 1e9).toFixed(1)}B` : 'N/A'}</div>
                                    {stmt.revenue_yoy !== null && stmt.revenue_yoy !== undefined && (
                                      <div className={`text-xs font-medium ${stmt.revenue_yoy >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {stmt.revenue_yoy >= 0 ? '+' : ''}{stmt.revenue_yoy.toFixed(1)}% YoY
                                      </div>
                                    )}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-slate-50/50">
                                <td className="px-3 py-2 text-slate-700">Gross Profit</td>
                                {financialStatements.income_statements.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.gross_profit ? `$${(stmt.gross_profit / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr>
                                <td className="px-3 py-2 text-slate-700">Operating Income</td>
                                {financialStatements.income_statements.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.operating_income ? `$${(stmt.operating_income / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-slate-50/50">
                                <td className="px-3 py-2 text-slate-700">Net Income</td>
                                {financialStatements.income_statements.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    <div>{stmt.net_income ? `$${(stmt.net_income / 1e9).toFixed(1)}B` : 'N/A'}</div>
                                    {stmt.net_income_yoy !== null && stmt.net_income_yoy !== undefined && (
                                      <div className={`text-xs font-medium ${stmt.net_income_yoy >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {stmt.net_income_yoy >= 0 ? '+' : ''}{stmt.net_income_yoy.toFixed(1)}% YoY
                                      </div>
                                    )}
                                  </td>
                                ))}
                              </tr>
                              <tr>
                                <td className="px-3 py-2 text-slate-700">EPS</td>
                                {financialStatements.income_statements.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    <div>{stmt.eps ? `$${stmt.eps.toFixed(2)}` : 'N/A'}</div>
                                    {stmt.eps_yoy !== null && stmt.eps_yoy !== undefined && (
                                      <div className={`text-xs font-medium ${stmt.eps_yoy >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {stmt.eps_yoy >= 0 ? '+' : ''}{stmt.eps_yoy.toFixed(1)}% YoY
                                      </div>
                                    )}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-blue-50/50 font-medium">
                                <td className="px-3 py-2 text-slate-700">Gross Margin</td>
                                {financialStatements.income_statements.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-blue-700">
                                    {stmt.gross_margin ? `${(stmt.gross_margin * 100).toFixed(1)}%` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-blue-50/50 font-medium">
                                <td className="px-3 py-2 text-slate-700">Net Margin</td>
                                {financialStatements.income_statements.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-blue-700">
                                    {stmt.net_margin ? `${(stmt.net_margin * 100).toFixed(1)}%` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Balance Sheet */}
                    {financialStatements.balance_sheets?.length > 0 && (
                      <div>
                        <h4 className="text-lg font-semibold text-slate-700 mb-3 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-green-500"></span>
                          Balance Sheet
                        </h4>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-slate-100">
                                <th className="px-3 py-2 text-left font-semibold text-slate-700">Metric</th>
                                {financialStatements.balance_sheets.slice(0, 5).map((stmt, idx) => (
                                  <th key={idx} className="px-3 py-2 text-right font-semibold text-slate-700">
                                    {stmt.period?.substring(0, 7) || `FY${stmt.fiscal_year}`}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              <tr>
                                <td className="px-3 py-2 text-slate-700">Total Assets</td>
                                {financialStatements.balance_sheets.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.total_assets ? `$${(stmt.total_assets / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-slate-50/50">
                                <td className="px-3 py-2 text-slate-700">Total Equity</td>
                                {financialStatements.balance_sheets.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.total_equity ? `$${(stmt.total_equity / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr>
                                <td className="px-3 py-2 text-slate-700">Cash</td>
                                {financialStatements.balance_sheets.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.cash ? `$${(stmt.cash / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-slate-50/50">
                                <td className="px-3 py-2 text-slate-700">Total Debt</td>
                                {financialStatements.balance_sheets.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.total_debt ? `$${(stmt.total_debt / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-green-50/50 font-medium">
                                <td className="px-3 py-2 text-slate-700">Debt/Equity</td>
                                {financialStatements.balance_sheets.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-green-700">
                                    {stmt.debt_to_equity ? `${stmt.debt_to_equity.toFixed(2)}x` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Cash Flow */}
                    {financialStatements.cash_flows?.length > 0 && (
                      <div>
                        <h4 className="text-lg font-semibold text-slate-700 mb-3 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                          Cash Flow Statement
                        </h4>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-slate-100">
                                <th className="px-3 py-2 text-left font-semibold text-slate-700">Metric</th>
                                {financialStatements.cash_flows.slice(0, 5).map((stmt, idx) => (
                                  <th key={idx} className="px-3 py-2 text-right font-semibold text-slate-700">
                                    {stmt.period?.substring(0, 7) || `FY${stmt.fiscal_year}`}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              <tr>
                                <td className="px-3 py-2 text-slate-700">Operating CF</td>
                                {financialStatements.cash_flows.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.operating_cf ? `$${(stmt.operating_cf / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-slate-50/50">
                                <td className="px-3 py-2 text-slate-700">Free Cash Flow</td>
                                {financialStatements.cash_flows.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.free_cash_flow ? `$${(stmt.free_cash_flow / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr>
                                <td className="px-3 py-2 text-slate-700">CapEx</td>
                                {financialStatements.cash_flows.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {stmt.capex ? `$${(stmt.capex / 1e9).toFixed(1)}B` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-purple-50/50 font-medium">
                                <td className="px-3 py-2 text-slate-700">FCF Margin</td>
                                {financialStatements.cash_flows.slice(0, 5).map((stmt, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-purple-700">
                                    {stmt.fcf_margin ? `${(stmt.fcf_margin * 100).toFixed(1)}%` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Key Ratios */}
                    {financialStatements.ratios?.length > 0 && (
                      <div>
                        <h4 className="text-lg font-semibold text-slate-700 mb-3 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                          Key Ratios
                        </h4>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-slate-100">
                                <th className="px-3 py-2 text-left font-semibold text-slate-700">Metric</th>
                                {financialStatements.ratios.slice(0, 5).map((ratio, idx) => (
                                  <th key={idx} className="px-3 py-2 text-right font-semibold text-slate-700">
                                    {ratio.period?.substring(0, 7) || `FY${ratio.fiscal_year}`}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              <tr>
                                <td className="px-3 py-2 text-slate-700">ROE</td>
                                {financialStatements.ratios.slice(0, 5).map((ratio, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {ratio.profitability?.roe ? `${(ratio.profitability.roe * 100).toFixed(1)}%` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr className="bg-slate-50/50">
                                <td className="px-3 py-2 text-slate-700">ROA</td>
                                {financialStatements.ratios.slice(0, 5).map((ratio, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {ratio.profitability?.roa ? `${(ratio.profitability.roa * 100).toFixed(1)}%` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                              <tr>
                                <td className="px-3 py-2 text-slate-700">Asset Turnover</td>
                                {financialStatements.ratios.slice(0, 5).map((ratio, idx) => (
                                  <td key={idx} className="px-3 py-2 text-right text-slate-600">
                                    {ratio.efficiency?.asset_turnover ? `${ratio.efficiency.asset_turnover.toFixed(2)}x` : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : activeTab === 'dcf_valuation' ? (
              /* DCF Valuation Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">DCF Valuation</h3>
                  <p className="text-sm text-slate-500 mt-1">Discounted cash flow model with LLM-reasoned assumptions</p>
                </div>
                {dcfModel ? (
                  <DCFTable dcfModel={dcfModel} />
                ) : sections.dcf_valuation ? (
                  <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                    <ReactMarkdown
                      components={{
                        table: ({ children }) => <div className="overflow-x-auto"><table className="w-full text-sm border-collapse">{children}</table></div>,
                        thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
                        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">{children}</th>,
                        td: ({ children }) => <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{children}</td>,
                        strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                        p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                      }}
                    >
                      {sections.dcf_valuation.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">DCF model not available</p>
                    <p className="text-sm mt-2">This may occur if required financial data is missing.</p>
                  </div>
                )}
              </div>
            ) : activeTab === 'comp_table' ? (
              /* Comparable Companies Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Comparable Companies</h3>
                  <p className="text-sm text-slate-500 mt-1">Peer valuation comparison</p>
                </div>
                {sections.comp_table ? (
                  <CompTable content={sections.comp_table.content} />
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">Comparable analysis not available</p>
                  </div>
                )}
              </div>
            ) : activeTab === 'earnings_model' ? (
              /* Earnings Model Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Earnings Model</h3>
                  <p className="text-sm text-slate-500 mt-1">Historical actuals and analyst estimates</p>
                </div>
                {sections.earnings_model ? (
                  <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                    <ReactMarkdown
                      components={{
                        table: ({ children }) => <div className="overflow-x-auto"><table className="w-full text-sm border-collapse">{children}</table></div>,
                        thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
                        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">{children}</th>,
                        td: ({ children }) => <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{children}</td>,
                        strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                        p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                      }}
                    >
                      {sections.earnings_model.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">Earnings model not available</p>
                  </div>
                )}
              </div>
            ) : activeTab === 'sensitivity' ? (
              /* Sensitivity Analysis Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Sensitivity Analysis</h3>
                  <p className="text-sm text-slate-500 mt-1">Fair value across different WACC and terminal growth assumptions</p>
                </div>
                {sensitivityData ? (
                  <SensitivityGrid sensitivityData={sensitivityData} />
                ) : sections.sensitivity ? (
                  <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                    <ReactMarkdown
                      components={{
                        table: ({ children }) => <div className="overflow-x-auto"><table className="w-full text-sm border-collapse">{children}</table></div>,
                        thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
                        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">{children}</th>,
                        td: ({ children }) => <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{children}</td>,
                        strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                        p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                      }}
                    >
                      {sections.sensitivity.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">Sensitivity analysis not available</p>
                    <p className="text-sm mt-2">Requires a successful DCF model.</p>
                  </div>
                )}
              </div>
            ) : activeTab === 'scenario_analysis' ? (
              /* Scenario Analysis Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Scenario Analysis</h3>
                  <p className="text-sm text-slate-500 mt-1">Bull / Base / Bear probability-weighted fair value</p>
                </div>
                {sections.scenario_analysis ? (
                  <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                    <ReactMarkdown
                      components={{
                        table: ({ children }) => <div className="overflow-x-auto"><table className="w-full text-sm border-collapse">{children}</table></div>,
                        thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
                        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">{children}</th>,
                        td: ({ children }) => <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{children}</td>,
                        strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                        p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                      }}
                    >
                      {sections.scenario_analysis.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">Scenario analysis not available</p>
                    <p className="text-sm mt-2">Requires a successful DCF model.</p>
                  </div>
                )}
              </div>
            ) : activeTab === 'football_field' ? (
              /* Football Field Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Valuation Football Field</h3>
                  <p className="text-sm text-slate-500 mt-1">Cross-method valuation range comparison</p>
                </div>
                {sections.football_field ? (
                  <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                    <ReactMarkdown
                      components={{
                        table: ({ children }) => <div className="overflow-x-auto"><table className="w-full text-sm border-collapse">{children}</table></div>,
                        thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
                        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">{children}</th>,
                        td: ({ children }) => <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{children}</td>,
                        strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                        p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                      }}
                    >
                      {sections.football_field.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">Football field not available</p>
                    <p className="text-sm mt-2">Requires valuation data from multiple methods.</p>
                  </div>
                )}
              </div>
            ) : activeTab === 'strategic_assessment' ? (
              /* Strategic Assessment Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Strategic Assessment</h3>
                  <p className="text-sm text-slate-500 mt-1">PESTEL analysis, Porter's Five Forces, and TAM/SAM/SOM</p>
                </div>
                {sections.strategic_assessment ? (
                  <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                    <ReactMarkdown
                      components={{
                        strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                        h2: ({ children }) => <h2 className="text-lg font-bold text-slate-800 mt-6 mb-3">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-base font-bold text-slate-800 mt-4 mb-2">{children}</h3>,
                        p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
                        li: ({ children }) => <li className="text-slate-700">{children}</li>,
                      }}
                    >
                      {sections.strategic_assessment.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">Strategic assessment not available</p>
                  </div>
                )}
              </div>
            ) : activeTab === 'precedent_transactions' ? (
              /* Precedent M&A Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Precedent M&A Transactions</h3>
                  <p className="text-sm text-slate-500 mt-1">Recent comparable M&A deal multiples</p>
                </div>
                {sections.precedent_transactions ? (
                  <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                    <ReactMarkdown
                      components={{
                        table: ({ children }) => <div className="overflow-x-auto"><table className="w-full text-sm border-collapse">{children}</table></div>,
                        thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
                        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">{children}</th>,
                        td: ({ children }) => <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{children}</td>,
                        strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                        p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                        em: ({ children }) => <em className="text-slate-500 italic">{children}</em>,
                      }}
                    >
                      {sections.precedent_transactions.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">Precedent transactions not available</p>
                    <p className="text-sm mt-2">Requires web search data for recent M&A activity.</p>
                  </div>
                )}
              </div>
            ) : activeTab === 'conviction' ? (
              /* Conviction Score Tab */
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-slate-800">Conviction Score</h3>
                  <p className="text-sm text-slate-500 mt-1">Decomposed investment conviction across key dimensions</p>
                </div>
                {convictionData ? (
                  <ConvictionScore convictionData={convictionData} />
                ) : sections.conviction ? (
                  <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                    <ReactMarkdown
                      components={{
                        table: ({ children }) => <div className="overflow-x-auto"><table className="w-full text-sm border-collapse">{children}</table></div>,
                        thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
                        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">{children}</th>,
                        td: ({ children }) => <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{children}</td>,
                        strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                        p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                      }}
                    >
                      {sections.conviction.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">Conviction scoring not available</p>
                  </div>
                )}
              </div>
            ) : Object.keys(sections).length === 0 ? (
              <div className="text-center py-16 text-slate-500">
                <p className="text-lg font-medium">No analysis results yet</p>
                <p className="text-sm mt-2">Results will appear here when analysis completes</p>
              </div>
            ) : activeTab === 'charts' ? (
              /* Charts Tab - Interactive Technical Charts */
              <div className="space-y-4">
                <div className="mb-4">
                  <h3 className="text-xl font-bold text-slate-800">Interactive Charts</h3>
                  <p className="text-sm text-slate-500 mt-1">
                    Price action with technical indicators. Use the timeframe buttons to adjust the view.
                  </p>
                </div>
                <ChartErrorBoundary>
                  <TechnicalChart ticker={ticker} />
                </ChartErrorBoundary>
              </div>
            ) : Object.entries(getVisibleSections()).length === 0 ? (
              <div className="text-center py-16 text-slate-500">
                <p className="text-lg font-medium">Section not available</p>
                <p className="text-sm mt-2">This section may not have been generated during analysis. Try running a new analysis or check the Full Report tab.</p>
              </div>
            ) : activeTab === 'all' && sections.full_report ? (
              /* Full Report Tab - Same font as other sections */
              <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer" className="text-[#C87A23] hover:underline font-medium">
                        {children}
                      </a>
                    ),
                    strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                    h2: ({ children }) => <h2 className="text-lg font-bold text-slate-800 mt-6 mb-3">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-base font-bold text-slate-800 mt-4 mb-2">{children}</h3>,
                    p: ({ children }) => <p className="mb-4 text-slate-700">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-5 mb-4 space-y-1">{children}</ul>,
                    li: ({ children }) => <li className="text-slate-700">{children}</li>,
                  }}
                >
                  {sections.full_report.content || 'No content available'}
                </ReactMarkdown>
              </div>
            ) : activeTab === 'technicals' ? (
              /* Chartism Tab - Technical Analysis Text */
              <div className="space-y-6">
                {sections.technicals ? (
                  <div>
                    <h3 className="text-xl font-bold text-slate-800 mb-4">Chartism Analysis</h3>
                    <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                      <ReactMarkdown
                        components={{
                          a: ({ href, children }) => (
                            <a href={href} target="_blank" rel="noopener noreferrer" className="text-[#C87A23] hover:underline font-medium">
                              {children}
                            </a>
                          ),
                          strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                          h2: ({ children }) => <h2 className="text-lg font-bold text-slate-800 mt-4 mb-2">{children}</h2>,
                          h3: ({ children }) => <h3 className="text-base font-bold text-slate-800 mt-3 mb-2">{children}</h3>,
                          h4: ({ children }) => <h4 className="text-sm font-bold text-slate-800 mt-3 mb-1">{children}</h4>,
                          p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                          ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
                          li: ({ children }) => <li className="text-slate-700">{children}</li>,
                        }}
                      >
                        {sections.technicals.content || 'No chartism analysis available'}
                      </ReactMarkdown>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-slate-50 rounded-lg">
                    <p className="text-lg font-medium">No chartism analysis available</p>
                    <p className="text-sm mt-2">Technical analysis will appear here after analysis completes</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-8">
                {Object.entries(getVisibleSections()).map(([sectionId, section]) => (
                  <div key={sectionId} className="border-b border-slate-100 pb-8 last:border-0">
                    <h3 className="text-xl font-bold text-slate-800 mb-4">
                      {section?.title || 'Section'}
                    </h3>
                    <div className="prose prose-slate max-w-none text-sm leading-relaxed">
                      <ReactMarkdown
                        components={{
                          a: ({ href, children }) => (
                            <a href={href} target="_blank" rel="noopener noreferrer" className="text-[#C87A23] hover:underline font-medium">
                              {children}
                            </a>
                          ),
                          strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                          h2: ({ children }) => <h2 className="text-lg font-bold text-slate-800 mt-4 mb-2">{children}</h2>,
                          h3: ({ children }) => <h3 className="text-base font-bold text-slate-800 mt-3 mb-2">{children}</h3>,
                          h4: ({ children }) => <h4 className="text-sm font-bold text-slate-800 mt-3 mb-1">{children}</h4>,
                          p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
                          ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
                          li: ({ children }) => <li className="text-slate-700">{children}</li>,
                        }}
                      >
                        {section?.content || 'No content available'}
                      </ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Scroll indicator */}
          {Object.keys(sections).length > 0 && (
            <div className="border-t border-slate-200 px-4 py-1 text-center" style={{ background: 'linear-gradient(to right, var(--amber-gradient-from), var(--amber-gradient-to))' }}>
              <p className="text-xs font-medium" style={{ color: 'var(--amber-text)' }}>
                Scroll down to ask questions about this analysis
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default AnalysisView
