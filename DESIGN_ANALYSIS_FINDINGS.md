# Software Design Analysis Findings

**Codebase**: Constant - Financial Analysis Platform
**Analyzed**: 2026-01-21
**Scope**: Full audit against software design principles checklist

---

## Executive Summary

The codebase demonstrates **good foundational practices** including:
- Frozen dataclasses for immutability
- Functional interfaces with `(result, error)` tuples
- No utils.py/helpers.py anti-patterns
- Proper use of pathlib for paths
- Good separation of concerns in data fetchers

**Critical issues** requiring attention:
1. **Shallow wrapper modules** that add no value
2. **Duplicated LLM_PRICING** data across two files
3. **Temporal decomposition** in orchestrator requiring 8+ sequential calls
4. **20+ magic number constants** without documentation of impact
5. **Minimal test coverage** - only manual integration tests exist

---

## Phase 1: Configuration & Foundation

### Findings

| Issue | File:Line | Severity | Status |
|-------|-----------|----------|--------|
| Config uses frozen dataclass ✓ | `config.py:16` | N/A | Good |
| Validation function exists ✓ | `config.py:53` | N/A | Good |
| Uses pathlib throughout ✓ | `config.py:24-25` | N/A | Good |
| JWT secret defaults to weak dev value | `auth.py:25` | Moderate | Needs fix |
| Bcrypt rounds undocumented | `auth.py:91` | Minor | Needs comment |

#### Issue 1.1: JWT Secret Default Value (Moderate)

**Location**: `backend/core/auth.py:25`
```python
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
```

**Problem**: Weak default that could accidentally reach production.

**Recommendation**: Remove default or fail fast if not set:
```python
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable must be set")
```

#### Issue 1.2: Magic Numbers Without Impact Documentation (Moderate)

**Location**: `src_george_researcher/analysis_agents.py:31-53`

```python
INITIAL_RESEARCH_LIMIT = 2500      # Initial research in topic identification
FULL_REPORT_FUNDAMENTALS_LIMIT = 1500  # Fundamentals in full report (increased)
# ... 20+ more constants
```

**Problem**: Comments describe *what* the value is for, but not *what happens if you change it*. This violates the "variable comment requirements" checklist item.

**Recommendation**: Add impact documentation:
```python
# Initial research character limit for topic identification prompts.
# Increasing: More context but higher token cost (~0.001 USD/1000 chars)
# Decreasing: Faster/cheaper but may miss important context
INITIAL_RESEARCH_LIMIT = 2500
```

---

## Phase 2: Module Depth & Interface Design

### Critical Issues

#### Issue 2.1: Shallow Wrapper Module - llm_wrapper.py (Critical)

**Location**: `backend/agents/llm_wrapper.py`

**Problem**: This module is a classic example of a "shallow module" - it adds almost no functionality over the underlying `src_george_researcher.llm` module. It primarily:
1. Re-exports `call_llm`
2. Adds `get_llm_response()` which just wraps config loading
3. Defines duplicate `LLMConfig` and `LLMResult` dataclasses

The module docstring even admits: "Re-exports: call_llm..."

**Impact**: Forces callers to understand two layers of abstraction for no benefit.

**Recommendation - Option A (Preferred)**: Delete `llm_wrapper.py` and have consumers import directly:
```python
# Instead of:
from backend.agents.llm_wrapper import get_llm_response
# Use:
from src_george_researcher.llm import call_llm
from src_george_researcher.config import load_config
```

**Recommendation - Option B**: If wrapper must exist, add real value like caching, retry logic, or circuit breakers.

#### Issue 2.2: Temporal Decomposition in Orchestrator (Critical)

**Location**: `src_george_researcher/orchestrator.py:510-664`

**Problem**: The `run_analysis()` function requires calling 8+ functions in exact sequence:
1. `validate_config()`
2. `ensure_directories()`
3. `_fetch_all_data_sources()`
4. `_run_individual_analyses()`
5. `_run_bull_bear_debate()`
6. `synthesize_recommendation()`
7. `filter_relevant_sources()`
8. Return `FullAnalysis`

This is textbook "temporal decomposition" - the order matters but isn't enforced by the interface.

**Impact**: Callers can accidentally call functions out of order. Error handling becomes complex.

**Recommendation**: Consolidate into a pipeline class or use a builder pattern:
```python
class AnalysisPipeline:
    """Enforces correct execution order through API design."""

    def __init__(self, symbol: str, config: Config):
        self.symbol = symbol
        self.config = config
        self._fetched = None
        self._analyzed = None

    def run(self) -> FullAnalysis:
        """Single entry point - no temporal decomposition exposed."""
        self._fetched = self._fetch_data()
        self._analyzed = self._analyze()
        return self._synthesize()
```

#### Issue 2.3: Orchestrator Wrapper Also Shallow (Moderate)

**Location**: `backend/agents/orchestrator_wrapper.py`

**Problem**: Another thin adapter that mostly re-exports:
```python
run_analysis = orch.run_analysis  # Line 49
Config = cfg.Config
load_config = cfg.load_config
```

The only added value is `run_full_analysis()` which routes US vs non-US.

**Recommendation**: Move the US/non-US routing logic into the main orchestrator module, eliminating the wrapper.

#### Issue 2.4: Information Leakage - Intermediate Types Exposed (Moderate)

**Location**: `src_george_researcher/orchestrator.py:135-159`

```python
@dataclass
class FetchedData:  # Exposed intermediate state
    ...

@dataclass
class AnalysisResults:  # Exposed intermediate state
    ...
```

**Problem**: These intermediate containers are exposed as public types but shouldn't be part of the API surface. They leak implementation details about the analysis pipeline.

**Recommendation**: Prefix with underscore or move to private module:
```python
@dataclass
class _FetchedData:  # Private intermediate state
    ...
```

---

## Phase 3: Type System & Data Contracts

### Findings

| Issue | File:Line | Severity | Status |
|-------|-----------|----------|--------|
| StockInfo properly typed ✓ | `stock_data.py:23-97` | N/A | Good |
| LLMResponse frozen dataclass ✓ | `llm.py:51-61` | N/A | Good |
| All fields have type hints ✓ | Throughout | N/A | Good |
| Mixed schema in StockInfo | `stock_data.py:49-93` | Minor | Design choice |
| Session metadata bypasses types | `session.py:56` | Moderate | Needs fix |

#### Issue 3.1: Untyped Metadata Dict (Moderate)

**Location**: `backend/core/session.py:56`

```python
@dataclass
class AnalysisSession:
    ...
    metadata: Dict = field(default_factory=dict)  # Untyped!
```

**Problem**: The `metadata` dict accepts anything, bypassing the type system. Looking at usage, it stores structured data like:
- `total_cost_usd`
- `total_tokens`
- `cost_breakdown`
- `is_us`
- `contradictions`
- `research_gaps`

**Recommendation**: Define a TypedDict for session metadata:
```python
from typing import TypedDict, List

class SessionMetadata(TypedDict, total=False):
    total_cost_usd: float
    total_tokens: int
    cost_breakdown: dict
    is_us: bool
    contradictions: List[dict]
    research_gaps: List[dict]

@dataclass
class AnalysisSession:
    metadata: SessionMetadata = field(default_factory=dict)
```

#### Issue 3.2: StockInfo Dual Schema Support (Minor - Design Choice)

**Location**: `stock_data.py:49-93`

```python
price_to_book: Optional[float] = None  # yfinance name
pb_ratio: Optional[float] = None  # FDS name (alias)
```

**Problem**: The dataclass has duplicate fields for yfinance vs FinancialDatasets.ai naming conventions.

**Analysis**: This is a reasonable design choice given the need to support two data sources. The aliases are documented. However, it means consumers must check both fields.

**Recommendation (Optional)**: Add properties to normalize access:
```python
@property
def price_to_book_normalized(self) -> Optional[float]:
    """Returns P/B ratio from either data source."""
    return self.price_to_book or self.pb_ratio
```

---

## Phase 4: Error Handling & Resilience

### Findings

| Issue | File:Line | Severity | Status |
|-------|-----------|----------|--------|
| Consistent (result, error) tuples ✓ | `stock_data.py`, `news.py` | N/A | Good |
| Graceful degradation in news ✓ | `news.py:271-310` | N/A | Good |
| Timeout handling ✓ | `llm.py:141-148` | N/A | Good |
| No custom exception classes | Throughout | Minor | Could improve |
| No circuit breakers | External API calls | Moderate | Missing |

#### Issue 4.1: Generic Exception Types (Minor)

**Location**: Throughout codebase

**Problem**: All exceptions are generic Python types (`ValueError`, `Exception`). No domain-specific exceptions exist.

**Current pattern**:
```python
except Exception as e:
    return (None, str(e))
```

**Recommendation**: Define domain exceptions for better error handling:
```python
# src_george_researcher/exceptions.py
class AnalysisError(Exception):
    """Base exception for analysis errors."""
    pass

class DataFetchError(AnalysisError):
    """Failed to fetch external data."""
    pass

class LLMError(AnalysisError):
    """LLM API call failed."""
    pass

class RateLimitError(AnalysisError):
    """API rate limit exceeded."""
    retry_after: Optional[int] = None
```

#### Issue 4.2: No Circuit Breaker for External APIs (Moderate)

**Location**: `llm.py`, `news.py`, `stock_data.py`

**Problem**: External API calls have no circuit breaker pattern. If an API starts failing, we'll keep hitting it.

**Recommendation**: Implement simple circuit breaker:
```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    reset_timeout: timedelta = timedelta(minutes=5)
    _failures: int = 0
    _last_failure: datetime = None
    _open: bool = False

    def record_failure(self):
        self._failures += 1
        self._last_failure = datetime.now()
        if self._failures >= self.failure_threshold:
            self._open = True

    def is_open(self) -> bool:
        if self._open and self._last_failure:
            if datetime.now() - self._last_failure > self.reset_timeout:
                self._open = False
                self._failures = 0
        return self._open
```

---

## Phase 5: Code Organization & Naming

### Findings

| Issue | File:Line | Severity | Status |
|-------|-----------|----------|--------|
| No utils.py in app code ✓ | N/A | N/A | Good |
| No helpers.py in app code ✓ | N/A | N/A | Good |
| Clear module purposes ✓ | Throughout | N/A | Good |
| "v2" naming in filename | `pdf_generator_v2.py` | Minor | Should rename |
| Large file: orchestrator.py | 29KB, 776 lines | Moderate | Could split |
| Large file: analysis_agents.py | 21KB, 578 lines | Moderate | Could split |
| Duplicated LLM_PRICING | Two locations | Critical | Must fix |

#### Issue 5.1: Duplicated LLM_PRICING Data (Critical)

**Locations**:
- `src_george_researcher/llm.py:14-40`
- `backend/core/cost_tracker.py:21-41`

**Problem**: Pricing data is defined in two places with slightly different models covered. This will drift out of sync.

**llm.py version**:
```python
LLM_PRICING = {
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "anthropic/claude-4-sonnet": {"input": 3.00, "output": 15.00},
    # ... includes Claude 4 models
}
```

**cost_tracker.py version**:
```python
OPENROUTER_PRICING = {
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    # ... doesn't include Claude 4 models
}
```

**Recommendation**: Create single source of truth:
```python
# src_george_researcher/pricing.py
"""LLM pricing data - single source of truth."""

LLM_PRICING = {
    # Claude 4 series (Dec 2024)
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    ...
}

def get_pricing(model: str) -> dict:
    return LLM_PRICING.get(model, LLM_PRICING["default"])
```

Then import from both locations.

#### Issue 5.2: "v2" Filename Anti-pattern (Minor)

**Location**: `backend/core/pdf_generator_v2.py`

**Problem**: Version numbers in filenames indicate incomplete migration. If v2 is the current version, rename to `pdf_generator.py` and delete v1.

**Recommendation**:
```bash
mv backend/core/pdf_generator_v2.py backend/core/pdf_generator.py
# Update all imports
```

#### Issue 5.3: Large Orchestrator Files (Moderate)

**Locations**:
- `src_george_researcher/orchestrator.py` - 776 lines
- `src_george_researcher/analysis_agents.py` - 578 lines

**Problem**: Files over 500 lines often violate single responsibility.

**Recommendation for orchestrator.py**: Split into:
- `orchestrator/pipeline.py` - Main orchestration logic
- `orchestrator/data_fetching.py` - `_fetch_all_data_sources()`
- `orchestrator/debate.py` - `_run_bull_bear_debate()`

**Recommendation for analysis_agents.py**: Already well-organized by function. The size is acceptable given the number of distinct analysis functions.

---

## Phase 6: Functional vs OOP Balance

### Findings

| Issue | File:Line | Severity | Status |
|-------|-----------|----------|--------|
| Frozen dataclasses for data ✓ | Throughout | N/A | Good |
| Pure functions for analysis ✓ | `analysis_agents.py` | N/A | Good |
| Classes for stateful entities ✓ | `SessionManager`, `BeliefGraph` | N/A | Good |
| Session requires manual save() | `session.py` | Moderate | Design issue |
| Global singleton patterns | Multiple | Minor | Could improve |

#### Issue 6.1: Session Temporal Coupling (Moderate)

**Location**: `backend/core/session.py:278-329`

**Problem**: After modifying a session, callers must remember to call `save()`:
```python
session.add_message('user', 'Hello')
session_manager._save_session(session)  # Easy to forget!
```

The context manager helps but isn't enforced:
```python
with session_manager.session_context(session_id) as session:
    session.add_message('user', 'Hello')
    # Auto-saved on exit
```

**Recommendation**: Make session modifications immediately persistent or require context manager:
```python
class AnalysisSession:
    def __init__(self, ..., on_change: Callable = None):
        self._on_change = on_change

    def add_message(self, ...):
        msg = Message(...)
        self.conversation_history.append(msg)
        if self._on_change:
            self._on_change(self)  # Auto-persist
        return msg
```

#### Issue 6.2: Global Singleton Patterns (Minor)

**Locations**:
- `session.py:605`: `session_manager = SessionManager()`
- `data_router.py:322`: `_router_instance: Optional[DataRouter] = None`
- `cost_tracker.py:254`: `global_tracker = CostTracker()`

**Problem**: Global singletons make testing harder and hide dependencies.

**Recommendation**: Use dependency injection where possible, or document singleton usage in module docstrings.

---

## Phase 7: Documentation & Comments

### Findings

| Issue | File:Line | Severity | Status |
|-------|-----------|----------|--------|
| Module docstrings present ✓ | All major files | N/A | Good |
| API rate limits documented ✓ | `news.py:1-17` | N/A | Good |
| Function docstrings present ✓ | Most functions | N/A | Good |
| Magic numbers lack impact docs | `analysis_agents.py` | Moderate | Needs fix |
| Complexity analysis in BeliefGraph ✓ | `belief_graph.py:83-91` | N/A | Good |

#### Issue 7.1: Constants Without Impact Documentation (Moderate)

Already covered in Phase 1, Issue 1.2. The 20+ token limit constants lack documentation about what happens when you change them.

#### Positive Finding: Good API Documentation

**Location**: `news.py:1-17`

```python
"""
News and sentiment data fetching from Alpha Vantage and EODHD.

API Info:
- Alpha Vantage NEWS_SENTIMENT API
  - Requires API key (free tier available)
  - Rate limit: 5 calls/minute, 500 calls/day on free tier
  - Premium tiers available for higher limits
  - Timeout: 30 seconds
...
"""
```

This is excellent documentation that should be replicated in other data fetcher modules.

---

## Phase 8: Testing Strategy

### Findings

| Issue | File:Line | Severity | Status |
|-------|-----------|----------|--------|
| Manual integration tests only | `test_api.py` | Critical | Needs improvement |
| No unit tests | N/A | Critical | Missing |
| No mocks for external APIs | N/A | Moderate | Missing |
| No property-based tests | N/A | Minor | Could add |

#### Issue 8.1: Minimal Test Coverage (Critical)

**Location**: `backend/test_api.py`

**Problem**: The only test file is a manual integration test that requires:
1. Running server first
2. Making actual API calls
3. Manual verification

```python
def run_all_tests():
    """Run all API tests."""
    # ... requires server running
    # ... makes real HTTP calls
```

**Current coverage**: ~0% unit tests, manual integration tests only.

**Recommendation**: Add comprehensive test suite:

```python
# tests/unit/test_llm.py
import pytest
from unittest.mock import patch
from src_george_researcher.llm import call_llm, LLMResponse

def test_call_llm_success():
    """Test successful LLM call."""
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value.status_code = 200
        mock_client.return_value.__enter__.return_value.post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Hello"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }

        result = call_llm(
            api_key="test",
            model="anthropic/claude-3-haiku",
            system_prompt="You are helpful.",
            user_prompt="Say hello"
        )

        assert result.success
        assert result.content == "Hello"
        assert result.tokens_used == 15

def test_call_llm_timeout():
    """Test LLM timeout handling."""
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")

        result = call_llm(
            api_key="test",
            model="anthropic/claude-3-haiku",
            system_prompt="",
            user_prompt=""
        )

        assert not result.success
        assert "timed out" in result.error
```

**Test structure recommendation**:
```
tests/
├── unit/
│   ├── test_llm.py
│   ├── test_config.py
│   ├── test_session.py
│   ├── test_belief_graph.py
│   └── data_fetchers/
│       ├── test_stock_data.py
│       └── test_news.py
├── integration/
│   ├── test_orchestrator.py
│   └── test_api_endpoints.py
└── conftest.py  # Shared fixtures
```

---

## Prioritized Action Items

### Critical (Fix Immediately)

1. **Consolidate LLM_PRICING** - Single source of truth for pricing data
   - Impact: Data will drift, causing incorrect cost calculations
   - Effort: ~1 hour

2. **Add unit tests** - At minimum for `llm.py`, `config.py`, `session.py`
   - Impact: No way to verify refactoring doesn't break things
   - Effort: ~4 hours for basic coverage

3. **Evaluate shallow wrappers** - Decide: delete or add real value
   - Impact: Unnecessary complexity in codebase
   - Effort: ~2 hours

### Moderate (Fix Soon)

4. **Document magic number impacts** - Add "what if you change this?" comments
   - Impact: Contributors can't safely tune parameters
   - Effort: ~2 hours

5. **Type the metadata dict** - Use TypedDict for SessionMetadata
   - Impact: Type safety gaps
   - Effort: ~1 hour

6. **Add circuit breaker** - For external API resilience
   - Impact: Cascading failures when APIs down
   - Effort: ~2 hours

7. **Fix JWT secret default** - Remove weak default or fail fast
   - Impact: Security risk
   - Effort: ~15 minutes

### Minor (Nice to Have)

8. **Rename pdf_generator_v2.py** - Remove version from filename
9. **Add custom exceptions** - Domain-specific error types
10. **Split large orchestrator** - If it grows further

---

## Verification Commands

After making changes, verify with:

```bash
# Run existing integration tests
cd backend && python test_api.py

# Start the application
./start.sh

# Test key flows manually:
# 1. Start analysis for a US ticker (e.g., AAPL)
# 2. Start analysis for a non-US ticker (e.g., TSM)
# 3. Chat with the analysis
# 4. Export PDF

# Type checking (after adding mypy to dependencies)
mypy backend/ src_george_researcher/ --ignore-missing-imports
```

---

## Appendix: Files Analyzed

| Directory | Files Analyzed | Lines of Code |
|-----------|---------------|---------------|
| `src_george_researcher/` | 8 | ~2,500 |
| `backend/core/` | 6 | ~1,800 |
| `backend/agents/` | 2 | ~280 |
| `src_george_researcher/data_fetchers/` | 5 | ~1,200 |
| **Total** | **21** | **~5,780** |
