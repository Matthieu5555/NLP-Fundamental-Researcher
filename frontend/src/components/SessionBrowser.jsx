import { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

function SessionBrowser({ onResumeSession, onClose }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTicker, setSearchTicker] = useState('')

  useEffect(() => {
    fetchSessions()
  }, [])

  const fetchSessions = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_URL}/api/sessions/`)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      setSessions(data.sessions || [])
      setError(null)
    } catch (err) {
      console.error('Failed to fetch sessions:', err)
      setError('Failed to load sessions. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleResume = async (sessionId) => {
    try {
      const response = await fetch(`${API_URL}/api/sessions/${sessionId}/resume`, {
        method: 'POST'
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const sessionData = await response.json()
      onResumeSession(sessionData)
      onClose()
    } catch (err) {
      console.error('Failed to resume session:', err)
      alert('Failed to resume session. Please try again.')
    }
  }

  const handleDelete = async (sessionId, e) => {
    e.stopPropagation() // Prevent triggering resume

    if (!confirm('Delete this analysis session?')) {
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/sessions/${sessionId}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      // Remove from list
      setSessions(prev => prev.filter(s => s.session_id !== sessionId))
    } catch (err) {
      console.error('Failed to delete session:', err)
      alert('Failed to delete session. Please try again.')
    }
  }

  const filteredSessions = sessions.filter(session =>
    !searchTicker || session.ticker.toLowerCase().includes(searchTicker.toLowerCase())
  )

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-slate-200">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Resume Past Analysis</h2>
            <p className="text-sm text-slate-600 mt-1">
              {sessions.length} session{sessions.length !== 1 ? 's' : ''} saved
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-slate-200">
          <input
            type="text"
            placeholder="Search by ticker..."
            value={searchTicker}
            onChange={(e) => setSearchTicker(e.target.value)}
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Sessions List */}
        <div className="flex-grow overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-600 mb-4">{error}</p>
              <button
                onClick={fetchSessions}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Retry
              </button>
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="text-center py-12">
              <svg className="w-16 h-16 mx-auto text-slate-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-slate-500">
                {searchTicker ? 'No sessions found for that ticker' : 'No past sessions found'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredSessions.map((session) => (
                <div
                  key={session.session_id}
                  onClick={() => handleResume(session.session_id)}
                  className="bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-300 rounded-lg p-4 cursor-pointer transition-all duration-200 group"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-grow">
                      <div className="flex items-center gap-3">
                        <h3 className="text-lg font-bold text-blue-600 group-hover:text-blue-700">
                          {session.ticker}
                        </h3>
                        <span className="text-xs text-slate-500">
                          {new Date(session.created_at).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric'
                          })}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600 mt-1 line-clamp-2">
                        {session.preview || 'No preview available'}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDelete(session.session_id, e)}
                      className="ml-4 text-slate-400 hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
                      title="Delete session"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                      </svg>
                      {session.message_count || 0} messages
                    </span>
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      {new Date(session.created_at).toLocaleTimeString('en-US', {
                        hour: 'numeric',
                        minute: '2-digit'
                      })}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50">
          <p className="text-xs text-slate-500 text-center">
            Sessions are automatically saved after each message
          </p>
        </div>
      </div>
    </div>
  )
}

export default SessionBrowser
