# Agent Onboarding: George Financial Researcher

## Project Overview

George is a financial research platform that performs automated equity analysis using LLMs. It has:
- **Backend**: FastAPI + Python with multi-agent LLM architecture
- **Frontend**: React + Vite
- **Data Sources**: FinancialDatasets.ai (US), Alpha Vantage (non-US), SEC filings, news APIs

## Codebase Structure

```
├── backend/                    # FastAPI backend
│   ├── agents/                 # LLM wrapper and orchestration
│   ├── core/                   # Core business logic
│   │   ├── base_db.py         # NEW: Async SQLite base class
│   │   ├── exceptions.py      # NEW: Custom exception hierarchy
│   │   ├── session.py         # Session management
│   │   ├── auth.py            # Authentication
│   │   └── ...
│   ├── dependencies.py        # NEW: FastAPI dependencies
│   ├── routers/               # API endpoints
│   └── jobs/                  # Background job queue
├── src_george_researcher/      # Core analysis engine
│   ├── analysis/              # Analysis modules
│   │   ├── shared/            # Shared utilities
│   │   │   ├── parsing.py     # NEW: JSON extraction utilities
│   │   │   └── ...
│   │   └── us/                # US-specific analysis
│   ├── data_fetchers/         # Data source clients
│   ├── orchestrator.py        # Main analysis orchestrator
│   ├── llm.py                 # LLM client with circuit breaker
│   ├── circuit_breaker.py     # NEW: Circuit breaker pattern
│   └── pricing.py             # NEW: Shared LLM pricing
├── tests/                     # Test suite (75 tests passing)
│   └── unit/
└── frontend/                  # React frontend
```

## What Has Been Done

### Phase 1: Foundation (Completed)
- [x] Created shared pricing module (`src_george_researcher/pricing.py`)
- [x] Added circuit breaker for LLM calls (`src_george_researcher/circuit_breaker.py`)
- [x] Added retry logic with exponential backoff (`backend/agents/llm_wrapper.py`)
- [x] Created test infrastructure (75 tests passing)
- [x] Fixed JWT security (requires secret in production)
- [x] Added `SessionMetadata` TypedDict for type safety
- [x] Documented magic numbers in `analysis_agents.py`

### Phase 2: Code Quality (Completed)
- [x] Fixed undefined `FullAnalysis` type reference
- [x] Ran Ruff auto-fix (78 issues fixed)
- [x] Removed all unused variables (7 fixed)
- [x] Fixed singleton naming conventions (6 files)
- [x] Created `AsyncSQLiteDB` base class (eliminates 3x duplicate code)
- [x] Created `extract_json_from_llm_response()` utility (eliminates 2x duplicate)
- [x] Created FastAPI dependencies for session lookup
- [x] Improved exception handling in auth.py and session.py

### Phase 3: Dependency Refactoring (Completed)
- [x] Refactored reports.py (8 endpoints) to use `get_user_session_with_report` dependency
- [x] Refactored chat.py (4 endpoints) to use `get_user_session` and `get_user_and_session` dependencies
- [x] Refactored analysis.py (6 endpoints) to use `get_user_session` dependency
- [x] Refactored sessions.py (1 endpoint) to use `get_user_session_with_report` dependency
- [x] Added `UserSession` NamedTuple and `get_user_and_session` dependency for endpoints needing both

### Phase 4: Complexity Reduction (In Progress)
- [x] Broke down `_generate_highlights` (complexity 41 → ~10) into 8 focused detection functions

### Metrics Improvement
| Metric | Before | After |
|--------|--------|-------|
| Ruff errors | 97 | 11 (all intentional E402) |
| Pylint score | 8.55/10 | ~9.0/10 |
| Tests | 61 | 75 |
| Duplicate code blocks | 13 | ~8 |

---

## What Still Needs To Be Done

### HIGH PRIORITY: Complexity Reduction

The following functions have F-grade cyclomatic complexity (41+) and need to be broken down:

| Function | Complexity | File | Suggested Action |
|----------|------------|------|------------------|
| `compute_growth_metrics` | 80 | `analysis/shared/growth_metrics.py` | Split into metric-specific functions |
| `format_financial_statements_for_report` | 75 | `analysis/us/financial_analysis.py` | Extract section formatters |
| `build_template_context` | 66 | `core/pdf_generator_v2.py` | Extract data collectors |
| `analyze_financial_statements` | 51 | `analysis/us/financial_analysis.py` | Split analysis phases |
| ~~`_generate_highlights`~~ | ~~41~~ | ~~`analysis/us/financial_analysis.py`~~ | ✅ Done - split into 8 detection functions |

**Approach**: Each function should be broken into smaller, single-purpose functions. The parent function becomes a coordinator that calls the smaller functions.

### MEDIUM PRIORITY: Remaining Duplicate Code

1. ~~**Session lookup pattern** (~20 more endpoints)~~ ✅ **DONE**
   - All routers refactored to use dependencies from `backend/dependencies.py`
   - 2 chat endpoints still use request body pattern (acceptable)

2. **Response model duplication**
   - `StartAnalysisResponse` defined in both `models/responses.py` and `routers/analysis.py`
   - Solution: Use single source of truth in `models/responses.py`

### MEDIUM PRIORITY: Broad Exception Catches

~65 remaining `except Exception` blocks. Priority files:
- `backend/jobs/worker.py` - Job execution errors
- `backend/core/rag_engine.py` - RAG pipeline errors
- `backend/core/contradiction_detector.py` - Analysis errors

**Approach**:
1. Identify what exceptions can actually be raised
2. Catch specific exceptions (`json.JSONDecodeError`, `httpx.TimeoutException`, etc.)
3. Use custom exceptions from `backend/core/exceptions.py` where appropriate

### LOW PRIORITY: Documentation

- Missing docstrings on ~25 `to_dict()` methods
- Some docstrings missing terminal periods (pydocstyle)

---

## Key Files to Understand

### New Infrastructure Files
- `backend/core/base_db.py` - Base class for async SQLite databases
- `backend/core/exceptions.py` - Custom exception hierarchy (use these!)
- `backend/dependencies.py` - FastAPI dependencies for common patterns
- `src_george_researcher/analysis/shared/parsing.py` - JSON extraction utilities
- `src_george_researcher/circuit_breaker.py` - Circuit breaker for external APIs
- `src_george_researcher/pricing.py` - Single source of truth for LLM pricing

### Core Business Logic
- `src_george_researcher/orchestrator.py` - Main analysis pipeline (non-US)
- `src_george_researcher/analysis/us/orchestrator.py` - US analysis pipeline
- `backend/core/session.py` - Session management with thread-safe access
- `backend/jobs/worker.py` - Background job processing

---

## How to Run Tests

```bash
# Run all tests
uv run python -m pytest tests/ -v

# Run specific test file
uv run python -m pytest tests/unit/test_session.py -v

# Run with coverage
uv run python -m pytest tests/ --cov=backend --cov=src_george_researcher
```

## How to Check Code Quality

```bash
# Ruff (fast linter)
uv run ruff check backend/ src_george_researcher/

# Auto-fix Ruff issues
uv run ruff check --fix backend/ src_george_researcher/

# Pylint (comprehensive)
uv run pylint backend/ src_george_researcher/ --score=y

# Complexity analysis
uv run radon cc backend/ src_george_researcher/ -s -a --min C
```

---

## Design Principles to Follow

Reference: The codebase follows principles from "A Philosophy of Software Design" (Ousterhout):

1. **Deep Modules**: Provide significant functionality through simple interfaces
2. **Pull Complexity Downwards**: Modules should absorb complexity, not expose it
3. **Define Errors Out of Existence**: Prefer idempotent operations
4. **Single Responsibility**: Each function/class does one thing
5. **DRY**: Extract duplicated code into shared utilities

### When Adding New Code

1. Use existing utilities:
   - `extract_json_from_llm_response()` for parsing LLM JSON
   - `get_user_session` dependency for endpoint session lookup
   - `AsyncSQLiteDB` base class for new databases
   - Custom exceptions from `backend/core/exceptions.py`

2. Follow patterns:
   - Specific exception catches, not bare `except Exception`
   - Type hints on all function signatures
   - Constants at top of file with impact documentation

---

## Quick Wins for a New Agent

1. **Refactor one endpoint to use dependencies** (5 min each)
   - Pick any endpoint in `routers/analysis.py` that has the session lookup pattern
   - Replace with `Depends(get_user_session)`

2. **Fix one broad exception catch** (10 min each)
   - Find an `except Exception` in a critical path
   - Replace with specific exception types

3. **Break down one complex function** (30-60 min each)
   - Start with `_generate_highlights` (complexity 41) - it's self-contained
   - Extract each highlight type into its own function

---

## Running the Application

```bash
# Start backend
cd backend && uvicorn main:app --reload

# Start frontend
cd frontend && npm run dev

# Or use the combined script
./start.sh
```

## Environment Variables Required

```
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=anthropic/claude-sonnet-4
FINANCIAL_DATASETS_API_KEY=...  # For US stocks
ALPHA_VANTAGE_API_KEY=...       # For non-US stocks
GEMINI_API_KEY=...              # For web search
JWT_SECRET=...                  # Required in production
```
