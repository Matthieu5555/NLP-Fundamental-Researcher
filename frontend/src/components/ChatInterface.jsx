import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { authFetch, API_URL } from '../utils/api'
import { parseSSEStream } from '../hooks/useSSEStream'

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
      const response = await authFetch(
        `${API_URL}/api/chat/stream?session_id=${sessionId}&message=${encodeURIComponent(userMessage)}`
      )

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      let fullResponse = ''
      let localSources = []
      let localAcknowledgment = null

      const commitMessage = () => {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: fullResponse,
          sources: localSources,
          acknowledgment: localAcknowledgment,
        }])
        setStreamingMessage('')
        setStreaming(false)
        setSearchStatus('')
        setCurrentSources([])
        setAcknowledgment(null)
      }

      await parseSSEStream(response, {
        onJSON(eventData) {
          if (eventData.status) {
            setSearchStatus(eventData.status)
            return
          }

          if (eventData.sources) {
            localSources = eventData.sources
            setCurrentSources(eventData.sources)
            return
          }

          if (eventData.event === 'report_updated') {
            setReportUpdateNotice(true)
            if (onReportUpdated) onReportUpdated()
            setTimeout(() => setReportUpdateNotice(false), 5000)
            return
          }

          if (eventData.event === 'report_edited') {
            const sectionName = eventData.section?.replace('_', ' ') || 'report'
            setReportEditNotice({ section: sectionName, action: eventData.action })
            if (onReportUpdated) onReportUpdated()
            setTimeout(() => setReportEditNotice(null), 5000)
            return
          }

          if (eventData.new_beliefs && eventData.new_beliefs.length > 0) {
            setBeliefNotice(eventData.new_beliefs.length)
            if (onNewBeliefs) onNewBeliefs(eventData.new_beliefs)
            setTimeout(() => setBeliefNotice(null), 5000)
            return
          }

          if (eventData.cost_usd !== undefined) {
            setChatCost(eventData.cost_usd)
            if (onCostUpdate) onCostUpdate(eventData.cost_usd)
            return
          }

          if (eventData.acknowledgment) {
            localAcknowledgment = eventData.acknowledgment
            setAcknowledgment(eventData.acknowledgment)
            return
          }

          if (eventData.sources_added && eventData.sources_added.length > 0) {
            if (onSourcesAdded) onSourcesAdded(eventData.sources_added)
            return
          }

          if (eventData.request_rationale) {
            setRationaleRequest(eventData.request_rationale)
            return
          }

          // eventData.text_done and any other sentinel events are intentionally ignored.
        },
        onText(chunk) {
          const text = chunk.replace('<br>', '\n')
          fullResponse += text
          setStreamingMessage(fullResponse)
        },
        onDone: commitMessage,
        onError(err) {
          console.error('Stream processing error:', err)
          setStreaming(false)
          setStreamingMessage('')
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: 'Sorry, there was an error. Please try again.',
          }])
        },
      })

    } catch (err) {
      console.error('Send message error:', err)
      setStreaming(false)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, there was an error. Please try again.'
      }])
    }
  }

  const handleKeyDown = (e) => {
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
      <div className="border-b border-slate-200 px-6 py-5" style={{ background: 'linear-gradient(to right, var(--brand-gradient-from), var(--brand-gradient-to))' }}>
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
                  className="block w-full text-left px-4 py-3 text-sm bg-white dark:bg-slate-800 rounded-lg border-2 transition-all shadow-sm hover:shadow" style={{ color: 'var(--brand-primary)', borderColor: 'var(--brand-border)' }}
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
                <div className="text-sm px-4 py-2 rounded-lg border flex items-center gap-2" style={{ backgroundColor: 'var(--brand-surface)', borderColor: 'var(--brand-border)', color: 'var(--brand-primary-dark)' }}>
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
                    ? 'text-white bg-brand'
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
                        <svg className="w-3 h-3 mt-0.5 flex-shrink-0 text-brand" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                          <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                        </svg>
                        <a
                          href={source.url.startsWith('http') ? source.url : `https://${source.url}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs hover:underline flex-1 text-brand"
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
            <div className="text-sm px-4 py-2 rounded-lg border flex items-center gap-2" style={{ backgroundColor: 'var(--brand-surface)', borderColor: 'var(--brand-border)', color: 'var(--brand-primary-dark)' }}>
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
            <div className="max-w-[85%] rounded-2xl px-5 py-3 bg-white dark:bg-slate-800 border-2 text-slate-800 shadow-md" style={{ borderColor: 'var(--brand-border)' }}>
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
                <p className="text-sm flex items-center gap-2" style={{ color: 'var(--brand-primary)' }}>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {searchStatus}
                </p>
              ) : (
                <div className="flex space-x-2">
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--brand-primary)' }}></div>
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--brand-primary)', animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--brand-primary)', animationDelay: '0.2s' }}></div>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Report Update Notice */}
      {reportUpdateNotice && (
        <div className="px-6 py-3 bg-accent-success-light border-t border-accent-success">
          <p className="text-sm text-accent-success-dark font-medium text-center">
            Report updated with new insights - scroll up to see changes
          </p>
        </div>
      )}

      {/* Report Edit Notice */}
      {reportEditNotice && (
        <div className="px-6 py-3 bg-accent-info-light border-t border-accent-info">
          <p className="text-sm text-accent-info-dark font-medium text-center flex items-center justify-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            {reportEditNotice.section} has been {reportEditNotice.action}ed - check the Full Report
          </p>
        </div>
      )}

      {/* Belief Extraction Notice */}
      {beliefNotice && (
        <div className="px-6 py-3 border-t" style={{ backgroundColor: 'var(--brand-surface)', borderColor: 'var(--brand-border)' }}>
          <p className="text-sm font-medium text-center" style={{ color: 'var(--brand-primary)' }}>
            Constant took note of that
          </p>
        </div>
      )}

      {/* Rationale Request - Follow-up prompt for beliefs without reasoning */}
      {rationaleRequest && !streaming && (
        <div className="px-6 py-3 border-t bg-accent-warning-light border-accent-warning">
          <button
            onClick={() => {
              setInput(rationaleRequest.followup_prompt)
              setRationaleRequest(null)
            }}
            className="w-full text-left group"
          >
            <p className="text-sm text-accent-warning-dark flex items-center justify-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="font-medium group-hover:underline">{rationaleRequest.followup_prompt}</span>
              <span className="text-xs text-accent-warning ml-1">(click to respond)</span>
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
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about the analysis..."
            disabled={streaming}
            rows={2}
            className="flex-1 px-4 py-3 border-2 border-slate-300 rounded-lg focus:ring-2 focus:ring-brand focus:border-brand resize-none disabled:bg-slate-100 disabled:cursor-not-allowed transition-all text-sm"
          />
          <button
            type="submit"
            disabled={!input.trim() || streaming}
            className="px-6 py-3 text-white font-semibold rounded-lg shadow-md hover:shadow-lg disabled:bg-slate-400 disabled:cursor-not-allowed transition-all duration-200 bg-brand-gradient"
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
