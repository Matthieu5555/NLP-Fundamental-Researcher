import { useState, useCallback } from 'react'
import DataAvailabilityBanner from './DataAvailabilityBanner'
import { authFetch, API_URL } from '../utils/api'
import { useAnalysisData } from '../hooks/useAnalysisData'
import { useDownload } from '../hooks/useDownload'

import AnalysisProgress from './analysis/AnalysisProgress'
import CostBreakdown from './analysis/CostBreakdown'
import ActionButtons from './analysis/ActionButtons'
import TabNavigation from './analysis/TabNavigation'
import { buildTabs, renderTab } from './analysis/tabRegistry'

function AnalysisView({ sessionId, ticker, onAnalysisComplete, reportVersion = 0, beliefs = [], isResumed = false, reportDirty = false, onUpdateReport, onUpdateAnalysis, isUpdatingReport = false, isUpdatingAnalysis = false, chatCost = 0 }) {
  const [activeTab, setActiveTab] = useState('thesis')
  const [watchlistAdded, setWatchlistAdded] = useState(false)

  const data = useAnalysisData(sessionId, ticker, reportVersion, { isResumed, onAnalysisComplete })
  const { downloading, trigger: triggerDownload } = useDownload(sessionId, ticker)

  const addToWatchlist = useCallback(async () => {
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
  }, [sessionId, ticker])

  // --- Derived ---

  const getAllSources = () => {
    const sourcesSection = data.sections.sources
    return (sourcesSection?.sources && Array.isArray(sourcesSection.sources)) ? sourcesSection.sources : []
  }

  const tabCtx = {
    sections: data.sections,
    beliefs,
    valuation: data.valuation,
    contradictions: data.contradictions,
    researchGaps: data.researchGaps,
    financialStatements: data.financialStatements,
    financialsLoading: data.financialsLoading,
    companyInfo: data.companyInfo,
    excludedSourceIds: data.excludedSourceIds,
    allSources: getAllSources(),
    onExclude: data.excludeSource,
    onRestore: data.restoreSource,
    ticker,
  }

  const tabs = buildTabs(tabCtx)
  const hasSections = Object.keys(data.sections).length > 0
  const showContent = !data.analysisRunning && !data.sectionsLoading && !data.error

  return (
    <div className="bg-surface-elevated rounded-lg border overflow-hidden">
      {/* Header */}
      <div className="border-b bg-surface-secondary px-6 py-5">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-primary">Analysis Results</h2>
            <div className="flex items-center gap-4 mt-1">
              <p className="text-sm text-secondary">Multi-agent analysis for {ticker}</p>
              <CostBreakdown costUsd={data.costUsd} chatCost={chatCost} costBreakdown={data.costBreakdown} />
            </div>
          </div>
          {!data.analysisRunning && !data.sectionsLoading && hasSections && (
            <ActionButtons
              onUpdateAnalysis={onUpdateAnalysis}
              onUpdateReport={onUpdateReport}
              onDownloadDocx={() => triggerDownload('docx')}
              onDownloadPptx={() => triggerDownload('pptx')}
              onDownloadExcel={() => triggerDownload('excel')}
              onAddToWatchlist={addToWatchlist}
              reportDirty={reportDirty}
              isUpdatingReport={isUpdatingReport}
              isUpdatingAnalysis={isUpdatingAnalysis}
              isDownloadingDocx={downloading.docx}
              isDownloadingPptx={downloading.pptx}
              isDownloadingExcel={downloading.excel}
              watchlistAdded={watchlistAdded}
            />
          )}
        </div>
      </div>

      {/* Data Availability Banner */}
      {data.companyInfo && !data.companyInfo.is_us && !data.analysisRunning && (
        <div className="px-6 pt-4">
          <DataAvailabilityBanner companyInfo={data.companyInfo} />
        </div>
      )}

      {/* Analysis Running */}
      {data.analysisRunning && (
        <AnalysisProgress progress={data.progress} progressStep={data.progressStep} progressTotal={data.progressTotal} />
      )}

      {/* Sections Loading */}
      {!data.analysisRunning && data.sectionsLoading && (
        <div className="px-6 py-12 text-center bg-surface-elevated">
          <div className="inline-flex items-center justify-center space-x-3 mb-4">
            <div className="w-8 h-8 border-4 spinner-brand rounded-full animate-spin"></div>
          </div>
          <p className="text-secondary">Loading analysis results...</p>
        </div>
      )}

      {/* Error */}
      {data.error && (
        <div className="px-6 py-8 bg-surface-elevated">
          <div className="bg-accent-danger-light border border-accent-danger rounded-lg p-6 text-center">
            <p className="text-sm text-accent-danger-dark font-medium mb-4">{data.error}</p>
            <button onClick={data.runAnalysis} className="px-4 py-2 bg-accent-danger text-white rounded-lg hover:bg-accent-danger-dark transition-colors">
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* Tabs and Content */}
      {showContent && (
        <>
          <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} sections={data.sections} beliefs={beliefs} />

          <div className="px-6 py-6 bg-surface-elevated">
            {renderTab(activeTab, tabCtx)}
          </div>

          {hasSections && (
            <div className="px-4 py-1 text-center bg-surface-secondary">
              <p className="text-xs font-medium text-brand">
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
