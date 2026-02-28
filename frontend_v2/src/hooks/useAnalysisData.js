import { useState, useEffect, useRef, useCallback } from 'react'
import { authFetch, API_URL } from '../utils/api'
import { parseSSEStream } from './useSSEStream'

/**
 * Encapsulates all data loading, analysis streaming, and report state
 * for AnalysisView. Returns everything the component needs to render,
 * keeping AnalysisView as a pure layout component.
 */
export function useAnalysisData(sessionId, ticker, reportVersion, { isResumed, onAnalysisComplete }) {
  // Analysis stream
  const [analysisRunning, setAnalysisRunning] = useState(false)
  const [progress, setProgress] = useState('')
  const [progressStep, setProgressStep] = useState(0)
  const [progressTotal, setProgressTotal] = useState(10)
  const [error, setError] = useState(null)
  const [costUsd, setCostUsd] = useState(null)
  const [costBreakdown, setCostBreakdown] = useState(null)

  // Report sections
  const [sections, setSections] = useState({})
  const [contradictions, setContradictions] = useState([])
  const [researchGaps, setResearchGaps] = useState([])
  const [excludedSourceIds, setExcludedSourceIds] = useState([])
  const [sectionsLoading, setSectionsLoading] = useState(false)

  // Supplementary data
  const [companyInfo, setCompanyInfo] = useState(null)
  const [financialStatements, setFinancialStatements] = useState(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)

  // Valuation (grouped as single object to reduce state count)
  // Prop names match canonical keys from shared/section_registry.json
  const [valuation, setValuation] = useState({
    dcf: null,
    sensitivity: null,
    sensitivityOperating: null,
    conviction: null,
    scenarios: null,
    footballField: null,
    earningsModel: null,
    precedents: null,
    comps: null,
  })

  const initRef = useRef({ sessionId: null, started: false })
  const analysisRunningRef = useRef(false)

  // --- Internal loaders ---

  const loadSections = useCallback(async () => {
    setSectionsLoading(true)
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sections`)
      if (!response.ok) throw new Error(`Sections request failed (${response.status})`)
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
  }, [sessionId])

  const loadCompanyInfo = async () => {
    try {
      const response = await authFetch(`${API_URL}/api/analysis/${sessionId}/company-info`)
      if (!response.ok) throw new Error(`Company info request failed (${response.status})`)
      setCompanyInfo(await response.json())
    } catch (err) {
      console.error('Load company info error:', err)
    }
  }

  const loadFinancialStatements = async () => {
    setFinancialsLoading(true)
    try {
      const response = await authFetch(`${API_URL}/api/analysis/${sessionId}/financial-statements`)
      if (!response.ok) throw new Error(`Financial statements request failed (${response.status})`)
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
      if (!response.ok) throw new Error(`Valuation data request failed (${response.status})`)
      const data = await response.json()
      setValuation({
        dcf: data.dcf || null,
        sensitivity: data.sensitivity || null,
        sensitivityOperating: data.sensitivity_operating || null,
        conviction: data.conviction || null,
        scenarios: data.scenarios || null,
        footballField: data.football_field || null,
        earningsModel: data.earnings_model || null,
        precedents: data.precedents || null,
        comps: data.comps || null,
      })
    } catch (err) {
      console.error('Load valuation data error:', err)
    }
  }

  // --- Public actions ---

  const runAnalysis = useCallback(async () => {
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
  }, [sessionId, loadSections])

  const excludeSource = useCallback(async (sourceId) => {
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sources/${sourceId}/exclude`, { method: 'POST' })
      const data = await response.json()
      if (data.success) setExcludedSourceIds(data.excluded_source_ids)
    } catch (err) {
      console.error('Exclude source error:', err)
    }
  }, [sessionId])

  const restoreSource = useCallback(async (sourceId) => {
    try {
      const response = await authFetch(`${API_URL}/api/reports/${sessionId}/sources/${sourceId}/restore`, { method: 'POST' })
      const data = await response.json()
      if (data.success) setExcludedSourceIds(data.excluded_source_ids)
    } catch (err) {
      console.error('Restore source error:', err)
    }
  }, [sessionId])

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

  return {
    analysisRunning,
    progress,
    progressStep,
    progressTotal,
    error,
    costUsd,
    costBreakdown,
    sections,
    contradictions,
    researchGaps,
    excludedSourceIds,
    sectionsLoading,
    companyInfo,
    financialStatements,
    financialsLoading,
    valuation,
    runAnalysis,
    excludeSource,
    restoreSource,
  }
}
