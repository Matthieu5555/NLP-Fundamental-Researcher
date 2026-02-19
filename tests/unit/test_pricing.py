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


def test_calculate_llm_cost_claude_sonnet_4():
    """Test cost calculation for Claude Sonnet 4."""
    # 10000 input tokens, 2000 output tokens
    # Input: (10000 / 1M) * $3.00 = $0.03
    # Output: (2000 / 1M) * $15.00 = $0.03
    # Total: $0.06
    cost = calculate_llm_cost("anthropic/claude-sonnet-4", 10000, 2000)
    assert abs(cost - 0.06) < 0.0000001


def test_calculate_llm_cost_opus_4():
    """Test cost calculation for Claude Opus 4."""
    # 10000 input tokens, 2000 output tokens
    # Input: (10000 / 1M) * $15.00 = $0.15
    # Output: (2000 / 1M) * $75.00 = $0.15
    # Total: $0.30
    cost = calculate_llm_cost("anthropic/claude-opus-4", 10000, 2000)
    assert abs(cost - 0.30) < 0.0000001


def test_pricing_dict_has_all_expected_models():
    """Test that pricing dict includes key models."""
    expected_models = [
        "anthropic/claude-3-haiku",
        "anthropic/claude-sonnet-4",
        "anthropic/claude-opus-4",
        "openai/gpt-4o",
        "google/gemini-2.0-flash",
        "default",
    ]
    for model in expected_models:
        assert model in LLM_PRICING, f"Missing pricing for {model}"


def test_pricing_has_input_and_output():
    """Test that all pricing entries have input and output keys."""
    for model, pricing in LLM_PRICING.items():
        assert "input" in pricing, f"Model {model} missing 'input' pricing"
        assert "output" in pricing, f"Model {model} missing 'output' pricing"
        assert pricing["input"] >= 0, f"Model {model} has negative input price"
        assert pricing["output"] >= 0, f"Model {model} has negative output price"
