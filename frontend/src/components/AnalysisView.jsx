import { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

function AnalysisView({ sessionId, ticker, onAnalysisComplete, reportVersion = 0 }) {
  const [activeTab, setActiveTab] = useState('all')
  const [analysisRunning, setAnalysisRunning] = useState(true)
  const [sectionsLoading, setSectionsLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [sections, setSections] = useState({})
  const [error, setError] = useState(null)

  useEffect(() => {
    if (sessionId) {
      runAnalysis()
    }
  }, [sessionId])

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
      const response = await fetch(`${API_URL}/api/analysis/${sessionId}/run`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error('Failed to start analysis')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      const readStream = async () => {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.substring(6)
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
              } catch (e) {
                // Not JSON, ignore
              }
            }
          }
        }
      }

      readStream().catch(err => {
        console.error('Stream read error:', err)
        setError('Analysis stream interrupted')
        setAnalysisRunning(false)
      })

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
      const response = await fetch(`${API_URL}/api/reports/${sessionId}/sections`)
      const data = await response.json()
      console.log('Sections loaded:', Object.keys(data.sections || {}))
      console.log('Section data:', data.sections)
      setSections(data.sections || {})
      setSectionsLoading(false)
      onAnalysisComplete()
    } catch (err) {
      console.error('Load sections error:', err)
      setError('Failed to load analysis results')
      setSectionsLoading(false)
    }
  }

  const tabs = [
    { id: 'all', label: 'Full Report' },
    { id: 'fundamentals', label: 'Fundamentals' },
    { id: 'technicals', label: 'Technicals' },
    { id: 'bull_case', label: 'Bull Case' },
    { id: 'bear_case', label: 'Bear Case' },
    { id: 'moat_analysis', label: 'Moat' },
    { id: 'further_research', label: 'Further Research' },
  ]

  const getVisibleSections = () => {
    if (activeTab === 'all') {
      return sections
    }
    const section = sections[activeTab]
    return section ? { [activeTab]: section } : {}
  }

  const downloadReport = async (format = 'markdown') => {
    try {
      const url = `${API_URL}/api/reports/${sessionId}?format=${format}`
      const response = await fetch(url)
      const content = await response.text()

      const blob = new Blob([content], { type: 'text/markdown' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `${ticker}_analysis.md`
      a.click()
      window.URL.revokeObjectURL(downloadUrl)
    } catch (err) {
      console.error('Download error:', err)
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
            <p className="text-sm text-slate-600 mt-1">Multi-agent analysis for {ticker}</p>
          </div>
          {!analysisRunning && !sectionsLoading && Object.keys(sections).length > 0 && (
            <button
              onClick={() => downloadReport('markdown')}
              className="px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 rounded-lg shadow-md hover:shadow-lg transition-all"
            >
              DOWNLOAD FINAL REPORT
            </button>
          )}
        </div>
      </div>

      {/* Analysis Running State */}
      {analysisRunning && (
        <div className="px-6 py-16 text-center bg-white">
          <div className="inline-flex items-center justify-center space-x-3 mb-4">
            <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
          <p className="text-lg text-slate-700 font-medium">{progress || 'Initializing analysis...'}</p>
          <p className="text-sm text-slate-500 mt-2">This may take 30-60 seconds</p>
        </div>
      )}

      {/* Sections Loading State */}
      {!analysisRunning && sectionsLoading && (
        <div className="px-6 py-12 text-center bg-white">
          <div className="inline-flex items-center justify-center space-x-3 mb-4">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
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
              {tabs.map((tab) => {
                const isActive = activeTab === tab.id
                const hasContent = tab.id === 'all' || sections[tab.id]

                return (
                  <button
                    key={tab.id}
                    onClick={() => hasContent && setActiveTab(tab.id)}
                    disabled={!hasContent}
                    className={`
                      flex items-center space-x-2 px-5 py-4 border-b-2 font-medium text-sm whitespace-nowrap transition-all
                      ${isActive
                        ? 'border-blue-500 text-blue-600 bg-white'
                        : hasContent
                          ? 'border-transparent text-slate-600 hover:text-slate-800 hover:border-slate-300 cursor-pointer'
                          : 'border-transparent text-slate-400 cursor-not-allowed'
                      }
                    `}
                  >
                    <span>{tab.label}</span>
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Content Area */}
          <div className="px-6 py-6 min-h-[400px] max-h-[600px] overflow-y-auto bg-white">
            {Object.keys(sections).length === 0 ? (
              <div className="text-center py-16 text-slate-500">
                <p className="text-lg font-medium">No analysis results yet</p>
                <p className="text-sm mt-2">Results will appear here when analysis completes</p>
              </div>
            ) : Object.entries(getVisibleSections()).length === 0 ? (
              <div className="text-center py-16 text-slate-500">
                <p>No content available for this section</p>
              </div>
            ) : (
              <div className="space-y-8">
                {Object.entries(getVisibleSections()).map(([sectionId, section]) => (
                  <div key={sectionId} className="border-b border-slate-100 pb-8 last:border-0">
                    <h3 className="text-xl font-bold text-slate-800 mb-4">
                      {section?.title || 'Section'}
                    </h3>
                    <div className="text-slate-700 leading-relaxed whitespace-pre-wrap text-sm">
                      {section?.content || 'No content available'}
                    </div>
                    {section?.sources && section.sources.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-slate-200">
                        <p className="text-xs font-semibold text-slate-500 mb-2">Sources:</p>
                        <ul className="text-xs text-slate-500 space-y-1">
                          {section.sources.map((source, idx) => (
                            <li key={idx}>• {source}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Scroll indicator */}
          {Object.keys(sections).length > 0 && (
            <div className="border-t border-slate-200 px-6 py-4 bg-gradient-to-r from-blue-50 to-indigo-50 text-center">
              <p className="text-sm text-blue-700 font-medium">
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
