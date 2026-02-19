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
