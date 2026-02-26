# George - AI Equity Research (Financial Analyst)

A full-stack financial analysis platform powered by multi-agent LLM architecture. Analyzes stocks using fundamentals, technicals, bull/bear debate, moat analysis, and SWOT, then lets you chat with the analysis. Private, all rights reserved.


## Quick Start

Prerequisites: Python 3.13+, Node.js 18+, uv.

```bash
cp backend/.env.example backend/.env   # then fill in API keys
cp frontend/.env.example frontend/.env
./start.sh                              # or run backend/frontend separately
```

Backend runs on port 5001, frontend on 5173. Required env vars:

```
OPENROUTER_API_KEY=...                  # Required for all LLM calls
OPENROUTER_MODEL=anthropic/claude-sonnet-4
GOOGLE_API_KEY=...                      # Gemini Search grounding
FDS_API_KEY=...                         # US financial data (FinancialDatasets.ai)
ALPHA_VANTAGE_API_KEY=...               # Non-US financial data
JWT_SECRET=...                          # Required in production
```

Run tests with `uv run python -m pytest tests/ -v`. Check code quality with `uv run ruff check backend/ src_george_researcher/` and `uv run pylint backend/ src_george_researcher/ --score=y`. Measure complexity with `uv run radon cc backend/ src_george_researcher/ -s -a --min C`.


## Architecture

The system is a React frontend talking to a FastAPI backend over HTTP and SSE. The backend runs a dual job queue with five workers (three US, two non-US) that process analyses in the background, persisted to SQLite so they survive browser closes and server restarts.

Data sources are split by region. US companies use FinancialDatasets.ai, which covers 30K+ tickers at 1000 req/min with detailed financials, insider trades, and analyst estimates. Non-US companies fall back to yfinance and Alpha Vantage, which is rate-limited to 5 req/min and 500/day. Both paths share OpenRouter for LLM calls (Claude Sonnet) and Gemini Search Grounding for real-time news. EODHD and direct SEC EDGAR access were removed in favor of FDS.

The queue separation means US analyses (~20/min throughput) are never blocked by the non-US rate limit bottleneck (~3-5/min). Each queue has its own token bucket rate limiter. LLM and Gemini calls run concurrently with data fetching and are never blocked by data queues.

Analysis runs through seven specialized agents: fundamentals, technicals, bull thesis, bear thesis, moat analysis, SWOT/strategy, and recommendation. US companies additionally get DCF valuation, comparable company analysis, sensitivity analysis, earnings model, and conviction scoring. Results are streamed to the frontend via SSE as each step completes.

The valuation module lives in `src_george_researcher/valuation/` with a clean separation between pure calculation code (dcf_engine, sensitivity, earnings_model) and LLM-driven agents (dcf_agent, comp_agent, conviction). All calculation dataclasses are frozen and provide `to_dict()` for serialization. Custom exceptions (AssumptionParseError, InsufficientDataError, PeerFetchError) distinguish failure modes.

Authentication uses bcrypt (12 rounds) password hashing with JWT access tokens (30 min) and refresh tokens (7 days, stored hashed). Registration requires email whitelisting via `data/authorized_users.csv`. All sessions are user-scoped and stored at `data/sessions/{user_id}/{session_id}.json` with ownership verified on every API call.

Caching uses TTL-based SQLite storage with a `@cached` decorator. Gemini search results cache for 2 hours, FDS prices for 24 hours, FDS financials for 7 days, and yfinance data for 24 hours. This reduces API costs 80-98%.


## Project Structure

```
backend/
  main.py                    FastAPI entry point with lifespan management
  routers/                   API routes: analysis, auth, cache, chart, chat,
                             companies, reports, sessions, settings, usage, watchlist
  core/                      Business logic: session, auth, auth_db, rag_engine,
                             pdf_generator_v2, report_builder, branding_config,
                             contradiction_detector, watchlist_db, usage_db,
                             settings_db, base_db, exceptions
  dependencies.py            FastAPI dependencies for session/auth lookup
  middleware/                 Auth middleware, usage tracking
  jobs/                      Dual job queue: models, queue (SQLite), worker pool
  models/                    Pydantic request/response models
src_george_researcher/
  analysis_agents.py         LLM analysis functions and AnalysisResult dataclass
  orchestrator.py            Non-US analysis pipeline
  llm.py                     LLM client with circuit breaker
  circuit_breaker.py         Circuit breaker for external API resilience
  pricing.py                 Single source of truth for LLM model pricing
  prompts/                   System prompts for each agent
  analysis/
    us/orchestrator.py       US analysis pipeline (24 steps including valuation)
    shared/                  Growth metrics, parsing utilities
  data_fetchers/
    stock_data.py            yfinance wrapper
    cache.py                 TTL-based SQLite cache with @cached decorator
    gemini_search.py         Gemini Search Grounding client
    us/financial_datasets_client.py   FDS.ai client (financials, insider, estimates)
  valuation/
    dcf_engine.py            Pure math DCF calculator (no LLM)
    dcf_agent.py             LLM-driven DCF assumption generator
    sensitivity.py           WACC x Terminal Growth 5x5 grid
    conviction.py            Conviction scoring with LLM structured output
    earnings_model.py        Historical + estimate earnings table builder
    comp_table.py            Comparable company analysis with peer selection
    comp_agent.py            LLM narrative for comp table
    exceptions.py            ValuationError hierarchy
frontend/src/
  App.jsx                    Main app with routing
  components/                AnalysisView, ChatInterface, SessionBrowser,
                             StockPicker, LoginForm, RegisterForm, AuthModal,
                             UsageStats, WatchlistDashboard, DCFTable,
                             SensitivityGrid, ConvictionScore, CompTable
  contexts/AuthContext.jsx   Auth state management
data/
  sessions/{user_id}/        Session JSON files
  jobs.db                    Job queue persistence
  auth.db                    Users and tokens
  usage.db                   Per-user usage tracking
  cache.db                   TTL-based data cache
  watchlist.db               User watchlists with fair values
  authorized_users.csv       Beta email whitelist
```


## API Endpoints

Health: `GET /health` returns worker stats and queue status. Auth: register (`POST /api/auth/register`), login (`POST /api/auth/login`), refresh (`POST /api/auth/refresh`), logout (`POST /api/auth/logout`), current user (`GET /api/auth/me`). Analysis: start (`POST /api/analysis/start`), status (`GET /api/analysis/{id}/status`), SSE progress (`GET /api/analysis/{id}/progress`). Chat: SSE stream (`GET /api/chat/stream`), history (`GET /api/chat/{id}/history`). Sessions: list (`GET /api/sessions/`), resume (`POST /api/sessions/{id}/resume`), delete (`DELETE /api/sessions/{id}`). Reports: get (`GET /api/reports/{id}`), PDF export (`POST /api/reports/{id}/export/pdf`), sections CRUD, valuation data (`GET /api/reports/{id}/valuation-data`), source exclude/restore. Companies: classify US/non-US (`GET /api/companies/classify/{ticker}`). Chart: data (`GET /api/chart/{ticker}/data`). Cache: stats, invalidate, cleanup, health. Usage: records, summary, daily, costs, stats. Watchlist: list, add, remove. Settings: get/update user settings.


## Key Features

The chat system uses RAG with three retrieval paths: SEC filings (FAISS vector search), news (Gemini Search Grounding triggered by keywords like "recent", "news", "latest"), and report content. Beliefs are extracted from chat messages into six categories (valuation, growth, risk, competitive, management, macro) and tracked as analyst opinions that influence report finalization.

PDF export produces professional reports using WeasyPrint with Jinja2 HTML templates. Reports include a header banner with key metrics, a 15-year price chart, the full analysis across all sections, sources, and analyst attribution. White-labeling is supported through branding configuration.

The watchlist tracks user stock positions with fair values from DCF analysis. When an analysis completes, the fair value is broadcast to all users who have that ticker on their watchlist. The watchlist endpoint fetches current prices concurrently via a thread pool to avoid blocking.

Cost tracking records actual token counts and costs from LLM API responses (not estimates) per user per session, with daily and monthly breakdowns.

The contradiction detector uses LLM-based semantic analysis to find disagreements between bull/bear cases and identify research gaps, falling back to heuristic detection if the LLM call fails.


## Tech Debt and Known Issues

High-priority complexity reduction targets: `compute_growth_metrics` (complexity 80), `format_financial_statements_for_report` (75), `build_template_context` (66), `analyze_financial_statements` (51). Each should be broken into smaller single-purpose functions with the parent becoming a coordinator.

About 65 broad `except Exception` blocks remain, concentrated in worker.py, rag_engine.py, and contradiction_detector.py. These should be narrowed to specific exception types.

`StartAnalysisResponse` is defined in both `models/responses.py` and `routers/analysis.py` and should use a single source of truth. Operating income is used as an EBITDA proxy in the earnings model, which understates EBITDA for capital-intensive companies. The `INDUSTRY_PEERS` and `SECTOR_PEERS` static mappings (100+ lines) are mixed in with calculation logic in comp_table.py and should be extracted to a config file.

Current metrics: 11 Ruff errors (all intentional E402 import ordering), Pylint ~9.0/10, 75 tests passing.


## Design Principles

The codebase follows principles from "A Philosophy of Software Design" by Ousterhout. Deep modules provide significant functionality through simple interfaces. Complexity is pulled downward so callers stay simple. Errors are defined out of existence where possible through idempotent operations. When adding new code, use the existing utilities: `extract_json_from_llm_response()` for parsing LLM JSON, `get_user_session` dependency for endpoint session lookup, `AsyncSQLiteDB` base class for new databases, and custom exceptions from both `backend/core/exceptions.py` and `src_george_researcher/valuation/exceptions.py`. Follow the pattern of specific exception catches, type hints on all signatures, and named constants with impact documentation at the top of files.


## Future Enhancements

Two major features are planned but not yet implemented.

The first is smarter news search. The current Gemini search uses generic queries that miss specialized angles like supply chain risks, regulatory developments, and competitive dynamics. Gemini results also lack publication dates, making recency filtering impossible. The plan is to build company-aware multi-angle search across five dimensions (core business, supply chain, competitive landscape, regulatory/macro, sentiment), extract dates from results via Gemini parsing or URL fetching, and add domain-specific relevance scoring beyond Gemini's confidence score. A `COMPANY_DEPENDENCIES` mapping would provide per-ticker knowledge of key inputs, competitors, and regulatory factors, with LLM fallback for unmapped companies. The system would also generate targeted due diligence queries from bull/bear disagreements.

The second is user-uploaded PDF sources with unified RAG. Users would upload research reports, earnings transcripts, or notes through the Sources tab. PDFs would be processed with PyMuPDF for native text extraction and Tesseract OCR as fallback for scanned pages, chunked into ~500 token segments, embedded with a configurable model (OpenAI text-embedding-3-small, Gemini text-embedding-004, or local all-MiniLM-L6-v2), and stored in per-session FAISS indexes. The RAG engine would then retrieve across all sources with a priority system: user beliefs first (always included), then user PDFs, then SEC filings, then news/web. Context would be budget-managed to fit within ~120K tokens with smart truncation rules that never cut beliefs and rank everything else by relevance score.


## Per-Analysis Cost Breakdown

A US analysis costs roughly $0.32 (LLM ~$0.25 via OpenRouter, FDS data ~$0.05, Gemini search ~$0.02). A non-US analysis costs roughly $0.22 (no FDS charges). Monthly projections: low usage (50 analyses) ~$15, medium (200) ~$60, heavy (500) ~$150. The cache layer dramatically reduces repeat costs with 80-98% hit rates depending on data type.
