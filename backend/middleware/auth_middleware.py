"""
Authentication middleware for FastAPI.

Provides dependencies for protecting routes with JWT authentication.
"""

import logging
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


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token_param: Optional[str] = Query(None, alias="token"),
) -> User:
    """
    FastAPI dependency that validates JWT and returns the current user.

    Checks for token in:
    1. Authorization header (Bearer token)
    2. Query parameter 'token' (for SSE/EventSource which can't set headers)

    Raises:
        HTTPException(401): If no token provided or token is invalid

    Returns:
        User object for the authenticated user
    """
    token = None

    # Try Authorization header first
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    # Fall back to query parameter (for SSE)
    if not token and token_param:
        token = token_param

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token and get user
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
    or None if not authenticated.

    Use this for endpoints that work with or without authentication,
    but provide enhanced features for authenticated users.

    Returns:
        User object if authenticated, None otherwise
    """
    token = None

    # Try Authorization header first
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    # Fall back to query parameter (for SSE)
    if not token and token_param:
        token = token_param

    if not token:
        return None

    # Try to validate token
    try:
        user = await get_user_from_token(token)
        return user
    except Exception:
        return None


def require_auth(user: User = Depends(get_current_user)) -> User:
    """
    Explicit dependency that requires authentication.

    This is equivalent to using Depends(get_current_user) directly,
    but provides a more explicit name for route definitions.

    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(require_auth)):
            return {"user_id": user.id}
    """
    return user
