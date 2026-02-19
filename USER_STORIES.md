# Constant - Your Intern: User Stories & Capabilities

This document describes the current capabilities of Constant in user story format. Each story represents a testable feature. If any story breaks during testing, it can be identified and fixed.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Session Management](#session-management)
3. [Stock Analysis](#stock-analysis)
4. [Chat & Conversation](#chat--conversation)
5. [Report Management](#report-management)
6. [Belief Tracking](#belief-tracking)
7. [Cost Tracking](#cost-tracking)
8. [Data Sources](#data-sources)
9. [Export & Download](#export--download)

---

## Authentication

### US-A01: Register with Whitelisted Email
**As a** beta user
**I want to** register for an account with my whitelisted email
**So that** I can access the analysis platform

**Acceptance Criteria:**
- Enter email and password on registration form
- Email must be on the whitelist (`data/authorized_users.csv`)
- If not whitelisted: "This email is not authorized for beta access"
- If whitelisted: Account created, automatically logged in
- Receive JWT access token and refresh token

**API:** `POST /api/auth/register` with `{"email": "...", "password": "...", "display_name": "..."}`

---

### US-A02: Login with Email/Password
**As a** registered user
**I want to** log in with my email and password
**So that** I can access my analysis sessions

**Acceptance Criteria:**
- Enter email and password on login form
- Invalid credentials show: "Invalid email or password"
- Successful login returns JWT tokens
- Access token expires in 30 minutes
- Refresh token stored for automatic renewal

**API:** `POST /api/auth/login` with `{"email": "...", "password": "..."}`

---

### US-A03: Auto Token Refresh
**As a** logged-in user
**I want** my session to stay active automatically
**So that** I don't have to log in frequently

**Acceptance Criteria:**
- Access token refreshes before expiration
- Refresh token valid for 7 days
- Refresh token stored hashed in database
- Old refresh token invalidated after use
- Session persists across browser refreshes

**API:** `POST /api/auth/refresh` with `{"refresh_token": "..."}`

---

### US-A04: View Current User
**As a** logged-in user
**I want to** see my account information
**So that** I know which account I'm using

**Acceptance Criteria:**
- Profile shows: email, display name, account created date
- Accessible from header/menu
- Returns 401 if not authenticated

**API:** `GET /api/auth/me` with `Authorization: Bearer {token}`

---

### US-A05: Logout
**As a** logged-in user
**I want to** log out of my account
**So that** I can secure my session

**Acceptance Criteria:**
- Click logout button
- Refresh token revoked on server
- Access token removed from browser
- Redirected to login page
- Cannot access protected routes after logout

**API:** `POST /api/auth/logout` with `{"refresh_token": "..."}`

---

### US-A06: Protected Routes
**As a** visitor
**I want** analysis features to require authentication
**So that** the platform is secure

**Acceptance Criteria:**
- Unauthenticated users see login/register modal
- Cannot start analysis without logging in
- Cannot access sessions without logging in
- API returns 401 for protected endpoints without token

---

### US-A07: Whitelist Management
**As an** administrator
**I want to** add users to the beta whitelist
**So that** I can control who has access

**Acceptance Criteria:**
- Whitelist stored in `data/authorized_users.csv`
- One email per line, comments start with #
- Changes take effect immediately (no restart needed)
- File reloaded on each registration attempt

**Current Beta Users:**
- matthieu.separt@gmail.com
- rami.sghaier@amundi.com
- samy.debbah@amundi.com

---

## Session Management

### US-001: Create Analysis Session
**As a** logged-in user
**I want to** start a new analysis session by entering a stock ticker
**So that** I can analyze a specific stock

**Acceptance Criteria:**
- Must be authenticated to start analysis
- Enter ticker symbol (e.g., "AAPL") in the stock picker
- System creates a new session with unique ID, owned by current user
- Session is persisted to disk (`data/sessions/{user_id}/{session_id}.json`)
- I can see the session is active in the UI

**API:** `POST /api/analysis/start` with `{"ticker": "AAPL"}` (requires auth token)

---

### US-002: Resume Previous Session
**As a** logged-in user
**I want to** resume a previous analysis session
**So that** I can continue where I left off

**Acceptance Criteria:**
- Click "Resume Analysis" button in header
- See list of **my** past sessions (user-filtered) with ticker, date, message count
- Cannot see other users' sessions
- Click on a session to resume it
- All previous messages and report state are restored
- Can continue chatting from where I left off

**API:** `GET /api/sessions/` then `POST /api/sessions/{session_id}/resume` (requires auth token, user-filtered)

---

### US-003: Delete Session
**As a** logged-in user
**I want to** delete an old analysis session
**So that** I can clean up sessions I no longer need

**Acceptance Criteria:**
- In session browser, click delete button on a session
- Can only delete sessions I own
- Confirm deletion
- Session is removed from list
- Session file is deleted from disk

**API:** `DELETE /api/sessions/{session_id}` (requires auth token, ownership verified)

---

### US-004: Session Persistence
**As a** user
**I want** my session to be automatically saved
**So that** I don't lose my work if I close the browser

**Acceptance Criteria:**
- Session auto-saves after each chat message
- Session auto-saves after analysis completes
- On server restart, all sessions are loaded from disk (user-scoped directories)
- No data loss between server restarts
- Sessions include user_id for ownership tracking

---

### US-005: User Session Isolation
**As a** user
**I want** my sessions to be private
**So that** other users cannot see my analysis work

**Acceptance Criteria:**
- Sessions are stored in user-specific directories: `data/sessions/{user_id}/`
- All session endpoints require authentication
- Session list only shows sessions I own
- Cannot access other users' sessions (returns 404)
- Cannot modify other users' sessions

**Implementation:**
- `SessionManager.get_session_for_user(session_id, user_id)` verifies ownership
- `SessionManager.list_sessions(user_id)` filters by user
- All routers use `Depends(get_current_user)` for auth

---

## Stock Analysis

### US-010: Run Full Analysis
**As a** user
**I want to** run a comprehensive multi-agent analysis on a stock
**So that** I can understand the investment thesis

**Acceptance Criteria:**
- Click "Analyze" button after entering ticker
- See real-time progress updates (14 steps)
- Progress shows: "Validating ticker...", "Running fundamentals...", etc.
- Analysis completes with all sections populated
- See total cost of analysis

**API:** `POST /api/analysis/{session_id}/run` (SSE stream)

**Analysis Agents:**
1. Fundamentals Agent - P/E, P/B, margins, growth
2. Technical Agent - RSI, MACD, SMA, trends
3. Bull Thesis Agent - Bullish arguments
4. Bear Thesis Agent - Bearish arguments
5. Moat Analysis Agent - Competitive advantages
6. SWOT Agent - Strengths, Weaknesses, Opportunities, Threats
7. Recommendation Agent - Final investment recommendation

---

### US-011: Ticker Validation
**As a** user
**I want** invalid tickers to be rejected immediately
**So that** I don't waste time on non-existent stocks

**Acceptance Criteria:**
- Enter invalid ticker (e.g., "XYZABC123")
- System validates with yfinance before analysis
- Error message: "Invalid ticker symbol: XYZABC123"
- No API costs incurred for invalid tickers

---

### US-012: Analysis Progress Streaming
**As a** user
**I want to** see real-time progress during analysis
**So that** I know the system is working and how far along it is

**Acceptance Criteria:**
- Progress bar shows current step (e.g., "Step 5 of 14")
- Status message updates for each agent
- Can see which agent is currently running
- Progress updates stream in real-time (SSE)

**SSE Events:**
```json
{"status": "running", "message": "Analyzing fundamentals...", "step": 3, "total": 14}
{"status": "complete", "message": "Analysis complete!", "sections": 8, "cost_usd": 0.0234}
```

---

### US-013: View Contradictions
**As a** user
**I want to** see where bull and bear cases contradict each other
**So that** I can understand the key debates about this stock

**Acceptance Criteria:**
- After analysis, "Further Research" section shows contradictions
- Each contradiction shows: disputed fact, bull interpretation, bear interpretation
- Contradictions are also available as structured data for UI cards

---

### US-014: View Research Gaps
**As a** user
**I want to** see what questions remain unanswered
**So that** I know what to research further

**Acceptance Criteria:**
- "Further Research" section lists research gaps
- Each gap is a question that needs more investigation
- Gaps are extracted from analysis by LLM

---

## Chat & Conversation

### US-020: Chat with Analyst
**As a** user
**I want to** ask follow-up questions about the analysis
**So that** I can dig deeper into specific topics

**Acceptance Criteria:**
- Type question in chat input
- Response streams word-by-word in real-time
- Response is based on the analysis report context
- Chat history is preserved in session

**API:** `GET /api/chat/stream?session_id={id}&message={text}` (SSE stream)

---

### US-021: Context-Aware Responses
**As a** user
**I want** the chat to remember our conversation
**So that** I can have a coherent multi-turn dialogue

**Acceptance Criteria:**
- Ask "What's the P/E ratio?"
- Follow up with "How does that compare to competitors?"
- System understands "that" refers to P/E ratio
- Last 10 messages are always included in context
- Older messages are summarized if context gets too long

---

### US-022: RAG-Enhanced Answers
**As a** user
**I want** the chat to search for recent news when relevant
**So that** I get up-to-date information

**Acceptance Criteria:**
- Ask "What's the latest news about this company?"
- System searches via Gemini Search Grounding (Google Search)
- Response includes recent news with source citations
- Sources appear below the response with clickable links

**Trigger Keywords:** "news", "recent", "latest", "announced", "earnings", "today"

---

### US-023: SEC Filing Search
**As a** user
**I want** the chat to search SEC filings for specific information
**So that** I can get authoritative financial data

**Acceptance Criteria:**
- Ask "What are the main risk factors from the 10-K?"
- System searches SEC filing chunks via FAISS
- Response includes relevant excerpts from 10-K
- Source shows filing section and date

**Trigger Keywords:** "10-k", "sec", "filing", "revenue", "risk", "financial statement"

---

### US-024: Report RAG Search
**As a** user
**I want** the chat to search the analysis report itself
**So that** answers reference what was already analyzed

**Acceptance Criteria:**
- Ask "What did the moat analysis conclude?"
- System searches report sections for relevant chunks
- Response references specific parts of the analysis
- No external API calls needed for report-only questions

---

### US-025: Search Status Indicator
**As a** user
**I want to** know when the system is searching external sources
**So that** I understand why the response might take longer

**Acceptance Criteria:**
- When RAG search triggers, UI shows "Constant is looking up some new information..."
- Status appears before response starts streaming
- Indicates system is fetching external data

---

## Report Management

### US-030: View Analysis Report
**As a** user
**I want to** view the complete analysis report
**So that** I can read all the findings

**Acceptance Criteria:**
- Report displays in main panel after analysis
- Sections include: Full Report, Fundamentals, Technicals, Bull Case, Bear Case, Moat, SWOT, Recommendation, Sources, Further Research
- Each section is collapsible/expandable
- Report updates in real-time as chat adds insights

**API:** `GET /api/reports/{session_id}`

---

### US-031: Report Sections
**As a** user
**I want** the report organized into clear sections
**So that** I can quickly find specific information

**Report Sections:**
| Section | Description |
|---------|-------------|
| Full Report | Executive summary narrative |
| Fundamentals | Valuation metrics (P/E, P/B, margins) |
| Technicals | Price action, RSI, MACD, trends |
| Bull Case | Bullish investment thesis |
| Bear Case | Bearish thesis and risks |
| Moat Analysis | Competitive advantages |
| SWOT | Strengths, Weaknesses, Opportunities, Threats |
| Recommendation | Final buy/hold/sell recommendation |
| Sources | All citations with links |
| Further Research | Contradictions and research gaps |

---

### US-032: Update Report Section
**As a** user
**I want to** manually edit a report section
**So that** I can correct or enhance the analysis

**Acceptance Criteria:**
- Click edit button on a section
- Edit content in markdown format
- Save changes
- Section version increments
- Changes persist across sessions

**API:** `PUT /api/reports/{session_id}/sections/{section_id}`

---

### US-033: View Report Statistics
**As a** user
**I want to** see statistics about the report
**So that** I understand its scope

**Acceptance Criteria:**
- See total character count
- See number of sections
- See total sources count
- See report version number
- See report age

**API:** `GET /api/reports/{session_id}/stats`

---

## Belief Tracking

### US-040: Extract Analyst Beliefs
**As a** user
**I want** my opinions expressed in chat to be captured
**So that** the report reflects my analysis contributions

**Acceptance Criteria:**
- Type "I think the P/E is too high for this growth rate"
- System extracts this as a belief using Haiku (cheap, fast)
- Belief is categorized (e.g., "valuation_view")
- Belief is routed to appropriate section (e.g., "fundamentals")
- Belief appears in chat with colored badge

**Belief Types:**
| Type | Badge | Color |
|------|-------|-------|
| confirmed_fact | CONFIRMED | Green |
| new_insight | INSIGHT | Purple |
| risk_identified | RISK | Red |
| opportunity | OPPORTUNITY | Amber |
| valuation_view | VALUATION | Blue |
| competitive | COMPETITIVE | Cyan |

---

### US-041: Belief Acknowledgment
**As a** user
**I want** confirmation when my belief is captured
**So that** I know the system understood my input

**Acceptance Criteria:**
- Express a belief without asking a question
- System responds with "understood" acknowledgment
- Express a belief with a follow-up question
- System responds with "noted" acknowledgment + answer

---

### US-042: View All Beliefs
**As a** user
**I want to** see all beliefs captured during the session
**So that** I can review my analytical contributions

**Acceptance Criteria:**
- Access beliefs via session endpoint
- See list of all extracted beliefs
- Each belief shows: content, type, target section, confidence
- Beliefs are stored in belief graph structure

**API:** `GET /api/sessions/{session_id}/beliefs`

---

### US-043: Finalize Session with Beliefs
**As a** user
**I want to** incorporate my beliefs into the report
**So that** the final report reflects my analysis

**Acceptance Criteria:**
- Click "Finalize" button
- System groups beliefs by target section
- LLM rewrites each section to incorporate beliefs
- Report shows "[Analyst Note]" markers where beliefs were added
- Session is marked as finalized

**API:** `POST /api/sessions/{session_id}/finalize`

---

### US-044: Analyst Sources in Report
**As a** user
**I want** my beliefs cited as sources
**So that** the report distinguishes AI analysis from my opinions

**Acceptance Criteria:**
- Beliefs create analyst sources [A1], [A2], etc.
- These appear in Sources section as "Analyst Belief"
- PDF export includes analyst sources with proper formatting

---

## Cost Tracking

### US-050: Track Analysis Cost
**As a** user
**I want to** see how much the analysis cost
**So that** I can manage my API budget

**Acceptance Criteria:**
- After analysis completes, see total cost in USD
- Cost breakdown available in session metadata
- Cost shown in completion message: "Analysis complete! Cost: $0.0234"

---

### US-051: Track Chat Cost
**As a** user
**I want to** see the cumulative cost of chat interactions
**So that** I know how much I'm spending on follow-up questions

**Acceptance Criteria:**
- Each chat response shows incremental cost
- Cumulative chat cost tracked in session
- Cost sent in SSE: `{"cost_usd": 0.0045}`
- Belief extraction cost (Haiku) included in total

---

### US-052: View Total Session Cost
**As a** user
**I want to** see the total cost for the entire session
**So that** I can track my overall spending

**Acceptance Criteria:**
- Session metadata includes: `total_cost_usd`, `chat_cost_usd`
- Total = analysis cost + chat cost
- Available in session resume data

---

## Data Sources

### US-060: Yahoo Finance Data
**As a** user
**I want** stock data from Yahoo Finance
**So that** I get reliable market data

**Data Retrieved:**
- Current price, market cap
- P/E ratio, P/B ratio
- 52-week high/low
- Sector, industry, country
- Business summary
- Analyst recommendations
- Historical price data (1 year)

---

### US-061: SEC 10-K Filing Data
**As a** user
**I want** SEC filing data analyzed
**So that** I get authoritative financial information

**Acceptance Criteria:**
- System fetches most recent 10-K filing
- Filing is chunked and embedded for semantic search
- Risk factors, business description, financials extracted
- Filing date and URL available in sources

---

### US-062: News via Gemini Search
**As a** user
**I want** recent news included in analysis
**So that** I understand current events affecting the stock

**Acceptance Criteria:**
- Gemini Search Grounding fetches recent news
- News articles include title, content, URL
- Sentiment is not pre-calculated (LLM interprets)
- Top 5 results used for context

**Requires:** `GOOGLE_API_KEY` environment variable

---

### US-063: Reddit Sentiment
**As a** user
**I want** Reddit discussions analyzed
**So that** I understand retail investor sentiment

**Acceptance Criteria:**
- System searches Reddit for stock mentions
- Posts from r/wallstreetbets, r/stocks, r/investing
- Shows: mention count, total score, top subreddits
- Individual posts with title, score, comments

---

## Export & Download

### US-070: Export as PDF
**As a** user
**I want to** download the analysis as a PDF
**So that** I can share it or read it offline

**Acceptance Criteria:**
- Click "Download PDF" button
- PDF generates with professional formatting
- Includes: cover page, table of contents, all sections
- Includes disclaimer at the end
- Analyst sources formatted as "[A1] Analyst Belief: ..."
- File named: `{ticker}_analysis_{date}.pdf`

**API:** `POST /api/reports/{session_id}/export/pdf`

---

### US-071: Export as Markdown
**As a** user
**I want to** download the analysis as Markdown
**So that** I can edit it in my own tools

**Acceptance Criteria:**
- Request report with format=markdown
- Full markdown document with headers, sections
- Sources formatted with links
- Can be opened in any text editor

**API:** `GET /api/reports/{session_id}?format=markdown`

---

### US-072: Regenerate Full Report
**As a** user
**I want to** regenerate the narrative report after adding beliefs
**So that** the executive summary reflects my latest insights

**Acceptance Criteria:**
- Click regenerate button
- System regenerates "Full Report" section
- New beliefs are incorporated into narrative
- Cost is tracked for regeneration

**API:** `POST /api/sessions/{session_id}/regenerate-report`

---

## Context Management

### US-080: Automatic Context Compression
**As a** user
**I want** long conversations to be handled gracefully
**So that** the system doesn't crash on token limits

**Acceptance Criteria:**
- Conversations over 50+ messages still work
- Older messages are summarized automatically
- Last 10 messages always kept in full
- Compression is transparent to user
- Response quality maintained

---

### US-081: Context Stats
**As a** user
**I want to** know if my context was compressed
**So that** I understand if older context was lost

**Acceptance Criteria:**
- Each response metadata includes `context_compressed: true/false`
- Token count included: `context_tokens: 3500`
- Available in message metadata

---

## Error Handling

### US-090: Graceful Error Recovery
**As a** user
**I want** errors to be handled gracefully
**So that** I can understand what went wrong

**Acceptance Criteria:**
- Invalid ticker shows clear error message
- API failures show user-friendly error
- Network issues don't crash the app
- Can retry after errors

---

### US-091: Missing API Keys
**As a** user
**I want** clear feedback when API keys are missing
**So that** I can configure the system properly

**Required Environment Variables:**
- `OPENROUTER_API_KEY` - Required for LLM calls
- `GOOGLE_API_KEY` - Optional, enables Gemini Search
- `FDS_API_KEY` - Optional, enables FinancialDatasets.ai for US companies

---

## Performance

### US-100: Streaming Responses
**As a** user
**I want** responses to stream word-by-word
**So that** I see results immediately without waiting

**Acceptance Criteria:**
- Analysis progress streams in real-time
- Chat responses stream word-by-word (~50ms per word)
- No long waits for complete response
- Can read response as it generates

---

### US-101: Parallel Agent Execution
**As a** user
**I want** analysis to run as fast as possible
**So that** I don't wait unnecessarily

**Acceptance Criteria:**
- Multiple agents can run in parallel where possible
- Progress updates accurately reflect parallel execution
- Total analysis time ~30-60 seconds for full analysis

---

## Frontend Features

### US-110: Responsive UI
**As a** user
**I want** the UI to work on different screen sizes
**So that** I can use it on desktop or tablet

**Acceptance Criteria:**
- Layout adapts to screen width
- Chat panel and report panel side-by-side on desktop
- Stacked on smaller screens
- All controls accessible

---

### US-111: Real-time Report Updates
**As a** user
**I want** the report to update in real-time during chat
**So that** I see my beliefs incorporated immediately

**Acceptance Criteria:**
- When beliefs are extracted, report refreshes
- SSE event: `{"event": "report_updated", "beliefs_extracted": 2}`
- No manual refresh needed
- Sources section updates with new citations

---

### US-112: Source Citations in Chat
**As a** user
**I want to** see source links below chat responses
**So that** I can verify information

**Acceptance Criteria:**
- RAG-enhanced responses show source citations
- Each source is clickable link
- Shows source type (news, filing, search)
- Shows date when available

---

## API Health

### US-120: Health Check
**As a** developer
**I want** a health check endpoint
**So that** I can monitor system status

**Acceptance Criteria:**
- `GET /health` returns 200 OK
- Response includes: status, version, uptime_seconds, workers, queues
- Can be used for load balancer health checks

**Response:**
```json
{
  "status": "healthy",
  "version": "2.1.0",
  "uptime_seconds": 3600,
  "workers": {"total_workers": 5, "us_workers": 3, "non_us_workers": 2},
  "queues": {"us": {}, "non_us": {}}
}
```

---

## Summary

**Total User Stories:** 53 (7 authentication + 1 user isolation)

**Core Capabilities:**
- **Authentication** with whitelist-based beta access
- **User Isolation** - sessions scoped to authenticated user
- Multi-agent stock analysis (7 specialized agents)
- Conversational chat with RAG enhancement
- Living document that updates from conversation
- Belief extraction and tracking
- Cost tracking per session
- PDF and Markdown export
- Session persistence and resume (user-scoped)
- Real-time streaming UI
- Data caching (80-98% API cost reduction)

**Tech Stack:**
- Backend: FastAPI, Python 3.13, uvicorn
- Frontend: React 19, Vite, Tailwind CSS v4
- Auth: bcrypt + JWT (python-jose)
- LLM: OpenRouter (Claude Sonnet default)
- Search: Gemini Search Grounding (Google)
- Embeddings: Sentence Transformers + FAISS
- Data: FinancialDatasets.ai (US), yfinance (Non-US), SEC EDGAR, Reddit API
- Job Queue: SQLite-backed dual queue (3 US + 2 Non-US workers)
- Cache: SQLite with TTL-based invalidation
