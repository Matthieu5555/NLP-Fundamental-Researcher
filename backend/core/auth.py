"""
Core authentication logic.

Handles password hashing (bcrypt) and JWT token operations.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Set

import bcrypt
from jose import JWTError, jwt

from .auth_db import auth_db, User

logger = logging.getLogger(__name__)

# Whitelist file path
WHITELIST_PATH = Path(__file__).parent.parent.parent / "data" / "authorized_users.csv"

# Configuration from environment
_jwt_secret = os.getenv("JWT_SECRET")
_env = os.getenv("FASTAPI_ENV", "development")

# JWT secret is REQUIRED in production
# In development, we use a weak default (NOT secure for production!)
if _env == "production" and not _jwt_secret:
    raise ValueError(
        "JWT_SECRET environment variable must be set in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

JWT_SECRET = _jwt_secret or "dev-secret-DO-NOT-USE-IN-PRODUCTION"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


# --- Whitelist Management ---

def load_whitelist() -> Set[str]:
    """
    Load authorized emails from the whitelist CSV file.

    Returns:
        Set of lowercase email addresses that are authorized to register.
        Returns empty set if file doesn't exist (allows all registrations).
    """
    if not WHITELIST_PATH.exists():
        logger.warning(f"Whitelist file not found: {WHITELIST_PATH}")
        return set()

    emails = set()
    try:
        with open(WHITELIST_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                emails.add(line.lower())
        logger.info(f"Loaded {len(emails)} authorized emails from whitelist")
    except PermissionError:
        logger.error(f"Permission denied reading whitelist: {WHITELIST_PATH}")
    except UnicodeDecodeError as e:
        logger.error(f"Whitelist file encoding error: {e}")
    except OSError as e:
        logger.error(f"Error reading whitelist file: {e}")

    return emails


def is_email_authorized(email: str) -> bool:
    """
    Check if an email is authorized to register.

    Args:
        email: Email address to check

    Returns:
        True if email is in the whitelist, False otherwise
    """
    whitelist = load_whitelist()
    # If whitelist is empty, allow all (for development)
    if not whitelist:
        logger.warning("Whitelist is empty - allowing all registrations")
        return True
    return email.lower() in whitelist


# --- Password Hashing ---

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password string
    """
    # Bcrypt work factor (rounds = 2^12 = 4096 iterations)
    # Impact of changing this value:
    #   - INCREASING: More secure but slower (each +1 doubles hashing time)
    #     Example: 12 -> 13 doubles from ~250ms to ~500ms per hash
    #   - DECREASING: Faster but less secure against brute-force attacks
    #     Below 10 is generally considered weak for modern hardware
    # Current value (12) is the recommended balance for 2024-2025
    # Takes ~250ms on modern hardware, provides strong protection
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        password: Plain text password to verify
        hashed: Bcrypt hashed password

    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


# --- JWT Token Operations ---

def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: The user ID to encode in the token
        expires_delta: Custom expiration time (defaults to ACCESS_TOKEN_EXPIRE_MINUTES)

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> Tuple[str, datetime]:
    """
    Create a refresh token.

    Returns a tuple of (token, expires_at) where token is a random string
    and expires_at is the expiration datetime.

    The actual token is NOT a JWT - it's a random string that will be
    hashed and stored in the database.

    Args:
        user_id: The user ID (for logging purposes)

    Returns:
        Tuple of (token_string, expiration_datetime)
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return token, expires_at


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Verify this is an access token
        if payload.get("type") != "access":
            logger.warning("Token is not an access token")
            return None

        return payload
    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None


# --- User Authentication ---

async def authenticate_user(email: str, password: str) -> Optional[User]:
    """
    Authenticate a user by email and password.

    Args:
        email: User email
        password: Plain text password

    Returns:
        User object if authentication succeeds, None otherwise
    """
    user = await auth_db.get_user_by_email(email)
    if not user:
        # Use constant-time comparison even for non-existent users
        # to prevent timing attacks
        verify_password(password, "$2b$12$dummy.hash.for.timing.attack.prevention")
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


async def register_user(
    email: str,
    password: str,
    display_name: Optional[str] = None,
    company: Optional[str] = None,
) -> User:
    """
    Register a new user.

    Args:
        email: User email (must be unique and on whitelist)
        password: Plain text password (will be hashed)
        display_name: Optional display name
        company: Optional company name

    Returns:
        Created User object

    Raises:
        ValueError: If email is already registered or not on whitelist
    """
    # Check whitelist first
    if not is_email_authorized(email):
        logger.warning(f"Registration rejected - email not on whitelist: {email}")
        raise ValueError("This email is not authorized for beta access. Please contact the administrator.")

    password_hash = hash_password(password)
    return await auth_db.create_user(
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        company=company,
    )


async def create_user_tokens(user: User) -> dict:
    """
    Create access and refresh tokens for a user.

    Also stores the refresh token hash in the database.

    Args:
        user: The User object

    Returns:
        Dict with access_token, refresh_token, token_type, expires_in
    """
    # Create access token (JWT)
    access_token = create_access_token(user.id)

    # Create refresh token (random string)
    refresh_token, expires_at = create_refresh_token(user.id)

    # Store refresh token hash in database
    token_hash = auth_db.hash_token(refresh_token)
    await auth_db.store_refresh_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # seconds
    }


async def refresh_access_token(refresh_token: str) -> Optional[dict]:
    """
    Exchange a refresh token for a new access token.

    Args:
        refresh_token: The refresh token string

    Returns:
        Dict with new access_token and expires_in, or None if invalid
    """
    # Hash the provided token and look it up
    token_hash = auth_db.hash_token(refresh_token)
    stored_token = await auth_db.validate_refresh_token(token_hash)

    if not stored_token:
        logger.warning("Invalid or expired refresh token")
        return None

    # Get the user
    user = await auth_db.get_user_by_id(stored_token.user_id)
    if not user:
        logger.warning(f"User not found for refresh token: {stored_token.user_id}")
        return None

    # Create new access token
    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def logout_user(refresh_token: str) -> bool:
    """
    Logout a user by revoking their refresh token.

    Args:
        refresh_token: The refresh token to revoke

    Returns:
        True if token was revoked, False if not found
    """
    token_hash = auth_db.hash_token(refresh_token)
    stored_token = await auth_db.validate_refresh_token(token_hash)

    if stored_token:
        await auth_db.revoke_refresh_token(stored_token.id)
        return True
    return False


async def logout_user_everywhere(user_id: str):
    """
    Logout a user from all devices by revoking all refresh tokens.

    Args:
        user_id: The user ID to logout
    """
    await auth_db.revoke_all_user_tokens(user_id)


async def get_user_from_token(token: str) -> Optional[User]:
    """
    Get a user from an access token.

    Args:
        token: JWT access token

    Returns:
        User object if token is valid, None otherwise
    """
    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return await auth_db.get_user_by_id(user_id)
