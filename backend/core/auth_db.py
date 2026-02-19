"""
Authentication database operations.

Handles user and refresh token storage in SQLite.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

from .base_db import AsyncSQLiteDB

logger = logging.getLogger(__name__)

# SQLite schema for auth
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    company TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
"""


@dataclass
class User:
    """User data model."""
    id: str
    email: str
    password_hash: str
    display_name: Optional[str] = None
    company: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_login_at: Optional[datetime] = None
    is_active: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "company": self.company,
            "created_at": self.created_at.isoformat(),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "is_active": self.is_active,
        }


@dataclass
class RefreshToken:
    """Refresh token data model."""
    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)
    revoked_at: Optional[datetime] = None

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid."""
        return (
            self.revoked_at is None
            and datetime.now() < self.expires_at
        )


class AuthDB(AsyncSQLiteDB):
    """
    Authentication database operations.

    Handles user CRUD and refresh token management.
    """

    SCHEMA = SCHEMA
    _db_name = "Auth"

    def __init__(self, db_path: str = "data/auth.db"):
        super().__init__(db_path)

    # --- User Operations ---

    async def create_user(
        self,
        email: str,
        password_hash: str,
        display_name: Optional[str] = None,
        company: Optional[str] = None,
    ) -> User:
        """
        Create a new user.

        Args:
            email: User email (must be unique)
            password_hash: Bcrypt hashed password
            display_name: Optional display name
            company: Optional company name

        Returns:
            Created User object

        Raises:
            ValueError: If email already exists
        """
        await self.initialize()

        user_id = str(uuid.uuid4())
        now = datetime.now()

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO users (id, email, password_hash, display_name, company, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, email.lower(), password_hash, display_name, company, now.isoformat(), True),
                )
                await db.commit()
            except aiosqlite.IntegrityError:
                raise ValueError(f"Email already registered: {email}")

        logger.info(f"Created user {user_id} with email {email}")

        return User(
            id=user_id,
            email=email.lower(),
            password_hash=password_hash,
            display_name=display_name,
            company=company,
            created_at=now,
            is_active=True,
        )

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE email = ? AND is_active = TRUE",
                (email.lower(),),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_user(dict(row))
        return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE id = ? AND is_active = TRUE",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_user(dict(row))
        return None

    async def update_last_login(self, user_id: str):
        """Update the last login timestamp for a user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (datetime.now().isoformat(), user_id),
            )
            await db.commit()

    async def deactivate_user(self, user_id: str):
        """Deactivate a user account (soft delete)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET is_active = FALSE WHERE id = ?",
                (user_id,),
            )
            await db.commit()
        logger.info(f"Deactivated user {user_id}")

    # --- Refresh Token Operations ---

    async def store_refresh_token(
        self,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> str:
        """
        Store a refresh token.

        Args:
            user_id: The user this token belongs to
            token_hash: SHA256 hash of the refresh token
            expires_at: When the token expires

        Returns:
            The token ID
        """
        await self.initialize()

        token_id = str(uuid.uuid4())
        now = datetime.now()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token_id, user_id, token_hash, expires_at.isoformat(), now.isoformat()),
            )
            await db.commit()

        logger.debug(f"Stored refresh token {token_id} for user {user_id}")
        return token_id

    async def validate_refresh_token(self, token_hash: str) -> Optional[RefreshToken]:
        """
        Validate a refresh token by its hash.

        Returns the RefreshToken if valid, None otherwise.
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM refresh_tokens
                WHERE token_hash = ? AND revoked_at IS NULL
                """,
                (token_hash,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    token = self._row_to_refresh_token(dict(row))
                    if token.is_valid:
                        return token
        return None

    async def revoke_refresh_token(self, token_id: str):
        """Revoke a specific refresh token."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?",
                (datetime.now().isoformat(), token_id),
            )
            await db.commit()
        logger.debug(f"Revoked refresh token {token_id}")

    async def revoke_token_by_hash(self, token_hash: str):
        """Revoke a refresh token by its hash."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE token_hash = ?",
                (datetime.now().isoformat(), token_hash),
            )
            await db.commit()

    async def revoke_all_user_tokens(self, user_id: str):
        """Revoke all refresh tokens for a user (logout everywhere)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE refresh_tokens SET revoked_at = ?
                WHERE user_id = ? AND revoked_at IS NULL
                """,
                (datetime.now().isoformat(), user_id),
            )
            await db.commit()
        logger.info(f"Revoked all refresh tokens for user {user_id}")

    async def cleanup_expired_tokens(self):
        """Remove expired and revoked refresh tokens."""
        async with aiosqlite.connect(self.db_path) as db:
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            result = await db.execute(
                """
                DELETE FROM refresh_tokens
                WHERE revoked_at IS NOT NULL
                OR expires_at < ?
                """,
                (cutoff,),
            )
            await db.commit()
            logger.info(f"Cleaned up {result.rowcount} expired refresh tokens")

    # --- Helper Methods ---

    def _row_to_user(self, row: dict) -> User:
        """Convert a database row to a User object."""
        return User(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            display_name=row.get("display_name"),
            company=row.get("company"),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_login_at=(
                datetime.fromisoformat(row["last_login_at"])
                if row.get("last_login_at")
                else None
            ),
            is_active=bool(row.get("is_active", True)),
        )

    def _row_to_refresh_token(self, row: dict) -> RefreshToken:
        """Convert a database row to a RefreshToken object."""
        return RefreshToken(
            id=row["id"],
            user_id=row["user_id"],
            token_hash=row["token_hash"],
            expires_at=datetime.fromisoformat(row["expires_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            revoked_at=(
                datetime.fromisoformat(row["revoked_at"])
                if row.get("revoked_at")
                else None
            ),
        )

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a refresh token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()


# Global auth database instance
auth_db = AuthDB()
