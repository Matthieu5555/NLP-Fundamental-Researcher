"""
User settings database operations.

Handles per-user settings storage in SQLite.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import aiosqlite

from .base_db import AsyncSQLiteDB

logger = logging.getLogger(__name__)

# SQLite schema for user settings
SCHEMA = """
CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    master_system_prompt TEXT DEFAULT '',
    llm_model TEXT DEFAULT 'anthropic/claude-sonnet-4',
    temperature REAL DEFAULT 0.7,
    theme TEXT DEFAULT 'light',
    show_cost_tracking BOOLEAN DEFAULT TRUE,
    default_chart_timeframe TEXT DEFAULT '1y',
    analysis_depth TEXT DEFAULT 'standard',
    auto_run_analysis BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_settings_user ON user_settings(user_id);
"""

# Default settings values
DEFAULTS = {
    "master_system_prompt": "",
    "llm_model": "anthropic/claude-sonnet-4",
    "temperature": 0.7,
    "theme": "light",
    "show_cost_tracking": True,
    "default_chart_timeframe": "1y",
    "analysis_depth": "standard",
    "auto_run_analysis": False,
}


@dataclass
class UserSettings:
    """User settings data model."""
    user_id: str
    master_system_prompt: str = ""
    llm_model: str = "anthropic/claude-sonnet-4"
    temperature: float = 0.7
    theme: str = "light"
    show_cost_tracking: bool = True
    default_chart_timeframe: str = "1y"
    analysis_depth: str = "standard"
    auto_run_analysis: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "master_system_prompt": self.master_system_prompt,
            "llm_model": self.llm_model,
            "temperature": self.temperature,
            "theme": self.theme,
            "show_cost_tracking": self.show_cost_tracking,
            "default_chart_timeframe": self.default_chart_timeframe,
            "analysis_depth": self.analysis_depth,
            "auto_run_analysis": self.auto_run_analysis,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SettingsDB(AsyncSQLiteDB):
    """
    User settings database operations.

    Handles user preferences and configuration storage.
    """

    SCHEMA = SCHEMA
    _db_name = "Settings"

    def __init__(self, db_path: str = "data/settings.db"):
        super().__init__(db_path)

    async def get_settings(self, user_id: str) -> UserSettings:
        """
        Get settings for a user.

        Creates default settings if none exist.

        Args:
            user_id: The user ID

        Returns:
            UserSettings object
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM user_settings WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_settings(dict(row))

        # No settings found - create defaults
        return await self._create_default_settings(user_id)

    async def _create_default_settings(self, user_id: str) -> UserSettings:
        """Create default settings for a new user."""
        now = datetime.now()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO user_settings (
                    user_id, master_system_prompt, llm_model, temperature,
                    theme, show_cost_tracking, default_chart_timeframe,
                    analysis_depth, auto_run_analysis, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    DEFAULTS["master_system_prompt"],
                    DEFAULTS["llm_model"],
                    DEFAULTS["temperature"],
                    DEFAULTS["theme"],
                    DEFAULTS["show_cost_tracking"],
                    DEFAULTS["default_chart_timeframe"],
                    DEFAULTS["analysis_depth"],
                    DEFAULTS["auto_run_analysis"],
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            await db.commit()

        logger.info(f"Created default settings for user {user_id}")

        return UserSettings(
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )

    async def update_settings(self, user_id: str, **updates) -> UserSettings:
        """
        Update user settings (partial update).

        Args:
            user_id: The user ID
            **updates: Fields to update

        Returns:
            Updated UserSettings object
        """
        await self.initialize()

        # Ensure settings exist
        await self.get_settings(user_id)

        # Filter valid fields
        valid_fields = {
            "master_system_prompt", "llm_model", "temperature",
            "theme", "show_cost_tracking", "default_chart_timeframe",
            "analysis_depth", "auto_run_analysis"
        }
        filtered_updates = {k: v for k, v in updates.items() if k in valid_fields}

        if not filtered_updates:
            return await self.get_settings(user_id)

        # Build update query
        set_clauses = [f"{field} = ?" for field in filtered_updates.keys()]
        set_clauses.append("updated_at = ?")
        values = list(filtered_updates.values())
        values.append(datetime.now().isoformat())
        values.append(user_id)

        query = f"UPDATE user_settings SET {', '.join(set_clauses)} WHERE user_id = ?"

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, values)
            await db.commit()

        logger.info(f"Updated settings for user {user_id}: {list(filtered_updates.keys())}")

        return await self.get_settings(user_id)

    async def reset_to_defaults(self, user_id: str) -> UserSettings:
        """
        Reset all settings to defaults.

        Args:
            user_id: The user ID

        Returns:
            Reset UserSettings object
        """
        await self.initialize()
        now = datetime.now()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE user_settings SET
                    master_system_prompt = ?,
                    llm_model = ?,
                    temperature = ?,
                    theme = ?,
                    show_cost_tracking = ?,
                    default_chart_timeframe = ?,
                    analysis_depth = ?,
                    auto_run_analysis = ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    DEFAULTS["master_system_prompt"],
                    DEFAULTS["llm_model"],
                    DEFAULTS["temperature"],
                    DEFAULTS["theme"],
                    DEFAULTS["show_cost_tracking"],
                    DEFAULTS["default_chart_timeframe"],
                    DEFAULTS["analysis_depth"],
                    DEFAULTS["auto_run_analysis"],
                    now.isoformat(),
                    user_id,
                ),
            )
            await db.commit()

        logger.info(f"Reset settings to defaults for user {user_id}")

        return await self.get_settings(user_id)

    async def delete_settings(self, user_id: str):
        """Delete settings for a user (used when user is deleted)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM user_settings WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
        logger.info(f"Deleted settings for user {user_id}")

    def _row_to_settings(self, row: dict) -> UserSettings:
        """Convert a database row to a UserSettings object."""
        return UserSettings(
            user_id=row["user_id"],
            master_system_prompt=row.get("master_system_prompt", ""),
            llm_model=row.get("llm_model", DEFAULTS["llm_model"]),
            temperature=float(row.get("temperature", DEFAULTS["temperature"])),
            theme=row.get("theme", DEFAULTS["theme"]),
            show_cost_tracking=bool(row.get("show_cost_tracking", True)),
            default_chart_timeframe=row.get("default_chart_timeframe", DEFAULTS["default_chart_timeframe"]),
            analysis_depth=row.get("analysis_depth", DEFAULTS["analysis_depth"]),
            auto_run_analysis=bool(row.get("auto_run_analysis", False)),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# Global settings database instance
settings_db = SettingsDB()
