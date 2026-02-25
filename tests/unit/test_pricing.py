"""Tests for the pricing module."""

from src_george_researcher.pricing import (
    get_llm_pricing,
    calculate_llm_cost,
    LLM_PRICING,
    GEMINI_SEARCH_PRICE_PER_QUERY,
)


def test_get_llm_pricing_known_model():
    """Test getting pricing for a known model."""
    pricing = get_llm_pricing("moonshotai/kimi-k2.5")
    assert pricing["input"] == 0.45
    assert pricing["output"] == 2.20


def test_get_llm_pricing_unknown_model():
    """Test that unknown models get default pricing."""
    pricing = get_llm_pricing("unknown/model-xyz")
    assert pricing == LLM_PRICING["default"]


def test_calculate_llm_cost():
    """Test cost calculation."""
    # 1000 input tokens, 500 output tokens with Kimi K2.5
    # Input: (1000 / 1M) * $0.45 = $0.00045
    # Output: (500 / 1M) * $2.20 = $0.0011
    # Total: $0.00155
    cost = calculate_llm_cost("moonshotai/kimi-k2.5", 1000, 500)
    assert abs(cost - 0.00155) < 0.0000001


def test_calculate_llm_cost_zero_tokens():
    """Test cost calculation with zero tokens."""
    cost = calculate_llm_cost("moonshotai/kimi-k2.5", 0, 0)
    assert cost == 0.0


def test_gemini_search_pricing_exists():
    """Test Gemini search pricing constant exists."""
    assert GEMINI_SEARCH_PRICE_PER_QUERY == 0.014


def test_calculate_llm_cost_claude_sonnet_46():
    """Test cost calculation for Claude Sonnet 4.6."""
    # 10000 input tokens, 2000 output tokens
    # Input: (10000 / 1M) * $3.00 = $0.03
    # Output: (2000 / 1M) * $15.00 = $0.03
    # Total: $0.06
    cost = calculate_llm_cost("anthropic/claude-sonnet-4.6", 10000, 2000)
    assert abs(cost - 0.06) < 0.0000001


def test_calculate_llm_cost_opus_46():
    """Test cost calculation for Claude Opus 4.6."""
    # 10000 input tokens, 2000 output tokens
    # Input: (10000 / 1M) * $5.00 = $0.05
    # Output: (2000 / 1M) * $25.00 = $0.05
    # Total: $0.10
    cost = calculate_llm_cost("anthropic/claude-opus-4.6", 10000, 2000)
    assert abs(cost - 0.10) < 0.0000001


def test_pricing_dict_has_all_expected_models():
    """Test that pricing dict includes key models."""
    expected_models = [
        "moonshotai/kimi-k2.5",
        "anthropic/claude-sonnet-4.6",
        "anthropic/claude-opus-4.6",
        "openai/gpt-5.2-pro",
        "openai/gpt-5-nano",
        "google/gemini-3.1-pro-preview",
        "google/gemini-3-flash-preview",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "deepseek/deepseek-v3.2-20251201",
        "qwen/qwen3.5-plus-02-15",
        "z-ai/glm-5-20260211",
        "z-ai/glm-4.7-flash-20260119",
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
