# George Researcher: Architecture & Multi-User Scaling Strategy

> **Comprehensive Technical Document**
>
> This document consolidates all architecture decisions, data source analysis, multi-user scaling strategy, and implementation plans for George Researcher.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Assessment](#2-current-architecture-assessment)
3. [Data Sources Analysis](#3-data-sources-analysis)
4. [Multi-User Scaling Bottlenecks](#4-multi-user-scaling-bottlenecks)
5. [Target Architecture: US vs Non-US Segregation](#5-target-architecture-us-vs-non-us-segregation)
6. [Dual Queue System](#6-dual-queue-system)
7. [FinancialDatasets.ai Integration](#7-financialdatasetsai-integration)
8. [Implementation Details](#8-implementation-details)
9. [API Reference](#9-api-reference)
10. [Implementation Phases](#10-implementation-phases)
11. [Cost Analysis](#11-cost-analysis)

---

## 1. Executive Summary

### The Problem

George Researcher needs to scale from single-user to multi-user while:
1. Supporting concurrent analyses without race conditions
2. Handling rate-limited APIs efficiently
3. Providing rich data for US companies via FinancialDatasets.ai
4. Gracefully degrading for non-US companies
5. Allowing analyses to complete even if users close their browser

### The Solution

**Dual Queue Architecture** with explicit US/Non-US separation:

| Queue | Data Sources | Speed | Workers |
|-------|--------------|-------|---------|
| **US Queue** | FinancialDatasets.ai (fast) | ~20+ analyses/min | 3+ |
| **Non-US Queue** | yfinance + Alpha Vantage (5/min bottleneck) | ~3-5 analyses/min | 1-2 |
| **Shared** | LLM (unlimited) + Gemini (1500/day) | No blocking | Concurrent with data fetch |

### Key Decisions

1. **EODHD**: Removed (was $80/month subscription)
2. **SEC EDGAR direct**: Replaced by FinancialDatasets.ai for US companies
3. **yfinance**: Reserved for non-US companies only (don't waste on US)
4. **Alpha Vantage**: Reserved for non-US companies only (5/min is precious)
5. **Two separate queues**: US jobs never blocked by non-US rate limits

---

## 2. Current Architecture Assessment

### Critical Issues ✅ ALL RESOLVED

| Issue | Severity | Status |
|-------|----------|--------|
| **Thread Safety** | ✅ Fixed | `SessionManager` now has proper locking via `session_context()` |
| **Blocking Analysis** | ✅ Fixed | Jobs persist to SQLite, analysis continues after browser close |
| **No Queue System** | ✅ Fixed | DualJobQueue with 3 US + 2 Non-US workers |
| **US/Non-US Conflation** | ✅ Fixed | Explicit classification and separate queues |
| **Rate Limit Handling** | ✅ Fixed | Token bucket rate limiters per queue |

### Current Data Flow (FastAPI + Job Queue)

```
User Request → FastAPI → DualJobQueue.enqueue() → SQLite
                              ↓
                    Worker Pool (async)
                    ├── US Worker 1-3 (FDS)
                    └── Non-US Worker 1-2 (Alpha Vantage)
                              ↓
                    Orchestrator → Data Fetchers → LLM Agents
                              ↓
                    job_queue.complete_job() → SQLite
                              ↓
Frontend polls /api/analysis/{id}/status → Result
              [NON-BLOCKING - browser can close]
```

### Current Data Sources (Before Refactoring)

| Source | Rate Limit | Coverage | Status |
|--------|------------|----------|--------|
| yfinance | Undocumented (risky) | Global | MOVE to Non-US only |
| Alpha Vantage | 5/min, 500/day | Global | MOVE to Non-US only |
| ~~EODHD~~ | ~~1000/day~~ | - | **REMOVED** |
| Reddit | ~10/min | Global | MOVE to Non-US only |
| ~~SEC EDGAR~~ | ~~10/sec~~ | US only | **REPLACED by FDS** |
| Gemini Search | 1500/day | Global | KEEP (shared) |
| OpenRouter LLM | Unlimited | Global | KEEP (shared) |

---

## 3. Data Sources Analysis

### 3.1 The yfinance Problem

yfinance is the **biggest risk** in the current architecture:

| Risk Factor | Description |
|-------------|-------------|
| Unofficial scraper | No authentication, looks like DDoS to Yahoo |
| Active blocking | Yahoo has increased rate limiting in 2025 |
| No reliability | Can break anytime Yahoo changes their site |
| No support | Open source, community-maintained |
| Unpredictable | Rate limits not documented |

**Decision**: Use yfinance ONLY for non-US companies where we have no alternative.

### 3.2 Alpha Vantage Bottleneck

- **Free tier**: 5 calls/minute, 500 calls/day
- **This is THE bottleneck** for non-US queue
- Each non-US analysis needs ~1-2 Alpha Vantage calls for news
- **Max throughput**: ~3-5 non-US analyses per minute

**Decision**: Reserve Alpha Vantage exclusively for non-US companies.

### 3.3 Data Source Classification (Final)

| Data Source | Rate Limit | Queue Assignment | Notes |
|-------------|------------|------------------|-------|
| **LLM (OpenRouter)** | Unlimited (pay per use) | Shared | ~$0.05/analysis |
| **Gemini Search** | 1500/day | Shared | ~$0.17/analysis |
| **FinancialDatasets.ai** | 1000/min (generous) | **US Queue ONLY** | New primary source |
| **yfinance** | Undocumented | **Non-US Queue ONLY** | Risky but necessary |
| **Alpha Vantage** | **5/min, 500/day** | **Non-US Queue ONLY** | THE BOTTLENECK |
| **Reddit** | ~10/min | **Non-US Queue ONLY** | Limited usefulness |

### 3.4 Removed Data Sources

| Source | Reason |
|--------|--------|
| **EODHD** | $80/month subscription - replaced by FDS for US, Alpha Vantage for non-US |
| **SEC EDGAR direct** | Replaced by FinancialDatasets.ai (includes SEC data) |

---

## 4. Multi-User Scaling Bottlenecks

### With 5 Concurrent Users (Current Architecture)

| Component | Calls (5 users) | Risk | Impact |
|-----------|-----------------|------|--------|
| **yfinance** | 15 concurrent | 🔴 HIGH | Random failures, blocking |
| **Alpha Vantage** | 5-10 calls | 🔴 HIGH | Exceeds 5/min limit |
| **Flask threads** | 5 blocked | 🟡 MEDIUM | Slow response, timeouts |
| **Reddit** | 50-60 calls | 🟡 MEDIUM | Some data missing |
| **Gemini** | 25 queries | 🟢 OK | Within 1500/day |
| **OpenRouter** | 35-40 calls | 🟢 OK | Unlimited |

### Bottleneck Priority

1. **P0 - yfinance**: Replace with FDS for US companies
2. **P1 - Alpha Vantage**: Isolate to non-US queue only
3. **P2 - Flask**: Add background job queue
4. **P3 - Thread safety**: Add locks to SessionManager

---

## 5. Target Architecture: US vs Non-US Segregation

### Directory Structure

```
src_george_researcher/
├── data_fetchers/
│   │
│   │  # ════════════════════════════════════════════════
│   │  #  US COMPANY DATA (FinancialDatasets.ai)
│   │  # ════════════════════════════════════════════════
│   ├── us/
│   │   ├── __init__.py
│   │   ├── financial_datasets_client.py   # API client + auth
│   │   ├── company_facts.py               # Company info, sector
│   │   ├── financials.py                  # Income, Balance, Cash Flow
│   │   ├── prices.py                      # OHLCV historical data
│   │   ├── insider_trades.py              # Insider trading activity
│   │   ├── analyst_estimates.py           # EPS forecasts
│   │   ├── news.py                        # News with sentiment
│   │   └── sec_filings.py                 # SEC filings via FDS
│   │
│   │  # ════════════════════════════════════════════════
│   │  #  NON-US / GLOBAL DATA
│   │  #  Note: EODHD REMOVED
│   │  # ════════════════════════════════════════════════
│   ├── global/
│   │   ├── __init__.py
│   │   ├── stock_data.py                  # yfinance wrapper
│   │   ├── technical_indicators.py        # Technical analysis
│   │   ├── alpha_vantage_news.py          # News (Alpha Vantage only)
│   │   ├── reddit_sentiment.py            # Reddit public API
│   │   └── gemini_search.py               # Google Gemini Search
│   │
│   │  # ════════════════════════════════════════════════
│   │  #  SHARED INFRASTRUCTURE
│   │  # ════════════════════════════════════════════════
│   ├── company_registry.py                # US company lookup
│   ├── data_router.py                     # Routes to US or Global
│   └── types.py                           # Shared dataclasses
│
├── analysis/
│   │  # ════════════════════════════════════════════════
│   │  #  US COMPANY ANALYSIS PIPELINE
│   │  # ════════════════════════════════════════════════
│   ├── us/
│   │   ├── orchestrator.py                # Full US analysis flow
│   │   ├── fundamentals.py                # FDS financials analysis
│   │   ├── insider_analysis.py            # Insider trading patterns
│   │   └── estimates_analysis.py          # Analyst consensus
│   │
│   │  # ════════════════════════════════════════════════
│   │  #  NON-US / GLOBAL ANALYSIS PIPELINE
│   │  # ════════════════════════════════════════════════
│   ├── global/
│   │   ├── orchestrator.py                # Degraded analysis flow
│   │   ├── fundamentals.py                # yfinance-only analysis
│   │   └── limitations.py                 # Documents unavailable data
│   │
│   │  # ════════════════════════════════════════════════
│   │  #  SHARED ANALYSIS MODULES
│   │  # ════════════════════════════════════════════════
│   ├── shared/
│   │   ├── technicals.py                  # Technical analysis
│   │   ├── bull_bear_debate.py            # Bull/Bear thesis
│   │   ├── moat_analysis.py               # Competitive moat
│   │   ├── swot_analysis.py               # SWOT analysis
│   │   └── recommendation.py              # Final synthesis
│   │
│   └── router.py                          # Routes to US or Global
```

### Data Availability by Region

#### US Companies (Full Data)

| Data Type | Source | Available |
|-----------|--------|-----------|
| Company Info | FinancialDatasets.ai | ✅ |
| Detailed Financials | FinancialDatasets.ai | ✅ |
| Historical Prices | FinancialDatasets.ai | ✅ |
| Insider Trades | FinancialDatasets.ai | ✅ |
| Analyst Estimates | FinancialDatasets.ai | ✅ |
| News | FinancialDatasets.ai | ✅ |
| SEC Filings | FinancialDatasets.ai | ✅ |
| Web Research | Gemini Search | ✅ |

#### Non-US Companies (Degraded)

| Data Type | Source | Available |
|-----------|--------|-----------|
| Company Info | yfinance | ✅ (basic) |
| Detailed Financials | - | ❌ |
| Historical Prices | yfinance | ✅ |
| Insider Trades | - | ❌ |
| Analyst Estimates | - | ❌ |
| News | Alpha Vantage | ✅ (limited) |
| SEC Filings | - | ❌ |
| Web Research | Gemini Search | ✅ (best source!) |

---

## 6. Dual Queue System

### Why Two Queues?

```
Problem: Alpha Vantage is 5 requests/minute
         If US and non-US share a queue, US analyses wait behind non-US rate limits

Solution: Separate queues with separate rate limiters
          US queue uses FDS (fast)
          Non-US queue uses Alpha Vantage (slow)
          They never compete for the same resources
```

### Architecture Diagram

```
                    ┌─────────────────────────────────────────┐
                    │         SHARED RESOURCES                │
                    │      (Used by BOTH queues)              │
                    │                                         │
                    │   • LLM Calls (unlimited, pay-per-use)  │
                    │   • Gemini Search (1500/day global)     │
                    │                                         │
                    │   IMPORTANT: These run CONCURRENTLY     │
                    │   with data fetching, even when data    │
                    │   is queued. Never blocked by queues.   │
                    └─────────────────────────────────────────┘
                                        │
                                        │
       ┌────────────────────────────────┴────────────────────────────────┐
       │                                                                 │
       │                       FastAPI Backend                            │
       │                    (Classifies & Routes)                        │
       │                                                                 │
       │   POST /api/analysis/start                                      │
       │     → classify_company(ticker)                                  │
       │     → route to US or Non-US queue                               │
       └────────────────────────────────┬────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
                    ▼                                       ▼
┌───────────────────────────────────┐   ┌───────────────────────────────────┐
│        US COMPANY QUEUE           │   │      NON-US COMPANY QUEUE         │
│         (Fast Queue)              │   │      (Rate-Limited Queue)         │
│                                   │   │                                   │
│  ┌─────────────────────────────┐  │   │  ┌─────────────────────────────┐  │
│  │ [User A: AAPL]    running   │  │   │  │ [User B: TSMC]    running   │  │
│  │ [User C: MSFT]    pending   │  │   │  │ [User D: ASML]    pending   │  │
│  │ [User A: GOOGL]   pending   │  │   │  │ [User B: SAP]     pending   │  │
│  └─────────────────────────────┘  │   │  └─────────────────────────────┘  │
│                                   │   │                                   │
│  Data Sources (US only):          │   │  Data Sources (Global):           │
│  ✓ FinancialDatasets.ai           │   │  ✓ yfinance (unlimited)           │
│    • company facts                │   │  ✓ Alpha Vantage (5/min!) ← SLOW  │
│    • financials                   │   │  ✓ Reddit (~10/min)               │
│    • prices                       │   │                                   │
│    • insider trades               │   │  NOT USED:                        │
│    • analyst estimates            │   │  ✗ FinancialDatasets.ai           │
│    • news                         │   │                                   │
│                                   │   │  Bottleneck: Alpha Vantage        │
│  NOT USED (save for non-US):      │   │  Max throughput: ~5 jobs/min      │
│  ✗ yfinance                       │   │                                   │
│  ✗ Alpha Vantage                  │   │                                   │
│  ✗ Reddit                         │   │                                   │
│                                   │   │                                   │
│  Workers: 3 (can run parallel)    │   │  Workers: 1-2 (rate limited)      │
└───────────────────────────────────┘   └───────────────────────────────────┘
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │           SESSION STORAGE               │
                    │     (Per-user session isolation)        │
                    │                                         │
                    │   US and Non-US results stored the      │
                    │   same way, just with different         │
                    │   data availability flags               │
                    └─────────────────────────────────────────┘
```

### Queue Characteristics

| Characteristic | US Queue | Non-US Queue |
|----------------|----------|--------------|
| **Speed** | Fast (FDS is generous) | Slow (Alpha Vantage 5/min) |
| **Workers** | 3+ concurrent | 1-2 max (rate limited) |
| **Bottleneck** | None significant | Alpha Vantage |
| **Data richness** | Full (9 data types) | Limited (5 data types) |
| **Throughput** | ~20+ analyses/min | ~3-5 analyses/min |
| **Estimated wait** | ~30 seconds/analysis | ~60 seconds/analysis |

### Benefits

1. **Queue Isolation**: US jobs never compete with non-US for rate limits
2. **Fair Scheduling**: FIFO within each queue
3. **No API Waste**: US companies don't consume Alpha Vantage quota
4. **Predictable Waits**: Non-US users know the queue is slower
5. **Browser Independence**: Jobs complete even if user closes tab

### Concurrent Execution Model

**Critical Design Principle**: LLM and Gemini Search are NEVER blocked by data fetch queues.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ANALYSIS EXECUTION MODEL                            │
│                                                                         │
│  Even for Non-US companies with queued financial data:                  │
│                                                                         │
│    ┌──────────────────┐     ┌──────────────────┐                        │
│    │   DATA FETCH     │     │   LLM + GEMINI   │                        │
│    │   (may queue)    │     │   (never queued) │                        │
│    └────────┬─────────┘     └────────┬─────────┘                        │
│             │                        │                                  │
│             │   CONCURRENT           │                                  │
│             ├────────────────────────┤                                  │
│             │                        │                                  │
│             ▼                        ▼                                  │
│    ┌──────────────────┐     ┌──────────────────┐                        │
│    │ yfinance data    │     │ Gemini web search│                        │
│    │ Alpha Vantage    │     │ LLM analysis     │                        │
│    │ (rate limited)   │     │ Report updates   │                        │
│    └────────┬─────────┘     └────────┬─────────┘                        │
│             │                        │                                  │
│             └────────────┬───────────┘                                  │
│                          ▼                                              │
│                 ┌──────────────────┐                                    │
│                 │   MERGE RESULTS  │                                    │
│                 │   Final Report   │                                    │
│                 └──────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

**What this means in practice**:

| Operation | Blocking Behavior |
|-----------|-------------------|
| **Gemini web research** | Runs immediately, never queued |
| **LLM analysis calls** | Runs immediately, never queued |
| **Report generation/updates** | Runs immediately, never queued |
| **Chat interactions** | Runs immediately, never queued |
| **yfinance stock data** | May queue for non-US (rate limited) |
| **Alpha Vantage news** | May queue for non-US (5/min limit) |
| **FinancialDatasets.ai** | Never queued (1000/min limit) |

**Implementation Note**: The orchestrator should spawn LLM/Gemini tasks in parallel
with data fetching. Even if financial data is waiting in queue, the user gets:
- Immediate Gemini web research results
- LLM-powered chat responses
- Report updates from chat conversations
- Technical analysis (from already-fetched price data)

---

## 7. FinancialDatasets.ai Integration

### API Overview

- **Coverage**: 30,000+ US tickers, 30+ years of data
- **Rate Limits**: 1,000 requests/minute (generous)
- **Pricing**: Pay-per-request (no monthly commitment)
- **Authentication**: `X-API-KEY` header

### Endpoints to Integrate

| Endpoint | Purpose | Priority | Cost |
|----------|---------|----------|------|
| `/company/facts` | Company info, sector, employees | P0 | FREE |
| `/company/facts/ciks/` | List of CIKs for autocomplete | P0 | FREE |
| `/analyst-estimates/tickers/` | Available tickers list | P0 | FREE |
| `/financials` | Income, Balance, Cash Flow | P0 | $0.02/req |
| `/prices` | Historical OHLCV data | P0 | $0.01/req |
| `/analyst-estimates` | EPS forecasts | P1 | $0.02/req |
| `/news` | Company news with sentiment | P1 | $0.02/req |
| `/insider-trades` | Insider trading activity | P1 | $0.02/req |
| `/financials/segmented-revenues` | Revenue by segment | P2 | $0.02/req |

### API Examples

```bash
# Company Facts (FREE)
curl --request GET \
  --url 'https://api.financialdatasets.ai/company/facts?ticker=AAPL' \
  --header 'X-API-KEY: <api-key>'

# Financials
curl --request GET \
  --url 'https://api.financialdatasets.ai/financials?ticker=AAPL&period=annual' \
  --header 'X-API-KEY: <api-key>'

# Historical Prices
curl --request GET \
  --url 'https://api.financialdatasets.ai/prices?ticker=AAPL&limit=500' \
  --header 'X-API-KEY: <api-key>'

# Insider Trades
curl --request GET \
  --url 'https://api.financialdatasets.ai/insider-trades?ticker=AAPL&limit=50' \
  --header 'X-API-KEY: <api-key>'
```

### Response Schemas

#### Company Facts
```json
{
  "company_facts": {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "cik": "0000320193",
    "industry": "Consumer Electronics",
    "sector": "Technology",
    "exchange": "NASDAQ",
    "is_active": true,
    "market_cap": 3000000000000,
    "number_of_employees": 164000,
    "website_url": "https://www.apple.com"
  }
}
```

#### Financials
```json
{
  "financials": {
    "income_statements": [{
      "ticker": "AAPL",
      "report_period": "2023-09-30",
      "period": "annual",
      "revenue": 383285000000,
      "gross_profit": 169148000000,
      "operating_income": 114301000000,
      "net_income": 96995000000,
      "earnings_per_share": 6.13
    }],
    "balance_sheets": [...],
    "cash_flow_statements": [...]
  }
}
```

---

## 8. Implementation Details

### 8.1 Data Router

```python
# src_george_researcher/data_fetchers/data_router.py

from enum import Enum
from dataclasses import dataclass

class CompanyRegion(Enum):
    US = "us"          # Full FinancialDatasets.ai support
    NON_US = "non_us"  # Degraded mode - yfinance + Gemini only

@dataclass(frozen=True)
class DataAvailability:
    """What data is available for a company."""
    stock_info: bool = True
    technical_indicators: bool = True
    price_history: bool = True
    detailed_financials: bool = False      # US only
    insider_trades: bool = False           # US only
    analyst_estimates: bool = False        # US only
    sec_filings: bool = False              # US only
    news_sentiment: bool = True
    gemini_search: bool = True

    @classmethod
    def us_company(cls):
        return cls(detailed_financials=True, insider_trades=True,
                   analyst_estimates=True, sec_filings=True, ...)

    @classmethod
    def non_us_company(cls):
        return cls(detailed_financials=False, insider_trades=False, ...)

class DataRouter:
    """Routes data requests based on company region."""

    def classify_company(self, ticker: str) -> CompanyClassification:
        if self._is_us_company(ticker):
            return CompanyClassification(
                region=CompanyRegion.US,
                available_data=DataAvailability.us_company()
            )
        else:
            return CompanyClassification(
                region=CompanyRegion.NON_US,
                available_data=DataAvailability.non_us_company()
            )
```

### 8.2 Dual Job Queue

```python
# backend/core/job_queue.py

class DualJobQueue:
    """Separate queues for US and Non-US companies."""

    def __init__(self):
        self._us_workers = []
        self._non_us_workers = []
        self._us_rate_limiter = USRateLimiter()
        self._non_us_rate_limiter = NonUSRateLimiter()
        self._shared_limiter = SharedResourceLimiter()

    def enqueue(self, user_id, session_id, ticker, is_us_company, options):
        queue = QueueType.US if is_us_company else QueueType.NON_US
        # Insert into SQLite with queue column
        return job_id, queue

    def start_workers(self, us_workers=3, non_us_workers=2):
        # US queue gets more workers (faster API)
        # Non-US queue is bottlenecked by Alpha Vantage anyway
        pass

class USRateLimiter:
    """FinancialDatasets.ai only - generous limits."""
    limits = {'financial_datasets': {'rpm': 1000}}

class NonUSRateLimiter:
    """Alpha Vantage is the bottleneck."""
    limits = {
        'alpha_vantage': {'rpm': 5, 'daily': 500},  # THE BOTTLENECK
        'reddit': {'rpm': 10},
        'yfinance': {'rpm': 100},
    }

class SharedResourceLimiter:
    """Resources shared by both queues."""
    limits = {
        'gemini_search': {'daily': 1500},
        # LLM is unlimited (pay-per-use)
    }
```

### 8.3 Thread-Safe Session Manager

```python
# backend/core/session.py

import threading
from contextlib import contextmanager

class ThreadSafeSessionManager:
    def __init__(self):
        self._sessions = {}
        self._lock = threading.RLock()
        self._session_locks = {}

    @contextmanager
    def session_context(self, session_id: str):
        """Thread-safe session access with auto-save."""
        with self._lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.Lock()
            session_lock = self._session_locks[session_id]

        with session_lock:
            session = self._sessions.get(session_id)
            yield session
            if session:
                self._save_session(session)
```

### 8.4 Frontend: Data Availability Banner

```jsx
// frontend/src/components/DataAvailabilityBanner.jsx

export default function DataAvailabilityBanner({ classification }) {
  if (classification?.region === 'us') return null;

  const unavailable = [];
  if (!classification.available_data.detailed_financials)
    unavailable.push('Financial Statements');
  if (!classification.available_data.insider_trades)
    unavailable.push('Insider Trades');
  // ...

  return (
    <div className="bg-amber-50 border-l-4 border-amber-500 p-4 mb-6">
      <h3 className="text-amber-800 font-medium">Limited Data Available</h3>
      <p className="text-amber-700 text-sm">
        {classification.company_name} is a non-US company.
        Some analysis features are not available:
      </p>
      <ul className="text-amber-700 text-sm list-disc list-inside">
        {unavailable.map(item => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}
```

---

## 9. API Reference

### New Endpoints

```
# Company Classification
GET  /api/companies/classify/{ticker}
     Returns: { ticker, region, is_valid, company_name, available_data }

GET  /api/companies/us-tickers
     Returns: List of all US tickers (for autocomplete)

# Background Jobs
POST /api/analysis/start
     Body: { ticker, options }
     Returns: { session_id, job_id, queue: "us"|"non_us", status: "queued" }

GET  /api/analysis/{session_id}/job-status
     Returns: { job_id, status, step, total, message, queue }

GET  /api/jobs/queue-stats
     Returns: { us_queue: {...}, non_us_queue: {...} }
```

### Response Examples

```json
// POST /api/analysis/start (US company)
{
  "session_id": "abc-123",
  "job_id": "job-456",
  "ticker": "AAPL",
  "queue": "us",
  "status": "queued",
  "estimated_wait_seconds": 30
}

// POST /api/analysis/start (Non-US company)
{
  "session_id": "def-789",
  "job_id": "job-012",
  "ticker": "TSMC",
  "queue": "non_us",
  "status": "queued",
  "estimated_wait_seconds": 120,
  "data_limitations": [
    "detailed_financials",
    "insider_trades",
    "analyst_estimates",
    "sec_filings"
  ]
}
```

---

## 10. Implementation Phases

### Phase 1: Foundation ✅ COMPLETE

- [x] Create `data_fetchers/us/` directory with FDS client
- [x] Create `data_router.py` for US/non-US classification
- [x] Add thread-safe locking to SessionManager
- [x] Create `/api/companies/us-tickers` endpoint
- [x] Create `types.py` with `CompanyRegion`, `DataAvailability`, `CompanyClassification`
- [x] Create `company_registry.py` for SEC CIK-based US detection

### Phase 2: US Data Integration 🟡 IN PROGRESS

- [x] Integrate FDS company facts
- [x] Integrate FDS financials
- [x] Integrate FDS prices
- [x] Integrate FDS insider trades
- [x] Integrate FDS analyst estimates
- [x] Integrate FDS news
- [x] Update `data_router.py` to route US companies to FDS
- [ ] Create `analysis/us/orchestrator.py`
- [ ] Update API to use AnalysisRouter

### Phase 3: FastAPI Migration + Background Processing ✅ COMPLETE

**Migration from Flask to FastAPI for async I/O handling.**

- [x] Add FastAPI dependencies (fastapi, uvicorn, pydantic, aiosqlite)
- [x] Create `backend/main.py` FastAPI app with lifespan
- [x] Create `backend/routers/` with converted route handlers
- [x] Create `backend/models/` with Pydantic request/response models
- [x] Implement DualJobQueue with SQLite persistence (`backend/jobs/`)
- [x] Create async worker tasks (3 US, 2 non-US) (`backend/jobs/worker.py`)
- [x] Update API endpoints to return job_id
- [x] Archive deprecated Flask app.py to `archive/flask_deprecated/`

**New Directory Structure:**
```
backend/
├── main.py              # FastAPI app entry point
├── routers/             # FastAPI routers
│   ├── analysis.py      # Job queue integration
│   ├── chat.py          # SSE streaming
│   ├── companies.py     # US/Non-US classification
│   ├── chart.py         # Technical charts
│   ├── sessions.py      # Session management
│   └── reports.py       # PDF export
├── models/              # Pydantic models
└── jobs/                # Dual job queue
    ├── models.py        # Job, JobStatus, QueueType
    ├── queue.py         # DualJobQueue (SQLite)
    └── worker.py        # WorkerPool, RateLimiter
```

### Phase 3.5: Enhanced Core Features ✅ COMPLETE

**Additional features implemented during Phase 3:**

- [x] PDF Generation v2 with WeasyPrint + Jinja2 templates (`backend/core/pdf_generator_v2.py`)
- [x] White-label branding support (`backend/core/branding_config.py`)
- [x] Belief classification with LLM (`backend/core/belief_classifier.py`)
- [x] Intent classification for user messages (`backend/core/intent_classifier.py`)
- [x] Report RAG for semantic search within reports (`backend/core/report_rag.py`)
- [x] Report editing with LLM validation (`backend/core/report_editor.py`)
- [x] Chart generation with 15-year price history (`backend/core/chart_generator.py`)
- [x] Cost tracking per message/session (`backend/core/cost_tracker.py`)
- [x] PDF data collector for financial statements (`backend/core/pdf_data_collector.py`)

### Phase 4: Non-US Handling ✅ COMPLETE (2024-12-25)

- [x] Data router classifies US vs Non-US (`data_fetchers/data_router.py`)
- [x] Separate queue workers (3 US, 2 Non-US)
- [x] Create `analysis/non_us/orchestrator.py` (wrapper for legacy orchestrator)
- [x] Create `limitations.py` module (`data_fetchers/limitations.py`)
- [x] Add DataAvailabilityBanner component (`frontend/src/components/DataAvailabilityBanner.jsx`)
- [x] Gracefully disable unavailable tabs with "(US only)" labels
- [x] CompanyClassification with DataAvailability dataclass

### Phase 5: Enhanced Features ✅ COMPLETE (2024-12-25)

- [x] Insider trades fetching via FDS (`financial_datasets_client.py`)
- [x] Analyst estimates fetching via FDS
- [x] Insider trades analysis integration in report (`us/orchestrator.py`)
- [x] Analyst estimates analysis in fundamentals section
- [x] Cost tracking per data source

**Note:** These features are US-only by design (FinancialDatasets.ai coverage).

---

## 11. Cost Analysis

### Per-Analysis Costs

| Component | US Company | Non-US Company |
|-----------|------------|----------------|
| FinancialDatasets.ai | ~$0.10 | $0 |
| Gemini Search (5 queries) | ~$0.17 | ~$0.17 |
| OpenRouter LLM (7-8 calls) | ~$0.05 | ~$0.05 |
| Alpha Vantage | $0 | $0 (free tier) |
| yfinance | $0 | $0 |
| Reddit | $0 | $0 |
| **Total** | **~$0.32** | **~$0.22** |

### Monthly Projections

| Volume | US Analyses | Non-US Analyses | Monthly Cost |
|--------|-------------|-----------------|--------------|
| Low (50/month) | 40 | 10 | ~$15 |
| Medium (200/month) | 160 | 40 | ~$60 |
| High (500/month) | 400 | 100 | ~$150 |

### Savings from Refactoring

- **EODHD subscription eliminated**: -$80/month
- **More efficient API usage**: US companies don't waste Alpha Vantage quota
- **No more random yfinance failures**: Improved reliability

---

## Appendix A: File Structure (Final)

```
george_researcher_js/
├── src_george_researcher/
│   ├── data_fetchers/
│   │   ├── us/                        # FinancialDatasets.ai
│   │   │   ├── financial_datasets_client.py
│   │   │   ├── company_facts.py
│   │   │   ├── financials.py
│   │   │   ├── prices.py
│   │   │   ├── insider_trades.py
│   │   │   ├── analyst_estimates.py
│   │   │   └── news.py
│   │   ├── global/                    # yfinance + Alpha Vantage
│   │   │   ├── stock_data.py
│   │   │   ├── technical_indicators.py
│   │   │   ├── alpha_vantage_news.py
│   │   │   ├── reddit_sentiment.py
│   │   │   └── gemini_search.py
│   │   ├── company_registry.py
│   │   ├── data_router.py
│   │   └── types.py
│   │
│   ├── analysis/
│   │   ├── us/orchestrator.py
│   │   ├── global/orchestrator.py
│   │   ├── shared/
│   │   └── router.py
│   │
│   └── prompts/
│
├── backend/
│   ├── main.py                        # FastAPI app entry point
│   ├── routers/                       # FastAPI route handlers
│   │   ├── analysis.py
│   │   ├── companies.py
│   │   ├── chat.py
│   │   ├── reports.py
│   │   ├── sessions.py
│   │   └── chart.py
│   ├── models/                        # Pydantic models
│   │   ├── requests.py
│   │   └── responses.py
│   ├── jobs/                          # Background job system
│   │   ├── queue.py                   # DualJobQueue
│   │   ├── worker.py                  # Worker implementation
│   │   └── models.py                  # Job dataclasses
│   │
│   ├── core/
│   │   ├── session.py                 # Thread-safe
│   │   └── rate_limiter.py
│   │
│   └── api/                           # DEPRECATED (Flask)
│
├── frontend/
│   └── src/components/
│       ├── DataAvailabilityBanner.jsx # NEW
│       ├── QueueStatus.jsx            # NEW
│       └── ...
│
└── data/
    ├── jobs.db                        # SQLite job queue
    └── sessions/
```

---

## Appendix B: Migration Checklist

### Before Starting
- [ ] Get FinancialDatasets.ai API key
- [ ] Document current rate limits for all APIs
- [ ] Backup existing session data
- [ ] Cancel EODHD subscription

### Phase 1 Checklist
- [ ] `financial_datasets_client.py` created and tested
- [ ] `company_registry.py` created and tested
- [ ] SessionManager locks added
- [ ] `/api/companies/us-tickers` endpoint working

### Phase 2 Checklist
- [ ] FDS company facts integrated
- [ ] FDS financials integrated
- [ ] FDS prices integrated
- [ ] US orchestrator working
- [ ] All existing tests passing

### Phase 3 Checklist
- [ ] DualJobQueue implemented
- [ ] Worker threads running
- [ ] API returns job_id
- [ ] Frontend polling working
- [ ] Analysis survives browser close

### Phase 4 Checklist ✅ COMPLETE
- [x] Non-US orchestrator working (`analysis/non_us/orchestrator.py`)
- [x] DataAvailabilityBanner showing (integrated in AnalysisView)
- [x] Tabs disabled appropriately (Financials tab shows "US only")
- [x] Non-US analysis completing without errors

### Phase 5 Checklist ✅ COMPLETE
- [x] Insider trades in US analysis (integrated in orchestrator)
- [x] Analyst estimates in US analysis (in fundamentals section)
- [x] Cost tracking per data source
- [x] US-only features clearly documented

---

---

## Appendix C: Implementation Status

### Phase 0: Thread Safety ✅ COMPLETE

| Component | Status | Details |
|-----------|--------|---------|
| `SessionManager._lock` | ✅ Done | RLock for protecting `_sessions` dict |
| `SessionManager._session_locks` | ✅ Done | Per-session locks for fine-grained concurrency |
| `session_context()` method | ✅ Done | Context manager with auto-save |
| `analysis.py` updated | ✅ Done | Uses `session_context()` for all session modifications |
| `chat.py` updated | ✅ Done | Thread-safe message handling and report edits |
| `sessions.py` updated | ✅ Done | Thread-safe finalize and regenerate operations |

### Phase 1: Foundation Infrastructure ✅ COMPLETE

| Component | Status | Details |
|-----------|--------|---------|
| `data_fetchers/types.py` | ✅ Done | `CompanyRegion`, `DataAvailability`, `CompanyClassification` |
| `data_fetchers/company_registry.py` | ✅ Done | SEC CIK-based US detection, cached weekly |
| `data_fetchers/data_router.py` | ✅ Done | Routes to US/Non-US sources, backward-compatible |
| `api/companies.py` | ✅ Done | `/classify/<ticker>`, `/us-tickers`, `/search`, `/stats`, `/availability/<ticker>` |
| Blueprint registered | ✅ Done | `/api/companies/*` routes active |
| `FDS_API_KEY` in environment | ✅ Done | Added to `.env` and `.env.example` |

### Phase 2: FDS Integration ✅ COMPLETE

| Component | Status | Details |
|-----------|--------|---------|
| `data_fetchers/us/__init__.py` | ✅ Done | Module exports for FDS client |
| `data_fetchers/us/financial_datasets_client.py` | ✅ Done | Full FDS API client with all endpoints |
| `data_router.py` updated | ✅ Done | Routes US companies to FDS with yfinance fallback |
| FDS company facts | ✅ Done | `/company/facts` integration |
| FDS financials | ✅ Done | `/financials` integration |
| FDS prices | ✅ Done | `/prices` integration |
| FDS insider trades | ✅ Done | `/insider-trades` integration |
| FDS analyst estimates | ✅ Done | `/analyst-estimates` integration |
| FDS news | ✅ Done | `/news` integration |
| `analysis/us/financial_analysis.py` | ✅ Done | Financial statements analysis with highlights |
| API: `/financial-statements` | ✅ Done | Endpoint for fetching analyzed financial data |
| API: `/company-info` | ✅ Done | Endpoint for company classification info |
| Frontend: Financial Statements tab | ✅ Done | 3-statement tables with ratios and highlights |
| PDF: Financial Statements section | ✅ Done | Included before Sources with highlights |

### Remaining Phases

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 3: FastAPI + Job Queue | ✅ Complete | FastAPI, DualJobQueue, 5 workers |
| Phase 3.5: Enhanced Core | ✅ Complete | PDF v2, belief extraction, cost tracking |
| Phase 4: Non-US Handling | ✅ Complete | DataAvailabilityBanner, limitations.py, non_us module |
| Phase 5: Enhanced Features | ✅ Complete | Insider trades + analyst estimates for US |

---

## 12. Target Vision: Multi-User Beta Platform

### 12.1 The Goal

Transform George Researcher from a single-user prototype into a **multi-user beta platform** capable of:
- Supporting 10-50 concurrent beta testers
- User authentication (email/password)
- Per-user session isolation
- Data caching to reduce API costs and latency
- Usage tracking and cost attribution per user

**Note:** GDPR compliance is deferred - this is for controlled beta testing only.

### 12.2 Authentication System

**Simple Email/Password Auth (Beta Phase)**

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTH ARCHITECTURE                        │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │───▶│   FastAPI    │───▶│   SQLite     │  │
│  │  (JWT Token) │    │  Auth Router │    │  users.db    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                             │
│  Tables:                                                    │
│  - users (id, email, password_hash, created_at, is_active) │
│  - sessions (session_id, user_id, ...)                     │
│  - api_usage (user_id, endpoint, cost_usd, timestamp)      │
└─────────────────────────────────────────────────────────────┘
```

**Implementation:**
- Password hashing with bcrypt
- JWT tokens for session management
- Token refresh mechanism
- Simple registration/login flow

**New Endpoints:**
```
POST /api/auth/register     - Create account
POST /api/auth/login        - Get JWT token
POST /api/auth/refresh      - Refresh token
GET  /api/auth/me           - Get current user
POST /api/auth/logout       - Invalidate token
```

### 12.3 Data Caching Strategy

**Problem:** Every analysis fetches fresh data from:
- FinancialDatasets.ai (~$0.10/analysis)
- Gemini Search (~$0.17/analysis)
- yfinance (rate limit risk)
- Alpha Vantage (5 req/min bottleneck)

**Solution:** Multi-layer caching with TTL-based invalidation

```
┌─────────────────────────────────────────────────────────────┐
│                    CACHING ARCHITECTURE                     │
│                                                             │
│  Request → Cache Check → [HIT] → Return cached             │
│                ↓                                            │
│            [MISS]                                           │
│                ↓                                            │
│         Fetch from API                                      │
│                ↓                                            │
│         Store in cache with TTL                             │
│                ↓                                            │
│         Return fresh data                                   │
└─────────────────────────────────────────────────────────────┘
```

**Cache Tiers:**

| Data Type | Storage | TTL | Key Pattern |
|-----------|---------|-----|-------------|
| **Stock Prices** | SQLite | 15 min | `prices:{ticker}:{date}` |
| **Company Facts** | SQLite | 7 days | `company:{ticker}` |
| **Financials** | SQLite | 24 hours | `financials:{ticker}:{period}` |
| **News Search** | SQLite | 1 hour | `news:{ticker}:{query_hash}` |
| **Gemini Search** | SQLite | 4 hours | `gemini:{query_hash}` |
| **SEC Filings** | File | 30 days | `data/cache/sec/{ticker}/{filing_type}.json` |
| **Embeddings** | File | 30 days | `data/embeddings/{ticker}/` |

**Implementation:**

```python
# backend/core/data_cache.py

class DataCache:
    def __init__(self, db_path: str = "data/cache.db"):
        self.db_path = db_path

    async def get(self, key: str) -> Optional[dict]:
        """Get cached data if not expired."""
        async with aiosqlite.connect(self.db_path) as db:
            row = await db.execute(
                "SELECT data, expires_at FROM cache WHERE key = ?", (key,)
            )
            if row and datetime.fromisoformat(row['expires_at']) > datetime.utcnow():
                return json.loads(row['data'])
        return None

    async def set(self, key: str, data: dict, ttl_seconds: int):
        """Cache data with TTL."""
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO cache (key, data, expires_at, created_at)
                   VALUES (?, ?, ?, ?)""",
                (key, json.dumps(data), expires_at.isoformat(), datetime.utcnow().isoformat())
            )
            await db.commit()
```

**Cache Integration Points:**

```python
# In data_fetchers/stock_data.py
async def get_stock_data(ticker: str) -> StockData:
    cache_key = f"stock:{ticker}"

    # Check cache first
    cached = await data_cache.get(cache_key)
    if cached:
        return StockData(**cached)

    # Fetch fresh
    data = await fetch_from_yfinance(ticker)

    # Cache for 15 minutes
    await data_cache.set(cache_key, data.to_dict(), ttl_seconds=900)

    return data
```

**Cost Savings Projection:**

| Scenario | Without Cache | With Cache | Savings |
|----------|---------------|------------|---------|
| Same ticker analyzed 5x/day | $1.60 | $0.32 | 80% |
| 10 users analyze AAPL | $3.20 | $0.32 | 90% |
| Popular ticker (50 analyses) | $16.00 | $0.32 | 98% |

### 12.4 User Session Isolation

**Current:** Sessions stored by session_id only
**Target:** Sessions scoped to user_id

```python
# Current: data/sessions/{session_id}.json
# Target:  data/sessions/{user_id}/{session_id}.json

class UserSessionManager:
    def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all sessions for a user."""
        user_dir = Path(f"data/sessions/{user_id}")
        return [self.load(f) for f in user_dir.glob("*.json")]

    def create_session(self, user_id: str, ticker: str) -> Session:
        """Create session scoped to user."""
        session = Session(
            session_id=str(uuid4()),
            user_id=user_id,
            ticker=ticker,
            created_at=datetime.utcnow()
        )
        self.save(session)
        return session
```

### 12.5 Usage Tracking

Track API usage per user for:
- Cost attribution
- Usage limits (if needed)
- Beta feedback prioritization

```sql
CREATE TABLE api_usage (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    ticker TEXT,
    cost_usd REAL DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Query: Total cost by user this month
SELECT user_id, SUM(cost_usd) as total_cost
FROM api_usage
WHERE timestamp >= date('now', 'start of month')
GROUP BY user_id;
```

---

## 13. Gap Analysis: Current State to Target

### 13.1 Current State Summary

| Component | Status | Notes |
|-----------|--------|-------|
| **Backend Framework** | ✅ FastAPI | Async, modern, production-ready |
| **Job Queue** | ✅ DualJobQueue | SQLite persistence, 5 workers |
| **Session Storage** | ✅ JSON files | User-scoped directories |
| **Authentication** | ✅ Complete | Email/password + JWT + whitelist |
| **Data Caching** | ✅ SQLite cache | TTL-based, decorator pattern |
| **User Isolation** | ✅ Complete | Sessions scoped to user, ownership verified |
| **Usage Tracking** | ✅ Complete | Per-user cost attribution |
| **Rate Limiting** | ✅ Per-queue | Token bucket per API |

### 13.2 Implementation Roadmap

#### Phase 6: Data Caching Layer ✅ COMPLETE (2024-12-24)

**Status:** Implemented with TTL-based SQLite cache and decorator pattern.

| Task | Status |
|------|--------|
| Create cache module with `DataCache` class | ✅ Done |
| Add cache table to SQLite schema | ✅ Done |
| Integrate cache in `stock_data.py` | ✅ Done (3 functions) |
| Integrate cache in `gemini_search.py` | ✅ Done |
| Integrate cache in FDS client | ✅ Done (6 functions) |
| Add cache stats endpoint | ✅ Done |
| Cache invalidation API | ✅ Done |

**Files created:**
```
src_george_researcher/
├── data_fetchers/
│   └── cache.py                # DataCache class + @cached decorator
backend/
├── routers/
│   └── cache.py                # /api/cache/* endpoints
```

**Files modified:**
```
src_george_researcher/
├── data_fetchers/
│   ├── stock_data.py           # @cached on 3 functions
│   ├── gemini_search.py        # @cached with exclude_params
│   └── us/
│       └── financial_datasets_client.py  # @cached on 6 functions
backend/
├── routers/__init__.py         # Added cache export
├── main.py                     # Registered cache router
```

**TTL Configuration:**
| Data Type | TTL | Cost Saved |
|-----------|-----|------------|
| gemini_search | 2h | $0.035/hit |
| fds_prices | 24h | $0.01/hit |
| fds_financials | 7d | $0.02/hit |
| fds_analyst_estimates | 7d | $0.02/hit |
| fds_insider_trades | 7d | $0.02/hit |
| fds_news | 2h | $0.02/hit |
| yfinance_* | 24h | Rate limit protection |

**API Endpoints:**
- `GET /api/cache/stats` - Statistics and cost savings
- `POST /api/cache/invalidate?ticker=X&data_type=Y` - Manual invalidation
- `POST /api/cache/cleanup` - Remove expired entries
- `GET /api/cache/health` - Configuration and status

#### Phase 7: Authentication System ✅ COMPLETE (2024-12-25)

**Status:** Implemented with email/password auth, JWT tokens, and whitelist-based registration.

| Task | Status |
|------|--------|
| Create users table schema | ✅ Done |
| Implement password hashing (bcrypt) | ✅ Done |
| Create auth router | ✅ Done |
| JWT token generation/validation | ✅ Done |
| Auth middleware for protected routes | ✅ Done |
| Frontend login/register UI | ✅ Done |
| **Whitelist-based registration** | ✅ Done |

**Whitelist System:**
- Registration requires email to be on whitelist
- Whitelist file: `data/authorized_users.csv`
- Unauthorized emails rejected with friendly message
- Easy to add/remove beta users

**Files created:**
```
backend/
├── core/
│   ├── auth.py                 # Auth logic, JWT, hashing, whitelist
│   └── auth_db.py              # SQLite user/token storage
├── routers/
│   └── auth.py                 # Login, register, refresh, logout
├── middleware/
│   └── auth_middleware.py      # JWT validation, get_current_user
data/
├── auth.db                     # Users and refresh tokens
└── authorized_users.csv        # Beta user whitelist
frontend/
├── src/
│   ├── components/
│   │   ├── LoginForm.jsx
│   │   ├── RegisterForm.jsx
│   │   └── AuthModal.jsx
│   └── contexts/
│       └── AuthContext.jsx     # Auth state management
```

**API Endpoints:**
```
POST /api/auth/register     - Create account (whitelist required)
POST /api/auth/login        - Get JWT token
POST /api/auth/refresh      - Refresh access token
GET  /api/auth/me           - Get current user
POST /api/auth/logout       - Invalidate refresh token
```

**Beta Users (Pre-registered):**
- matthieu.separt@gmail.com
- rami.sghaier@amundi.com
- samy.debbah@amundi.com

#### Phase 8: User-Scoped Sessions ✅ COMPLETE (2024-12-25)

**Why third:** Builds on auth to isolate user data.

| Task | Status |
|------|--------|
| Migrate session storage to user directories | ✅ Done |
| Update SessionManager for user scoping | ✅ Done |
| Update session API endpoints | ✅ Done |
| Migrate existing sessions | ✅ 37 sessions migrated to matthieu.separt |
| Update frontend session browser | ✅ Done |

**Implementation Details:**
- Sessions now stored in `data/sessions/{user_id}/{session_id}.json`
- `AnalysisSession` dataclass has `user_id` field
- `SessionManager` methods: `get_session_for_user()`, `list_sessions(user_id)`, `migrate_session_to_user()`
- All routers (sessions, analysis, chat, reports) require auth and verify ownership
- Frontend `SessionBrowser` uses authenticated axios client

#### Phase 9: Usage Tracking ✅ COMPLETE (2024-12-25)

| Task | Status |
|------|--------|
| Create api_usage table | ✅ Done |
| Add tracking middleware | ✅ Done |
| Create usage dashboard endpoint | ✅ Done |
| Frontend usage display | ✅ Done |

**Implementation:**
- `backend/core/usage_db.py` - UsageDB class with `api_usage` table
- `backend/middleware/usage_tracker.py` - `track_request()` helper
- `backend/routers/usage.py` - 5 endpoints (/me, /summary, /daily, /costs, /stats)
- `frontend/src/components/UsageStats.jsx` - Modal showing usage stats

### 13.3 Implementation Order

1. **Phase 6: Data Caching** - ✅ COMPLETE (2024-12-24)
2. **Phase 7: Authentication** - ✅ COMPLETE (2024-12-25)
3. **Phase 8: User-Scoped Sessions** - ✅ COMPLETE (2024-12-25)
4. **Phase 9: Usage Tracking** - ✅ COMPLETE (2024-12-25)

**All phases complete!** Platform is production-ready for beta.

### 13.4 Database Schema (Target State)

```sql
-- data/app.db (consolidated from jobs.db + new tables)

-- Existing: Jobs table (from jobs.db)
CREATE TABLE jobs (...);

-- NEW: Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- NEW: Cache table
CREATE TABLE cache (
    key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0
);

-- NEW: Usage tracking
CREATE TABLE api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    ticker TEXT,
    cost_usd REAL DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    cached BOOLEAN DEFAULT FALSE,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- NEW: Sessions linked to users
CREATE TABLE user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_accessed_at TEXT,
    is_archived BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes
CREATE INDEX idx_cache_expires ON cache(expires_at);
CREATE INDEX idx_usage_user ON api_usage(user_id);
CREATE INDEX idx_usage_timestamp ON api_usage(timestamp);
CREATE INDEX idx_sessions_user ON user_sessions(user_id);
```

### 13.5 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cache invalidation bugs | Medium | High | Conservative TTLs, manual invalidation |
| JWT security issues | Low | High | Use established library (python-jose) |
| Migration data loss | Low | Medium | Backup before migration |
| Rate limit exceeded during beta | Medium | Medium | Per-user soft limits |
| API costs spike | Medium | High | Cache layer + usage monitoring |

### 13.6 Success Metrics for Beta

| Metric | Target |
|--------|--------|
| Concurrent users supported | 10-50 |
| Cache hit rate | >60% |
| Average analysis cost | <$0.15 (down from $0.32) |
| System uptime | >95% |
| API response time (cached) | <500ms |
| User registration success | >95% |

---

*Document Version: 2.5*
*Last Updated: December 2024*
*All Phases (0-9): Complete*
*Platform Status: Production-Ready for Beta*
