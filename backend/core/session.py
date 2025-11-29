"""
Session management for analysis conversations.

Each stock analysis gets a unique session that tracks:
- Conversation history
- Belief graph state
- Report state
- User preferences
"""

import uuid
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
import logging

from .belief_graph import BeliefGraph
from .report_builder import ReportState, SectionType

logger = logging.getLogger(__name__)

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
    Manages multiple analysis sessions with JSON persistence.

    Sessions are stored both in-memory and persisted to disk as JSON files.
    On startup, all sessions are loaded from disk.
    """

    def __init__(self, storage_dir: str = None):
        """
        Initialize session manager.

        Args:
            storage_dir: Directory to store session files (default: ./data/sessions)
        """
        self._sessions: Dict[str, AnalysisSession] = {}

        # Set up storage directory
        if storage_dir is None:
            storage_dir = Path(__file__).parent.parent.parent / "data" / "sessions"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Load all existing sessions from disk
        self._load_all_sessions()

    def _load_all_sessions(self):
        """Load all sessions from disk on startup."""
        logger.info(f"Loading sessions from {self.storage_dir}")

        session_files = list(self.storage_dir.glob("*.json"))
        logger.info(f"Found {len(session_files)} session files")

        for session_file in session_files:
            try:
                session = self._load_session_from_file(session_file)
                self._sessions[session.session_id] = session
                logger.info(f"Loaded session {session.session_id} for {session.ticker}")
            except Exception as e:
                logger.error(f"Failed to load session {session_file}: {e}")

        logger.info(f"Successfully loaded {len(self._sessions)} sessions")

    def _load_session_from_file(self, session_file: Path) -> AnalysisSession:
        """
        Load a session from a JSON file.

        Args:
            session_file: Path to JSON file

        Returns:
            AnalysisSession: Loaded session
        """
        with open(session_file, 'r') as f:
            data = json.load(f)

        # Reconstruct session
        session = AnalysisSession(
            session_id=data['session_id'],
            ticker=data['ticker'],
            created_at=datetime.fromisoformat(data['created_at']),
            metadata=data.get('metadata', {})
        )

        # Reconstruct conversation history
        for msg_data in data.get('conversation_history', []):
            msg = Message(
                role=msg_data['role'],
                content=msg_data['content'],
                timestamp=datetime.fromisoformat(msg_data['timestamp']),
                metadata=msg_data.get('metadata', {})
            )
            session.conversation_history.append(msg)

        # Reconstruct report state
        if data.get('report_sections'):
            session.report_state = ReportState(ticker=session.ticker)
            for section_data in data['report_sections']:
                from .report_builder import Section
                section = Section(
                    title=section_data['title'],
                    content=section_data['content'],
                    section_type=SectionType(section_data['section_type']),
                    sources=section_data.get('sources', []),
                    last_updated=datetime.fromisoformat(section_data['last_updated']),
                    confidence=section_data.get('confidence', 0.7),
                    version=section_data.get('version', 1)
                )
                # Generate section_id from title (same as original)
                section_id = section_data.get('section_id', section_data['title'].lower().replace(' ', '_'))
                session.report_state.sections[section_id] = section

        # Reconstruct belief graph
        if data.get('belief_graph'):
            # Simple reconstruction - belief graph will be empty for now
            session.belief_graph = BeliefGraph()

        return session

    def _save_session(self, session: AnalysisSession):
        """
        Save session to disk as JSON.

        Args:
            session: Session to save
        """
        session_file = self.storage_dir / f"{session.session_id}.json"

        session_data = {
            "session_id": session.session_id,
            "ticker": session.ticker,
            "created_at": session.created_at.isoformat(),
            "metadata": session.metadata,
            "conversation_history": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in session.conversation_history
            ],
            "report_sections": [
                {
                    "section_id": section_id,
                    "title": section.title,
                    "content": section.content,
                    "section_type": section.section_type.value,
                    "sources": section.sources,
                    "last_updated": section.last_updated.isoformat(),
                    "confidence": section.confidence,
                    "version": section.version
                }
                for section_id, section in (session.report_state.sections.items() if session.report_state else {}).items()
            ],
            "belief_graph": session.belief_graph.to_dict() if hasattr(session.belief_graph, 'to_dict') else {}
        }

        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            logger.debug(f"Saved session {session.session_id} to {session_file}")
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")

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

        # Auto-save on creation
        self._save_session(session)

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

    def update_session(self, session_id: str):
        """
        Explicitly save a session to disk.

        Call this after modifying a session (e.g., after chat messages).

        Args:
            session_id: Session ID to save
        """
        session = self.get_session(session_id)
        if session:
            self._save_session(session)

    def list_sessions(self, limit: int = 50) -> List[Dict]:
        """
        List all active sessions (summary view).

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session summaries, sorted by creation date (newest first)
        """
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True
        )[:limit]

        return [
            {
                **session.to_dict(),
                'message_count': len(session.conversation_history),
                'preview': session.conversation_history[-1].content[:100] if session.conversation_history else ""
            }
            for session in sessions
        ]

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
