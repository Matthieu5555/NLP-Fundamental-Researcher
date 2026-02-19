# Design Implementation Guide

**Project**: Constant - Financial Analysis Platform
**Purpose**: Step-by-step guide to implement design improvements
**Estimated Total Time**: 8-12 hours across multiple sessions

---

## Before You Start

### Understanding the Codebase

This is a financial analysis platform with:
- **Frontend**: React app in `frontend/`
- **Backend**: FastAPI in `backend/`
- **Core Logic**: Analysis agents in `src_george_researcher/`

The architecture has two data paths:
- **US companies**: Use FinancialDatasets.ai API (rich data)
- **Non-US companies**: Use yfinance + Gemini Search (limited data)

### How to Run the App

```bash
# Start everything
./start.sh

# Or manually:
cd backend && uv run uvicorn main:app --port 5001 --reload &
cd frontend && npm run dev &
```

### How to Verify Changes Don't Break Things

```bash
# 1. Run existing integration test
cd backend && python test_api.py

# 2. Manual smoke test (after starting app):
#    - Go to http://localhost:5173
#    - Analyze AAPL (US company)
#    - Analyze TSM (non-US company)
#    - Chat with the analysis
#    - Export PDF
```

---

## Implementation Order

The changes are ordered by:
1. **Dependencies** - Fix foundational issues first
2. **Risk** - Low-risk changes before high-risk
3. **Verification** - Each step is independently testable

```
Phase 1: Create shared pricing module (15 min)
    ↓
Phase 2: Add unit test infrastructure (1 hour)
    ↓
Phase 3: Write tests for existing code (2 hours)
    ↓
Phase 4: Fix configuration issues (30 min)
    ↓
Phase 5: Type the metadata dict (30 min)
    ↓
Phase 6: Document magic numbers (1 hour)
    ↓
Phase 7: Evaluate wrapper modules (2 hours)
    ↓
Phase 8: Add circuit breaker (1 hour)
```

---

## Phase 1: Create Shared Pricing Module

**Why first**: Two files have duplicated LLM pricing data. This will cause bugs when prices change. Fix before adding tests so tests use the correct source.

**Time**: 15 minutes

### Step 1.1: Create the shared module

Create `src_george_researcher/pricing.py`:

```python
"""
LLM and API pricing data - single source of truth.

Pricing is per 1 million tokens (USD).
Last updated: January 2025

To update prices:
1. Check OpenRouter: https://openrouter.ai/docs/models
2. Check Google AI: https://ai.google.dev/pricing
3. Update the dicts below
4. Run tests to verify cost calculations
"""

from typing import Dict

# OpenRouter LLM pricing (per 1M tokens)
LLM_PRICING: Dict[str, Dict[str, float]] = {
    # Anthropic Claude 4 series
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "anthropic/claude-4-sonnet": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4": {"input": 15.00, "output": 75.00},
    "anthropic/claude-4-opus": {"input": 15.00, "output": 75.00},

    # Anthropic Claude 3.x series
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3.5-haiku": {"input": 0.80, "output": 4.00},
    "anthropic/claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "anthropic/claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3-opus": {"input": 15.00, "output": 75.00},

    # OpenAI models
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "openai/gpt-3.5-turbo": {"input": 0.50, "output": 1.50},

    # Google models via OpenRouter
    "google/gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "google/gemini-2.0-flash-exp": {"input": 0.00, "output": 0.00},
    "google/gemini-flash-1.5": {"input": 0.075, "output": 0.30},
    "google/gemini-pro": {"input": 0.125, "output": 0.375},
    "google/gemini-pro-1.5": {"input": 1.25, "output": 5.00},

    # Native Gemini API
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash": {"input": 0.10, "output": 0.40},

    # Default fallback (conservative estimate)
    "default": {"input": 3.00, "output": 15.00},
}

# Gemini Search Grounding pricing (per query)
GEMINI_SEARCH_PRICE_PER_QUERY = 0.014  # $14 per 1,000 queries


def get_llm_pricing(model: str) -> Dict[str, float]:
    """
    Get pricing for an LLM model.

    Args:
        model: Model identifier (e.g., "anthropic/claude-3-haiku")

    Returns:
        Dict with "input" and "output" prices per 1M tokens
    """
    return LLM_PRICING.get(model, LLM_PRICING["default"])


def calculate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for an LLM API call.

    Args:
        model: Model identifier
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens

    Returns:
        Cost in USD
    """
    pricing = get_llm_pricing(model)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost
```

### Step 1.2: Update llm.py to use shared module

Edit `src_george_researcher/llm.py`:

```python
# Remove the LLM_PRICING dict (lines 14-40)
# Remove the _calculate_cost function (lines 43-48)

# Add this import at the top:
from .pricing import calculate_llm_cost

# The call_llm function already calls _calculate_cost,
# just change line 129 from:
#     cost_usd = _calculate_cost(model, input_tokens, output_tokens)
# to:
#     cost_usd = calculate_llm_cost(model, input_tokens, output_tokens)
```

### Step 1.3: Update cost_tracker.py to use shared module

Edit `backend/core/cost_tracker.py`:

```python
# Remove OPENROUTER_PRICING dict (lines 21-41)
# Remove GEMINI_SEARCH_PRICE_PER_QUERY (line 45)
# Remove calculate_llm_cost function (lines 113-140)
# Remove calculate_search_cost function (lines 143-155)

# Add these imports at the top:
import sys
from pathlib import Path

# Ensure src_george_researcher is importable
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src_george_researcher.pricing import (
    calculate_llm_cost,
    GEMINI_SEARCH_PRICE_PER_QUERY,
)

# Add local calculate_search_cost that uses the imported constant:
def calculate_search_cost(num_queries: int = 1) -> float:
    """Calculate cost for Gemini Search Grounding queries."""
    return num_queries * GEMINI_SEARCH_PRICE_PER_QUERY
```

### Step 1.4: Verify

```bash
# Start the app and run a quick analysis
./start.sh
# In another terminal:
cd backend && python test_api.py
```

Check that cost displays correctly in the UI after analyzing a stock.

---

## Phase 2: Add Unit Test Infrastructure

**Why second**: We need tests before making bigger changes. Setting up the infrastructure now makes all future work safer.

**Time**: 1 hour

### Step 2.1: Create test directory structure

```bash
mkdir -p tests/unit/data_fetchers
mkdir -p tests/integration
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/unit/data_fetchers/__init__.py
touch tests/integration/__init__.py
```

### Step 2.2: Create conftest.py with shared fixtures

Create `tests/conftest.py`:

```python
"""
Shared test fixtures for all tests.

Usage in tests:
    def test_something(mock_config, mock_llm_response):
        ...
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import dataclass
from typing import Optional

# Ensure imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src_george_researcher.config import Config
from src_george_researcher.llm import LLMResponse


@pytest.fixture
def mock_config() -> Config:
    """Provide a test configuration that doesn't require real API keys."""
    return Config(
        openrouter_api_key="test-key-not-real",
        openrouter_model="anthropic/claude-3-haiku",
        alpha_vantage_key="test-av-key",
        eodhd_key="test-eodhd-key",
        google_api_key="test-google-key",
        data_dir=Path("/tmp/test_data"),
        embeddings_dir=Path("/tmp/test_embeddings"),
        chunk_size=1000,
        chunk_overlap=100,
        max_debate_rounds=2,
    )


@pytest.fixture
def mock_llm_response() -> LLMResponse:
    """Provide a successful mock LLM response."""
    return LLMResponse(
        content="This is a test response from the LLM.",
        model="anthropic/claude-3-haiku",
        tokens_used=150,
        success=True,
        error=None,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.0001,
    )


@pytest.fixture
def mock_llm_error_response() -> LLMResponse:
    """Provide a failed mock LLM response."""
    return LLMResponse(
        content="",
        model="anthropic/claude-3-haiku",
        tokens_used=0,
        success=False,
        error="API rate limit exceeded",
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
    )


@pytest.fixture
def mock_httpx_client():
    """
    Mock httpx.Client for testing API calls without network.

    Usage:
        def test_api_call(mock_httpx_client):
            mock_httpx_client.return_value.__enter__.return_value.get.return_value.json.return_value = {"data": "test"}
    """
    with patch('httpx.Client') as mock:
        yield mock


# Stock data fixtures
@pytest.fixture
def sample_stock_info():
    """Provide sample stock info for AAPL."""
    from src_george_researcher.data_fetchers.stock_data import StockInfo
    return StockInfo(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        current_price=185.50,
        market_cap=2.8e12,
        pe_ratio=28.5,
        forward_pe=25.2,
        profit_margin=0.25,
        roe=0.45,
        revenue_growth=0.08,
        business_summary="Apple Inc. designs, manufactures, and markets smartphones...",
    )
```

### Step 2.3: Create pytest configuration

Create `pytest.ini` in project root:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
```

### Step 2.4: Add pytest to dependencies

Edit `pyproject.toml`, add to dependencies:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
]
```

Then install:

```bash
uv sync --extra dev
```

### Step 2.5: Verify infrastructure works

Create a simple test `tests/unit/test_pricing.py`:

```python
"""Tests for the pricing module."""

from src_george_researcher.pricing import (
    get_llm_pricing,
    calculate_llm_cost,
    LLM_PRICING,
    GEMINI_SEARCH_PRICE_PER_QUERY,
)


def test_get_llm_pricing_known_model():
    """Test getting pricing for a known model."""
    pricing = get_llm_pricing("anthropic/claude-3-haiku")
    assert pricing["input"] == 0.25
    assert pricing["output"] == 1.25


def test_get_llm_pricing_unknown_model():
    """Test that unknown models get default pricing."""
    pricing = get_llm_pricing("unknown/model-xyz")
    assert pricing == LLM_PRICING["default"]


def test_calculate_llm_cost():
    """Test cost calculation."""
    # 1000 input tokens, 500 output tokens with Haiku
    # Input: (1000 / 1M) * $0.25 = $0.00025
    # Output: (500 / 1M) * $1.25 = $0.000625
    # Total: $0.000875
    cost = calculate_llm_cost("anthropic/claude-3-haiku", 1000, 500)
    assert abs(cost - 0.000875) < 0.0000001


def test_calculate_llm_cost_zero_tokens():
    """Test cost calculation with zero tokens."""
    cost = calculate_llm_cost("anthropic/claude-3-haiku", 0, 0)
    assert cost == 0.0


def test_gemini_search_pricing_exists():
    """Test Gemini search pricing constant exists."""
    assert GEMINI_SEARCH_PRICE_PER_QUERY == 0.014
```

Run the tests:

```bash
uv run pytest tests/unit/test_pricing.py -v
```

Expected output: All tests pass.

---

## Phase 3: Write Tests for Core Modules

**Why third**: Now that infrastructure exists, write tests for the modules we'll modify. This creates a safety net.

**Time**: 2 hours

### Step 3.1: Tests for llm.py

Create `tests/unit/test_llm.py`:

```python
"""Tests for the LLM client module."""

import pytest
from unittest.mock import patch, Mock
import httpx

from src_george_researcher.llm import call_llm, LLMResponse, test_connection


class TestCallLLM:
    """Tests for the call_llm function."""

    def test_successful_call(self):
        """Test a successful LLM API call."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello, world!"}}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
            }
        }

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = call_llm(
                api_key="test-key",
                model="anthropic/claude-3-haiku",
                system_prompt="You are helpful.",
                user_prompt="Say hello",
            )

        assert result.success is True
        assert result.content == "Hello, world!"
        assert result.tokens_used == 60
        assert result.input_tokens == 50
        assert result.output_tokens == 10
        assert result.cost_usd > 0

    def test_http_error(self):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = call_llm(
                api_key="test-key",
                model="anthropic/claude-3-haiku",
                system_prompt="",
                user_prompt="test",
            )

        assert result.success is False
        assert "429" in result.error
        assert result.tokens_used == 0

    def test_timeout(self):
        """Test handling of timeout errors."""
        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")

            result = call_llm(
                api_key="test-key",
                model="anthropic/claude-3-haiku",
                system_prompt="",
                user_prompt="test",
            )

        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_master_prompt_injection(self):
        """Test that master_prompt is prepended to system prompt."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        captured_payload = None

        def capture_post(url, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get('json', {})
            return mock_response

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = capture_post

            call_llm(
                api_key="test-key",
                model="anthropic/claude-3-haiku",
                system_prompt="Base instructions",
                user_prompt="test",
                master_prompt="Always be concise.",
            )

        # Verify master_prompt was injected
        system_content = captured_payload["messages"][0]["content"]
        assert "Always be concise" in system_content
        assert "Base instructions" in system_content


class TestLLMResponse:
    """Tests for the LLMResponse dataclass."""

    def test_immutability(self):
        """Test that LLMResponse is frozen (immutable)."""
        response = LLMResponse(
            content="test",
            model="test-model",
            tokens_used=10,
            success=True,
        )

        with pytest.raises(AttributeError):
            response.content = "modified"
```

### Step 3.2: Tests for config.py

Create `tests/unit/test_config.py`:

```python
"""Tests for the configuration module."""

import os
import pytest
from unittest.mock import patch
from pathlib import Path

from src_george_researcher.config import (
    Config,
    load_config,
    validate_config,
    ensure_directories,
)


class TestConfig:
    """Tests for the Config dataclass."""

    def test_config_is_frozen(self, mock_config):
        """Test that Config is immutable."""
        with pytest.raises(AttributeError):
            mock_config.openrouter_api_key = "new-key"

    def test_paths_are_pathlib(self, mock_config):
        """Test that path fields use pathlib.Path."""
        assert isinstance(mock_config.data_dir, Path)
        assert isinstance(mock_config.embeddings_dir, Path)


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_loads_from_environment(self):
        """Test that config loads from environment variables."""
        test_env = {
            "OPENROUTER_API_KEY": "test-api-key",
            "OPENROUTER_MODEL": "test-model",
            "DATA_DIR": "/custom/data",
        }

        with patch.dict(os.environ, test_env, clear=False):
            config = load_config()

        assert config.openrouter_api_key == "test-api-key"
        assert config.openrouter_model == "test-model"
        assert config.data_dir == Path("/custom/data")

    def test_uses_defaults_when_not_set(self):
        """Test that missing env vars use defaults."""
        # Clear relevant env vars
        env_without_keys = {k: v for k, v in os.environ.items()
                           if not k.startswith("OPENROUTER")}

        with patch.dict(os.environ, env_without_keys, clear=True):
            config = load_config()

        assert config.openrouter_api_key == ""  # Default empty
        assert config.openrouter_model == "anthropic/claude-3-haiku"  # Default model


class TestValidateConfig:
    """Tests for the validate_config function."""

    def test_valid_config(self, mock_config):
        """Test validation passes with valid config."""
        is_valid, errors = validate_config(mock_config)
        assert is_valid is True
        assert len(errors) == 0

    def test_missing_api_key(self):
        """Test validation fails without API key."""
        config = Config(
            openrouter_api_key="",  # Missing!
            openrouter_model="test",
            alpha_vantage_key=None,
            eodhd_key=None,
            google_api_key=None,
            data_dir=Path("/tmp"),
            embeddings_dir=Path("/tmp"),
            chunk_size=1000,
            chunk_overlap=100,
            max_debate_rounds=2,
        )

        is_valid, errors = validate_config(config)
        assert is_valid is False
        assert "OPENROUTER_API_KEY" in errors[0]


class TestEnsureDirectories:
    """Tests for the ensure_directories function."""

    def test_creates_directories(self, tmp_path):
        """Test that directories are created if missing."""
        config = Config(
            openrouter_api_key="test",
            openrouter_model="test",
            alpha_vantage_key=None,
            eodhd_key=None,
            google_api_key=None,
            data_dir=tmp_path / "new_data",
            embeddings_dir=tmp_path / "new_embeddings",
            chunk_size=1000,
            chunk_overlap=100,
            max_debate_rounds=2,
        )

        # Directories shouldn't exist yet
        assert not config.data_dir.exists()
        assert not config.embeddings_dir.exists()

        ensure_directories(config)

        # Now they should exist
        assert config.data_dir.exists()
        assert config.embeddings_dir.exists()
```

### Step 3.3: Tests for session.py

Create `tests/unit/test_session.py`:

```python
"""Tests for the session management module."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import tempfile
import json

from backend.core.session import (
    Message,
    AnalysisSession,
    SessionManager,
)


class TestMessage:
    """Tests for the Message dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}

    def test_message_with_metadata(self):
        """Test message with metadata."""
        msg = Message(
            role="assistant",
            content="Response",
            metadata={"tokens": 50, "cost": 0.001}
        )

        assert msg.metadata["tokens"] == 50


class TestAnalysisSession:
    """Tests for the AnalysisSession dataclass."""

    def test_session_creation(self):
        """Test creating a session."""
        session = AnalysisSession(
            session_id="test-123",
            ticker="AAPL",
        )

        assert session.session_id == "test-123"
        assert session.ticker == "AAPL"
        assert session.conversation_history == []
        assert session.metadata == {}

    def test_add_message(self):
        """Test adding messages to session."""
        session = AnalysisSession(session_id="test", ticker="AAPL")

        msg = session.add_message("user", "What is the P/E ratio?")

        assert len(session.conversation_history) == 1
        assert session.conversation_history[0].content == "What is the P/E ratio?"
        assert msg.role == "user"

    def test_get_recent_history(self):
        """Test getting recent conversation history."""
        session = AnalysisSession(session_id="test", ticker="AAPL")

        # Add 15 messages
        for i in range(15):
            session.add_message("user", f"Message {i}")

        recent = session.get_recent_history(n=5)

        assert len(recent) == 5
        assert recent[0].content == "Message 10"  # Messages 10-14
        assert recent[-1].content == "Message 14"

    def test_to_dict(self):
        """Test serializing session to dict."""
        session = AnalysisSession(
            session_id="test-123",
            ticker="AAPL",
            user_id="user-456",
        )
        session.add_message("user", "Hello")

        data = session.to_dict()

        assert data["session_id"] == "test-123"
        assert data["ticker"] == "AAPL"
        assert data["user_id"] == "user-456"
        assert data["message_count"] == 1


class TestSessionManager:
    """Tests for the SessionManager class."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary directory for session storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_create_session(self, temp_storage):
        """Test creating a new session."""
        manager = SessionManager(storage_dir=temp_storage)

        session = manager.create_session(
            ticker="AAPL",
            user_id="user-123",
        )

        assert session.ticker == "AAPL"
        assert session.user_id == "user-123"
        assert session.session_id is not None

        # Session should be saved to disk
        user_dir = Path(temp_storage) / "user-123"
        assert user_dir.exists()
        assert (user_dir / f"{session.session_id}.json").exists()

    def test_get_session(self, temp_storage):
        """Test retrieving a session."""
        manager = SessionManager(storage_dir=temp_storage)
        created = manager.create_session(ticker="AAPL")

        retrieved = manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.ticker == "AAPL"

    def test_get_nonexistent_session(self, temp_storage):
        """Test getting a session that doesn't exist."""
        manager = SessionManager(storage_dir=temp_storage)

        result = manager.get_session("nonexistent-id")

        assert result is None

    def test_session_context_auto_saves(self, temp_storage):
        """Test that session_context auto-saves changes."""
        manager = SessionManager(storage_dir=temp_storage)
        session = manager.create_session(ticker="AAPL")
        session_id = session.session_id

        # Modify session via context manager
        with manager.session_context(session_id) as s:
            s.add_message("user", "Test message")

        # Create new manager to reload from disk
        new_manager = SessionManager(storage_dir=temp_storage)
        reloaded = new_manager.get_session(session_id)

        assert len(reloaded.conversation_history) == 1
        assert reloaded.conversation_history[0].content == "Test message"

    def test_list_sessions_by_user(self, temp_storage):
        """Test listing sessions filtered by user."""
        manager = SessionManager(storage_dir=temp_storage)

        # Create sessions for different users
        manager.create_session(ticker="AAPL", user_id="user-1")
        manager.create_session(ticker="GOOGL", user_id="user-1")
        manager.create_session(ticker="MSFT", user_id="user-2")

        user1_sessions = manager.list_sessions(user_id="user-1")

        assert len(user1_sessions) == 2
        tickers = {s["ticker"] for s in user1_sessions}
        assert tickers == {"AAPL", "GOOGL"}
```

### Step 3.4: Run all tests

```bash
uv run pytest tests/ -v
```

All tests should pass. If any fail, fix the issues before proceeding.

---

## Phase 4: Fix Configuration Issues

**Why fourth**: With tests in place, we can safely make config changes.

**Time**: 30 minutes

### Step 4.1: Make JWT secret required in production

Edit `backend/core/auth.py`:

```python
# Replace line 25:
# JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")

# With:
import os

_jwt_secret = os.getenv("JWT_SECRET")
_env = os.getenv("FASTAPI_ENV", "development")

if _env == "production" and not _jwt_secret:
    raise ValueError(
        "JWT_SECRET environment variable must be set in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

JWT_SECRET = _jwt_secret or "dev-secret-DO-NOT-USE-IN-PRODUCTION"
```

### Step 4.2: Document bcrypt rounds

Edit `backend/core/auth.py`, add comment before line 91:

```python
def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    ...
    """
    # Bcrypt work factor (rounds = 2^12 = 4096 iterations)
    # Increasing: More secure but slower (each +1 doubles time)
    # Decreasing: Faster but less secure
    # 12 is recommended balance for 2024 (takes ~250ms on modern hardware)
    salt = bcrypt.gensalt(rounds=12)
    ...
```

### Step 4.3: Verify

```bash
# Test that dev mode still works
FASTAPI_ENV=development uv run python -c "from backend.core.auth import JWT_SECRET; print('OK')"

# Test that production mode requires secret
FASTAPI_ENV=production JWT_SECRET= uv run python -c "from backend.core.auth import JWT_SECRET"
# Should raise ValueError
```

---

## Phase 5: Type the Metadata Dict

**Why fifth**: Improves type safety for session metadata without breaking changes.

**Time**: 30 minutes

### Step 5.1: Define SessionMetadata TypedDict

Edit `backend/core/session.py`, add after imports (around line 19):

```python
from typing import List, Dict, Optional, Generator, TypedDict


class SessionMetadata(TypedDict, total=False):
    """
    Typed metadata for analysis sessions.

    All fields are optional (total=False) to support gradual adoption.
    Add new fields here when storing structured data in session.metadata.
    """
    # Analysis results
    total_cost_usd: float
    total_tokens: int
    is_us: bool

    # Cost breakdown from analysis
    cost_breakdown: Dict[str, float]

    # Contradictions and research gaps from analysis
    contradictions: List[Dict]
    research_gaps: List[Dict]

    # Report metadata
    headline: str
```

### Step 5.2: Update AnalysisSession

Change line 56 from:
```python
metadata: Dict = field(default_factory=dict)
```

To:
```python
metadata: SessionMetadata = field(default_factory=dict)
```

### Step 5.3: Verify

```bash
uv run pytest tests/unit/test_session.py -v
```

---

## Phase 6: Document Magic Numbers

**Why sixth**: Helps future developers (and you) understand tuning impacts.

**Time**: 1 hour

### Step 6.1: Update analysis_agents.py constants

Edit `src_george_researcher/analysis_agents.py`, replace lines 29-53 with documented versions:

```python
# =============================================================================
# CONTEXT LIMITS FOR LLM PROMPTS
# =============================================================================
# These limits control how much context is passed to each agent.
# All values are in characters (not tokens).
#
# Tuning guidance:
# - INCREASING a limit: More context but higher token cost (~0.001 USD per 1000 chars)
#   May improve coherence but risks hitting model context limits
# - DECREASING a limit: Faster/cheaper but agents may miss important context
#   May cause disjointed analysis if key facts are truncated
#
# The limits below are tuned for Claude 3 Haiku (200K context).
# For smaller context models, reduce all limits by 50%.
# =============================================================================

# Initial research - used when identifying follow-up topics
# Higher = more topics identified, but diminishing returns after ~3000
INITIAL_RESEARCH_LIMIT = 2500

# Full report section limits - controls density of final report
# These are the primary tuning knobs for report length
FULL_REPORT_FUNDAMENTALS_LIMIT = 1500  # Core financial metrics
FULL_REPORT_THESIS_LIMIT = 1200        # Bull/bear arguments
FULL_REPORT_MOAT_LIMIT = 1000          # Competitive analysis
FULL_REPORT_STRATEGY_LIMIT = 1000      # Strategic outlook
FULL_REPORT_SENTIMENT_LIMIT = 800      # News sentiment summary
FULL_REPORT_TECHNICALS_LIMIT = 800     # Technical indicators

# Cross-agent context - how much one agent sees of another's output
# Critical for debate quality - bull/bear need to see full counter-arguments
FUNDAMENTALS_CONTEXT_LIMIT = 1500      # Fundamentals passed to thesis agents
COUNTER_ARGUMENT_LIMIT = 1500          # Counter-argument in debate rounds
MOAT_CONTEXT_LIMIT = 1000              # Moat analysis in thesis
STRATEGY_CONTEXT_LIMIT = 1000          # Strategy in thesis
TECHNICALS_CONTEXT_LIMIT = 1000        # Technicals context

# Sentiment context - news/sentiment passed to various agents
SENTIMENT_LIMIT = 800                  # General sentiment context
NEWS_CONTEXT_LIMIT = 800               # News headlines/summaries

# Business description limits
BUSINESS_SUMMARY_LIMIT = 800           # Company description
MOAT_SUMMARY_LIMIT = 1000              # Business summary in moat analysis

# Recommendation synthesis - what the final recommendation agent sees
RECOMMENDATION_BULL_BEAR_LIMIT = 800   # Bull/bear summaries
RECOMMENDATION_STRATEGY_LIMIT = 800    # Strategy summary
RECOMMENDATION_SENTIMENT_LIMIT = 600   # Sentiment summary
RECOMMENDATION_FUNDAMENTALS_LIMIT = 800  # Fundamentals summary
RECOMMENDATION_MOAT_LIMIT = 600        # Moat summary
RECOMMENDATION_TECHNICALS_LIMIT = 600  # Technicals summary

# Strategy agent context
STRATEGY_FUNDAMENTALS_LIMIT = 800      # Fundamentals in strategy analysis
```

### Step 6.2: Verify

```bash
# Run a full analysis to ensure nothing broke
./start.sh
# Then analyze a ticker in the UI
```

---

## Phase 7: Evaluate Wrapper Modules

**Why seventh**: The wrapper modules add complexity without clear value. Decide what to do with them.

**Time**: 2 hours

### Decision Point

You have three options:

**Option A: Keep wrappers, add value** (Recommended if you want to add features)
- Add caching to `llm_wrapper.py`
- Add retry logic with exponential backoff
- Add request/response logging

**Option B: Delete wrappers, import directly** (Recommended for simplicity)
- Remove `backend/agents/llm_wrapper.py`
- Remove `backend/agents/orchestrator_wrapper.py`
- Update imports throughout

**Option C: Keep as-is** (If time constrained)
- Document why wrappers exist
- Add TODO for future cleanup

### If you choose Option A (Add Value):

Edit `backend/agents/llm_wrapper.py`, add retry logic:

```python
import time
from functools import wraps

def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator that adds retry logic with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                result = func(*args, **kwargs)

                # If function returns LLMResult/LLMResponse, check success
                if hasattr(result, 'success'):
                    if result.success:
                        return result
                    # Rate limit errors should retry
                    if result.error and "rate limit" in result.error.lower():
                        last_error = result.error
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limited, retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    # Other errors don't retry
                    return result
                else:
                    # Function doesn't return result object, just return
                    return result

            # All retries exhausted
            logger.error(f"All {max_retries} retries failed: {last_error}")
            return result
        return wrapper
    return decorator


@with_retry(max_retries=3, base_delay=1.0)
def get_llm_response_with_usage(...):
    # ... existing implementation
```

### If you choose Option B (Delete Wrappers):

This is more invasive. You'll need to:

1. Find all imports of wrapper modules
2. Replace with direct imports
3. Delete the wrapper files

```bash
# Find all usages
grep -r "from backend.agents.llm_wrapper" --include="*.py"
grep -r "from backend.agents.orchestrator_wrapper" --include="*.py"
```

Then update each file. This typically affects:
- `backend/routers/*.py`
- `backend/core/*.py`
- `backend/jobs/*.py`

---

## Phase 8: Add Circuit Breaker (Optional)

**Why eighth**: Improves resilience when external APIs fail.

**Time**: 1 hour

### Step 8.1: Create circuit breaker module

Create `src_george_researcher/circuit_breaker.py`:

```python
"""
Circuit breaker pattern for external API calls.

Prevents cascading failures by temporarily blocking calls to failing services.

Usage:
    breaker = CircuitBreaker("openrouter", failure_threshold=5)

    if breaker.is_open():
        return cached_response_or_error()

    try:
        result = call_external_api()
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        raise
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for a single service.

    States:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Service failing, requests blocked
    - HALF_OPEN: Testing if service recovered

    Args:
        name: Service name (for logging)
        failure_threshold: Failures before opening circuit (default: 5)
        reset_timeout: Seconds before trying again (default: 60)
        success_threshold: Successes in half-open to close (default: 2)
    """
    name: str
    failure_threshold: int = 5
    reset_timeout: int = 60
    success_threshold: int = 2

    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _last_failure_time: Optional[datetime] = field(default=None, init=False)
    _state: str = field(default="closed", init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        with self._lock:
            if self._state == "closed":
                return False

            if self._state == "open":
                # Check if we should transition to half-open
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    if elapsed >= self.reset_timeout:
                        logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN")
                        self._state = "half_open"
                        self._successes = 0
                        return False
                return True

            # half_open: allow request through
            return False

    def record_failure(self):
        """Record a failed request."""
        with self._lock:
            self._failures += 1
            self._last_failure_time = datetime.now()

            if self._state == "half_open":
                # Any failure in half-open reopens circuit
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (failure during test)")
                self._state = "open"
            elif self._failures >= self.failure_threshold:
                logger.warning(f"Circuit {self.name}: CLOSED -> OPEN ({self._failures} failures)")
                self._state = "open"

    def record_success(self):
        """Record a successful request."""
        with self._lock:
            if self._state == "half_open":
                self._successes += 1
                if self._successes >= self.success_threshold:
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED (recovered)")
                    self._state = "closed"
                    self._failures = 0
            elif self._state == "closed":
                # Reset failure count on success
                self._failures = 0

    def get_state(self) -> Dict:
        """Get current state for monitoring."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state,
                "failures": self._failures,
                "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
            }


# Global circuit breakers for each external service
_breakers: Dict[str, CircuitBreaker] = {}
_breakers_lock = Lock()


def get_circuit_breaker(service: str) -> CircuitBreaker:
    """Get or create circuit breaker for a service."""
    with _breakers_lock:
        if service not in _breakers:
            _breakers[service] = CircuitBreaker(name=service)
        return _breakers[service]


def get_all_breaker_states() -> Dict[str, Dict]:
    """Get states of all circuit breakers (for monitoring endpoint)."""
    with _breakers_lock:
        return {name: breaker.get_state() for name, breaker in _breakers.items()}
```

### Step 8.2: Integrate with LLM calls

Edit `src_george_researcher/llm.py`, add to `call_llm`:

```python
from .circuit_breaker import get_circuit_breaker

def call_llm(...) -> LLMResponse:
    breaker = get_circuit_breaker("openrouter")

    if breaker.is_open():
        return LLMResponse(
            content="",
            model=model,
            tokens_used=0,
            success=False,
            error="Service temporarily unavailable (circuit breaker open)",
        )

    try:
        # ... existing implementation ...

        if response.status_code == 200:
            breaker.record_success()
            # ... rest of success handling
        else:
            breaker.record_failure()
            # ... rest of error handling

    except httpx.TimeoutException:
        breaker.record_failure()
        return LLMResponse(...)
    except Exception as e:
        breaker.record_failure()
        return LLMResponse(...)
```

### Step 8.3: Add monitoring endpoint (optional)

Edit `backend/main.py` to add a health/status endpoint:

```python
from src_george_researcher.circuit_breaker import get_all_breaker_states

@app.get("/health/circuits")
def get_circuit_status():
    """Get status of all circuit breakers."""
    return {"circuits": get_all_breaker_states()}
```

---

## Final Verification

After completing all phases:

```bash
# Run all tests
uv run pytest tests/ -v

# Start the app
./start.sh

# Run integration tests
cd backend && python test_api.py

# Manual smoke test:
# 1. Analyze AAPL (US)
# 2. Analyze TSM (non-US)
# 3. Chat with analysis
# 4. Export PDF
# 5. Check costs display correctly
```

---

## Summary Checklist

- [ ] Phase 1: Created `pricing.py`, updated `llm.py` and `cost_tracker.py`
- [ ] Phase 2: Set up test infrastructure in `tests/`
- [ ] Phase 3: Wrote unit tests for `llm.py`, `config.py`, `session.py`
- [ ] Phase 4: Made JWT secret required in production, documented bcrypt rounds
- [ ] Phase 5: Added `SessionMetadata` TypedDict
- [ ] Phase 6: Documented all magic number constants with impact descriptions
- [ ] Phase 7: Decided on wrapper module strategy (keep/add value/delete)
- [ ] Phase 8: (Optional) Added circuit breaker pattern

All tests passing? Ready for production.
