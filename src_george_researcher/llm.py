"""
LLM client for OpenRouter API.
Functional interface for making LLM calls with circuit breaker protection.
"""
import httpx
from typing import Optional
from dataclasses import dataclass

from .pricing import calculate_llm_cost
from .circuit_breaker import get_circuit_breaker


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Circuit breaker for OpenRouter API
# Prevents cascading failures when the API is down
_openrouter_breaker = get_circuit_breaker(
    "openrouter",
    failure_threshold=5,   # Open after 5 consecutive failures
    reset_timeout=60,      # Try again after 60 seconds
    success_threshold=2,   # Need 2 successes to fully close
)


@dataclass(frozen=True)
class LLMResponse:
    """Immutable LLM response container."""
    content: str
    model: str
    tokens_used: int
    success: bool
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def call_llm(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    master_prompt: str = "",
) -> LLMResponse:
    """
    Make a single LLM call via OpenRouter with circuit breaker protection.

    Args:
        api_key: OpenRouter API key
        model: Model identifier (e.g., anthropic/claude-3-haiku)
        system_prompt: System message
        user_prompt: User message
        temperature: Sampling temperature (0.0 for deterministic)
        max_tokens: Maximum response tokens
        master_prompt: User's custom system prompt to prepend (controls tone, style)

    Returns:
        LLMResponse with content or error
    """
    # Check circuit breaker - fail fast if service is known to be down
    if _openrouter_breaker.is_open():
        return LLMResponse(
            content="",
            model=model,
            tokens_used=0,
            success=False,
            error="Service temporarily unavailable (circuit breaker open). Please try again in a minute.",
        )

    # Inject master prompt if provided
    if master_prompt:
        system_prompt = f"USER PREFERENCES:\n{master_prompt}\n\n---\n\n{system_prompt}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/george-researcher",
        "X-Title": "George Financial Researcher",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(OPENROUTER_URL, headers=headers, json=payload)

        if response.status_code != 200:
            # Record failure for retryable errors (rate limits, server errors)
            if response.status_code in (429, 500, 502, 503, 504):
                _openrouter_breaker.record_failure()
            return LLMResponse(
                content="",
                model=model,
                tokens_used=0,
                success=False,
                error=f"HTTP {response.status_code}: {response.text[:200]}",
            )

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        # Calculate cost
        cost_usd = calculate_llm_cost(model, input_tokens, output_tokens)

        # Record success with circuit breaker
        _openrouter_breaker.record_success()

        return LLMResponse(
            content=content,
            model=model,
            tokens_used=total_tokens,
            success=True,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

    except httpx.TimeoutException:
        _openrouter_breaker.record_failure()
        return LLMResponse(
            content="",
            model=model,
            tokens_used=0,
            success=False,
            error="Request timed out",
        )
    except Exception as e:
        _openrouter_breaker.record_failure()
        return LLMResponse(
            content="",
            model=model,
            tokens_used=0,
            success=False,
            error=str(e),
        )


def check_connection(api_key: str, model: str) -> tuple[bool, str]:
    """
    Test the LLM connection with a minimal call.

    Returns:
        (success, message)
    """
    response = call_llm(
        api_key=api_key,
        model=model,
        system_prompt="You are a test assistant.",
        user_prompt="Respond with exactly: OK",
        max_tokens=10,
    )

    if response.success:
        return (True, f"Connection successful. Model: {model}")
    else:
        return (False, f"Connection failed: {response.error}")
