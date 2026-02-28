"""Tests for Pydantic request model validation.

Covers:
- StartAnalysisRequest: ticker constraints
- ChatMessageRequest: required fields
- ExportPdfRequest: default values
- SearchTickersRequest: limit bounds
"""

import pytest
from pydantic import ValidationError

from backend.models.requests import (
    StartAnalysisRequest,
    ChatMessageRequest,
    ExportPdfRequest,
    SearchTickersRequest,
    ClassifyTickerRequest,
    UpdateSectionRequest,
)


class TestStartAnalysisRequest:
    """Ticker field constraints."""

    def test_valid_ticker(self):
        req = StartAnalysisRequest(ticker="AAPL")
        assert req.ticker == "AAPL"

    def test_empty_ticker_raises(self):
        with pytest.raises(ValidationError):
            StartAnalysisRequest(ticker="")

    def test_ticker_over_10_chars_raises(self):
        with pytest.raises(ValidationError):
            StartAnalysisRequest(ticker="A" * 11)

    def test_ticker_at_max_length(self):
        req = StartAnalysisRequest(ticker="A" * 10)
        assert len(req.ticker) == 10

    def test_options_default_none(self):
        req = StartAnalysisRequest(ticker="AAPL")
        assert req.options is None

    def test_options_accepted(self):
        req = StartAnalysisRequest(ticker="AAPL", options={"include_moat": True})
        assert req.options["include_moat"] is True


class TestChatMessageRequest:
    """Required fields."""

    def test_valid_message(self):
        req = ChatMessageRequest(session_id="abc-123", message="Hello")
        assert req.message == "Hello"

    def test_empty_message_raises(self):
        with pytest.raises(ValidationError):
            ChatMessageRequest(session_id="abc-123", message="")

    def test_missing_session_id_raises(self):
        with pytest.raises(ValidationError):
            ChatMessageRequest(message="Hello")


class TestExportPdfRequest:
    """Default value checking."""

    def test_defaults(self):
        req = ExportPdfRequest()
        assert req.firm_id == "george"
        assert req.analyst_id == "default"

    def test_custom_firm_id(self):
        req = ExportPdfRequest(firm_id="custom")
        assert req.firm_id == "custom"


class TestSearchTickersRequest:
    """Limit bounds validation."""

    def test_default_limit(self):
        req = SearchTickersRequest(query="apple")
        assert req.limit == 20

    def test_limit_at_max(self):
        req = SearchTickersRequest(query="apple", limit=100)
        assert req.limit == 100

    def test_limit_above_max_raises(self):
        with pytest.raises(ValidationError):
            SearchTickersRequest(query="apple", limit=101)

    def test_limit_zero_raises(self):
        with pytest.raises(ValidationError):
            SearchTickersRequest(query="apple", limit=0)

    def test_limit_negative_raises(self):
        with pytest.raises(ValidationError):
            SearchTickersRequest(query="apple", limit=-1)

    def test_empty_query_raises(self):
        with pytest.raises(ValidationError):
            SearchTickersRequest(query="")


class TestClassifyTickerRequest:
    """Ticker classification request."""

    def test_valid(self):
        req = ClassifyTickerRequest(ticker="MSFT")
        assert req.ticker == "MSFT"

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            ClassifyTickerRequest(ticker="")


class TestUpdateSectionRequest:
    """Section update request."""

    def test_valid(self):
        req = UpdateSectionRequest(content="New content here")
        assert req.content == "New content here"

    def test_empty_content_raises(self):
        with pytest.raises(ValidationError):
            UpdateSectionRequest(content="")

    def test_sources_optional(self):
        req = UpdateSectionRequest(content="Content")
        assert req.sources is None
