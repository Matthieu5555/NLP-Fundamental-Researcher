"""
LLM and API pricing data - single source of truth.

Pricing is per 1 million tokens (USD).
Last updated: February 2026

To update prices:
1. Check OpenRouter: https://openrouter.ai/docs/models
2. Check Google AI: https://ai.google.dev/pricing
3. Update the dicts below
4. Run tests to verify cost calculations
"""

from typing import Dict


# OpenRouter LLM pricing (per 1M tokens)
LLM_PRICING: Dict[str, Dict[str, float]] = {
    # Moonshot AI
    "moonshotai/kimi-k2.5": {"input": 0.45, "output": 2.20},
    "moonshotai/kimi-k2-thinking": {"input": 0.47, "output": 2.00},

    # DeepSeek
    "deepseek/deepseek-v3.2-20251201": {"input": 0.26, "output": 0.38},
    "deepseek/deepseek-v3.2-speciale-20251201": {"input": 0.40, "output": 1.20},

    # Alibaba Qwen
    "qwen/qwen3.5-plus-02-15": {"input": 0.40, "output": 2.40},
    "qwen/qwen3.5-397b-a17b": {"input": 0.55, "output": 3.50},
    "qwen/qwen3-coder-next-2025-02-03": {"input": 0.12, "output": 0.75},
    "qwen/qwen3-max-thinking-20260123": {"input": 1.20, "output": 6.00},

    # Zhipu AI GLM
    "z-ai/glm-5-20260211": {"input": 0.95, "output": 2.55},
    "z-ai/glm-4.7-20251222": {"input": 0.38, "output": 1.70},
    "z-ai/glm-4.7-flash-20260119": {"input": 0.06, "output": 0.40},
    "z-ai/glm-4.6-20251208": {"input": 0.30, "output": 0.90},

    # Anthropic Claude 4.6 series
    "anthropic/claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4.6": {"input": 5.00, "output": 25.00},

    # Anthropic Claude 4 series (legacy)
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4": {"input": 15.00, "output": 75.00},

    # OpenAI models
    "openai/gpt-5.2-pro": {"input": 21.00, "output": 168.00},
    "openai/gpt-5-nano": {"input": 0.05, "output": 0.40},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},

    # Google models via OpenRouter
    "google/gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    "google/gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "google/gemini-2.0-flash": {"input": 0.10, "output": 0.40},

    # Meta
    "meta-llama/llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},

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
        model: Model identifier (e.g., "moonshotai/kimi-k2.5")

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
