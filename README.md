# Constant - Your LLM Intern (Financial Analyst)

A full-stack financial analysis platform powered by multi-agent LLM architecture. Analyzes stocks using fundamentals, technicals, bull/bear debate, moat analysis, and SWOT - then lets you chat with the analysis.

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Environment Setup

```bash
# Clone and enter directory
cd george_researcher_js

# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit backend/.env with your API keys:
# OPENROUTER_API_KEY=sk-...     (Required - LLM calls)
# GOOGLE_API_KEY=...            (Recommended - Gemini Search)
# FDS_API_KEY=...               (Recommended - US financial data)
```

### Run the App

```bash
# Option 1: Use the start script
./start.sh

# Option 2: Run manually
# Terminal 1 - Backend
uv run uvicorn backend.main:app --host 0.0.0.0 --port 5001

# Terminal 2 - Frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                          │
│              Port 5173 (Vite Dev Server)                     │
│  StockPicker → AnalysisView → ChatInterface → SessionBrowser │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/SSE
┌────────────────────────▼────────────────────────────────────┐
│                  Backend (FastAPI)                           │
│              Port 5001 (Uvicorn)                             │
│  6 Routers │ Dual Job Queue │ 5 Workers (3 US + 2 Non-US)   │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   US Data          Non-US Data      Shared Resources
   (FDS.ai)         (yfinance)       (OpenRouter LLM)
                    (Alpha Vantage)  (Gemini Search)
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent Analysis** | 7 specialized agents (fundamentals, technicals, bull, bear, moat, SWOT, recommendation) |
| **Bull/Bear Debate** | Two-round debate system for balanced viewpoints |
| **RAG-Enhanced Chat** | Search SEC filings, news, and report content |
| **Belief Tracking** | Extracts and tracks user opinions from chat |
| **PDF Export** | Professional "Goldman Sachs" style reports |
| **Session Persistence** | Resume analyses across browser sessions |
| **Cost Tracking** | Per-message and per-session cost breakdown |
| **Dual Queue System** | Separate US/Non-US workers for rate limit management |
| **Authentication** | Email/password auth with whitelist-based beta access |
| **Data Caching** | TTL-based caching reduces API costs 80-98% |

## API Endpoints

| Category | Endpoint | Description |
|----------|----------|-------------|
| Health | `GET /health` | System status with worker stats |
| Auth | `POST /api/auth/register` | Register (whitelist required) |
| Auth | `POST /api/auth/login` | Login, get JWT token |
| Auth | `GET /api/auth/me` | Get current user |
| Analysis | `POST /api/analysis/start` | Start new analysis |
| Analysis | `GET /api/analysis/{id}/progress` | SSE progress stream |
| Chat | `GET /api/chat/stream` | SSE chat with RAG |
| Sessions | `GET /api/sessions/` | List all sessions |
| Reports | `POST /api/reports/{id}/export/pdf` | Export PDF |

## Project Structure

```
george_researcher_js/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── routers/             # API routes (7 modules incl. auth)
│   ├── core/                # Business logic (15+ modules)
│   │   ├── auth.py          # JWT, bcrypt, whitelist
│   │   └── auth_db.py       # User/token SQLite storage
│   ├── middleware/          # Auth middleware
│   ├── jobs/                # Dual job queue system
│   └── models/              # Pydantic models
├── frontend/
│   └── src/
│       ├── App.jsx          # Main app
│       ├── components/      # React components
│       └── contexts/        # AuthContext for auth state
├── src_george_researcher/
│   ├── analysis_agents.py   # LLM analysis functions
│   ├── orchestrator.py      # Analysis pipeline
│   └── data_fetchers/       # Data sources
└── data/
    ├── sessions/            # Session JSON files
    ├── jobs.db              # Job queue database
    ├── auth.db              # User accounts & tokens
    └── authorized_users.csv # Beta whitelist
```

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE_AND_SCALING.md](./ARCHITECTURE_AND_SCALING.md) | Full architecture, data sources, scaling strategy |
| [USER_STORIES.md](./USER_STORIES.md) | Feature documentation as user stories |
| [CONTEXT.md](./CONTEXT.md) | Development context and recent changes |
| [NEWS_REFACTOR.md](./NEWS_REFACTOR.md) | Future enhancement: smarter news search |

## Current Status

| Phase | Status |
|-------|--------|
| Phase 1-3.5: Core Platform | ✅ Complete |
| Phase 4: Non-US Handling | ✅ Complete |
| Phase 5: Enhanced Features | ✅ Complete (US) |
| Phase 6: Data Caching | ✅ Complete |
| Phase 7: Authentication | ✅ Complete |
| Phase 8: User-Scoped Sessions | ✅ Complete |
| Phase 9: Usage Tracking | ✅ Complete |

**Beta Infrastructure:** Complete. All phases through 9 implemented.

## Tech Stack

- **Backend:** FastAPI, Python 3.13, uvicorn, aiosqlite
- **Frontend:** React 19, Vite, Tailwind CSS v4
- **LLM:** OpenRouter (Claude Sonnet)
- **Search:** Gemini Search Grounding
- **Data:** FinancialDatasets.ai (US), yfinance (Non-US), SEC EDGAR
- **PDF:** WeasyPrint + Jinja2 templates

## License

Private - All rights reserved
