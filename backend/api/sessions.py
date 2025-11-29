"""
Sessions API endpoints.

Handles session management: listing, resuming, and deleting past analysis sessions.
"""

from flask import Blueprint, request, jsonify
from pathlib import Path
from core.session import session_manager

sessions_bp = Blueprint('sessions', __name__)


@sessions_bp.route('/', methods=['GET'])
def list_sessions():
    """
    Get list of all sessions.

    Query parameters:
        limit: Number of sessions to return (default: 50)

    Returns:
        {
            "sessions": [
                {
                    "session_id": "uuid",
                    "ticker": "AAPL",
                    "created_at": "ISO timestamp",
                    "message_count": 34,
                    "preview": "First 100 chars of last message..."
                },
                ...
            ],
            "count": 10
        }
    """
    limit = request.args.get('limit', 50, type=int)
    sessions = session_manager.list_sessions(limit=limit)

    return jsonify({
        'sessions': sessions,
        'count': len(sessions)
    })


@sessions_bp.route('/<session_id>', methods=['GET'])
def get_session_detail(session_id: str):
    """
    Get full session details for resuming.

    Returns:
        {
            "session_id": "uuid",
            "ticker": "AAPL",
            "created_at": "ISO timestamp",
            "message_count": 34,
            "has_report": true,
            "last_message": "...",
            "metadata": {...}
        }
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    return jsonify({
        'session_id': session.session_id,
        'ticker': session.ticker,
        'created_at': session.created_at.isoformat(),
        'message_count': len(session.conversation_history),
        'has_report': session.report_state is not None,
        'last_message': session.conversation_history[-1].content if session.conversation_history else None,
        'metadata': session.metadata
    })


@sessions_bp.route('/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """
    Delete a session and its file.

    Returns:
        {
            "success": true,
            "message": "Session deleted"
        }
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    # Delete from memory
    success = session_manager.delete_session(session_id)

    # Delete file
    if success:
        session_file = session_manager.storage_dir / f"{session_id}.json"
        if session_file.exists():
            try:
                session_file.unlink()
            except Exception as e:
                return jsonify({
                    'error': f'Failed to delete session file: {str(e)}'
                }), 500

    return jsonify({
        'success': True,
        'message': 'Session deleted'
    })


@sessions_bp.route('/<session_id>/resume', methods=['POST'])
def resume_session(session_id: str):
    """
    Resume a session (returns full session state for frontend).

    Returns:
        {
            "session_id": "uuid",
            "ticker": "AAPL",
            "conversation_history": [...],
            "report": {...},
            "metadata": {...}
        }
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    return jsonify({
        'session_id': session.session_id,
        'ticker': session.ticker,
        'created_at': session.created_at.isoformat(),
        'conversation_history': [
            {
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'metadata': msg.metadata
            }
            for msg in session.conversation_history
        ],
        'report': session.report_state.to_dict() if session.report_state else None,
        'metadata': session.metadata
    })
