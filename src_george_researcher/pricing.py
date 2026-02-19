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
