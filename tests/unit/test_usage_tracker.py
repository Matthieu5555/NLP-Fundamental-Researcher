"""Tests for usage tracker middleware utility functions.

Covers:
- extract_ticker_from_path: path pattern matching for tickers
- extract_session_id_from_path: UUID extraction from API paths
- get_estimated_cost: endpoint cost estimation lookup
"""

import pytest

pytest.importorskip("bcrypt", reason="bcrypt not installed (import chain: middleware -> auth -> bcrypt)")

from backend.middleware.usage_tracker import (
    extract_ticker_from_path,
    extract_session_id_from_path,
    get_estimated_cost,
)


class TestExtractTickerFromPath:
    """Ticker extraction from URL path segments."""

    def test_chart_path(self):
        assert extract_ticker_from_path("/api/chart/AAPL/data") == "AAPL"

    def test_classify_path(self):
        assert extract_ticker_from_path("/api/companies/classify/MSFT") == "MSFT"

    def test_analysis_start_returns_none(self):
        assert extract_ticker_from_path("/api/analysis/start") is None

    def test_lowercase_uppercased(self):
        assert extract_ticker_from_path("/api/chart/aapl/data") == "AAPL"

    def test_too_short_path_returns_none(self):
        assert extract_ticker_from_path("/api/chart") is None

    def test_unrelated_path_returns_none(self):
        assert extract_ticker_from_path("/api/sessions/list") is None

    def test_root_path(self):
        assert extract_ticker_from_path("/") is None

    def test_empty_path(self):
        assert extract_ticker_from_path("") is None


class TestExtractSessionIdFromPath:
    """Session ID extraction from URL paths."""

    _SAMPLE_UUID = "abc-123-def-456-ghij"

    def test_analysis_status_path(self):
        path = f"/api/analysis/{self._SAMPLE_UUID}/status"
        assert extract_session_id_from_path(path) == self._SAMPLE_UUID

    def test_reports_path(self):
        path = f"/api/reports/{self._SAMPLE_UUID}"
        assert extract_session_id_from_path(path) == self._SAMPLE_UUID

    def test_sessions_resume_path(self):
        path = f"/api/sessions/{self._SAMPLE_UUID}/resume"
        assert extract_session_id_from_path(path) == self._SAMPLE_UUID

    def test_short_segment_without_dashes_returns_none(self):
        assert extract_session_id_from_path("/api/analysis/start") is None

    def test_analysis_start_returns_none(self):
        assert extract_session_id_from_path("/api/analysis/start") is None

    def test_unrelated_path_returns_none(self):
        assert extract_session_id_from_path("/api/health") is None

    def test_real_uuid_format(self):
        uuid = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        path = f"/api/analysis/{uuid}/status"
        assert extract_session_id_from_path(path) == uuid


class TestGetEstimatedCost:
    """Endpoint cost estimation lookup."""

    def test_analysis_start(self):
        assert get_estimated_cost("/api/analysis/start") == 0.32

    def test_chat_stream(self):
        assert get_estimated_cost("/api/chat/stream") == 0.02

    def test_pdf_export(self):
        assert get_estimated_cost("/api/reports/export/pdf") == 0.01

    def test_unknown_returns_zero(self):
        assert get_estimated_cost("/api/unknown/endpoint") == 0.0

    def test_partial_match(self):
        # The function does substring matching
        assert get_estimated_cost("/api/analysis/start?foo=bar") == 0.32
