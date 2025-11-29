import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

function ChatInterface({ sessionId, ticker, onReportUpdated }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamingMessage, setStreamingMessage] = useState('')
  const [reportUpdateNotice, setReportUpdateNotice] = useState(false)
  const [searchStatus, setSearchStatus] = useState('')
  const [currentSources, setCurrentSources] = useState([])
  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMessage])

  const sendMessage = async (e) => {
    e.preventDefault()

    if (!input.trim() || streaming) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])

    setStreaming(true)
    setStreamingMessage('')

    try {
      const eventSource = new EventSource(
        `${API_URL}/api/chat/stream?session_id=${sessionId}&message=${encodeURIComponent(userMessage)}`
      )

      let fullResponse = ''

      eventSource.onmessage = (event) => {
        if (event.data === '[DONE]') {
          eventSource.close()
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: fullResponse,
            sources: currentSources
          }])
          setStreamingMessage('')
          setStreaming(false)
          setSearchStatus('')
          setCurrentSources([])
          return
        }

        // Check for JSON events (status, sources, report update)
        try {
          const eventData = JSON.parse(event.data)

          // Handle search status
          if (eventData.status) {
            setSearchStatus(eventData.status)
            return
          }

          // Handle sources
          if (eventData.sources) {
            setCurrentSources(eventData.sources)
            return
          }

          // Handle report update event
          if (eventData.event === 'report_updated') {
            setReportUpdateNotice(true)
            if (onReportUpdated) {
              onReportUpdated()
            }
            setTimeout(() => setReportUpdateNotice(false), 5000)
            return
          }
        } catch (e) {
          // Not JSON, treat as regular chunk
        }

        const chunk = event.data.replace('<br>', '\n')
        fullResponse += chunk
        setStreamingMessage(fullResponse)
      }

      eventSource.onerror = (error) => {
        console.error('Chat stream error:', error)
        eventSource.close()
        setStreaming(false)
        setStreamingMessage('')
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Sorry, there was an error. Please try again.'
        }])
      }

    } catch (err) {
      console.error('Send message error:', err)
      setStreaming(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(e)
    }
  }

  const exampleQuestions = [
    'What is the return on equity?',
    'How does debt-to-equity compare to competitors?',
    'What are the biggest risks?',
    'Analyze the latest earnings report',
  ]

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-50 to-blue-50 border-b border-slate-200 px-6 py-5">
        <h2 className="text-2xl font-bold text-slate-800">Dive Deeper on {ticker}</h2>
        <p className="text-sm text-slate-600 mt-1">
          Bring your knowledge and intuition - ask anything about the company, financials, risks, or opportunities
        </p>
      </div>

      {/* Chat Messages */}
      <div className="h-[500px] overflow-y-auto px-6 py-6 bg-slate-50 space-y-4">
        {messages.length === 0 && !streaming && (
          <div className="text-center py-12">
            <div className="space-y-2 max-w-2xl mx-auto">
              <p className="text-xs text-slate-500 font-semibold mb-3">Example questions:</p>
              {exampleQuestions.map((question, idx) => (
                <button
                  key={idx}
                  onClick={() => setInput(question)}
                  className="block w-full text-left px-4 py-3 text-sm text-blue-700 bg-white hover:bg-blue-50 rounded-lg border-2 border-blue-200 hover:border-blue-300 transition-all shadow-sm hover:shadow"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, idx) => (
          <div
            key={idx}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[85%] ${message.role === 'assistant' ? 'space-y-2' : ''}`}>
              <div
                className={`rounded-2xl px-5 py-3 shadow-md ${
                  message.role === 'user'
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white'
                    : 'bg-white border-2 border-slate-200 text-slate-800'
                }`}
              >
                {message.role === 'user' ? (
                  <p className="text-sm leading-relaxed">{message.content}</p>
                ) : (
                  <div className="prose prose-sm prose-slate max-w-none">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                )}
              </div>

              {/* Display sources for assistant messages */}
              {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                <div className="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3">
                  <p className="text-xs font-semibold text-slate-600 mb-2">Sources:</p>
                  <div className="space-y-1">
                    {message.sources.map((source, srcIdx) => (
                      <div key={srcIdx} className="flex items-start gap-2">
                        <svg className="w-3 h-3 text-blue-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                          <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                        </svg>
                        <a
                          href={source.url.startsWith('http') ? source.url : `https://${source.url}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-600 hover:text-blue-800 hover:underline flex-1"
                        >
                          {source.title}
                          {source.date && source.date !== 'recent' && (
                            <span className="text-slate-500 ml-1">({source.date})</span>
                          )}
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {streaming && streamingMessage && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-2xl px-5 py-3 bg-white border-2 border-blue-200 text-slate-800 shadow-md">
              <div className="prose prose-sm prose-slate max-w-none">
                <ReactMarkdown>{streamingMessage}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {streaming && !streamingMessage && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-5 py-3 bg-white border-2 border-slate-200 shadow-md">
              {searchStatus ? (
                <p className="text-sm text-blue-600 flex items-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {searchStatus}
                </p>
              ) : (
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Report Update Notice */}
      {reportUpdateNotice && (
        <div className="px-6 py-3 bg-green-50 border-t border-green-200">
          <p className="text-sm text-green-700 font-medium text-center">
            Report updated with new insights - scroll up to see changes
          </p>
        </div>
      )}

      {/* Input Form */}
      <div className="border-t-2 border-slate-200 bg-white px-6 py-5">
        <form onSubmit={sendMessage} className="flex space-x-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question about the analysis..."
            disabled={streaming}
            rows={2}
            className="flex-1 px-4 py-3 border-2 border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none disabled:bg-slate-100 disabled:cursor-not-allowed transition-all text-sm"
          />
          <button
            type="submit"
            disabled={!input.trim() || streaming}
            className="px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-semibold rounded-lg shadow-md hover:shadow-lg disabled:from-slate-400 disabled:to-slate-500 disabled:cursor-not-allowed transition-all duration-200"
          >
            {streaming ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              'Send'
            )}
          </button>
        </form>
        <p className="text-xs text-slate-500 mt-3 text-center">
          Press <kbd className="px-2 py-1 bg-slate-200 rounded text-xs font-mono">Enter</kbd> to send • <kbd className="px-2 py-1 bg-slate-200 rounded text-xs font-mono">Shift + Enter</kbd> for new line
        </p>
      </div>
    </div>
  )
}

export default ChatInterface
