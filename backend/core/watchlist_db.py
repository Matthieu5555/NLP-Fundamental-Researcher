"""
Watchlist database for tracking user stock watchlists with fair value data.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    user_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    last_fair_value REAL,
    last_session_id TEXT,
    company_name TEXT,
    PRIMARY KEY (user_id, ticker)
);
"""


@dataclass
class WatchlistItem:
    """A single watchlist entry."""
    user_id: str
    ticker: str
    added_at: str
    last_fair_value: Optional[float] = None
    last_session_id: Optional[str] = None
    company_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "added_at": self.added_at,
            "last_fair_value": self.last_fair_value,
            "last_session_id": self.last_session_id,
            "company_name": self.company_name,
        }


class WatchlistDB:
    """Watchlist database operations."""

    def __init__(self, db_path: str = "data/watchlist.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self):
        """Initialize the database schema."""
        if self._initialized:
            return
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        self._initialized = True

    async def get_watchlist(self, user_id: str) -> List[WatchlistItem]:
        """Get all watchlist items for a user."""
        await self.initialize()
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    WatchlistItem(
                        user_id=row["user_id"],
                        ticker=row["ticker"],
                        added_at=row["added_at"],
                        last_fair_value=row["last_fair_value"],
                        last_session_id=row["last_session_id"],
                        company_name=row["company_name"],
                    )
                    for row in rows
                ]

    async def add_to_watchlist(
        self,
        user_id: str,
        ticker: str,
        company_name: Optional[str] = None,
        fair_value: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> WatchlistItem:
        """Add or update a ticker on the watchlist."""
        await self.initialize()
        now = datetime.now().isoformat()
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT INTO watchlist (user_id, ticker, added_at, last_fair_value, last_session_id, company_name)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, ticker) DO UPDATE SET
                     last_fair_value = COALESCE(excluded.last_fair_value, last_fair_value),
                     last_session_id = COALESCE(excluded.last_session_id, last_session_id),
                     company_name = COALESCE(excluded.company_name, company_name)""",
                (user_id, ticker.upper(), now, fair_value, session_id, company_name),
            )
            await db.commit()

        return WatchlistItem(
            user_id=user_id,
            ticker=ticker.upper(),
            added_at=now,
            last_fair_value=fair_value,
            last_session_id=session_id,
            company_name=company_name,
        )

    async def remove_from_watchlist(self, user_id: str, ticker: str) -> bool:
        """Remove a ticker from the watchlist."""
        await self.initialize()
        async with aiosqlite.connect(str(self.db_path)) as db:
            result = await db.execute(
                "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
                (user_id, ticker.upper()),
            )
            await db.commit()
            return result.rowcount > 0

    async def update_fair_value(
        self,
        user_id: str,
        ticker: str,
        fair_value: float,
        session_id: Optional[str] = None,
    ) -> None:
        """Update fair value for a single user's watchlist item."""
        await self.initialize()
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """UPDATE watchlist
                   SET last_fair_value = ?, last_session_id = COALESCE(?, last_session_id)
                   WHERE user_id = ? AND ticker = ?""",
                (fair_value, session_id, user_id, ticker.upper()),
            )
            await db.commit()

    async def broadcast_fair_value(
        self,
        ticker: str,
        fair_value: float,
        session_id: Optional[str] = None,
    ) -> None:
        """Update fair value for all users who have this ticker on their watchlist."""
        await self.initialize()
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """UPDATE watchlist
                   SET last_fair_value = ?, last_session_id = COALESCE(?, last_session_id)
                   WHERE ticker = ?""",
                (fair_value, session_id, ticker.upper()),
            )
            await db.commit()


# Singleton instance
watchlist_db = WatchlistDB()
