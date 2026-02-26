"""Integration tests for the FastAPI backend.

Tests real HTTP request/response cycles using FastAPI TestClient.
This catches issues that unit tests miss: routing, middleware, auth, serialization.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app

TEST_EMAIL = "integration-test@george-research.dev"
TEST_PASSWORD = "testpass123!"


@pytest.fixture(scope="module")
def client():
    """Create a test client that shares the app lifecycle."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_tokens(client):
    """Register a test user and return auth tokens."""
    # Bypass whitelist for test user registration
    with patch("backend.core.auth.is_email_authorized", return_value=True):
        resp = client.post("/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "display_name": "Integration Test",
        })
        if resp.status_code == 200:
            return resp.json()["tokens"]

    # Already registered — login instead
    resp = client.post("/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["tokens"]


@pytest.fixture(scope="module")
def auth_header(auth_tokens):
    """Bearer auth header for authenticated requests."""
    return {"Authorization": f"Bearer {auth_tokens['access_token']}"}


# =============================================================================
# Health & Root
# =============================================================================

class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data

    def test_root_endpoint(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# =============================================================================
# Auth
# =============================================================================

class TestAuth:
    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "short@test.com",
            "password": "short",
        })
        assert resp.status_code == 422

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@nowhere.com",
            "password": "whatever123!",
        })
        assert resp.status_code == 401

    def test_me_requires_auth(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_auth(self, client, auth_header):
        resp = client.get("/api/auth/me", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == TEST_EMAIL
        assert data["is_active"] is True

    def test_me_with_bad_token(self, client):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_refresh_with_valid_token(self, client, auth_tokens):
        resp = client.post("/api/auth/refresh", json={
            "refresh_token": auth_tokens["refresh_token"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    def test_refresh_with_invalid_token(self, client):
        resp = client.post("/api/auth/refresh", json={
            "refresh_token": "bogus-token",
        })
        assert resp.status_code == 401

    def test_logout(self, client, auth_tokens):
        resp = client.post("/api/auth/logout", json={
            "refresh_token": auth_tokens["refresh_token"],
        })
        assert resp.status_code == 200


# =============================================================================
# Sessions
# =============================================================================

class TestSessions:
    def test_list_sessions_requires_auth(self, client):
        resp = client.get("/api/sessions/")
        assert resp.status_code == 401

    def test_list_sessions(self, client, auth_header):
        resp = client.get("/api/sessions/", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "count" in data

    def test_get_nonexistent_session(self, client, auth_header):
        resp = client.get("/api/sessions/nonexistent-id", headers=auth_header)
        assert resp.status_code == 404


# =============================================================================
# Companies (public endpoints)
# =============================================================================

class TestCompanies:
    def test_classify_ticker(self, client):
        resp = client.get("/api/companies/classify/AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["is_us"] is True

    def test_classify_nonexistent_ticker(self, client):
        resp = client.get("/api/companies/classify/ZZZZZ99")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_us"] is False

    def test_search_companies(self, client):
        resp = client.get("/api/companies/search", params={"q": "Apple"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_search_requires_query(self, client):
        resp = client.get("/api/companies/search")
        assert resp.status_code == 422

    def test_us_tickers(self, client):
        resp = client.get("/api/companies/us-tickers", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert "tickers" in data
        assert len(data["tickers"]) <= 5

    def test_stats(self, client):
        resp = client.get("/api/companies/stats")
        assert resp.status_code == 200


# =============================================================================
# Chart (public endpoints)
# =============================================================================

class TestChart:
    def test_timeframes(self, client):
        resp = client.get("/api/chart/timeframes")
        assert resp.status_code == 200
        data = resp.json()
        assert "timeframes" in data
        assert "1Y" in data["timeframes"]


# =============================================================================
# Cache (public endpoints)
# =============================================================================

class TestCache:
    def test_cache_stats(self, client):
        resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_entries" in data

    def test_cache_health(self, client):
        resp = client.get("/api/cache/health")
        assert resp.status_code == 200


# =============================================================================
# Settings
# =============================================================================

class TestSettings:
    def test_available_models_is_public(self, client):
        resp = client.get("/api/settings/available-models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) > 0

    def test_get_settings_requires_auth(self, client):
        resp = client.get("/api/settings/")
        assert resp.status_code == 401

    def test_get_settings(self, client, auth_header):
        resp = client.get("/api/settings/", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_model" in data
        assert "theme" in data

    def test_update_settings(self, client, auth_header):
        resp = client.put("/api/settings/", headers=auth_header, json={
            "theme": "dark",
        })
        assert resp.status_code == 200
        assert resp.json()["theme"] == "dark"

    def test_reset_settings(self, client, auth_header):
        resp = client.post("/api/settings/reset", headers=auth_header)
        assert resp.status_code == 200


# =============================================================================
# Usage
# =============================================================================

class TestUsage:
    def test_usage_requires_auth(self, client):
        resp = client.get("/api/usage/me")
        assert resp.status_code == 401

    def test_usage_me(self, client, auth_header):
        resp = client.get("/api/usage/me", headers=auth_header)
        assert resp.status_code == 200

    def test_usage_summary(self, client, auth_header):
        resp = client.get("/api/usage/summary", headers=auth_header)
        assert resp.status_code == 200

    def test_usage_stats(self, client, auth_header):
        resp = client.get("/api/usage/stats", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "current_month" in data
        assert "all_time" in data

    def test_usage_daily(self, client, auth_header):
        resp = client.get("/api/usage/daily", headers=auth_header)
        assert resp.status_code == 200

    def test_usage_costs(self, client, auth_header):
        resp = client.get("/api/usage/costs", headers=auth_header)
        assert resp.status_code == 200
        assert "total_cost_usd" in resp.json()


# =============================================================================
# Watchlist
# =============================================================================

class TestWatchlist:
    def test_watchlist_requires_auth(self, client):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 401

    def test_get_watchlist(self, client, auth_header):
        resp = client.get("/api/watchlist", headers=auth_header)
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_add_and_remove_from_watchlist(self, client, auth_header):
        # Add
        resp = client.post("/api/watchlist/TEST", headers=auth_header, json={
            "company_name": "Test Corp",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify it's there
        resp = client.get("/api/watchlist", headers=auth_header)
        tickers = [item["ticker"] for item in resp.json()["items"]]
        assert "TEST" in tickers

        # Remove
        resp = client.delete("/api/watchlist/TEST", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# =============================================================================
# Reports (require existing session with report)
# =============================================================================

class TestReports:
    def test_report_requires_auth(self, client):
        resp = client.get("/api/reports/some-session-id")
        assert resp.status_code == 401

    def test_report_nonexistent_session(self, client, auth_header):
        resp = client.get("/api/reports/nonexistent-id", headers=auth_header)
        assert resp.status_code == 404


# =============================================================================
# Analysis
# =============================================================================

class TestAnalysis:
    def test_start_requires_auth(self, client):
        resp = client.post("/api/analysis/start", json={"ticker": "AAPL"})
        assert resp.status_code == 401

    def test_queue_stats_is_public(self, client):
        resp = client.get("/api/analysis/queue/stats")
        assert resp.status_code == 200
