"""Chat API router.

Handles conversational interactions with the financial analyst.

Endpoints:
    GET  /stream              - SSE stream chat responses
    POST /message             - Send message (non-streaming)
    GET  /{session_id}/history - Get conversation history
    GET  /{session_id}/beliefs - Get tracked beliefs

SSE Event Formats:
    - {"status": "..."} - Status update
    - Raw text chunks - Response tokens
    - {"text_done": true} - Text streaming complete
    - {"sources": [...]} - Source citations
    - {"new_beliefs": [...]} - Extracted beliefs
    - {"cost_usd": X.XXXX} - Cost for this turn
    - "[DONE]" - Stream end marker
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.core.session import session_manager, AnalysisSession
from backend.core.auth_db import User
from backend.middleware.auth_middleware import get_current_user
from backend.dependencies import get_user_session, get_user_and_session, UserSession
from backend.agents.llm_wrapper import get_user_llm_config
from backend.middleware.usage_tracker import track_request
from backend.services.chat_service import ChatService, ChatTurnResult

logger = logging.getLogger(__name__)

router = APIRouter()

# Delay between words in SSE stream — balances readability with perceived speed
WORD_STREAM_DELAY = 0.02


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    session_id: str
    message: str


def _sse_json(data: Dict[str, Any]) -> str:
    """Format a JSON object as SSE event."""
    return f"data: {json.dumps(data)}\n\n"


def _stream_response_words(response_text: str):
    """Stream response text word by word."""
    words = response_text.split()
    for word in words:
        chunk = word + " "
        chunk_escaped = chunk.replace("\n", "<br>")
        yield f"data: {chunk_escaped}\n\n"
        time.sleep(WORD_STREAM_DELAY)


def _stream_turn_result(result: ChatTurnResult):
    """Yield SSE events from a ChatTurnResult."""
    # Pre-flight status so client knows what happened
    if result.report_edited:
        yield _sse_json({"status": f"Editing {result.edit_section or 'report'}..."})
    if result.rag_search_performed:
        yield _sse_json({"status": "George is looking up some new information..."})

    yield from _stream_response_words(result.response_text)
    yield _sse_json({"text_done": True})

    if result.sources_added:
        yield _sse_json({"sources_added": result.sources_added})

    yield _sse_json({"cost_usd": round(result.total_chat_cost_usd, 4)})

    if result.report_edited:
        yield _sse_json({"event": "report_edited", "section": result.edit_section})

    if result.extracted_beliefs:
        yield _sse_json(
            {"event": "report_updated", "beliefs_extracted": len(result.extracted_beliefs)}
        )

    if result.citations:
        yield _sse_json({"sources": result.citations})

    if result.extracted_beliefs:
        yield _sse_json({"new_beliefs": result.extracted_beliefs})


@router.get("/stream")
async def stream_chat(
    message: str = Query(..., description="User message"),
    ctx: UserSession = Depends(get_user_and_session),
):
    """Stream chat responses using Server-Sent Events.

    User must own the session. The main chat endpoint: classifies intent,
    retrieves RAG context, calls LLM, extracts beliefs, streams word-by-word.
    """
    user, session = ctx
    session_id = session.session_id
    ticker = session.ticker

    llm_config = await get_user_llm_config(user.id)

    with session_manager.session_context(session_id) as sess:
        if sess:
            sess.add_message("user", message)

    def generate():
        try:
            service = ChatService(session, llm_config)
            logger.info("Chat request for %s, ticker %s", session_id, ticker)

            result = service.process_turn(message)
            yield from _stream_turn_result(result)
            yield "data: [DONE]\n\n"
            logger.info("Chat response completed")

            asyncio.create_task(
                track_request(
                    user=user,
                    endpoint="/api/chat/stream",
                    method="GET",
                    ticker=ticker,
                    session_id=session_id,
                    cost_usd=result.total_chat_cost_usd,
                    tokens_used=result.tokens_used,
                )
            )

        except Exception as e:
            import traceback

            logger.error("Chat error: %s", traceback.format_exc())
            yield f"data: Chat error: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/message")
async def send_message(
    request: ChatMessageRequest, user: User = Depends(get_current_user)
):
    """Send a message and get complete response (non-streaming).

    User must own the session. Same pipeline as /stream but returns JSON.
    """
    session = session_manager.get_session_for_user(request.session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    llm_config = await get_user_llm_config(user.id)

    with session_manager.session_context(request.session_id) as sess:
        if sess:
            sess.add_message("user", request.message)

    service = ChatService(session, llm_config)
    result = service.process_turn(request.message)

    await track_request(
        user=user,
        endpoint="/api/chat/message",
        method="POST",
        ticker=session.ticker,
        session_id=request.session_id,
        cost_usd=result.total_chat_cost_usd,
        tokens_used=result.tokens_used,
    )

    return {
        "response": result.response_text,
        "session_id": request.session_id,
        "sources": result.citations,
        "beliefs_extracted": result.extracted_beliefs,
        "metadata": {
            "message_count": len(session.conversation_history),
            "intent": result.intent,
            "report_updated": result.report_updated,
            "rag_search_performed": result.rag_search_performed,
            "cost_usd": round(result.turn_cost_usd, 4),
        },
    }


@router.get("/{session_id}/history")
async def get_history(
    limit: Optional[int] = None,
    session: AnalysisSession = Depends(get_user_session),
):
    """Get conversation history for a session. User must own the session."""
    if limit:
        messages = session.get_recent_history(limit)
    else:
        messages = session.conversation_history

    return {
        "session_id": session.session_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata,
            }
            for msg in messages
        ],
    }


@router.get("/{session_id}/beliefs")
async def get_beliefs(
    session: AnalysisSession = Depends(get_user_session),
):
    """Get all beliefs tracked for this session. User must own the session."""
    beliefs = session.belief_graph.get_all_beliefs()
    stats = session.belief_graph.get_stats()

    return {
        "session_id": session.session_id,
        "beliefs": [belief.to_dict() for belief in beliefs],
        "stats": stats,
    }
