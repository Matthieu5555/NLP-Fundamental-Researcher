"""
Authentication API router.

Endpoints:
    GET  /config   - Public auth configuration (is login required?)
    POST /register - Create new user account
    POST /login    - Authenticate and get tokens
    POST /refresh  - Exchange refresh token for new access token
    POST /logout   - Revoke refresh token
    GET  /me       - Get current user info
"""

import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Header

from backend.models.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    LogoutRequest,
    UserResponse,
    TokenResponse,
    AuthResponse,
    MessageResponse,
)
from backend.core.auth import (
    register_user,
    authenticate_user,
    create_user_tokens,
    refresh_access_token,
    logout_user,
)
from backend.core.auth_db import auth_db, User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/config")
async def auth_config():
    """Public endpoint: tells the frontend whether login is required."""
    return {"require_auth": os.getenv("REQUIRE_AUTH", "false").lower() == "true"}


# Dependency to get current user (will be defined in middleware)
# For now, we import it here when the middleware is created
async def get_current_user_from_header(authorization: str = None) -> User:
    """
    Extract and validate user from Authorization header.
    This is a simple version - the full middleware will be more robust.
    """
    from backend.core.auth import get_user_from_token

    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    user = await get_user_from_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """
    Create a new user account.

    Returns user info and authentication tokens.
    """
    try:
        # Create the user
        user = await register_user(
            email=request.email,
            password=request.password,
            display_name=request.display_name,
            company=request.company,
        )

        # Create tokens
        tokens = await create_user_tokens(user)

        # Update last login
        await auth_db.update_last_login(user.id)

        logger.info(f"User registered: {user.email}")

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                company=user.company,
                created_at=user.created_at.isoformat(),
                is_active=user.is_active,
            ),
            tokens=TokenResponse(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_type=tokens["token_type"],
                expires_in=tokens["expires_in"],
            ),
        )

    except ValueError as e:
        # Email already exists
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and get tokens.

    Returns user info and authentication tokens.
    """
    # Authenticate
    user = await authenticate_user(request.email, request.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create tokens
    tokens = await create_user_tokens(user)

    # Update last login
    await auth_db.update_last_login(user.id)

    logger.info(f"User logged in: {user.email}")

    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            company=user.company,
            created_at=user.created_at.isoformat(),
            is_active=user.is_active,
        ),
        tokens=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest):
    """
    Exchange refresh token for new access token.

    The refresh token remains valid until logout or expiry.
    """
    result = await refresh_access_token(request.refresh_token)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=None,  # Don't return new refresh token on refresh
        token_type=result["token_type"],
        expires_in=result["expires_in"],
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(request: LogoutRequest):
    """
    Logout by revoking the refresh token.

    The access token will still be valid until it expires,
    but the refresh token cannot be used to get new tokens.
    """
    success = await logout_user(request.refresh_token)

    if success:
        logger.info("User logged out")
        return MessageResponse(message="Logged out successfully", success=True)
    else:
        # Don't reveal if token existed or not
        return MessageResponse(message="Logged out successfully", success=True)


@router.get("/me", response_model=UserResponse)
async def get_me(authorization: Optional[str] = Header(None)):
    """
    Get current user information.

    Requires valid access token in Authorization header.
    """
    # Get token from header
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await get_current_user_from_header(authorization)

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at.isoformat(),
        is_active=user.is_active,
    )
