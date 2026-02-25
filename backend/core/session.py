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
import threading
from contextlib import contextmanager
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Generator, TypedDict
import logging

from .belief_graph import BeliefGraph
from .report_builder import ReportState, SectionType, AnalystSource

logger = logging.getLogger(__name__)

class SessionMetadata(TypedDict, total=False):
    """
    Typed metadata for analysis sessions.

    All fields are optional (total=False) to support gradual adoption.
    Add new fields here when storing structured data in session.metadata.

    Impact of adding fields:
    - Adding new optional fields is backwards-compatible with existing sessions
    - Use type: ignore comment when reading fields that may not exist in old sessions
    """
    # Analysis results
    total_cost_usd: float
    total_tokens: int
    is_us: bool  # True if US company, affects data availability

    # Cost breakdown from analysis
    cost_breakdown: Dict[str, float]

    # Contradictions and research gaps from analysis
    contradictions: List[Dict]
    research_gaps: List[Dict]

    # Report metadata
    headline: str


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
        user_id: ID of the user who owns this session (None for legacy sessions)
        created_at: Timestamp when session was created
        conversation_history: List of messages exchanged
        belief_graph: User beliefs and facts about the stock
        report_state: Current state of the analysis report
        metadata: Additional session info (user preferences, etc.)
    """
    session_id: str
    ticker: str
    user_id: Optional[str] = None  # User who owns this session
    created_at: datetime = field(default_factory=datetime.now)
    conversation_history: List[Message] = field(default_factory=list)
    belief_graph: BeliefGraph = field(default_factory=BeliefGraph)
    report_state: Optional[ReportState] = None
    metadata: SessionMetadata = field(default_factory=dict)
    analyst_sources: List[AnalystSource] = field(default_factory=list)

    def add_analyst_source(self, belief_content: str, insight_type: str, section: str) -> AnalystSource:
        """
        Create and store an analyst source from extracted belief.

        Args:
            belief_content: The belief statement
            insight_type: Type of insight (confirmed_fact, risk_identified, etc.)
            section: Target section for this belief

        Returns:
            AnalystSource: The created analyst source with [A#] id
        """
        next_id = f"A{len(self.analyst_sources) + 1}"
        source = AnalystSource(
            id=next_id,
            belief_content=belief_content,
            insight_type=insight_type,
            section=section
        )
        self.analyst_sources.append(source)
        return source

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
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'message_count': len(self.conversation_history),
            'metadata': self.metadata,
            'analyst_sources': [src.to_dict() for src in self.analyst_sources]
        }


class SessionManager:
    """
    Manages multiple analysis sessions with JSON persistence.

    Sessions are stored both in-memory and persisted to disk as JSON files.
    Storage structure: data/sessions/{user_id}/{session_id}.json

    On startup, all sessions are loaded from disk (both legacy flat structure
    and new user-scoped directories).

    Thread Safety:
        This class IS thread-safe. Uses a global RLock for protecting the
        _sessions dict and per-session locks for individual session access.
        Use the session_context() context manager for thread-safe session
        modifications that auto-save on exit.
    """

    def __init__(self, storage_dir: str = None):
        """
        Initialize session manager.

        Args:
            storage_dir: Directory to store session files (default: ./data/sessions)
        """
        self._sessions: Dict[str, AnalysisSession] = {}

        # Thread safety locks
        self._lock = threading.RLock()  # Protects _sessions dict access
        self._session_locks: Dict[str, threading.Lock] = {}  # Per-session locks

        # Set up storage directory
        if storage_dir is None:
            storage_dir = Path(__file__).parent.parent.parent / "data" / "sessions"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Load all existing sessions from disk
        self._load_all_sessions()

    def _get_user_storage_dir(self, user_id: str) -> Path:
        """Get storage directory for a specific user."""
        user_dir = self.storage_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _get_session_file_path(self, session: AnalysisSession) -> Path:
        """Get the file path for a session based on its user_id."""
        if session.user_id:
            return self._get_user_storage_dir(session.user_id) / f"{session.session_id}.json"
        else:
            # Legacy sessions without user_id stored in root
            return self.storage_dir / f"{session.session_id}.json"

    def _load_all_sessions(self):
        """Load all sessions from disk on startup.

        Loads from both:
        - Legacy flat structure: data/sessions/{session_id}.json
        - User-scoped structure: data/sessions/{user_id}/{session_id}.json
        """
        logger.info(f"Loading sessions from {self.storage_dir}")

        # Load legacy sessions from root directory
        legacy_files = [f for f in self.storage_dir.glob("*.json") if f.is_file()]
        logger.info(f"Found {len(legacy_files)} legacy session files")

        for session_file in legacy_files:
            try:
                session = self._load_session_from_file(session_file)
                self._sessions[session.session_id] = session
                logger.debug(f"Loaded legacy session {session.session_id} for {session.ticker}")
            except (json.JSONDecodeError, ValueError) as e:
                # Corrupted or malformed session file
                logger.error(f"Corrupted session file {session_file}: {e}")
            except OSError as e:
                logger.error(f"Failed to read session {session_file}: {e}")

        # Load user-scoped sessions from subdirectories
        user_dirs = [d for d in self.storage_dir.iterdir() if d.is_dir()]
        user_session_count = 0

        for user_dir in user_dirs:
            user_id = user_dir.name
            user_files = list(user_dir.glob("*.json"))

            for session_file in user_files:
                try:
                    session = self._load_session_from_file(session_file, user_id=user_id)
                    self._sessions[session.session_id] = session
                    user_session_count += 1
                    logger.debug(f"Loaded session {session.session_id} for user {user_id}")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Corrupted session file {session_file}: {e}")
                except OSError as e:
                    logger.error(f"Failed to read session {session_file}: {e}")

        logger.info(f"Successfully loaded {len(self._sessions)} sessions ({len(legacy_files)} legacy, {user_session_count} user-scoped)")

    def _load_session_from_file(self, session_file: Path, user_id: str = None) -> AnalysisSession:
        """
        Load a session from a JSON file.

        Args:
            session_file: Path to JSON file
            user_id: User ID to assign (overrides file content if provided)

        Returns:
            AnalysisSession: Loaded session
        """
        with open(session_file, 'r') as f:
            data = json.load(f)

        # Validate required fields
        if 'session_id' not in data or 'ticker' not in data:
            raise ValueError(f"Session file missing required fields: {session_file}")

        # Use provided user_id or fall back to stored user_id
        effective_user_id = user_id or data.get('user_id')

        # Reconstruct session
        session = AnalysisSession(
            session_id=data['session_id'],
            ticker=data['ticker'],
            user_id=effective_user_id,
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            metadata=data.get('metadata', {})
        )

        # Reconstruct conversation history
        for msg_data in data.get('conversation_history', []):
            try:
                msg = Message(
                    role=msg_data.get('role', 'user'),
                    content=msg_data.get('content', ''),
                    timestamp=datetime.fromisoformat(msg_data.get('timestamp', datetime.now().isoformat())),
                    metadata=msg_data.get('metadata', {})
                )
                session.conversation_history.append(msg)
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping malformed message in session {data['session_id']}: {e}")

        # Reconstruct report state
        if data.get('report_sections'):
            session.report_state = ReportState(ticker=session.ticker)
            for section_data in data['report_sections']:
                try:
                    from .report_builder import Section
                    title = section_data.get('title', 'Untitled')
                    section = Section(
                        title=title,
                        content=section_data.get('content', ''),
                        section_type=SectionType(section_data.get('section_type', 'general')),
                        sources=section_data.get('sources', []),
                        last_updated=datetime.fromisoformat(section_data.get('last_updated', datetime.now().isoformat())),
                        confidence=section_data.get('confidence', 0.7),
                        version=section_data.get('version', 1)
                    )
                    # Generate section_id from title (same as original)
                    section_id = section_data.get('section_id', title.lower().replace(' ', '_'))
                    session.report_state.sections[section_id] = section
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping malformed section in session {data['session_id']}: {e}")
            # Restore excluded source IDs
            session.report_state.excluded_source_ids = data.get('excluded_source_ids', [])

        # Reconstruct belief graph
        if data.get('belief_graph'):
            session.belief_graph = BeliefGraph.from_dict(data['belief_graph'])

        # Reconstruct analyst sources
        for src_data in data.get('analyst_sources', []):
            session.analyst_sources.append(AnalystSource.from_dict(src_data))

        return session

    def _save_session(self, session: AnalysisSession):
        """
        Save session to disk as JSON.

        Sessions with user_id are saved to: data/sessions/{user_id}/{session_id}.json
        Legacy sessions without user_id are saved to: data/sessions/{session_id}.json

        Args:
            session: Session to save
        """
        session_file = self._get_session_file_path(session)

        session_data = {
            "session_id": session.session_id,
            "ticker": session.ticker,
            "user_id": session.user_id,
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
                    "sources": [s.to_dict() if hasattr(s, 'to_dict') else s for s in section.sources],
                    "last_updated": section.last_updated.isoformat(),
                    "confidence": section.confidence,
                    "version": section.version
                }
                for section_id, section in (session.report_state.sections.items() if session.report_state else [])
            ],
            "excluded_source_ids": session.report_state.excluded_source_ids if session.report_state else [],
            "belief_graph": session.belief_graph.to_dict() if hasattr(session.belief_graph, 'to_dict') else {},
            "analyst_sources": [src.to_dict() for src in session.analyst_sources]
        }

        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            logger.debug(f"Saved session {session.session_id} to {session_file}")
        except TypeError as e:
            # Non-serializable data in session - this is a bug we need to know about
            logger.error(f"Session {session.session_id} contains non-serializable data: {e}")
            raise  # Re-raise to surface the bug
        except OSError as e:
            logger.error(f"Failed to save session {session.session_id} to disk: {e}")

    @contextmanager
    def session_context(self, session_id: str, auto_save: bool = True) -> Generator[Optional[AnalysisSession], None, None]:
        """
        Thread-safe context manager for session access.

        Acquires per-session lock and optionally auto-saves on exit.
        Use this for any operation that modifies session state.

        Args:
            session_id: Session ID to access
            auto_save: If True, automatically save session on exit (default: True)

        Yields:
            AnalysisSession or None if session not found

        Example:
            with session_manager.session_context(session_id) as session:
                if session:
                    session.add_message('user', 'Hello')
                    # Auto-saved on context exit
        """
        # Get or create the per-session lock (under global lock)
        with self._lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.Lock()
            session_lock = self._session_locks[session_id]

        # Acquire the per-session lock
        with session_lock:
            session = self._sessions.get(session_id)
            try:
                yield session
            finally:
                # Auto-save if session exists and auto_save is True
                if session and auto_save:
                    self._save_session(session)

    def create_session(self, ticker: str, user_id: str = None, metadata: Dict = None) -> AnalysisSession:
        """
        Create a new analysis session for a stock.

        Thread-safe: Uses global lock for session dict modification.

        Args:
            ticker: Stock ticker symbol
            user_id: ID of the user creating the session (required for user-scoped storage)
            metadata: Optional session metadata (user preferences, etc.)

        Returns:
            AnalysisSession: Newly created session
        """
        with self._lock:
            session_id = str(uuid.uuid4())
            session = AnalysisSession(
                session_id=session_id,
                ticker=ticker.upper(),
                user_id=user_id,
                metadata=metadata or {}
            )
            self._sessions[session_id] = session
            self._session_locks[session_id] = threading.Lock()

            # Auto-save on creation
            self._save_session(session)

            logger.info(f"Created session {session_id} for {ticker} (user: {user_id}), total sessions in memory: {len(self._sessions)}")
            return session

    def get_session(self, session_id: str) -> Optional[AnalysisSession]:
        """
        Retrieve a session by ID.

        Thread-safe: Uses global lock for dict access.
        Note: For modifications, use session_context() instead.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                logger.debug(f"Session {session_id} not found in memory. Available: {list(self._sessions.keys())[:5]}... ({len(self._sessions)} total)")
            return session

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from memory (does not delete JSON file).

        Thread-safe: Uses global lock for dict modification.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                # Clean up the session lock too
                if session_id in self._session_locks:
                    del self._session_locks[session_id]
                return True
            return False

    def update_session(self, session_id: str):
        """
        Explicitly save a session to disk.

        Thread-safe: Uses session_context for safe access.
        Prefer using session_context() directly for modifications.

        Args:
            session_id: Session ID to save
        """
        with self.session_context(session_id, auto_save=True):
            pass  # Auto-save happens on context exit

    def list_sessions(self, user_id: str = None, limit: int = 50) -> List[Dict]:
        """
        List active sessions (summary view), optionally filtered by user.

        Thread-safe: Uses global lock for dict access.

        Args:
            user_id: If provided, only return sessions for this user
            limit: Maximum number of sessions to return

        Returns:
            List of session summaries, sorted by creation date (newest first)
        """
        with self._lock:
            # Filter by user if specified
            if user_id:
                sessions = [s for s in self._sessions.values() if s.user_id == user_id]
            else:
                sessions = list(self._sessions.values())

            # Sort by creation date (newest first) and limit
            sessions = sorted(
                sessions,
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

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Remove sessions older than max_age_hours.

        Thread-safe: Uses global lock for dict modification.

        Session Expiry Logic:
            Sessions are considered expired based on their created_at timestamp,
            NOT their last activity. This means a session with recent messages
            but an old creation date will still be cleaned up.

            TODO: Consider using last_updated or last message timestamp instead
            for more intuitive expiry behavior.

        Note:
            This method only removes sessions from memory. JSON files on disk
            are NOT deleted. Call this periodically (e.g., via cron or startup)
            to prevent memory bloat.

        Args:
            max_age_hours: Maximum session age in hours (default: 24)

        Returns:
            int: Number of sessions removed
        """
        with self._lock:
            now = datetime.now()
            to_delete = []

            for session_id, session in self._sessions.items():
                age = (now - session.created_at).total_seconds() / 3600
                if age > max_age_hours:
                    to_delete.append(session_id)

            for session_id in to_delete:
                del self._sessions[session_id]
                # Clean up session lock too
                if session_id in self._session_locks:
                    del self._session_locks[session_id]

            return len(to_delete)

    def get_session_for_user(self, session_id: str, user_id: str) -> Optional[AnalysisSession]:
        """
        Get a session only if it belongs to the specified user.

        Thread-safe: Uses global lock for dict access.

        Args:
            session_id: Session ID to retrieve
            user_id: User ID to verify ownership

        Returns:
            AnalysisSession if found and owned by user, None otherwise
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.user_id == user_id:
                return session
            return None

    def migrate_session_to_user(self, session_id: str, user_id: str) -> bool:
        """
        Migrate a legacy session to a user's directory.

        This moves the session file from the flat structure to the user-scoped structure
        and updates the session's user_id.

        Thread-safe: Uses session_context for safe modification.

        Args:
            session_id: Session ID to migrate
            user_id: User ID to assign ownership to

        Returns:
            bool: True if migration successful, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            # Get old file path (before changing user_id)
            old_file = self._get_session_file_path(session)

            # Update user_id
            session.user_id = user_id

            # Get new file path (after changing user_id)
            new_file = self._get_session_file_path(session)

            # Save to new location
            self._save_session(session)

            # Delete old file if it's different and exists
            if old_file != new_file and old_file.exists():
                try:
                    old_file.unlink()
                    logger.info(f"Migrated session {session_id} from {old_file} to {new_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete old session file {old_file}: {e}")

            return True

    def migrate_all_legacy_sessions_to_user(self, user_id: str) -> int:
        """
        Migrate all legacy sessions (without user_id) to a specific user.

        Args:
            user_id: User ID to assign ownership to

        Returns:
            int: Number of sessions migrated
        """
        count = 0
        with self._lock:
            sessions_to_migrate = [
                s.session_id for s in self._sessions.values()
                if s.user_id is None
            ]

        for session_id in sessions_to_migrate:
            if self.migrate_session_to_user(session_id, user_id):
                count += 1

        logger.info(f"Migrated {count} legacy sessions to user {user_id}")
        return count


# Global session manager instance
session_manager = SessionManager()
