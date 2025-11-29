# George Financial Analyst - Architecture Document

## Project Vision

Transform George from a multi-page Streamlit app into a **conversational financial research platform** where users collaborate with an AI agent to build customized investment research reports through natural dialogue.

### Key Workflow
1. User selects a stock ticker
2. Initial AI analysis runs (fundamental, technical, sentiment, bull/bear cases)
3. User reads analysis and asks follow-up questions via chat interface
4. AI updates its "beliefs" about the company based on conversation
5. Report dynamically updates as new insights emerge
6. User downloads final PDF report at end of session

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND (SPA)                         │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────────┐   │
│  │ Stock Picker │  │ Analysis View │  │  Chat Interface    │   │
│  │   • Search   │  │  • Initial    │  │  • Streaming msgs  │   │
│  │   • Recent   │  │    Report     │  │  • User questions  │   │
│  └──────────────┘  │  • Live       │  │  • Source citations│   │
│                     │    Updates    │  │  • Belief updates  │   │
│                     └───────────────┘  └────────────────────┘   │
│                                                                  │
│                     WebSocket / Server-Sent Events               │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ↕
┌─────────────────────────────────────────────────────────────────┐
│              FLASK / FASTAPI BACKEND (Python)                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Conversation Manager                           │ │
│  │  • Session management (one per stock analysis)             │ │
│  │  • Routes queries to appropriate handlers                  │ │
│  │  • Maintains conversation history                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  RAG Engine │  │ Belief Graph │  │   Report Builder     │  │
│  │             │  │              │  │                      │  │
│  │ • FAISS     │  │ • NetworkX   │  │ • Section Manager    │  │
│  │ • SEC docs  │  │ • User       │  │ • Markdown Gen       │  │
│  │ • News      │  │   beliefs    │  │ • PDF Export         │  │
│  │ • Semantic  │  │ • Facts      │  │ • Live Updates       │  │
│  │   search    │  │ • Timestamps │  │                      │  │
│  └─────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              LLM Orchestrator                               │ │
│  │  • OpenRouter API client                                   │ │
│  │  • Multi-agent dispatch (bull/bear/fundamental/etc)        │ │
│  │  • Streaming response handling                             │ │
│  │  • Context window management                               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Data Fetchers (existing code)                  │ │
│  │  • yfinance (stock fundamentals, technicals)               │ │
│  │  • Alpha Vantage / EODHD (news sentiment)                  │ │
│  │  • Reddit API (retail sentiment)                           │ │
│  │  • Tavily (web search)                                     │ │
│  │  • SEC EDGAR (10-K filings)                                │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Frontend
- **React 18+** with Vite (fast, modern build tool)
- **TailwindCSS** for styling (consistent with reference repos)
- **WebSocket or SSE** for real-time streaming from LLM
- **React Context API** for state management (conversation history, report state)
- **Axios** for HTTP requests
- **Markdown renderer** (react-markdown) for displaying analysis

### Backend
- **Flask** (initially) or **FastAPI** (if async becomes critical)
  - Flask pros: Simpler, matches reference repos, easy to migrate from Streamlit
  - FastAPI pros: Better async support, automatic API docs, faster performance
- **Flask-CORS** for cross-origin requests
- **Flask-SocketIO** or **SSE** for streaming responses

### Data & Storage
- **FAISS** (existing) - Vector store for SEC filings and conversation chunks
- **NetworkX** - In-memory knowledge graph for belief tracking
  - Nodes: Entities (ticker, metrics, user beliefs)
  - Edges: Relationships (has_PE_ratio, user_believes, contradicts)
- **SQLite** (optional) - Session persistence if needed later

### LLM Integration
- **OpenRouter API** (existing) - Keep current setup
- **Streaming support** - Token-by-token response to frontend

### Report Generation
- **Markdown** - In-memory document builder
- **Pandoc or WeasyPrint** - PDF conversion (keep existing fpdf2 or upgrade)

---

## Core Components Deep Dive

### 1. Conversation Manager

**Responsibilities:**
- Create new analysis session when user selects stock
- Store conversation history (user messages + AI responses)
- Track active session state (stock ticker, analysis stage, user beliefs)
- Manage context window (summarize old turns when approaching token limit)

**Data Structure:**
```python
class AnalysisSession:
    session_id: str
    ticker: str
    created_at: datetime
    conversation_history: List[Message]
    belief_graph: BeliefGraph
    report_state: ReportState
    metadata: dict  # user preferences, analysis options
```

---

### 2. Belief Graph System

**Core Concept:** Track user beliefs and factual claims as they evolve during conversation.

**Graph Schema:**
```
Nodes:
- Entity(id, type, name)  # e.g., (AAPL, stock), (PE_ratio, metric)
- Belief(id, content, confidence, timestamp, source)
- Fact(id, content, source, verified_at)

Edges:
- (Stock) -[HAS_METRIC]-> (Metric)
- (User) -[BELIEVES]-> (Belief)
- (Belief) -[SUPPORTS/CONTRADICTS]-> (Belief)
- (Fact) -[CITED_BY]-> (Source)
```

**Operations:**
```python
class BeliefGraph:
    def add_belief(self, content: str, confidence: float, timestamp: datetime)
    def update_belief(self, belief_id: str, new_content: str)
    def find_contradictions(self, new_belief: Belief) -> List[Belief]
    def get_current_stance(self, topic: str) -> Belief
    def merge_beliefs(self, old: Belief, new: Belief) -> Belief
```

**When to Update:**
1. User explicitly states opinion: "I think AAPL is overvalued"
2. User agrees with AI insight: "You're right about the weak margins"
3. User asks for calculation that reveals preference: "Can you compute ROE?" → implies cares about profitability
4. User changes mind: Detect via contradiction analysis

**Conflict Resolution:**
- Timestamp priority: Newer beliefs override older
- Explicit user confirmation: "Should I update the report to reflect this?"
- Confidence decay: Lower confidence of old beliefs when contradicted

---

### 3. RAG Engine

**Two-Tier Retrieval:**

**Tier 1: Conversation Memory (recent context)**
- Last N conversation turns (N=10 for MVP)
- Embedded and stored in FAISS
- Retrieved for context continuity

**Tier 2: Knowledge Base (deep search)**
- SEC 10-K filings (existing implementation)
- News articles
- Reddit discussions
- Web search results
- Embedded and chunked in FAISS

**Retrieval Flow:**
```python
def retrieve_context(user_query: str, session: AnalysisSession):
    # 1. Get relevant conversation turns
    conv_context = faiss_conv.search(user_query, k=5)

    # 2. Get relevant knowledge chunks
    knowledge = faiss_knowledge.search(user_query, k=10)

    # 3. Query belief graph for relevant user stances
    beliefs = session.belief_graph.search_beliefs(user_query)

    # 4. Combine and rank by relevance
    return {
        "conversation": conv_context,
        "knowledge": knowledge,
        "beliefs": beliefs
    }
```

---

### 4. Report Builder

**Dynamic Report Structure:**
```python
class ReportState:
    sections: Dict[str, Section]  # e.g., {"executive_summary": Section(...)}
    metadata: dict  # ticker, date, user name, etc.
    version: int  # increment on each update

class Section:
    title: str
    content: str  # markdown
    sources: List[str]  # citations
    last_updated: datetime
    confidence: float  # how confident AI is in this section
```

**Update Strategies:**

**Strategy A: Versioned Sections (MVP)**
- Each conversation turn can append or replace a section
- Keep full history for rollback
- Regenerate markdown/PDF on-demand

**Strategy B: Streaming Diffs (Future)**
- LLM generates JSON patch operations
- Frontend applies diffs in real-time
- More complex but feels more "live"

**Section Routing Logic:**
```python
def route_insight_to_section(insight: str, current_sections: List[str]) -> str:
    """Use LLM to decide where new insight belongs"""
    prompt = f"""
    Current report sections: {current_sections}
    New insight: {insight}

    Where should this insight go?
    Options: {current_sections} OR create_new_section
    """
    return llm.classify(prompt)
```

---

### 5. LLM Orchestrator

**Agent Types (from existing code):**
1. Fundamental Analysis Agent
2. Technical Analysis Agent
3. Bull Case Agent
4. Bear Case Agent
5. Moat Analysis Agent
6. SWOT Agent
7. Synthesis Agent
8. **NEW: Conversational Agent** (handles user Q&A)

**Context Management:**
```python
def build_llm_context(user_query: str, session: AnalysisSession):
    # 1. System prompt (role definition)
    system = get_agent_prompt("conversational")

    # 2. Retrieved context
    context = retrieve_context(user_query, session)

    # 3. Current beliefs
    beliefs = session.belief_graph.to_markdown()

    # 4. Recent conversation (last 5 turns)
    history = session.conversation_history[-5:]

    # 5. Current report state (summary)
    report_summary = session.report_state.summarize()

    return {
        "system": system,
        "context": context,
        "beliefs": beliefs,
        "history": history,
        "report": report_summary
    }
```

**Streaming Response:**
```python
def stream_response(query: str, session: AnalysisSession):
    context = build_llm_context(query, session)

    for token in openrouter_client.stream(context):
        yield token  # Send to frontend via SSE/WebSocket

    # After streaming completes, update belief graph
    extract_and_update_beliefs(response, session)
```

---

## API Design

### REST Endpoints

```
POST /api/analysis/start
Body: { ticker: "AAPL" }
Response: { session_id: "uuid", status: "initializing" }

GET /api/analysis/{session_id}/status
Response: { status: "ready", report_preview: {...} }

GET /api/analysis/{session_id}/report
Response: { markdown: "...", pdf_url: "..." }

POST /api/chat
Body: { session_id: "uuid", message: "Can you compute ROE?" }
Response: SSE stream of tokens

GET /api/beliefs/{session_id}
Response: { beliefs: [...], graph_visualization: {...} }

POST /api/report/export
Body: { session_id: "uuid", format: "pdf" }
Response: { download_url: "..." }
```

### WebSocket / SSE Events

```
# Server → Client
event: token         # Streaming LLM response
event: belief_update # New belief added to graph
event: report_update # Section modified
event: analysis_complete # Initial analysis done

# Client → Server
send_message         # User chat message
update_preference    # User toggles analysis options
export_report        # Request PDF download
```

---

## Data Flow Examples

### Example 1: Initial Analysis

```
1. User enters "AAPL" → Frontend → POST /api/analysis/start
2. Backend creates AnalysisSession
3. Runs existing multi-agent pipeline:
   - Fetch stock data (yfinance)
   - Fetch sentiment (news, Reddit)
   - Run 7 analysis agents
4. Streams progress to frontend via SSE
5. Builds initial report sections
6. Frontend displays tabbed analysis view
```

### Example 2: Conversational Update

```
1. User asks: "Can you compute the return on equity?"
2. Frontend → POST /api/chat with message
3. Backend:
   a. Retrieves context (conversation history, stock data, beliefs)
   b. LLM classifies intent: "computation_request"
   c. Executes calculation: ROE = Net Income / Shareholder Equity
   d. Streams response: "Based on latest 10-K, ROE is 14.2%..."
   e. Detects implicit belief: user cares about profitability metrics
   f. Updates belief graph: add_belief("user_cares_about_profitability")
   g. Suggests: "Should I add a profitability analysis section to your report?"
4. Frontend displays streamed response + confirmation prompt
5. User confirms → Backend adds new section to report
```

### Example 3: Belief Contradiction

```
1. Earlier conversation: User said "AAPL looks undervalued"
   → BeliefGraph stores: (user, BELIEVES, "AAPL undervalued", confidence=0.7)

2. User asks: "What's the PEG ratio?"
3. LLM responds: "PEG is 3.2, suggesting overvaluation compared to growth"
4. User says: "Hmm, that's concerning"
5. Backend detects contradiction:
   - find_contradictions("AAPL overvalued") → finds prior belief
6. Backend prompts: "Earlier you thought AAPL was undervalued. Based on the
   PEG ratio, should I update your thesis to 'overvalued' or 'fairly valued'?"
7. User selects "fairly valued"
8. BeliefGraph updates: merge_beliefs(old, new) → "AAPL fairly valued" (confidence=0.8)
9. Report regenerates executive summary with updated stance
```

---

## Migration Strategy from Current Streamlit App

### Phase 1: Backend API (Weeks 1-2)
- [ ] Extract existing analysis code into API endpoints
- [ ] Create Flask app with /api/analysis/start endpoint
- [ ] Implement session management
- [ ] Add SSE/WebSocket for streaming
- [ ] Test API with Postman/curl

### Phase 2: Frontend Foundation (Weeks 2-3)
- [ ] Bootstrap React app with Vite
- [ ] Create stock picker component
- [ ] Implement WebSocket/SSE client
- [ ] Build chat interface with streaming support
- [ ] Display initial analysis results

### Phase 3: Belief System (Weeks 3-4)
- [ ] Implement NetworkX belief graph
- [ ] Add belief extraction from conversation
- [ ] Create contradiction detection
- [ ] Build confirmation prompts in UI
- [ ] Visualize belief graph (optional)

### Phase 4: Dynamic Reports (Weeks 4-5)
- [ ] Implement report state management
- [ ] Add section routing logic
- [ ] Create markdown → PDF pipeline
- [ ] Add live report updates in UI
- [ ] Implement download functionality

### Phase 5: RAG Integration (Weeks 5-6)
- [ ] Migrate FAISS embeddings to backend
- [ ] Add conversation memory to vector store
- [ ] Implement two-tier retrieval
- [ ] Optimize context window management
- [ ] Add source citations to responses

### Phase 6: Polish & Deploy (Weeks 6-7)
- [ ] Error handling and edge cases
- [ ] Performance optimization
- [ ] Add loading states and UX polish
- [ ] Write deployment docs
- [ ] Deploy to production (Vercel + Railway/Render)

---

## Technical Challenges & Solutions

### Challenge 1: Context Window Management
**Problem:** Long conversations + large SEC filings exceed token limits

**Solutions:**
- Summarize old conversation turns (keep last 10 raw, summarize older)
- Use sliding window for RAG retrieval
- Implement "memory consolidation" (LLM summarizes key insights periodically)
- Cache expensive computations (financial ratios, embeddings)

### Challenge 2: Belief Update UX
**Problem:** User doesn't want to manually approve every belief update

**Solutions:**
- Confidence thresholds: Auto-update if confidence > 0.9, else ask
- Batch updates: Show summary of changes after conversation ends
- Undo functionality: "Revert last 3 updates"
- Explicit mode toggle: "Auto-update report" vs "Ask me first"

### Challenge 3: Report Structure Drift
**Problem:** Unstructured conversation leads to chaotic report sections

**Solutions:**
- Enforce max sections limit (e.g., 10 sections max)
- Use section templates (Executive Summary, Financials, Risks, etc.)
- LLM suggests merging related sections periodically
- User can manually reorganize sections in UI

### Challenge 4: Real-time Performance
**Problem:** LLM responses + embeddings + graph updates = slow

**Solutions:**
- Stream tokens immediately (don't wait for full response)
- Run belief extraction async (after response completes)
- Use background jobs for PDF generation
- Cache embeddings for common queries
- Optimize FAISS index (use IVF for large datasets)

---

## Security & Privacy Considerations

1. **API Keys:** Store in environment variables, never expose to frontend
2. **Session Isolation:** Each session isolated, no cross-user data leakage
3. **Input Validation:** Sanitize user queries to prevent injection attacks
4. **Rate Limiting:** Prevent API abuse (max queries per session)
5. **Data Retention:** Clear old sessions after 7 days (GDPR compliance)
6. **Disclaimer:** Prominent "Not financial advice" warnings

---

## Success Metrics

### MVP Success Criteria:
- [ ] User can analyze a stock via initial multi-agent run
- [ ] User can ask 10+ follow-up questions via chat
- [ ] Report updates with at least 3 new insights from conversation
- [ ] User can download PDF with conversation-enhanced analysis
- [ ] Belief graph tracks at least 5 user preferences/opinions
- [ ] No crashes during 30-minute analysis session

### Future Enhancements:
- Multi-stock comparison mode
- Collaborative sessions (multiple users analyzing same stock)
- Historical session replay ("Show me my AAPL analysis from last month")
- Export to Google Docs / Notion
- Voice input/output (speech-to-text for queries)

---

## Reference Implementations

### Cloned Repositories (in `reference_repos/`):
1. **Streaming-AI-Chatbot-with-Flask-and-React/**
   - Shows Flask SSE streaming setup
   - React chat interface with message history
   - Clean separation of frontend/backend

2. **fullstack-rag/**
   - LangChain + Flask + React architecture
   - Vector store integration patterns
   - RAG retrieval flow

3. **bedrock-rag/**
   - AWS Bedrock integration (may adapt prompts)
   - FAISS usage examples
   - PDF processing pipeline

### Key Learnings from References:
- Use `Flask-CORS` for dev environment
- SSE is simpler than WebSocket for one-way streaming
- React `useEffect` + `EventSource` for SSE consumption
- Store conversation state in React Context
- Use `yield` in Flask for streaming responses

---

## File Structure (Proposed)

```
george_researcher/
├── backend/
│   ├── app.py                    # Flask application entry point
│   ├── api/
│   │   ├── analysis.py           # Analysis endpoints
│   │   ├── chat.py               # Chat endpoints
│   │   └── reports.py            # Report export endpoints
│   ├── core/
│   │   ├── session.py            # Session management
│   │   ├── belief_graph.py       # Belief tracking system
│   │   ├── rag_engine.py         # RAG retrieval logic
│   │   └── report_builder.py    # Dynamic report generation
│   ├── agents/                   # LLM agents (from existing code)
│   │   ├── orchestrator.py
│   │   ├── analysis.py
│   │   └── prompts/
│   ├── data_fetchers/            # Keep existing code
│   └── utils/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── StockPicker.jsx
│   │   │   ├── AnalysisView.jsx
│   │   │   ├── ChatInterface.jsx
│   │   │   ├── ReportPreview.jsx
│   │   │   └── BeliefGraph.jsx
│   │   ├── contexts/
│   │   │   ├── SessionContext.jsx
│   │   │   └── ReportContext.jsx
│   │   ├── services/
│   │   │   ├── api.js             # Axios client
│   │   │   └── sse.js             # SSE handler
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── reference_repos/              # Cloned examples (gitignored)
├── docs/
│   ├── ARCHITECTURE.md           # This file
│   └── API.md                    # API documentation
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Next Steps

1. ✅ Document architecture (this file)
2. Review reference repos for implementation patterns
3. Set up Flask backend skeleton
4. Create React frontend with Vite
5. Implement first API endpoint: `/api/analysis/start`
6. Build chat streaming (Flask SSE + React EventSource)
7. Iterate on belief graph prototype
8. Connect dynamic report updates

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-11-29 | Use Flask over FastAPI for MVP | Simpler, matches reference repos, team familiarity |
| 2025-11-29 | NetworkX for belief graph (not Neo4j) | In-memory, zero setup, sufficient for MVP |
| 2025-11-29 | SSE over WebSocket | One-way streaming is simpler, sufficient for chat |
| 2025-11-29 | Versioned sections over streaming diffs | Easier state management for MVP |
| 2025-11-29 | Keep OpenRouter API | Already integrated, supports streaming |

---

*This document will be updated as architecture evolves.*
