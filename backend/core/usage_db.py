"""
Usage tracking database operations.

Tracks API usage per user for cost attribution and monitoring.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import aiosqlite

logger = logging.getLogger(__name__)

# SQLite schema for usage tracking
SCHEMA = """
CREATE TABLE IF NOT EXISTS api_usage (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    ticker TEXT,
    session_id TEXT,
    cost_usd REAL DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    cached BOOLEAN DEFAULT FALSE,
    duration_ms INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_user ON api_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON api_usage(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_endpoint ON api_usage(endpoint);
CREATE INDEX IF NOT EXISTS idx_usage_ticker ON api_usage(ticker);
"""


@dataclass
class UsageRecord:
    """Individual usage record."""
    id: str
    user_id: str
    endpoint: str
    method: str
    timestamp: datetime
    ticker: Optional[str] = None
    session_id: Optional[str] = None
    cost_usd: float = 0.0
    tokens_used: int = 0
    cached: bool = False
    duration_ms: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "ticker": self.ticker,
            "session_id": self.session_id,
            "cost_usd": self.cost_usd,
            "tokens_used": self.tokens_used,
            "cached": self.cached,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class UsageSummary:
    """Aggregated usage summary."""
    total_requests: int
    total_cost_usd: float
    total_tokens: int
    cached_requests: int
    cache_hit_rate: float
    by_endpoint: Dict[str, int]
    by_ticker: Dict[str, int]
    period_start: datetime
    period_end: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_requests": self.total_requests,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_tokens": self.total_tokens,
            "cached_requests": self.cached_requests,
            "cache_hit_rate": round(self.cache_hit_rate, 2),
            "by_endpoint": self.by_endpoint,
            "by_ticker": self.by_ticker,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
        }


class UsageDB:
    """
    Usage tracking database operations.

    Handles recording and querying API usage per user.
    """

    def __init__(self, db_path: str = "data/usage.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self):
        """Initialize the database schema."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

        self._initialized = True
        logger.info(f"Usage database initialized at {self.db_path}")

    async def record_usage(
        self,
        user_id: str,
        endpoint: str,
        method: str,
        ticker: Optional[str] = None,
        session_id: Optional[str] = None,
        cost_usd: float = 0.0,
        tokens_used: int = 0,
        cached: bool = False,
        duration_ms: int = 0,
    ) -> UsageRecord:
        """
        Record an API usage event.

        Args:
            user_id: The user making the request
            endpoint: The API endpoint called (e.g., "/api/analysis/start")
            method: HTTP method (GET, POST, etc.)
            ticker: Optional stock ticker if relevant
            session_id: Optional session ID if relevant
            cost_usd: API cost in USD (LLM, data sources)
            tokens_used: LLM tokens used
            cached: Whether the response was cached
            duration_ms: Request duration in milliseconds

        Returns:
            Created UsageRecord
        """
        await self.initialize()

        record_id = str(uuid.uuid4())
        now = datetime.now()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO api_usage
                (id, user_id, endpoint, method, ticker, session_id,
                 cost_usd, tokens_used, cached, duration_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    user_id,
                    endpoint,
                    method.upper(),
                    ticker,
                    session_id,
                    cost_usd,
                    tokens_used,
                    cached,
                    duration_ms,
                    now.isoformat(),
                ),
            )
            await db.commit()

        logger.debug(f"Recorded usage: {user_id} -> {method} {endpoint} (${cost_usd:.4f})")

        return UsageRecord(
            id=record_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method.upper(),
            ticker=ticker,
            session_id=session_id,
            cost_usd=cost_usd,
            tokens_used=tokens_used,
            cached=cached,
            duration_ms=duration_ms,
            timestamp=now,
        )

    async def get_user_usage(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100,
    ) -> List[UsageRecord]:
        """
        Get recent usage records for a user.

        Args:
            user_id: The user to get usage for
            days: Number of days to look back
            limit: Maximum records to return

        Returns:
            List of UsageRecord objects
        """
        await self.initialize()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM api_usage
                WHERE user_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (user_id, cutoff, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_record(dict(row)) for row in rows]

    async def get_user_summary(
        self,
        user_id: str,
        days: int = 30,
    ) -> UsageSummary:
        """
        Get aggregated usage summary for a user.

        Args:
            user_id: The user to summarize
            days: Number of days to aggregate

        Returns:
            UsageSummary object
        """
        await self.initialize()

        now = datetime.now()
        cutoff = now - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Get totals
            async with db.execute(
                """
                SELECT
                    COUNT(*) as total_requests,
                    COALESCE(SUM(cost_usd), 0) as total_cost,
                    COALESCE(SUM(tokens_used), 0) as total_tokens,
                    COALESCE(SUM(CASE WHEN cached THEN 1 ELSE 0 END), 0) as cached_requests
                FROM api_usage
                WHERE user_id = ? AND timestamp >= ?
                """,
                (user_id, cutoff_iso),
            ) as cursor:
                row = await cursor.fetchone()
                totals = dict(row) if row else {
                    "total_requests": 0,
                    "total_cost": 0,
                    "total_tokens": 0,
                    "cached_requests": 0,
                }

            # Get by endpoint
            async with db.execute(
                """
                SELECT endpoint, COUNT(*) as count
                FROM api_usage
                WHERE user_id = ? AND timestamp >= ?
                GROUP BY endpoint
                ORDER BY count DESC
                LIMIT 10
                """,
                (user_id, cutoff_iso),
            ) as cursor:
                rows = await cursor.fetchall()
                by_endpoint = {row["endpoint"]: row["count"] for row in rows}

            # Get by ticker
            async with db.execute(
                """
                SELECT ticker, COUNT(*) as count
                FROM api_usage
                WHERE user_id = ? AND timestamp >= ? AND ticker IS NOT NULL
                GROUP BY ticker
                ORDER BY count DESC
                LIMIT 10
                """,
                (user_id, cutoff_iso),
            ) as cursor:
                rows = await cursor.fetchall()
                by_ticker = {row["ticker"]: row["count"] for row in rows}

        total_requests = totals["total_requests"]
        cached_requests = totals["cached_requests"]
        cache_hit_rate = (cached_requests / total_requests * 100) if total_requests > 0 else 0

        return UsageSummary(
            total_requests=total_requests,
            total_cost_usd=totals["total_cost"],
            total_tokens=totals["total_tokens"],
            cached_requests=cached_requests,
            cache_hit_rate=cache_hit_rate,
            by_endpoint=by_endpoint,
            by_ticker=by_ticker,
            period_start=cutoff,
            period_end=now,
        )

    async def get_daily_breakdown(
        self,
        user_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get daily usage breakdown for a user.

        Args:
            user_id: The user to query
            days: Number of days to look back

        Returns:
            List of daily stats
        """
        await self.initialize()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as requests,
                    COALESCE(SUM(cost_usd), 0) as cost_usd,
                    COALESCE(SUM(tokens_used), 0) as tokens
                FROM api_usage
                WHERE user_id = ? AND timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                """,
                (user_id, cutoff),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "date": row["date"],
                        "requests": row["requests"],
                        "cost_usd": round(row["cost_usd"], 4),
                        "tokens": row["tokens"],
                    }
                    for row in rows
                ]

    async def get_cost_by_category(
        self,
        user_id: str,
        days: int = 30,
    ) -> Dict[str, float]:
        """
        Get cost breakdown by endpoint category.

        Args:
            user_id: The user to query
            days: Number of days to look back

        Returns:
            Dict mapping category to total cost
        """
        await self.initialize()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT
                    CASE
                        WHEN endpoint LIKE '%/analysis%' THEN 'analysis'
                        WHEN endpoint LIKE '%/chat%' THEN 'chat'
                        WHEN endpoint LIKE '%/reports%' THEN 'reports'
                        ELSE 'other'
                    END as category,
                    COALESCE(SUM(cost_usd), 0) as cost
                FROM api_usage
                WHERE user_id = ? AND timestamp >= ?
                GROUP BY category
                ORDER BY cost DESC
                """,
                (user_id, cutoff),
            ) as cursor:
                rows = await cursor.fetchall()
                return {row["category"]: round(row["cost"], 4) for row in rows}

    async def cleanup_old_records(self, days: int = 90):
        """
        Delete usage records older than specified days.

        Args:
            days: Delete records older than this many days
        """
        await self.initialize()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            result = await db.execute(
                "DELETE FROM api_usage WHERE timestamp < ?",
                (cutoff,),
            )
            await db.commit()
            logger.info(f"Cleaned up {result.rowcount} old usage records")

    def _row_to_record(self, row: dict) -> UsageRecord:
        """Convert a database row to a UsageRecord object."""
        return UsageRecord(
            id=row["id"],
            user_id=row["user_id"],
            endpoint=row["endpoint"],
            method=row["method"],
            ticker=row.get("ticker"),
            session_id=row.get("session_id"),
            cost_usd=row.get("cost_usd", 0.0),
            tokens_used=row.get("tokens_used", 0),
            cached=bool(row.get("cached", False)),
            duration_ms=row.get("duration_ms", 0),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )


# Global usage database instance
usage_db = UsageDB()
