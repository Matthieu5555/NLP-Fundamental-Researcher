"""
Authentication middleware for FastAPI.

Provides dependencies for protecting routes with JWT authentication.
When REQUIRE_AUTH is not "true" (the default), all routes receive a synthetic
local user so the app works out of the box without registration.
"""

import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException, Header, Query
from fastapi.security import OAuth2PasswordBearer

from backend.core.auth import get_user_from_token
from backend.core.auth_db import User

logger = logging.getLogger(__name__)

# OAuth2 scheme for Swagger UI integration
# auto_error=False allows us to handle missing tokens ourselves
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,
)


def _auth_required() -> bool:
    """Check whether authentication is enforced."""
    return os.getenv("REQUIRE_AUTH", "false").lower() == "true"


# Synthetic user returned when auth is disabled, matching the User dataclass shape.
_LOCAL_USER = User(
    id="local",
    email="local@localhost",
    password_hash="",
    display_name="Local User",
    company=None,
    is_active=True,
)


def _extract_token(
    authorization: Optional[str],
    token_param: Optional[str],
) -> Optional[str]:
    """Extract bearer token from header or query parameter."""
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    return token_param or None


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token_param: Optional[str] = Query(None, alias="token"),
) -> User:
    """
    FastAPI dependency that returns the current user.

    When REQUIRE_AUTH is false (default), returns a local user without
    checking tokens. If a valid token is present it still decodes it,
    so auth works transparently when someone opts in.
    """
    token = _extract_token(authorization, token_param)

    if not _auth_required():
        # Even with auth disabled, honour a valid token if one is supplied
        if token:
            user = await get_user_from_token(token)
            if user:
                return user
        return _LOCAL_USER

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token_param: Optional[str] = Query(None, alias="token"),
) -> Optional[User]:
    """
    FastAPI dependency that returns the current user if authenticated,
    or the local user when auth is disabled, or None when auth is
    enabled but no token is present.
    """
    token = _extract_token(authorization, token_param)

    if not _auth_required():
        if token:
            user = await get_user_from_token(token)
            if user:
                return user
        return _LOCAL_USER

    if not token:
        return None

    try:
        return await get_user_from_token(token)
    except Exception:
        return None


def require_auth(user: User = Depends(get_current_user)) -> User:
    """Explicit dependency that requires authentication."""
    return user
