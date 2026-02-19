# Development Context

> Quick reference for developers picking up this project. For full architecture details, see [ARCHITECTURE_AND_SCALING.md](./ARCHITECTURE_AND_SCALING.md).

## Current State (December 2024)

**Status:** Multi-user beta platform - all core infrastructure complete
**Target:** Production readiness and advanced features

### What's Working
- Full stock analysis pipeline (7 agents)
- SSE streaming for progress and chat
- PDF export with professional formatting
- Session persistence (JSON files)
- Dual job queue (3 US + 2 Non-US workers)
- Belief extraction from chat
- Cost tracking per session
- **Non-US company handling with data availability banner** (Phase 4 complete)
- **Insider trades + analyst estimates for US companies** (Phase 5 complete for US)
- **Data caching with TTL-based SQLite cache** (Phase 6 complete)
- **Authentication with whitelist-based registration** (Phase 7 complete)
- **User-scoped sessions with ownership verification** (Phase 8 complete)
- **Usage tracking per user with cost attribution** (Phase 9 complete)

### Notes
- Phase 5 features (insider trades, analyst estimates) are US-only by design
- Non-US companies use yfinance + Gemini Search with graceful degradation

### Beta Users (Pre-registered)
- matthieu.separt@gmail.com (password: separt.matthieu)
- rami.sghaier@amundi.com (password: sghaier.rami)
- samy.debbah@amundi.com (password: debbah.samy)

---

## Latest Migration: Flask to FastAPI (2025-12-09)

### What Was Done

The backend was migrated from Flask to FastAPI with a dual job queue system for browser-independent analysis.

### New Architecture

```
backend/
├── main.py                    # FastAPI app entry point with lifespan
├── routers/                   # FastAPI routers (replaces Flask blueprints)
│   ├── analysis.py            # Job queue integration, SSE progress
│   ├── chat.py                # SSE streaming, RAG, belief extraction
│   ├── companies.py           # Company classification (US/Non-US)
│   ├── chart.py               # Technical chart data
│   ├── sessions.py            # Session management
│   └── reports.py             # PDF export, section management
├── models/                    # Pydantic request/response models
│   ├── requests.py
│   └── responses.py
└── jobs/                      # Dual job queue system
    ├── models.py              # Job, JobStatus, QueueType
    ├── queue.py               # DualJobQueue with SQLite persistence
    └── worker.py              # Worker, WorkerPool, RateLimiter
```

### Key Changes

1. **Flask → FastAPI**: All Flask blueprints migrated to FastAPI routers
2. **Dual Job Queue**: Browser-independent analysis with SQLite persistence
   - US Queue: 3 workers (FinancialDatasets.ai, 1000 req/min)
   - Non-US Queue: 2 workers (Alpha Vantage, 5 req/min)
3. **Async Support**: Full async/await patterns
4. **Dependencies Updated**: Removed flask/flask-cors, added fastapi/uvicorn/pydantic/aiosqlite

### Files Archived

Deprecated Flask files moved to `archive/flask_deprecated/`:
- `backend/app.py` - Old Flask entry point
- `backend/api/` - Old Flask blueprints (analysis.py, chat.py, companies.py, chart.py, reports.py, sessions.py)

### Starting the Server

```bash
# Using start script
./start.sh

# Or directly
uv run uvicorn backend.main:app --host 0.0.0.0 --port 5001
```

### API Endpoints (40 routes)

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| Health | `/` | GET | API status |
| Health | `/health` | GET | Health with worker/queue stats |
| Analysis | `/api/analysis/start` | POST | Start analysis (enqueue job) |
| Analysis | `/api/analysis/{id}/status` | GET | Get job status |
| Analysis | `/api/analysis/{id}/progress` | GET | SSE progress stream |
| Cache | `/api/cache/stats` | GET | Cache statistics and cost savings |
| Cache | `/api/cache/invalidate` | POST | Invalidate cache by ticker/type |
| Cache | `/api/cache/cleanup` | POST | Remove expired entries |
| Cache | `/api/cache/health` | GET | Cache configuration |
| Chat | `/api/chat/stream` | GET | SSE chat stream |
| Chat | `/api/chat/{id}/history` | GET | Conversation history |
| Sessions | `/api/sessions/` | GET | List sessions |
| Sessions | `/api/sessions/{id}/resume` | POST | Resume session |
| Reports | `/api/reports/{id}` | GET | Get report |
| Reports | `/api/reports/{id}/export/pdf` | POST | Export PDF |
| Companies | `/api/companies/classify/{ticker}` | GET | Classify US/Non-US |
| Chart | `/api/chart/{ticker}/data` | GET | Chart data |

### Verified Working

```
GET  /health          → Workers: 5 (3 US, 2 Non-US)
GET  /api/sessions/   → 24 sessions loaded
GET  /api/companies/classify/AAPL → {"is_us": true, "region": "us"}
```

---

## Previous Work

### Contradiction Detection Enhancement
- Added LLM-based semantic contradiction detection (`backend/core/contradiction_detector.py`)
- Falls back to heuristic if LLM fails

### Module Naming Fix
- Renamed `src_george_researcher/analysis.py` → `analysis_agents.py`
- Fixed conflict with `analysis/` package directory

### Context Limits Increased
- FUNDAMENTALS_CONTEXT_LIMIT: 600 → 1500
- COUNTER_ARGUMENT_LIMIT: 600 → 1500
- SWOT_CONTEXT_LIMIT: 500 → 1000
- TECHNICALS_CONTEXT_LIMIT: 400 → 1000
- MOAT_CONTEXT_LIMIT: 400 → 1000

---

## Implementation History

See **ARCHITECTURE_AND_SCALING.md Section 13** for full gap analysis.

### Phase 4: Non-US Handling ✅ COMPLETE (2024-12-25)

Graceful degradation for non-US companies with clear data availability communication.

**Files Created:**
- `src_george_researcher/data_fetchers/limitations.py` - Data availability documentation
- `src_george_researcher/analysis/non_us/__init__.py` - Non-US analysis module
- `src_george_researcher/analysis/non_us/orchestrator.py` - Non-US orchestrator wrapper
- `frontend/src/components/DataAvailabilityBanner.jsx` - Prominent warning banner

**Files Modified:**
- `src_george_researcher/analysis/__init__.py` - Added non_us exports
- `frontend/src/components/AnalysisView.jsx` - Integrated DataAvailabilityBanner

**Features:**
- DataAvailabilityBanner shows unavailable features for non-US companies
- Disabled tabs with "(US only)" labels
- Dual queue routing (US vs Non-US workers)
- CompanyClassification with DataAvailability dataclass

### Phase 5: Enhanced Features ✅ COMPLETE (2024-12-25)

Insider trades and analyst estimates fully integrated for US companies.

**Implementation:**
- `src_george_researcher/data_fetchers/us/financial_datasets_client.py` - Fetching methods
- `src_george_researcher/analysis/us/orchestrator.py` - Analysis integration
- Insider analysis displayed in reports
- Analyst estimates in fundamentals section

**Note:** These features are US-only by design (FinancialDatasets.ai coverage).

### Phase 6: Data Caching ✅ COMPLETE (2024-12-24)

TTL-based SQLite caching implemented to reduce API costs 80-98%.

**Files Created:**
- `src_george_researcher/data_fetchers/cache.py` - Core cache with `DataCache` class and `@cached` decorator
- `backend/routers/cache.py` - Cache stats, invalidation, and cleanup endpoints

**Files Modified:**
- `src_george_researcher/data_fetchers/us/financial_datasets_client.py` - 6 functions cached
- `src_george_researcher/data_fetchers/stock_data.py` - 3 yfinance functions cached
- `src_george_researcher/data_fetchers/gemini_search.py` - Gemini search cached

**TTL Configuration:**
| Data Type | TTL | Cost/Request |
|-----------|-----|--------------|
| gemini_search | 2h | $0.035 |
| fds_prices | 24h | $0.01 |
| fds_financials | 7d | $0.02 |
| yfinance_* | 24h | Free |

### Phase 7: Authentication ✅ COMPLETE (2024-12-25)

Email/password authentication with whitelist-based registration for beta access control.

**Files Created:**
- `backend/core/auth.py` - Auth logic, JWT, bcrypt hashing, whitelist checking
- `backend/core/auth_db.py` - SQLite user/token storage
- `backend/routers/auth.py` - Login, register, refresh, logout endpoints
- `backend/middleware/auth_middleware.py` - JWT validation
- `data/authorized_users.csv` - Beta user whitelist
- `frontend/src/components/LoginForm.jsx` - Login UI
- `frontend/src/components/RegisterForm.jsx` - Registration UI
- `frontend/src/components/AuthModal.jsx` - Auth modal wrapper
- `frontend/src/contexts/AuthContext.jsx` - Auth state management

**Features:**
- Whitelist-based registration (only authorized emails can register)
- bcrypt password hashing (12 rounds)
- JWT access tokens (30 min expiry)
- Refresh tokens (7 day expiry, stored hashed in DB)
- Constant-time password comparison (timing attack protection)

### Phase 8: User-Scoped Sessions ✅ COMPLETE (2024-12-25)

Sessions are now isolated per user with ownership verification on all endpoints.

**Files Modified:**
- `backend/core/session.py` - Added user_id to AnalysisSession, user-scoped storage
- `backend/routers/sessions.py` - All endpoints require auth, filter by user
- `backend/routers/analysis.py` - Creates sessions with user_id, verifies ownership
- `backend/routers/chat.py` - Verifies session ownership before chat
- `backend/routers/reports.py` - Verifies session ownership for all operations
- `frontend/src/components/SessionBrowser.jsx` - Uses authenticated API client

**Storage Structure:**
```
data/sessions/
├── {user_id}/                    # User-scoped directory
│   ├── {session_id}.json         # Session file with user_id field
│   └── ...
└── (legacy sessions migrated)
```

**Key Features:**
- Sessions stored in `data/sessions/{user_id}/{session_id}.json`
- All API endpoints require authentication
- Users can only see/access their own sessions
- Ownership verified on every session operation
- Built-in migration helpers for legacy sessions

**Migration:**
- All 37 existing sessions migrated to matthieu.separt@gmail.com
- `SessionManager.migrate_session_to_user()` for individual migration
- `SessionManager.migrate_all_legacy_sessions_to_user()` for bulk migration

### Phase 9: Usage Tracking ✅ COMPLETE (2024-12-25)

Per-user usage tracking with cost attribution.

**Files Created:**
- `backend/core/usage_db.py` - UsageDB class with SQLite storage
- `backend/middleware/usage_tracker.py` - Track request helper and UsageTracker context manager
- `backend/routers/usage.py` - Usage API endpoints
- `frontend/src/components/UsageStats.jsx` - Usage display modal

**Files Modified:**
- `backend/routers/chat.py` - Added usage tracking to /stream and /message
- `backend/routers/analysis.py` - Added usage tracking to /start
- `backend/main.py` - Registered usage router and database
- `frontend/src/App.jsx` - Integrated UsageStats component

**API Endpoints:**
- `GET /api/usage/me` - Recent usage records
- `GET /api/usage/summary` - Aggregated summary
- `GET /api/usage/daily` - Daily breakdown
- `GET /api/usage/costs` - Cost by category
- `GET /api/usage/stats` - Quick stats (current month + all time)

**Features:**
- Tracks all API requests with cost, tokens, ticker, session
- Per-user SQLite storage (`data/usage.db`)
- Frontend modal showing usage stats (click user name)
- Daily/monthly breakdowns
- Top tickers display
