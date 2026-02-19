import { useState, useEffect } from 'react'
import StockPicker from './components/StockPicker'
import AnalysisView from './components/AnalysisView'
import ChatInterface from './components/ChatInterface'
import SessionBrowser from './components/SessionBrowser'
import AuthModal from './components/AuthModal'
import UsageStats from './components/UsageStats'
import SettingsModal from './components/SettingsModal'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import api from './utils/api'
import './index.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

function AppContent() {
  const { isAuthenticated, user, logout, loading: authLoading } = useAuth()
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [ticker, setTicker] = useState(null)
  const [analysisComplete, setAnalysisComplete] = useState(false)
  const [reportVersion, setReportVersion] = useState(0)
  const [showSessionBrowser, setShowSessionBrowser] = useState(false)
  const [showUsageStats, setShowUsageStats] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [beliefs, setBeliefs] = useState([])

  // Load user theme on startup
  useEffect(() => {
    if (!isAuthenticated) return

    const loadTheme = async () => {
      try {
        const response = await api.get('/api/settings/')
        const theme = response.data.theme || 'light'
        if (theme === 'dark') {
          document.documentElement.classList.add('dark')
        } else {
          document.documentElement.classList.remove('dark')
        }
      } catch (err) {
        console.error('Failed to load theme:', err)
      }
    }

    loadTheme()
  }, [isAuthenticated])
  const [isResumed, setIsResumed] = useState(false)
  const [reportDirty, setReportDirty] = useState(false)
  const [isUpdatingReport, setIsUpdatingReport] = useState(false)
  const [chatCost, setChatCost] = useState(0)

  const handleAnalysisStart = (newSessionId, newTicker) => {
    setSessionId(newSessionId)
    setTicker(newTicker)
    setAnalysisComplete(false)
    setBeliefs([])
    setIsResumed(false)  // New analysis, not resumed
  }

  const handleAnalysisComplete = () => {
    setAnalysisComplete(true)
  }

  const handleReset = () => {
    setSessionId(null)
    setTicker(null)
    setAnalysisComplete(false)
    setReportVersion(0)
    setBeliefs([])
    setIsResumed(false)
    setReportDirty(false)
    setIsUpdatingReport(false)
    setChatCost(0)
  }

  const handleReportUpdated = () => {
    setReportVersion(prev => prev + 1)
  }

  const handleNewBeliefs = (newBeliefs) => {
    if (newBeliefs && newBeliefs.length > 0) {
      setBeliefs(prev => [...prev, ...newBeliefs])
      setReportDirty(true)  // Mark report as needing update
    }
  }

  const handleUpdateReport = async () => {
    if (!sessionId || isUpdatingReport) return

    setIsUpdatingReport(true)
    try {
      const response = await api.post(`/api/sessions/${sessionId}/regenerate-report`)
      console.log('Report updated:', response.data)

      // Refresh sections and clear dirty flag
      setReportVersion(prev => prev + 1)
      setReportDirty(false)
    } catch (err) {
      console.error('Update report error:', err)
      alert('Failed to update report. Please try again.')
    } finally {
      setIsUpdatingReport(false)
    }
  }

  const handleCostUpdate = (cost) => {
    setChatCost(cost)
  }

  const handleSourcesAdded = (newSources) => {
    // Trigger a report refresh to show new sources in Sources tab
    if (newSources && newSources.length > 0) {
      console.log('New sources added:', newSources.length)
      setReportVersion(prev => prev + 1)
    }
  }

  const handleResumeSession = async (sessionData) => {
    setSessionId(sessionData.session_id)
    setTicker(sessionData.ticker)
    setAnalysisComplete(true)
    setIsResumed(true)  // Mark as resumed session
    setReportVersion(prev => prev + 1)
    setShowSessionBrowser(false)

    // Load existing beliefs for resumed session
    try {
      const response = await api.get(`/api/sessions/${sessionData.session_id}/beliefs`)
      const data = response.data
      // Convert beliefs to frontend format
      const loadedBeliefs = data.beliefs.map(b => ({
        content: b.content,
        type: b.source?.split(':')[0] || 'confirmed_fact',
        section: b.source?.split(':')[1] || 'general',
        confidence: b.confidence
      }))
      setBeliefs(loadedBeliefs)
    } catch (err) {
      console.error('Failed to load beliefs:', err)
    }
  }

  // Show loading spinner while checking auth
  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-600 mx-auto"></div>
          <p className="mt-4 text-slate-600">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white shadow-md border-b border-slate-200 px-8 py-6">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold">
              <span style={{ color: '#C87A23' }}>Constant</span>
              <span className="text-slate-700"> - Your LLM Intern</span>
            </h1>
            {ticker && isAuthenticated && (
              <p className="mt-1 text-sm text-slate-600">
                Currently analyzing: <span className="font-semibold" style={{ color: '#C87A23' }}>{ticker}</span>
              </p>
            )}
          </div>
          <div className="flex gap-2 items-center">
            {isAuthenticated ? (
              <>
                {/* Action Buttons (left side) */}
                {!sessionId && (
                  <button
                    onClick={() => setShowSessionBrowser(true)}
                    className="px-4 py-2 text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 hover:border-slate-400 rounded-lg transition-all"
                  >
                    Resume Analysis
                  </button>
                )}
                {sessionId && (
                  <button
                    onClick={handleReset}
                    className="px-4 py-2 text-sm font-medium text-white rounded-lg transition-all" style={{ background: 'linear-gradient(to right, #C87A23, #B06A1A)' }}
                  >
                    New Analysis
                  </button>
                )}
                {/* Divider */}
                <div className="w-px h-6 bg-slate-200 mx-1"></div>
                {/* User Info & Usage Stats */}
                <button
                  onClick={() => setShowUsageStats(true)}
                  className="px-3 py-2 text-sm text-slate-600 hover:text-amber-600 hover:bg-slate-50 rounded-lg transition-all flex items-center gap-2"
                  title="View usage statistics"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <span className="max-w-[120px] truncate">{user?.display_name || user?.email}</span>
                </button>
                {/* Settings Button */}
                <button
                  onClick={() => setShowSettings(true)}
                  className="p-2 text-slate-500 hover:text-amber-600 hover:bg-slate-50 rounded-lg transition-all"
                  title="Settings"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </button>
                <button
                  onClick={logout}
                  className="px-4 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-all"
                >
                  Sign Out
                </button>
              </>
            ) : (
              <button
                onClick={() => setShowAuthModal(true)}
                className="px-5 py-2.5 text-sm font-medium text-white rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
                style={{ background: 'linear-gradient(to right, #C87A23, #B06A1A)' }}
              >
                Sign In
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-grow overflow-y-auto">
        {isAuthenticated ? (
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
                beliefs={beliefs}
                isResumed={isResumed}
                reportDirty={reportDirty}
                onUpdateReport={handleUpdateReport}
                isUpdatingReport={isUpdatingReport}
                chatCost={chatCost}
              />
            )}

            {/* Chat Interface */}
            {sessionId && analysisComplete && (
              <ChatInterface
                sessionId={sessionId}
                ticker={ticker}
                onReportUpdated={handleReportUpdated}
                onNewBeliefs={handleNewBeliefs}
                onCostUpdate={handleCostUpdate}
                onSourcesAdded={handleSourcesAdded}
              />
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-md px-8">
              <div className="text-6xl mb-6" style={{ color: '#C87A23' }}>
                <svg className="w-24 h-24 mx-auto" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-4">
                Welcome to Constant
              </h2>
              <p className="text-slate-600 mb-8">
                Your AI-powered equity research assistant. Get comprehensive stock analysis with multi-agent debate, moat analysis, and strategy.
              </p>
              <button
                onClick={() => setShowAuthModal(true)}
                className="px-8 py-3 text-lg font-medium text-white rounded-lg shadow-lg hover:shadow-xl transition-all duration-200"
                style={{ background: 'linear-gradient(to right, #C87A23, #B06A1A)' }}
              >
                Get Started
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-slate-50 border-t border-slate-100 py-0.5">
        <p className="text-center text-[9px] text-slate-400">
          Verify important information, LLMs can make mistakes, This analysis should not be considered financial advice
        </p>
      </footer>

      {/* Session Browser Modal */}
      {showSessionBrowser && (
        <SessionBrowser
          onResumeSession={handleResumeSession}
          onClose={() => setShowSessionBrowser(false)}
        />
      )}

      {/* Auth Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
      />

      {/* Usage Stats Modal */}
      <UsageStats
        isOpen={showUsageStats}
        onClose={() => setShowUsageStats(false)}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
      />
    </div>
  )
}

// Main App wrapper with AuthProvider
function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App
