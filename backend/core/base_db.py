"""
Base class for async SQLite database operations.

Provides common initialization pattern to avoid duplication across
auth_db, settings_db, and job queue implementations.
"""

import logging
from abc import ABC
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


class AsyncSQLiteDB(ABC):
    """
    Base class for async SQLite database operations.

    Handles:
    - Path creation and parent directory setup
    - Lazy initialization with idempotent schema creation
    - Common connection patterns

    Subclasses must define:
    - SCHEMA: Class attribute with SQL schema
    - _db_name: Human-readable name for logging

    Example:
        class MyDB(AsyncSQLiteDB):
            SCHEMA = '''CREATE TABLE IF NOT EXISTS items (...)'''
            _db_name = "items"

            def __init__(self, db_path: str = "data/items.db"):
                super().__init__(db_path)
    """

    # Subclasses should override these
    SCHEMA: str = ""
    _db_name: str = "database"

    def __init__(self, db_path: str):
        """
        Initialize database connection parameters.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self):
        """
        Initialize the database schema.

        Idempotent: safe to call multiple times.
        Creates tables only if they don't exist.
        """
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(self.SCHEMA)
            await db.commit()

        self._initialized = True
        logger.info(f"{self._db_name} database initialized at {self.db_path}")

    async def _ensure_initialized(self):
        """Ensure database is initialized before operations."""
        if not self._initialized:
            await self.initialize()
