import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { getAccessToken } from '../utils/api'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

function ChatInterface({ sessionId, ticker, onReportUpdated, onNewBeliefs, onCostUpdate, onSourcesAdded }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamingMessage, setStreamingMessage] = useState('')
  const [reportUpdateNotice, setReportUpdateNotice] = useState(false)
  const [reportEditNotice, setReportEditNotice] = useState(null)
  const [beliefNotice, setBeliefNotice] = useState(null)
  const [searchStatus, setSearchStatus] = useState('')
  const [currentSources, setCurrentSources] = useState([])
  const [chatCost, setChatCost] = useState(0)
  const [acknowledgment, setAcknowledgment] = useState(null)
  const [rationaleRequest, setRationaleRequest] = useState(null) // Follow-up for beliefs without rationale
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
    setAcknowledgment(null)
    setRationaleRequest(null) // Clear any pending rationale request

    try {
      // Use fetch with auth header instead of EventSource (which doesn't support headers)
      const token = getAccessToken()
      const response = await fetch(
        `${API_URL}/api/chat/stream?session_id=${sessionId}&message=${encodeURIComponent(userMessage)}`,
        {
          headers: {
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
        }
      )

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullResponse = ''
      let localSources = []
      let localAcknowledgment = null

      const processStream = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read()

            if (done) {
              // Stream ended
              setMessages(prev => [...prev, {
                role: 'assistant',
                content: fullResponse,
                sources: localSources,
                acknowledgment: localAcknowledgment
              }])
              setStreamingMessage('')
              setStreaming(false)
              setSearchStatus('')
              setCurrentSources([])
              setAcknowledgment(null)
              break
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.substring(6)

                if (data === '[DONE]') {
                  setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: fullResponse,
                    sources: localSources,
                    acknowledgment: localAcknowledgment
                  }])
                  setStreamingMessage('')
                  setStreaming(false)
                  setSearchStatus('')
                  setCurrentSources([])
                  setAcknowledgment(null)
                  return
                }

                // Check for JSON events
                try {
                  const eventData = JSON.parse(data)

                  if (eventData.status) {
                    setSearchStatus(eventData.status)
                    continue
                  }

                  if (eventData.sources) {
                    localSources = eventData.sources
                    setCurrentSources(eventData.sources)
                    continue
                  }

                  if (eventData.event === 'report_updated') {
                    setReportUpdateNotice(true)
                    if (onReportUpdated) onReportUpdated()
                    setTimeout(() => setReportUpdateNotice(false), 5000)
                    continue
                  }

                  if (eventData.event === 'report_edited') {
                    const sectionName = eventData.section?.replace('_', ' ') || 'report'
                    setReportEditNotice({ section: sectionName, action: eventData.action })
                    if (onReportUpdated) onReportUpdated()
                    setTimeout(() => setReportEditNotice(null), 5000)
                    continue
                  }

                  if (eventData.new_beliefs && eventData.new_beliefs.length > 0) {
                    setBeliefNotice(eventData.new_beliefs.length)
                    if (onNewBeliefs) onNewBeliefs(eventData.new_beliefs)
                    setTimeout(() => setBeliefNotice(null), 5000)
                    continue
                  }

                  if (eventData.cost_usd !== undefined) {
                    setChatCost(eventData.cost_usd)
                    if (onCostUpdate) onCostUpdate(eventData.cost_usd)
                    continue
                  }

                  if (eventData.acknowledgment) {
                    localAcknowledgment = eventData.acknowledgment
                    setAcknowledgment(eventData.acknowledgment)
                    continue
                  }

                  if (eventData.sources_added && eventData.sources_added.length > 0) {
                    if (onSourcesAdded) onSourcesAdded(eventData.sources_added)
                    continue
                  }

                  if (eventData.request_rationale) {
                    setRationaleRequest(eventData.request_rationale)
                    continue
                  }

                  if (eventData.text_done) {
                    continue
                  }
                } catch (e) {
                  // Not JSON, treat as text chunk
                }

                const chunk = data.replace('<br>', '\n')
                fullResponse += chunk
                setStreamingMessage(fullResponse)
              }
            }
          }
        } catch (err) {
          console.error('Stream processing error:', err)
          setStreaming(false)
          setStreamingMessage('')
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: 'Sorry, there was an error. Please try again.'
          }])
        }
      }

      processStream()

    } catch (err) {
      console.error('Send message error:', err)
      setStreaming(false)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, there was an error. Please try again.'
      }])
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(e)
    }
  }

  const exampleQuestions = [
    // Research questions
    'What is the return on equity?',
    'What are the biggest risks?',
    // Report editing commands
    'Make the bull case shorter and more punchy',
    'Emphasize the debt concerns in the bear case',
  ]

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="border-b border-slate-200 px-6 py-5" style={{ background: 'linear-gradient(to right, var(--amber-gradient-from), var(--amber-gradient-to))' }}>
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Dive Deeper on {ticker}</h2>
          <p className="text-sm text-slate-600 mt-1">
            Bring your knowledge and intuition - ask anything about the company, financials, risks, or opportunities
          </p>
        </div>
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
                  className="block w-full text-left px-4 py-3 text-sm bg-white dark:bg-slate-800 rounded-lg border-2 transition-all shadow-sm hover:shadow" style={{ color: 'var(--amber-text)', borderColor: 'var(--amber-border)' }}
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
            className={`flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            {/* Show acknowledgment above assistant message if present */}
            {message.role === 'assistant' && message.acknowledgment && (
              <div className="mb-2">
                <div className="text-sm px-4 py-2 rounded-lg border flex items-center gap-2" style={{ backgroundColor: 'var(--amber-bg-light)', borderColor: 'var(--amber-border)', color: 'var(--amber-text-dark)' }}>
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="font-medium">
                    {message.acknowledgment === 'noted' ? 'Constant took note of that' : 'I get your point'}
                  </span>
                </div>
              </div>
            )}
            <div className={`max-w-[85%] ${message.role === 'assistant' ? 'space-y-2' : ''}`}>
              <div
                className={`rounded-2xl px-5 py-3 shadow-md ${
                  message.role === 'user'
                    ? 'text-white' + ' bg-[#C87A23]'
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
                        <svg className="w-3 h-3 mt-0.5 flex-shrink-0" fill="#C87A23" viewBox="0 0 20 20">
                          <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                          <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                        </svg>
                        <a
                          href={source.url.startsWith('http') ? source.url : `https://${source.url}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs hover:underline flex-1" style={{ color: '#C87A23' }}
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

        {/* Acknowledgment display above streaming response */}
        {streaming && acknowledgment && (
          <div className="flex justify-start mb-2">
            <div className="text-sm px-4 py-2 rounded-lg border flex items-center gap-2" style={{ backgroundColor: 'var(--amber-bg-light)', borderColor: 'var(--amber-border)', color: 'var(--amber-text-dark)' }}>
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="font-medium">
                {acknowledgment === 'noted' ? 'Constant took note of that' : 'I get your point'}
              </span>
            </div>
          </div>
        )}

        {streaming && streamingMessage && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-2xl px-5 py-3 bg-white dark:bg-slate-800 border-2 text-slate-800 shadow-md" style={{ borderColor: 'var(--amber-border)' }}>
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
                <p className="text-sm flex items-center gap-2" style={{ color: 'var(--amber-text)' }}>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {searchStatus}
                </p>
              ) : (
                <div className="flex space-x-2">
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--amber-text)' }}></div>
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--amber-text)', animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--amber-text)', animationDelay: '0.2s' }}></div>
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

      {/* Report Edit Notice */}
      {reportEditNotice && (
        <div className="px-6 py-3 bg-blue-50 border-t border-blue-200">
          <p className="text-sm text-blue-700 font-medium text-center flex items-center justify-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            {reportEditNotice.section} has been {reportEditNotice.action}ed - check the Full Report
          </p>
        </div>
      )}

      {/* Belief Extraction Notice */}
      {beliefNotice && (
        <div className="px-6 py-3 border-t" style={{ backgroundColor: 'var(--amber-bg-light)', borderColor: 'var(--amber-border)' }}>
          <p className="text-sm font-medium text-center" style={{ color: 'var(--amber-text)' }}>
            Constant took note of that
          </p>
        </div>
      )}

      {/* Rationale Request - Follow-up prompt for beliefs without reasoning */}
      {rationaleRequest && !streaming && (
        <div className="px-6 py-3 border-t bg-amber-50 border-amber-200">
          <button
            onClick={() => {
              setInput(rationaleRequest.followup_prompt)
              setRationaleRequest(null)
            }}
            className="w-full text-left group"
          >
            <p className="text-sm text-amber-800 flex items-center justify-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="font-medium group-hover:underline">{rationaleRequest.followup_prompt}</span>
              <span className="text-xs text-amber-600 ml-1">(click to respond)</span>
            </p>
          </button>
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
            className="flex-1 px-4 py-3 border-2 border-slate-300 rounded-lg focus:ring-2 focus:ring-[#C87A23] focus:border-[#C87A23] resize-none disabled:bg-slate-100 disabled:cursor-not-allowed transition-all text-sm"
          />
          <button
            type="submit"
            disabled={!input.trim() || streaming}
            className="px-6 py-3 text-white font-semibold rounded-lg shadow-md hover:shadow-lg disabled:bg-slate-400 disabled:cursor-not-allowed transition-all duration-200" style={{ background: 'linear-gradient(to right, #C87A23, #B06A1A)' }}
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
