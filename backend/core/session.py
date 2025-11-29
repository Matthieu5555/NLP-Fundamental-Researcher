"""
Session management for analysis conversations.

Each stock analysis gets a unique session that tracks:
- Conversation history
- Belief graph state
- Report state
- User preferences
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from .belief_graph import BeliefGraph
from .report_builder import ReportState

@dataclass
class Message:
    """Represents a single message in the conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)  # sources, token count, etc.

@dataclass
class AnalysisSession:
    """
    Represents a stock analysis session.

    Attributes:
        session_id: Unique identifier for this session
        ticker: Stock ticker symbol
        created_at: Timestamp when session was created
        conversation_history: List of messages exchanged
        belief_graph: User beliefs and facts about the stock
        report_state: Current state of the analysis report
        metadata: Additional session info (user preferences, etc.)
    """
    session_id: str
    ticker: str
    created_at: datetime = field(default_factory=datetime.now)
    conversation_history: List[Message] = field(default_factory=list)
    belief_graph: BeliefGraph = field(default_factory=BeliefGraph)
    report_state: Optional[ReportState] = None
    metadata: Dict = field(default_factory=dict)

    def add_message(self, role: str, content: str, metadata: Dict = None):
        """Add a message to conversation history."""
        msg = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.conversation_history.append(msg)
        return msg

    def get_recent_history(self, n: int = 10) -> List[Message]:
        """Get last N messages from conversation."""
        return self.conversation_history[-n:]

    def to_dict(self) -> Dict:
        """Serialize session to dictionary."""
        return {
            'session_id': self.session_id,
            'ticker': self.ticker,
            'created_at': self.created_at.isoformat(),
            'message_count': len(self.conversation_history),
            'metadata': self.metadata
        }


class SessionManager:
    """
    Manages multiple analysis sessions.

    In production, this would be backed by Redis or a database.
    For MVP, we use in-memory storage.
    """

    def __init__(self):
        self._sessions: Dict[str, AnalysisSession] = {}

    def create_session(self, ticker: str, metadata: Dict = None) -> AnalysisSession:
        """
        Create a new analysis session for a stock.

        Args:
            ticker: Stock ticker symbol
            metadata: Optional session metadata (user preferences, etc.)

        Returns:
            AnalysisSession: Newly created session
        """
        session_id = str(uuid.uuid4())
        session = AnalysisSession(
            session_id=session_id,
            ticker=ticker.upper(),
            metadata=metadata or {}
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[AnalysisSession]:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[Dict]:
        """List all active sessions (summary view)."""
        return [session.to_dict() for session in self._sessions.values()]

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Remove sessions older than max_age_hours."""
        now = datetime.now()
        to_delete = []

        for session_id, session in self._sessions.items():
            age = (now - session.created_at).total_seconds() / 3600
            if age > max_age_hours:
                to_delete.append(session_id)

        for session_id in to_delete:
            del self._sessions[session_id]

        return len(to_delete)


# Global session manager instance
session_manager = SessionManager()
