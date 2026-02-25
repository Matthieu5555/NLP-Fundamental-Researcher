"""
Wrapper for the existing LLM module with retry logic.

Provides a simplified interface for making LLM calls from the backend API,
with automatic retry on transient failures (rate limits, timeouts).

Note: Path setup for src_george_researcher imports is centralized in backend/main.py.
The fallback here ensures this module works when imported directly (e.g., tests).

Re-exports:
    call_llm                    - Low-level LLM call function (returns LLMResponse)
    get_llm_response            - High-level wrapper (returns str, handles errors)
    get_llm_response_with_settings - Settings-aware wrapper using user preferences
    get_llm_response_with_usage - Settings-aware wrapper with retry and usage tracking

Retry Behavior:
    - Automatically retries on rate limit errors (HTTP 429)
    - Uses exponential backoff: 1s, 2s, 4s delays between retries
    - Default: 3 retries before giving up
    - Timeouts and other transient errors also trigger retries

Environment Variables Required:
    OPENROUTER_API_KEY - API key for OpenRouter
    OPENROUTER_MODEL   - Model to use (default: moonshotai/kimi-k2.5)
"""

import time
import logging
from typing import Optional
from dataclasses import dataclass

# Set up logging
logger = logging.getLogger(__name__)

# sys.path configured in backend/main.py
from src_george_researcher import llm as llm_module  # noqa: E402
from src_george_researcher import config  # noqa: E402

# Re-export original function for direct use
call_llm = llm_module.call_llm

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================
# Impact of changing these values:
#   - MAX_RETRIES: More retries = more resilient but longer wait on persistent failures
#   - BASE_DELAY: Higher delay = more polite to API but slower recovery
#   - Exponential backoff formula: delay = BASE_DELAY * (2 ** attempt)

MAX_RETRIES = 3      # Total attempts before giving up
BASE_DELAY = 1.0     # Initial delay in seconds (doubles each retry)


def _is_retryable_error(error: Optional[str]) -> bool:
    """
    Determine if an LLM error should trigger a retry.

    Returns True for transient errors that may resolve on retry:
    - Rate limit errors (HTTP 429)
    - Timeout errors
    - Server errors (HTTP 5xx)

    Returns False for permanent errors:
    - Authentication failures (HTTP 401/403)
    - Bad request (HTTP 400)
    - Model not found (HTTP 404)
    """
    if not error:
        return False

    error_lower = error.lower()
    retryable_patterns = [
        "rate limit",
        "429",
        "timed out",
        "timeout",
        "502",
        "503",
        "504",
        "server error",
        "connection",
        "temporarily unavailable",
    ]
    return any(pattern in error_lower for pattern in retryable_patterns)


def _call_llm_with_retry(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    master_prompt: str = "",
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
) -> "llm_module.LLMResponse":
    """
    Call LLM with automatic retry on transient failures.

    Uses exponential backoff: delay = base_delay * (2 ** attempt)
    Example with base_delay=1.0: waits 1s, 2s, 4s between retries.

    Args:
        api_key: OpenRouter API key
        model: Model identifier
        system_prompt: System instructions
        user_prompt: User message
        temperature: Sampling temperature
        master_prompt: Optional user master prompt
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)

    Returns:
        LLMResponse from the underlying call_llm function
    """
    last_result = None

    for attempt in range(max_retries):
        result = call_llm(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            master_prompt=master_prompt,
        )

        # Success - return immediately
        if result.success:
            if attempt > 0:
                logger.info(f"LLM call succeeded after {attempt + 1} attempts")
            return result

        # Check if error is retryable
        if not _is_retryable_error(result.error):
            logger.warning(f"Non-retryable LLM error: {result.error}")
            return result

        last_result = result

        # Calculate delay with exponential backoff
        delay = base_delay * (2 ** attempt)

        # Log retry attempt
        if attempt < max_retries - 1:
            logger.warning(
                f"LLM call failed (attempt {attempt + 1}/{max_retries}): {result.error}. "
                f"Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)
        else:
            logger.error(
                f"LLM call failed after {max_retries} attempts: {result.error}"
            )

    # All retries exhausted, return last result
    return last_result


def get_llm_response(
    prompt: str, system_prompt: str = "", temperature: float = 0.7
) -> str:
    """
    High-level wrapper for LLM calls.

    Loads config from environment, calls the LLM, and returns the response
    content as a string. Handles errors by returning an error message string.

    Args:
        prompt: User message / query
        system_prompt: System instructions for the LLM
        temperature: Sampling temperature (0.0-1.0)

    Returns:
        Response text from LLM, or "Error: ..." message if call failed

    Raises:
        No exceptions - errors are returned as strings
    """
    logger.info(
        f"LLM request - prompt: {len(prompt)} chars, system: {len(system_prompt)} chars"
    )

    cfg = config.load_config()

    # Validate API key is present
    if not cfg.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY not set in environment")
        return "Error: OPENROUTER_API_KEY not configured"

    result = call_llm(
        user_prompt=prompt,
        system_prompt=system_prompt,
        api_key=cfg.openrouter_api_key,
        model=cfg.openrouter_model,
        temperature=temperature,
    )

    logger.info(
        f"LLM response - success: {result.success}, tokens: {result.tokens_used}"
    )

    if not result.success:
        logger.error(f"LLM error: {result.error}")
        return f"Error: {result.error}"

    return result.content


@dataclass
class LLMConfig:
    """User LLM configuration from settings."""

    model: str = "moonshotai/kimi-k2.5"
    temperature: float = 0.7
    master_prompt: str = ""


async def get_user_llm_config(user_id: str) -> LLMConfig:
    """
    Fetch user's LLM settings from database.

    Args:
        user_id: The user's ID

    Returns:
        LLMConfig with user's preferences
    """
    from backend.core.settings_db import settings_db

    try:
        settings = await settings_db.get_settings(user_id)
        return LLMConfig(
            model=settings.llm_model,
            temperature=settings.temperature,
            master_prompt=settings.master_system_prompt,
        )
    except (KeyError, ValueError, OSError) as e:
        logger.warning(f"Failed to load user settings, using defaults: {e}")
        return LLMConfig()


@dataclass
class LLMResult:
    """Result from LLM call with actual usage stats."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None


def get_llm_response_with_settings(
    prompt: str,
    system_prompt: str = "",
    llm_config: Optional[LLMConfig] = None,
) -> str:
    """
    Settings-aware wrapper for LLM calls.

    Uses user's preferred model, temperature, and master prompt.

    Args:
        prompt: User message / query
        system_prompt: System instructions for the LLM
        llm_config: User's LLM configuration (from get_user_llm_config)

    Returns:
        Response text from LLM, or "Error: ..." message if call failed

    Note: For actual token counts, use get_llm_response_with_usage() instead.
    """
    result = get_llm_response_with_usage(prompt, system_prompt, llm_config)
    return result.content if result.success else f"Error: {result.error}"


def get_llm_response_with_usage(
    prompt: str,
    system_prompt: str = "",
    llm_config: Optional[LLMConfig] = None,
) -> LLMResult:
    """
    Settings-aware wrapper for LLM calls with automatic retry on transient failures.

    Uses user's preferred model, temperature, and master prompt.
    Returns actual token counts from the API response, not estimates.
    Automatically retries on rate limits and timeouts with exponential backoff.

    Args:
        prompt: User message / query
        system_prompt: System instructions for the LLM
        llm_config: User's LLM configuration (from get_user_llm_config)

    Returns:
        LLMResult with content and actual usage stats
    """
    cfg = config.load_config()

    # Validate API key is present
    if not cfg.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY not set in environment")
        return LLMResult(
            content="", success=False, error="OPENROUTER_API_KEY not configured"
        )

    # Use settings or defaults
    if llm_config is None:
        llm_config = LLMConfig()

    # Use user's model preference, fallback to env config
    model = llm_config.model or cfg.openrouter_model
    temperature = llm_config.temperature
    master_prompt = llm_config.master_prompt

    logger.info(
        f"LLM request (with settings) - model: {model}, temp: {temperature}, "
        f"master_prompt: {len(master_prompt)} chars, prompt: {len(prompt)} chars"
    )

    # Use retry wrapper for resilience against transient failures
    result = _call_llm_with_retry(
        api_key=cfg.openrouter_api_key,
        model=model,
        system_prompt=system_prompt,
        user_prompt=prompt,
        temperature=temperature,
        master_prompt=master_prompt,
    )

    logger.info(
        f"LLM response - success: {result.success}, "
        f"tokens: {result.tokens_used} (in: {result.input_tokens}, out: {result.output_tokens}), "
        f"cost: ${result.cost_usd:.6f}"
    )

    if not result.success:
        logger.error(f"LLM error: {result.error}")
        return LLMResult(content="", success=False, error=result.error)

    return LLMResult(
        content=result.content,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.tokens_used,
        cost_usd=result.cost_usd,
        success=True,
    )
