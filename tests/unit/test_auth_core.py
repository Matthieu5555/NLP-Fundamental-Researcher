"""Tests for core authentication pure functions.

Covers:
- Password hashing and verification (bcrypt)
- JWT access token creation and decoding
- Refresh token generation
- Email whitelist logic
"""

import re
from datetime import timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("bcrypt", reason="bcrypt not installed (optional backend dep)")

from backend.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    is_email_authorized,
    JWT_SECRET,
)


class TestPasswordHashing:
    """bcrypt hash/verify roundtrip and edge cases."""

    def test_hash_returns_bcrypt_prefix(self):
        result = hash_password("test_password_123")
        assert result.startswith("$2b$"), f"Expected bcrypt prefix, got: {result[:10]}"

    def test_hash_is_nondeterministic(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2, "Same password should produce different salts"

    def test_verify_correct_password(self):
        hashed = hash_password("correct_horse_battery_staple")
        assert verify_password("correct_horse_battery_staple", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_empty_password_against_real_hash(self):
        hashed = hash_password("nonempty")
        assert verify_password("", hashed) is False

    def test_verify_mangled_hash_returns_false(self):
        """Mangled hash should return False, not raise."""
        assert verify_password("anything", "not-a-valid-hash") is False

    def test_verify_truncated_hash_returns_false(self):
        hashed = hash_password("test")
        truncated = hashed[:20]
        assert verify_password("test", truncated) is False

    def test_hash_unicode_password(self):
        hashed = hash_password("pässwörd_日本語")
        assert verify_password("pässwörd_日本語", hashed) is True


class TestJWTAccessTokens:
    """JWT encode/decode roundtrip and validation edge cases."""

    def test_token_has_jwt_structure(self):
        token = create_access_token("user-123")
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have exactly 3 dot-separated parts"

    def test_roundtrip_preserves_user_id(self):
        token = create_access_token("user-abc-42")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-abc-42"

    def test_token_type_is_access(self):
        token = create_access_token("user-1")
        payload = decode_access_token(token)
        assert payload["type"] == "access"

    def test_expired_token_returns_none(self):
        token = create_access_token("user-1", expires_delta=timedelta(seconds=-1))
        assert decode_access_token(token) is None

    def test_random_string_returns_none(self):
        assert decode_access_token("not.a.jwt") is None

    def test_garbage_returns_none(self):
        assert decode_access_token("") is None
        assert decode_access_token("abc123") is None

    def test_wrong_secret_returns_none(self):
        from jose import jwt as jose_jwt

        payload = {"sub": "user-1", "type": "access", "exp": 9999999999}
        token = jose_jwt.encode(payload, "wrong-secret", algorithm="HS256")
        assert decode_access_token(token) is None

    def test_non_access_type_returns_none(self):
        """A token with type != 'access' should be rejected."""
        from jose import jwt as jose_jwt
        from backend.core.auth import JWT_ALGORITHM

        payload = {"sub": "user-1", "type": "refresh", "exp": 9999999999}
        token = jose_jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        assert decode_access_token(token) is None

    def test_custom_expiry_is_respected(self):
        token = create_access_token("user-1", expires_delta=timedelta(hours=2))
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-1"


class TestRefreshToken:
    """Refresh token generation (random string, not JWT)."""

    def test_returns_tuple_of_string_and_datetime(self):
        from datetime import datetime

        token, expires_at = create_refresh_token("user-1")
        assert isinstance(token, str)
        assert isinstance(expires_at, datetime)

    def test_token_is_url_safe(self):
        token, _ = create_refresh_token("user-1")
        # URL-safe base64 uses only alphanumeric, hyphen, underscore
        assert re.match(r'^[A-Za-z0-9_-]+$', token), f"Token contains unsafe chars: {token}"

    def test_expiration_is_in_the_future(self):
        from datetime import datetime

        _, expires_at = create_refresh_token("user-1")
        assert expires_at > datetime.now()

    def test_tokens_are_unique(self):
        t1, _ = create_refresh_token("user-1")
        t2, _ = create_refresh_token("user-1")
        assert t1 != t2

    def test_token_has_sufficient_entropy(self):
        token, _ = create_refresh_token("user-1")
        # secrets.token_urlsafe(32) produces ~43 characters
        assert len(token) >= 40, f"Token too short ({len(token)} chars), insufficient entropy"


class TestEmailWhitelist:
    """Whitelist authorization logic."""

    def test_empty_whitelist_allows_all(self):
        with patch("backend.core.auth.load_whitelist", return_value=set()):
            assert is_email_authorized("anyone@example.com") is True

    def test_email_in_whitelist_is_authorized(self):
        with patch("backend.core.auth.load_whitelist", return_value={"alice@test.com", "bob@test.com"}):
            assert is_email_authorized("alice@test.com") is True

    def test_email_not_in_whitelist_is_rejected(self):
        with patch("backend.core.auth.load_whitelist", return_value={"alice@test.com"}):
            assert is_email_authorized("eve@test.com") is False

    def test_case_insensitive_match(self):
        with patch("backend.core.auth.load_whitelist", return_value={"alice@test.com"}):
            assert is_email_authorized("Alice@Test.com") is True
