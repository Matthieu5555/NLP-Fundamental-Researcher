import { useState } from 'react'
import StockPicker from './components/StockPicker'
import AnalysisView from './components/AnalysisView'
import ChatInterface from './components/ChatInterface'
import './index.css'

function App() {
  const [sessionId, setSessionId] = useState(null)
  const [ticker, setTicker] = useState(null)
  const [analysisComplete, setAnalysisComplete] = useState(false)
  const [reportVersion, setReportVersion] = useState(0)

  const handleAnalysisStart = (newSessionId, newTicker) => {
    setSessionId(newSessionId)
    setTicker(newTicker)
    setAnalysisComplete(false)
  }

  const handleAnalysisComplete = () => {
    setAnalysisComplete(true)
  }

  const handleReset = () => {
    setSessionId(null)
    setTicker(null)
    setAnalysisComplete(false)
    setReportVersion(0)
  }

  const handleReportUpdated = () => {
    setReportVersion(prev => prev + 1)
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white shadow-md border-b border-slate-200 px-8 py-6">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              George Financial Analyst
            </h1>
            {ticker && (
              <p className="mt-1 text-sm text-slate-600">
                Currently analyzing: <span className="font-semibold text-blue-600">{ticker}</span>
              </p>
            )}
          </div>
          {sessionId && (
            <button
              onClick={handleReset}
              className="px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
            >
              New Analysis
            </button>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-grow overflow-y-auto">
        <div className="max-w-7xl mx-auto px-8 py-8 space-y-8">
          {/* Stock Picker */}
          <div className={sessionId ? 'opacity-50 pointer-events-none' : ''}>
            <StockPicker
              onAnalysisStart={handleAnalysisStart}
              disabled={!!sessionId}
            />
          </div>

          {/* Analysis Results */}
          {sessionId && (
            <AnalysisView
              sessionId={sessionId}
              ticker={ticker}
              onAnalysisComplete={handleAnalysisComplete}
              reportVersion={reportVersion}
            />
          )}

          {/* Chat Interface */}
          {sessionId && analysisComplete && (
            <ChatInterface
              sessionId={sessionId}
              ticker={ticker}
              onReportUpdated={handleReportUpdated}
            />
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 px-8 py-4">
        <p className="text-center text-sm text-slate-500">
          WARNING: This analysis should not be considered as financial advice
        </p>
      </footer>
    </div>
  )
}

export default App
