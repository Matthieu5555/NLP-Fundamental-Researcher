"""
LLM client for OpenRouter API.
Functional interface for making LLM calls.
"""
import httpx
from typing import Optional
from dataclasses import dataclass


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True)
class LLMResponse:
    """Immutable LLM response container."""
    content: str
    model: str
    tokens_used: int
    success: bool
    error: Optional[str] = None


def call_llm(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> LLMResponse:
    """
    Make a single LLM call via OpenRouter.

    Args:
        api_key: OpenRouter API key
        model: Model identifier (e.g., anthropic/claude-3-haiku)
        system_prompt: System message
        user_prompt: User message
        temperature: Sampling temperature (0.0 for deterministic)
        max_tokens: Maximum response tokens

    Returns:
        LLMResponse with content or error
    """
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
            return LLMResponse(
                content="",
                model=model,
                tokens_used=0,
                success=False,
                error=f"HTTP {response.status_code}: {response.text[:200]}",
            )

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        tokens = data.get("usage", {}).get("total_tokens", 0)

        return LLMResponse(
            content=content,
            model=model,
            tokens_used=tokens,
            success=True,
        )

    except httpx.TimeoutException:
        return LLMResponse(
            content="",
            model=model,
            tokens_used=0,
            success=False,
            error="Request timed out",
        )
    except Exception as e:
        return LLMResponse(
            content="",
            model=model,
            tokens_used=0,
            success=False,
            error=str(e),
        )


def test_connection(api_key: str, model: str) -> tuple[bool, str]:
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
