"""Tests for cost tracking module.

Covers:
- estimate_tokens_from_text: word-based token estimation
- calculate_search_cost: Gemini search pricing
- SessionCost: dataclass properties, serialization roundtrip
- CostTracker: accumulation, reset, display formatting
"""

import pytest

from backend.core.cost_tracker import (
    estimate_tokens_from_text,
    calculate_search_cost,
    SessionCost,
    CostTracker,
    get_model_pricing_info,
    TOKENS_PER_WORD,
)
from src_george_researcher.pricing import GEMINI_SEARCH_PRICE_PER_QUERY


# =============================================================================
# estimate_tokens_from_text
# =============================================================================

class TestEstimateTokens:
    """Word-based token estimation heuristic."""

    def test_empty_string_returns_zero(self):
        assert estimate_tokens_from_text("") == 0

    def test_single_word(self):
        result = estimate_tokens_from_text("hello")
        assert result == int(1 * TOKENS_PER_WORD)

    def test_hundred_words(self):
        text = " ".join(["word"] * 100)
        result = estimate_tokens_from_text(text)
        expected = int(100 * TOKENS_PER_WORD)
        assert result == expected

    def test_whitespace_only_returns_zero(self):
        assert estimate_tokens_from_text("   ") == 0

    def test_result_is_integer(self):
        result = estimate_tokens_from_text("a few words here")
        assert isinstance(result, int)

    def test_scales_with_length(self):
        short = estimate_tokens_from_text("one two three")
        long = estimate_tokens_from_text("one two three four five six seven eight nine ten")
        assert long > short


# =============================================================================
# calculate_search_cost
# =============================================================================

class TestCalculateSearchCost:
    """Gemini search query cost calculation."""

    def test_single_query(self):
        cost = calculate_search_cost(1)
        assert abs(cost - GEMINI_SEARCH_PRICE_PER_QUERY) < 1e-10

    def test_ten_queries(self):
        cost = calculate_search_cost(10)
        assert abs(cost - 10 * GEMINI_SEARCH_PRICE_PER_QUERY) < 1e-10

    def test_zero_queries(self):
        assert calculate_search_cost(0) == 0.0


# =============================================================================
# SessionCost
# =============================================================================

class TestSessionCost:
    """SessionCost dataclass: computed properties and serialization."""

    def _make(self, **kwargs) -> SessionCost:
        defaults = dict(
            llm_input_tokens=1000,
            llm_output_tokens=500,
            llm_calls=3,
            search_queries=2,
            llm_cost_usd=0.005,
            search_cost_usd=0.001,
        )
        defaults.update(kwargs)
        return SessionCost(**defaults)

    def test_total_tokens(self):
        sc = self._make(llm_input_tokens=1000, llm_output_tokens=500)
        assert sc.total_tokens == 1500

    def test_total_cost(self):
        sc = self._make(llm_cost_usd=0.005, search_cost_usd=0.001)
        assert abs(sc.total_cost_usd - 0.006) < 1e-10

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected_keys = {
            "llm_input_tokens", "llm_output_tokens", "llm_calls",
            "search_queries", "llm_cost_usd", "search_cost_usd",
            "total_tokens", "total_cost_usd",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_rounds_costs(self):
        sc = self._make(llm_cost_usd=0.00123456789)
        d = sc.to_dict()
        # Should be rounded to 6 decimal places
        assert d["llm_cost_usd"] == round(0.00123456789, 6)

    def test_from_dict_roundtrip(self):
        original = self._make()
        d = original.to_dict()
        restored = SessionCost.from_dict(d)
        assert restored.llm_input_tokens == original.llm_input_tokens
        assert restored.llm_output_tokens == original.llm_output_tokens
        assert restored.llm_calls == original.llm_calls

    def test_from_dict_empty(self):
        sc = SessionCost.from_dict({})
        assert sc.llm_input_tokens == 0
        assert sc.llm_cost_usd == 0.0
        assert sc.total_tokens == 0

    def test_default_values_are_zero(self):
        sc = SessionCost()
        assert sc.total_tokens == 0
        assert sc.total_cost_usd == 0.0


# =============================================================================
# CostTracker
# =============================================================================

class TestCostTracker:
    """CostTracker accumulation, reset, and display formatting."""

    def test_fresh_tracker_has_zero_cost(self):
        tracker = CostTracker()
        assert tracker.get_total_cost() == 0.0

    def test_add_llm_call_accumulates(self):
        tracker = CostTracker()
        cost1 = tracker.add_llm_call("moonshotai/kimi-k2.5", 500, 200)
        cost2 = tracker.add_llm_call("moonshotai/kimi-k2.5", 500, 200)
        assert cost1 > 0
        assert tracker.session_cost.llm_calls == 2
        assert tracker.session_cost.llm_input_tokens == 1000
        assert tracker.session_cost.llm_output_tokens == 400
        assert abs(tracker.session_cost.llm_cost_usd - (cost1 + cost2)) < 1e-10

    def test_add_search_query(self):
        tracker = CostTracker()
        cost = tracker.add_search_query(3)
        assert cost > 0
        assert tracker.session_cost.search_queries == 3
        assert abs(tracker.session_cost.search_cost_usd - cost) < 1e-10

    def test_get_summary_matches_session_cost(self):
        tracker = CostTracker()
        tracker.add_llm_call("moonshotai/kimi-k2.5", 100, 50)
        summary = tracker.get_summary()
        assert summary["llm_calls"] == 1
        assert summary["total_tokens"] == 150

    def test_reset_zeroes_everything(self):
        tracker = CostTracker()
        tracker.add_llm_call("moonshotai/kimi-k2.5", 500, 200)
        tracker.add_search_query(2)
        tracker.reset()
        assert tracker.get_total_cost() == 0.0
        assert tracker.session_cost.llm_calls == 0

    def test_format_sub_cent(self):
        tracker = CostTracker()
        tracker.add_llm_call("moonshotai/kimi-k2.5", 100, 50)
        display = tracker.format_cost_display()
        # Sub-cent amounts use 4 decimal places
        assert display.startswith("$")
        assert len(display.split(".")[1]) == 4

    def test_format_above_cent(self):
        tracker = CostTracker()
        # Add enough calls to exceed $0.01
        for _ in range(100):
            tracker.add_llm_call("anthropic/claude-sonnet-4", 10000, 5000)
        if tracker.get_total_cost() >= 0.01:
            display = tracker.format_cost_display()
            assert len(display.split(".")[1]) == 2


# =============================================================================
# get_model_pricing_info
# =============================================================================

class TestModelPricingInfo:
    """Model pricing info retrieval."""

    def test_returns_expected_keys(self):
        info = get_model_pricing_info("moonshotai/kimi-k2.5")
        assert "model" in info
        assert "input_per_1m" in info
        assert "output_per_1m" in info
        assert "search_per_query" in info

    def test_model_name_passed_through(self):
        info = get_model_pricing_info("some-model/name")
        assert info["model"] == "some-model/name"
