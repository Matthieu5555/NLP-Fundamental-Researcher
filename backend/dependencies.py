"""
FastAPI dependencies for common patterns.

Dependencies are injectable functions that handle cross-cutting concerns
like session lookup, authentication checks, and authorization.

Usage:
    from backend.dependencies import get_user_session

    @router.get("/{session_id}/details")
    async def get_details(
        session: AnalysisSession = Depends(get_user_session),
        user: User = Depends(get_current_user),
    ):
        # session is guaranteed to exist and belong to user
        return session.to_dict()
"""

from fastapi import Depends, HTTPException, Path, Query
from typing import Optional, NamedTuple

from backend.core.session import session_manager, AnalysisSession
from backend.core.auth_db import User
from backend.middleware.auth_middleware import get_current_user


class UserSession(NamedTuple):
    """Container for user and session, for endpoints that need both."""

    user: User
    session: AnalysisSession


def get_user_session(
    session_id: str = Path(..., description="Session ID"),
    user: User = Depends(get_current_user),
) -> AnalysisSession:
    """
    Dependency that retrieves a session and verifies user ownership.

    Raises HTTPException 404 if session not found or doesn't belong to user.

    Usage:
        @router.get("/{session_id}")
        async def get_session(session: AnalysisSession = Depends(get_user_session)):
            return session.to_dict()
    """
    session = session_manager.get_session_for_user(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def get_user_session_with_report(
    session_id: str = Path(..., description="Session ID"),
    user: User = Depends(get_current_user),
) -> AnalysisSession:
    """
    Dependency that retrieves a session with report state.

    Raises HTTPException 404 if session not found or doesn't belong to user.
    Raises HTTPException 400 if session has no report yet.

    Usage:
        @router.get("/{session_id}/report")
        async def get_report(session: AnalysisSession = Depends(get_user_session_with_report)):
            return session.report_state.to_dict()
    """
    session = session_manager.get_session_for_user(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.report_state:
        raise HTTPException(status_code=400, detail="No report available yet")
    return session


def get_optional_user_session(
    session_id: str = Path(..., description="Session ID"),
    user: User = Depends(get_current_user),
) -> Optional[AnalysisSession]:
    """
    Dependency that retrieves a session without raising if not found.

    Returns None if session not found. Use when you want to handle
    missing sessions yourself (e.g., creating if not exists).
    """
    return session_manager.get_session_for_user(session_id, user.id)


def get_user_and_session(
    session_id: str = Query(..., description="Session ID"),
    user: User = Depends(get_current_user),
) -> UserSession:
    """
    Dependency that retrieves both user and session for endpoints that need both.

    Uses Query parameter for session_id (for GET endpoints like /stream).
    Raises HTTPException 404 if session not found or doesn't belong to user.

    Usage:
        @router.get("/stream")
        async def stream(ctx: UserSession = Depends(get_user_and_session)):
            user, session = ctx
            # or use ctx.user, ctx.session
    """
    session = session_manager.get_session_for_user(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return UserSession(user=user, session=session)
