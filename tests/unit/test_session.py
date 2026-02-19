"""Tests for the session management module."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import tempfile
import json

from backend.core.session import (
    Message,
    AnalysisSession,
    SessionManager,
)


class TestMessage:
    """Tests for the Message dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}

    def test_message_with_metadata(self):
        """Test message with metadata."""
        msg = Message(
            role="assistant",
            content="Response",
            metadata={"tokens": 50, "cost": 0.001}
        )

        assert msg.metadata["tokens"] == 50


class TestAnalysisSession:
    """Tests for the AnalysisSession dataclass."""

    def test_session_creation(self):
        """Test creating a session."""
        session = AnalysisSession(
            session_id="test-123",
            ticker="AAPL",
        )

        assert session.session_id == "test-123"
        assert session.ticker == "AAPL"
        assert session.conversation_history == []
        assert session.metadata == {}

    def test_add_message(self):
        """Test adding messages to session."""
        session = AnalysisSession(session_id="test", ticker="AAPL")

        msg = session.add_message("user", "What is the P/E ratio?")

        assert len(session.conversation_history) == 1
        assert session.conversation_history[0].content == "What is the P/E ratio?"
        assert msg.role == "user"

    def test_add_message_with_metadata(self):
        """Test adding message with metadata."""
        session = AnalysisSession(session_id="test", ticker="AAPL")

        msg = session.add_message("assistant", "The P/E is 28.", {"tokens": 10})

        assert msg.metadata["tokens"] == 10

    def test_get_recent_history(self):
        """Test getting recent conversation history."""
        session = AnalysisSession(session_id="test", ticker="AAPL")

        # Add 15 messages
        for i in range(15):
            session.add_message("user", f"Message {i}")

        recent = session.get_recent_history(n=5)

        assert len(recent) == 5
        assert recent[0].content == "Message 10"  # Messages 10-14
        assert recent[-1].content == "Message 14"

    def test_get_recent_history_fewer_messages(self):
        """Test getting recent history with fewer messages than requested."""
        session = AnalysisSession(session_id="test", ticker="AAPL")

        session.add_message("user", "Message 1")
        session.add_message("user", "Message 2")

        recent = session.get_recent_history(n=10)

        assert len(recent) == 2

    def test_to_dict(self):
        """Test serializing session to dict."""
        session = AnalysisSession(
            session_id="test-123",
            ticker="AAPL",
            user_id="user-456",
        )
        session.add_message("user", "Hello")

        data = session.to_dict()

        assert data["session_id"] == "test-123"
        assert data["ticker"] == "AAPL"
        assert data["user_id"] == "user-456"
        assert data["message_count"] == 1

    def test_session_with_user_id(self):
        """Test session with user ID."""
        session = AnalysisSession(
            session_id="test-123",
            ticker="GOOGL",
            user_id="user-789"
        )

        assert session.user_id == "user-789"


class TestSessionManager:
    """Tests for the SessionManager class."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary directory for session storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_create_session(self, temp_storage):
        """Test creating a new session."""
        manager = SessionManager(storage_dir=temp_storage)

        session = manager.create_session(
            ticker="AAPL",
            user_id="user-123",
        )

        assert session.ticker == "AAPL"
        assert session.user_id == "user-123"
        assert session.session_id is not None

        # Session should be saved to disk
        user_dir = Path(temp_storage) / "user-123"
        assert user_dir.exists()
        assert (user_dir / f"{session.session_id}.json").exists()

    def test_create_session_uppercase_ticker(self, temp_storage):
        """Test that ticker is uppercased."""
        manager = SessionManager(storage_dir=temp_storage)

        session = manager.create_session(ticker="aapl")

        assert session.ticker == "AAPL"

    def test_get_session(self, temp_storage):
        """Test retrieving a session."""
        manager = SessionManager(storage_dir=temp_storage)
        created = manager.create_session(ticker="AAPL")

        retrieved = manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.ticker == "AAPL"

    def test_get_nonexistent_session(self, temp_storage):
        """Test getting a session that doesn't exist."""
        manager = SessionManager(storage_dir=temp_storage)

        result = manager.get_session("nonexistent-id")

        assert result is None

    def test_session_context_auto_saves(self, temp_storage):
        """Test that session_context auto-saves changes."""
        manager = SessionManager(storage_dir=temp_storage)
        session = manager.create_session(ticker="AAPL")
        session_id = session.session_id

        # Modify session via context manager
        with manager.session_context(session_id) as s:
            s.add_message("user", "Test message")

        # Create new manager to reload from disk
        new_manager = SessionManager(storage_dir=temp_storage)
        reloaded = new_manager.get_session(session_id)

        assert len(reloaded.conversation_history) == 1
        assert reloaded.conversation_history[0].content == "Test message"

    def test_session_context_nonexistent(self, temp_storage):
        """Test session_context with nonexistent session."""
        manager = SessionManager(storage_dir=temp_storage)

        with manager.session_context("nonexistent") as session:
            assert session is None

    def test_list_sessions_all(self, temp_storage):
        """Test listing all sessions."""
        manager = SessionManager(storage_dir=temp_storage)

        manager.create_session(ticker="AAPL", user_id="user-1")
        manager.create_session(ticker="GOOGL", user_id="user-1")
        manager.create_session(ticker="MSFT", user_id="user-2")

        all_sessions = manager.list_sessions()

        assert len(all_sessions) == 3

    def test_list_sessions_by_user(self, temp_storage):
        """Test listing sessions filtered by user."""
        manager = SessionManager(storage_dir=temp_storage)

        # Create sessions for different users
        manager.create_session(ticker="AAPL", user_id="user-1")
        manager.create_session(ticker="GOOGL", user_id="user-1")
        manager.create_session(ticker="MSFT", user_id="user-2")

        user1_sessions = manager.list_sessions(user_id="user-1")

        assert len(user1_sessions) == 2
        tickers = {s["ticker"] for s in user1_sessions}
        assert tickers == {"AAPL", "GOOGL"}

    def test_delete_session(self, temp_storage):
        """Test deleting a session from memory."""
        manager = SessionManager(storage_dir=temp_storage)
        session = manager.create_session(ticker="AAPL")
        session_id = session.session_id

        result = manager.delete_session(session_id)

        assert result is True
        assert manager.get_session(session_id) is None

    def test_delete_nonexistent_session(self, temp_storage):
        """Test deleting a session that doesn't exist."""
        manager = SessionManager(storage_dir=temp_storage)

        result = manager.delete_session("nonexistent")

        assert result is False

    def test_get_session_for_user(self, temp_storage):
        """Test getting session only if owned by user."""
        manager = SessionManager(storage_dir=temp_storage)
        session = manager.create_session(ticker="AAPL", user_id="user-1")

        # Should return session for correct user
        result = manager.get_session_for_user(session.session_id, "user-1")
        assert result is not None

        # Should return None for wrong user
        result = manager.get_session_for_user(session.session_id, "user-2")
        assert result is None

    def test_sessions_persist_across_restarts(self, temp_storage):
        """Test that sessions are loaded from disk on restart."""
        # Create session with first manager
        manager1 = SessionManager(storage_dir=temp_storage)
        session = manager1.create_session(ticker="AAPL", user_id="user-1")
        session.add_message("user", "Hello")
        manager1.update_session(session.session_id)

        # Create new manager (simulating restart)
        manager2 = SessionManager(storage_dir=temp_storage)
        reloaded = manager2.get_session(session.session_id)

        assert reloaded is not None
        assert reloaded.ticker == "AAPL"
        assert len(reloaded.conversation_history) == 1
