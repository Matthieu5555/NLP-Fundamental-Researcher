"""
Usage tracking middleware for FastAPI.

Provides utilities to track API usage per user.
"""

import logging
import time
from typing import Optional


from backend.core.usage_db import usage_db
from backend.core.auth_db import User

logger = logging.getLogger(__name__)


async def track_request(
    user: User,
    endpoint: str,
    method: str,
    ticker: Optional[str] = None,
    session_id: Optional[str] = None,
    cost_usd: float = 0.0,
    tokens_used: int = 0,
    cached: bool = False,
    duration_ms: int = 0,
):
    """
    Track an API request for a user.

    This is the main function to call from route handlers
    when you want to record usage.

    Args:
        user: The authenticated user
        endpoint: The API endpoint called
        method: HTTP method (GET, POST, etc.)
        ticker: Optional stock ticker if relevant
        session_id: Optional session ID if relevant
        cost_usd: API cost in USD
        tokens_used: LLM tokens used
        cached: Whether response was from cache
        duration_ms: Request duration in milliseconds
    """
    try:
        await usage_db.record_usage(
            user_id=user.id,
            endpoint=endpoint,
            method=method,
            ticker=ticker,
            session_id=session_id,
            cost_usd=cost_usd,
            tokens_used=tokens_used,
            cached=cached,
            duration_ms=duration_ms,
        )
    except Exception as e:
        # Don't fail the request if usage tracking fails
        logger.warning(f"Failed to track usage: {e}")


class UsageTracker:
    """
    Context manager for tracking request duration and recording usage.

    Usage:
        async with UsageTracker(user, "/api/chat/stream", "GET", ticker="AAPL") as tracker:
            # Do work
            tracker.add_cost(0.05)
            tracker.add_tokens(1000)
    """

    def __init__(
        self,
        user: User,
        endpoint: str,
        method: str,
        ticker: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.user = user
        self.endpoint = endpoint
        self.method = method
        self.ticker = ticker
        self.session_id = session_id
        self.cost_usd = 0.0
        self.tokens_used = 0
        self.cached = False
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self.start_time) * 1000)
        await track_request(
            user=self.user,
            endpoint=self.endpoint,
            method=self.method,
            ticker=self.ticker,
            session_id=self.session_id,
            cost_usd=self.cost_usd,
            tokens_used=self.tokens_used,
            cached=self.cached,
            duration_ms=duration_ms,
        )
        return False  # Don't suppress exceptions

    def add_cost(self, cost: float):
        """Add to the cost for this request."""
        self.cost_usd += cost

    def add_tokens(self, tokens: int):
        """Add to the token count for this request."""
        self.tokens_used += tokens

    def set_cached(self, cached: bool = True):
        """Mark this request as served from cache."""
        self.cached = cached


def extract_ticker_from_path(path: str) -> Optional[str]:
    """
    Extract ticker from common path patterns.

    Examples:
        /api/analysis/start -> None (ticker in body)
        /api/chart/AAPL/data -> AAPL
        /api/companies/classify/MSFT -> MSFT
    """
    parts = path.split("/")

    # Pattern: /api/chart/{ticker}/data
    if len(parts) >= 4 and parts[2] == "chart":
        return parts[3].upper()

    # Pattern: /api/companies/classify/{ticker}
    if len(parts) >= 5 and parts[2] == "companies" and parts[3] == "classify":
        return parts[4].upper()

    return None


def extract_session_id_from_path(path: str) -> Optional[str]:
    """
    Extract session_id from common path patterns.

    Examples:
        /api/analysis/{session_id}/status -> session_id
        /api/reports/{session_id} -> session_id
        /api/sessions/{session_id}/resume -> session_id
    """
    parts = path.split("/")

    # Pattern: /api/analysis/{session_id}/*
    if len(parts) >= 4 and parts[2] == "analysis":
        # Check if it looks like a UUID
        if len(parts[3]) > 10 and "-" in parts[3]:
            return parts[3]

    # Pattern: /api/reports/{session_id}/*
    if len(parts) >= 4 and parts[2] == "reports":
        if len(parts[3]) > 10 and "-" in parts[3]:
            return parts[3]

    # Pattern: /api/sessions/{session_id}/*
    if len(parts) >= 4 and parts[2] == "sessions":
        if len(parts[3]) > 10 and "-" in parts[3]:
            return parts[3]

    return None


# Cost estimates for different operations (used when actual cost not available)
ESTIMATED_COSTS = {
    "/api/analysis/start": 0.32,  # Full analysis cost
    "/api/chat/stream": 0.02,    # Average chat message
    "/api/reports/export/pdf": 0.01,  # PDF generation
}


def get_estimated_cost(endpoint: str) -> float:
    """Get estimated cost for an endpoint if not provided."""
    for pattern, cost in ESTIMATED_COSTS.items():
        if pattern in endpoint:
            return cost
    return 0.0
