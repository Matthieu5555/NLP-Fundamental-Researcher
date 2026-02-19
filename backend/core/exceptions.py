"""
Custom exception hierarchy for the backend.

Design principles:
1. Exceptions carry context for debugging
2. Hierarchy enables catching at appropriate granularity
3. Each exception maps to a clear failure mode

Usage:
    try:
        result = call_llm(...)
    except LLMError as e:
        logger.error(f"LLM failed: {e.message}", extra={"model": e.model})
        # Handle or re-raise
"""

from typing import Optional


class GeorgeError(Exception):
    """Base exception for all George backend errors."""

    def __init__(self, message: str, **context):
        self.message = message
        self.context = context
        super().__init__(message)

    def __str__(self):
        if self.context:
            ctx = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx})"
        return self.message


# =============================================================================
# LLM / AI Errors
# =============================================================================

class LLMError(GeorgeError):
    """Base class for LLM-related errors."""

    def __init__(self, message: str, model: str = "", **context):
        self.model = model
        super().__init__(message, model=model, **context)


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded - retryable after backoff."""

    def __init__(self, model: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(
            "Rate limit exceeded",
            model=model,
            retry_after=retry_after,
        )


class LLMTimeoutError(LLMError):
    """LLM request timed out - retryable."""

    def __init__(self, model: str, timeout_seconds: float):
        super().__init__(
            f"Request timed out after {timeout_seconds}s",
            model=model,
            timeout=timeout_seconds,
        )


class LLMResponseError(LLMError):
    """LLM returned an error response - may or may not be retryable."""

    def __init__(self, model: str, status_code: int, response_text: str):
        self.status_code = status_code
        self.response_text = response_text
        self.retryable = status_code in (429, 500, 502, 503, 504)
        super().__init__(
            f"HTTP {status_code}: {response_text[:100]}",
            model=model,
            status_code=status_code,
            retryable=self.retryable,
        )


class LLMParseError(LLMError):
    """Failed to parse LLM response (e.g., invalid JSON)."""

    def __init__(self, model: str, expected_format: str, raw_content: str):
        super().__init__(
            f"Failed to parse {expected_format} from response",
            model=model,
            expected_format=expected_format,
            content_preview=raw_content[:200],
        )


# =============================================================================
# Data Fetching Errors
# =============================================================================

class DataFetchError(GeorgeError):
    """Base class for data fetching errors."""

    def __init__(self, message: str, source: str, **context):
        self.source = source
        super().__init__(message, source=source, **context)


class DataSourceUnavailable(DataFetchError):
    """External data source is unavailable - may be temporary."""

    def __init__(self, source: str, reason: str):
        super().__init__(f"{source} unavailable: {reason}", source=source)


class DataNotFound(DataFetchError):
    """Requested data does not exist (e.g., unknown ticker)."""

    def __init__(self, source: str, ticker: str):
        self.ticker = ticker
        super().__init__(f"No data found for {ticker}", source=source, ticker=ticker)


class RateLimitError(DataFetchError):
    """External API rate limit hit."""

    def __init__(self, source: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for {source}",
            source=source,
            retry_after=retry_after,
        )


# =============================================================================
# Session / State Errors
# =============================================================================

class SessionError(GeorgeError):
    """Base class for session-related errors."""

    def __init__(self, message: str, session_id: str = "", **context):
        self.session_id = session_id
        super().__init__(message, session_id=session_id, **context)


class SessionNotFound(SessionError):
    """Session does not exist."""

    def __init__(self, session_id: str):
        super().__init__("Session not found", session_id=session_id)


class SessionExpired(SessionError):
    """Session has expired."""

    def __init__(self, session_id: str):
        super().__init__("Session expired", session_id=session_id)


class SessionCorrupted(SessionError):
    """Session data is corrupted and cannot be loaded."""

    def __init__(self, session_id: str, reason: str):
        super().__init__(f"Session corrupted: {reason}", session_id=session_id)


# =============================================================================
# Authentication Errors
# =============================================================================

class AuthError(GeorgeError):
    """Base class for authentication errors."""
    pass


class InvalidCredentials(AuthError):
    """Invalid username or password."""

    def __init__(self):
        super().__init__("Invalid credentials")


class TokenExpired(AuthError):
    """JWT or refresh token has expired."""

    def __init__(self, token_type: str = "access"):
        super().__init__(f"{token_type.capitalize()} token expired", token_type=token_type)


class TokenInvalid(AuthError):
    """Token is malformed or signature is invalid."""

    def __init__(self, reason: str = ""):
        super().__init__(f"Invalid token{': ' + reason if reason else ''}")


# =============================================================================
# Analysis Errors
# =============================================================================

class AnalysisError(GeorgeError):
    """Base class for analysis pipeline errors."""

    def __init__(self, message: str, ticker: str = "", stage: str = "", **context):
        self.ticker = ticker
        self.stage = stage
        super().__init__(message, ticker=ticker, stage=stage, **context)


class AnalysisDataInsufficient(AnalysisError):
    """Not enough data to perform analysis."""

    def __init__(self, ticker: str, missing: str):
        super().__init__(
            f"Insufficient data for analysis: missing {missing}",
            ticker=ticker,
            missing=missing,
        )


# =============================================================================
# Configuration Errors
# =============================================================================

class ConfigError(GeorgeError):
    """Configuration is invalid or missing."""

    def __init__(self, message: str, key: str = "", **context):
        self.key = key
        super().__init__(message, key=key, **context)


class MissingAPIKey(ConfigError):
    """Required API key is not configured."""

    def __init__(self, key_name: str):
        super().__init__(f"Missing required API key: {key_name}", key=key_name)
