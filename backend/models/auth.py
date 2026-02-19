"""
Pydantic models for authentication endpoints.
"""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr


# --- Request Models ---

class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        description="User password",
        min_length=8,
        max_length=128,
    )
    display_name: Optional[str] = Field(
        default=None,
        description="Display name (optional)",
        max_length=100,
    )
    company: Optional[str] = Field(
        default=None,
        description="Company name (optional)",
        max_length=100,
    )


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str = Field(..., description="Refresh token")


class LogoutRequest(BaseModel):
    """Request body for logout."""

    refresh_token: str = Field(..., description="Refresh token to revoke")


# --- Response Models ---

class UserResponse(BaseModel):
    """User information response."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    display_name: Optional[str] = Field(None, description="Display name")
    company: Optional[str] = Field(None, description="Company name")
    created_at: str = Field(..., description="Account creation timestamp")
    is_active: bool = Field(..., description="Whether account is active")


class TokenResponse(BaseModel):
    """Token response for login/refresh."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token (only on login)")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")


class AuthResponse(BaseModel):
    """Combined auth response with user and tokens."""

    user: UserResponse = Field(..., description="User information")
    tokens: TokenResponse = Field(..., description="Authentication tokens")


class MessageResponse(BaseModel):
    """Simple message response for logout, etc."""

    message: str = Field(..., description="Response message")
    success: bool = Field(default=True, description="Whether operation succeeded")
