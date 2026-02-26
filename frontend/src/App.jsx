import { useReducer, useEffect } from 'react'
import StockPicker from './components/StockPicker'
import AnalysisView from './components/AnalysisView'
import ChatInterface from './components/ChatInterface'
import SessionBrowser from './components/SessionBrowser'
import AuthModal from './components/AuthModal'
import UsageStats from './components/UsageStats'
import SettingsModal from './components/SettingsModal'
import WatchlistDashboard from './components/WatchlistDashboard'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import api from './utils/api'
import './index.css'

// State machine for the analysis session and UI modals
const initialState = {
  sessionId: null,
  ticker: null,
  analysisComplete: false,
  reportVersion: 0,
  beliefs: [],
  isResumed: false,
  reportDirty: false,
  isUpdatingReport: false,
  chatCost: 0,
  showAuthModal: false,
  showSessionBrowser: false,
  showUsageStats: false,
  showSettings: false,
  showWatchlist: false,
}

function appReducer(state, action) {
  switch (action.type) {
    case 'ANALYSIS_START':
      return {
        ...state,
        sessionId: action.sessionId,
        ticker: action.ticker,
        analysisComplete: false,
        beliefs: [],
        isResumed: false,
        reportDirty: false,
        chatCost: 0,
      }
    case 'ANALYSIS_COMPLETE':
      return { ...state, analysisComplete: true }
    case 'RESET':
      return {
        ...initialState,
        showAuthModal: state.showAuthModal,
      }
    case 'NEW_BELIEFS':
      return {
        ...state,
        beliefs: [...state.beliefs, ...action.beliefs],
        reportDirty: true,
      }
    case 'SET_BELIEFS':
      return { ...state, beliefs: action.beliefs }
    case 'REPORT_UPDATED':
      return {
        ...state,
        reportVersion: state.reportVersion + 1,
        reportDirty: false,
      }
    case 'REPORT_VERSION_BUMP':
      return { ...state, reportVersion: state.reportVersion + 1 }
    case 'SET_UPDATING_REPORT':
      return { ...state, isUpdatingReport: action.value }
    case 'SET_COST':
      return { ...state, chatCost: action.cost }
    case 'RESUME_SESSION':
      return {
        ...state,
        sessionId: action.sessionId,
        ticker: action.ticker,
        analysisComplete: true,
        isResumed: true,
        reportVersion: state.reportVersion + 1,
        showSessionBrowser: false,
      }
    case 'TOGGLE_MODAL':
      return { ...state, [action.modal]: action.value ?? !state[action.modal] }
    default:
      return state
  }
}

function AppContent() {
  const { isAuthenticated, user, logout, loading: authLoading } = useAuth()
  const [state, dispatch] = useReducer(appReducer, initialState)

  const {
    sessionId, ticker, analysisComplete, reportVersion, beliefs,
    isResumed, reportDirty, isUpdatingReport, chatCost,
    showAuthModal, showSessionBrowser, showUsageStats, showSettings, showWatchlist,
  } = state

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

  const handleAnalysisStart = (newSessionId, newTicker) => {
    dispatch({ type: 'ANALYSIS_START', sessionId: newSessionId, ticker: newTicker })
  }

  const handleUpdateReport = async () => {
    if (!sessionId || isUpdatingReport) return

    dispatch({ type: 'SET_UPDATING_REPORT', value: true })
    try {
      await api.post(`/api/sessions/${sessionId}/regenerate-report`)
      dispatch({ type: 'REPORT_UPDATED' })
    } catch (err) {
      console.error('Update report error:', err)
      alert('Failed to update report. Please try again.')
    } finally {
      dispatch({ type: 'SET_UPDATING_REPORT', value: false })
    }
  }

  const handleResumeSession = async (sessionData) => {
    dispatch({ type: 'RESUME_SESSION', sessionId: sessionData.session_id, ticker: sessionData.ticker })

    try {
      const response = await api.get(`/api/sessions/${sessionData.session_id}/beliefs`)
      const loadedBeliefs = response.data.beliefs.map(b => ({
        content: b.content,
        type: b.source?.split(':')[0] || 'confirmed_fact',
        section: b.source?.split(':')[1] || 'general',
        confidence: b.confidence
      }))
      dispatch({ type: 'SET_BELIEFS', beliefs: loadedBeliefs })
    } catch (err) {
      console.error('Failed to load beliefs:', err)
    }
  }

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand mx-auto"></div>
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
              <span className="text-brand">Constant</span>
              <span className="text-slate-700"> - Your LLM Intern</span>
            </h1>
            {ticker && isAuthenticated && (
              <p className="mt-1 text-sm text-slate-600">
                Currently analyzing: <span className="font-semibold text-brand">{ticker}</span>
              </p>
            )}
          </div>
          <div className="flex gap-2 items-center">
            {isAuthenticated ? (
              <>
                {!sessionId && (
                  <>
                    <button
                      onClick={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showSessionBrowser', value: true })}
                      className="px-4 py-2 text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 hover:border-slate-400 rounded-lg transition-all"
                    >
                      Resume Analysis
                    </button>
                    <button
                      onClick={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showWatchlist' })}
                      className={`px-4 py-2 text-sm font-medium rounded-lg transition-all border ${
                        showWatchlist
                          ? 'text-accent-info-dark bg-accent-info-light border-accent-info'
                          : 'text-slate-700 bg-white hover:bg-slate-50 border-slate-300 hover:border-slate-400'
                      }`}
                    >
                      Watchlist
                    </button>
                  </>
                )}
                {sessionId && (
                  <button
                    onClick={() => dispatch({ type: 'RESET' })}
                    className="px-4 py-2 text-sm font-medium text-white rounded-lg transition-all bg-brand-gradient"
                  >
                    New Analysis
                  </button>
                )}
                <div className="w-px h-6 bg-slate-200 mx-1"></div>
                <button
                  onClick={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showUsageStats', value: true })}
                  className="px-3 py-2 text-sm text-slate-600 hover:text-brand hover:bg-slate-50 rounded-lg transition-all flex items-center gap-2"
                  title="View usage statistics"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <span className="max-w-[120px] truncate">{user?.display_name || user?.email}</span>
                </button>
                <button
                  onClick={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showSettings', value: true })}
                  className="p-2 text-slate-500 hover:text-brand hover:bg-slate-50 rounded-lg transition-all"
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
                onClick={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showAuthModal', value: true })}
                className="px-5 py-2.5 text-sm font-medium text-white rounded-lg shadow-md hover:shadow-lg transition-all duration-200 bg-brand-gradient"
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
            {showWatchlist && !sessionId && (
              <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
                <WatchlistDashboard
                  onNavigateToSession={(sid, t) => {
                    dispatch({ type: 'TOGGLE_MODAL', modal: 'showWatchlist', value: false })
                    handleResumeSession({ session_id: sid, ticker: t })
                  }}
                />
              </div>
            )}

            <div className={sessionId ? 'opacity-50 pointer-events-none' : ''}>
              <StockPicker
                onAnalysisStart={handleAnalysisStart}
                disabled={!!sessionId}
              />
            </div>

            {sessionId && (
              <AnalysisView
                sessionId={sessionId}
                ticker={ticker}
                onAnalysisComplete={() => dispatch({ type: 'ANALYSIS_COMPLETE' })}
                reportVersion={reportVersion}
                beliefs={beliefs}
                isResumed={isResumed}
                reportDirty={reportDirty}
                onUpdateReport={handleUpdateReport}
                isUpdatingReport={isUpdatingReport}
                chatCost={chatCost}
              />
            )}

            {sessionId && analysisComplete && (
              <ChatInterface
                sessionId={sessionId}
                ticker={ticker}
                onReportUpdated={() => dispatch({ type: 'REPORT_VERSION_BUMP' })}
                onNewBeliefs={(newBeliefs) => {
                  if (newBeliefs?.length > 0) dispatch({ type: 'NEW_BELIEFS', beliefs: newBeliefs })
                }}
                onCostUpdate={(cost) => dispatch({ type: 'SET_COST', cost })}
                onSourcesAdded={(sources) => {
                  if (sources?.length > 0) dispatch({ type: 'REPORT_VERSION_BUMP' })
                }}
              />
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-md px-8">
              <div className="text-6xl mb-6 text-brand">
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
                onClick={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showAuthModal', value: true })}
                className="px-8 py-3 text-lg font-medium text-white rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 bg-brand-gradient"
              >
                Get Started
              </button>
            </div>
          </div>
        )}
      </main>

      <footer className="bg-slate-50 border-t border-slate-100 py-0.5">
        <p className="text-center text-[9px] text-slate-400">
          Verify important information, LLMs can make mistakes, This analysis should not be considered financial advice
        </p>
      </footer>

      {showSessionBrowser && (
        <SessionBrowser
          onResumeSession={handleResumeSession}
          onClose={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showSessionBrowser', value: false })}
        />
      )}

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showAuthModal', value: false })}
      />

      <UsageStats
        isOpen={showUsageStats}
        onClose={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showUsageStats', value: false })}
      />

      <SettingsModal
        isOpen={showSettings}
        onClose={() => dispatch({ type: 'TOGGLE_MODAL', modal: 'showSettings', value: false })}
      />
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App
