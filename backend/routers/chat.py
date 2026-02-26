"""
Chat API router.

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
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.core.session import session_manager, AnalysisSession
from backend.core.auth_db import User
from backend.middleware.auth_middleware import get_current_user
from backend.dependencies import get_user_session, get_user_and_session, UserSession
from backend.core.report_updater import update_report_from_conversation
from backend.core.belief_classifier import (
    extract_beliefs_from_conversation,
    get_badge_for_belief,
)
from backend.core.cost_tracker import CostTracker
from backend.core.report_builder import Source
from backend.core.rag_engine import RAGEngine
from backend.core.report_rag import ReportRAG
from backend.core.context_manager import ContextManager
from backend.core.intent_classifier import classify_intent, UserIntent
from backend.core.report_editor import edit_section, generate_edit_confirmation
from backend.agents.llm_wrapper import (
    get_llm_response_with_usage,
    get_user_llm_config,
    call_llm,
)
from backend.middleware.usage_tracker import track_request

logger = logging.getLogger(__name__)

router = APIRouter()

# Fast, cheap model for background belief extraction (doesn't need high reasoning)
BELIEF_EXTRACTION_MODEL = "moonshotai/kimi-k2.5"
# Delay between words in SSE stream — balances readability with perceived speed
WORD_STREAM_DELAY = 0.02


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    session_id: str
    message: str


def _sse_json(data: Dict[str, Any]) -> str:
    """Format a JSON object as SSE event."""
    return f"data: {json.dumps(data)}\n\n"


def _build_report_summary(session: AnalysisSession) -> str:
    """Build a summary of the report for LLM context."""
    if not session.report_state:
        return ""

    summary = f"Analysis for {session.ticker}:\n"
    for section_id, section in list(session.report_state.sections.items())[:3]:
        summary += f"\n{section.title}:\n{section.content[:200]}...\n"

    if session.metadata.get("contradictions"):
        summary += "\n\nKey Conflicts in Analysis:\n"
        for c in session.metadata["contradictions"]:
            summary += f"- {c.get('disputed_fact', 'Unknown')}: "
            summary += f"Bulls say: {c.get('bull_interpretation', 'N/A')} | "
            summary += f"Bears say: {c.get('bear_interpretation', 'N/A')}\n"

    if session.metadata.get("research_gaps"):
        summary += "\nResearch Gaps:\n"
        for gap in session.metadata["research_gaps"][:5]:
            summary += (
                f"- {gap.get('question', gap) if isinstance(gap, dict) else gap}\n"
            )

    return summary


def _execute_report_rag(message: str, session: AnalysisSession) -> str:
    """Search the report for relevant chunks."""
    if not session.report_state:
        return ""

    try:
        report_rag = ReportRAG()
        if report_rag.build_index(session.report_state):
            relevant_chunks = report_rag.search(message, k=5)
            if relevant_chunks:
                return report_rag.format_results_for_llm(
                    relevant_chunks, max_chars=2000
                )
    except Exception as e:
        logger.warning(f"Report RAG failed: {e}")
    return ""


def _stream_response_words(response_text: str):
    """Stream response text word by word."""
    words = response_text.split()
    for word in words:
        chunk = word + " "
        chunk_escaped = chunk.replace("\n", "<br>")
        yield f"data: {chunk_escaped}\n\n"
        time.sleep(WORD_STREAM_DELAY)


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    if not url:
        return ""
    url = url.lower().strip()
    for prefix in ["https://", "http://"]:
        if url.startswith(prefix):
            url = url[len(prefix) :]
            break
    if url.startswith("www."):
        url = url[4:]
    return url.rstrip("/")


def _add_rag_sources_to_report(
    session: AnalysisSession, rag_sources: list
) -> List[Dict]:
    """Add RAG sources (RAGSource objects) to the report's sources section."""
    if not rag_sources or not session.report_state:
        return []

    sources_section = session.report_state.sections.get("sources")
    if not sources_section or not hasattr(sources_section, "sources"):
        return []

    existing_urls = set()
    for existing_source in sources_section.sources:
        if hasattr(existing_source, "url"):
            existing_urls.add(_normalize_url(existing_source.url))

    sources_added = []
    current_count = len(sources_section.sources)

    for src in rag_sources:
        src_url = src.url if hasattr(src, "url") else ""
        normalized_url = _normalize_url(src_url)

        if normalized_url and normalized_url in existing_urls:
            continue

        current_count += 1
        new_source = Source(
            id=current_count,
            title=src.title if hasattr(src, "title") else "Research",
            url=src_url,
            source_type=src.source_type if hasattr(src, "source_type") else "search",
            date=src.date if hasattr(src, "date") else "recent",
        )
        sources_section.sources.append(new_source)
        sources_added.append(new_source.to_dict())
        existing_urls.add(normalized_url)

    return sources_added


def _extract_and_store_beliefs(
    session: AnalysisSession,
    message: str,
    response_text: str,
    cost_tracker: CostTracker,
) -> List[Any]:
    """Extract beliefs from conversation and store in session."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return []

    try:
        extracted_beliefs = extract_beliefs_from_conversation(
            user_message=message,
            ai_response=response_text,
            ticker=session.ticker,
            llm_func=call_llm,
            api_key=api_key,
            model=BELIEF_EXTRACTION_MODEL,
        )

        cost_tracker.add_llm_call(BELIEF_EXTRACTION_MODEL, 500, 200)

        for belief in extracted_beliefs:
            session.belief_graph.add_belief(
                content=belief.content,
                confidence=belief.confidence,
                source=f"chat:{belief.target_section}",
            )
            session.add_analyst_source(
                belief_content=belief.content,
                insight_type=belief.insight_type.value,
                section=belief.target_section,
            )

        return extracted_beliefs

    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Belief extraction failed: {e}")
        return []


def _format_beliefs_for_frontend(beliefs: List[Any]) -> List[Dict]:
    """Format extracted beliefs for frontend display."""
    return [
        {
            "content": b.content,
            "type": b.insight_type.value,
            "section": b.target_section,
            "confidence": b.confidence,
            "badge": get_badge_for_belief(b.insight_type)["label"],
            "badge_color": get_badge_for_belief(b.insight_type)["color"],
            "badge_bg": get_badge_for_belief(b.insight_type)["bg"],
            "has_rationale": b.has_rationale,
            "rationale": b.rationale,
        }
        for b in beliefs
    ]


@router.get("/stream")
async def stream_chat(
    message: str = Query(..., description="User message"),
    ctx: UserSession = Depends(get_user_and_session),
):
    """
    Stream chat responses using Server-Sent Events.

    User must own the session. The main chat endpoint - uses RAG for external context,
    extracts beliefs, and streams word-by-word response.
    """
    user, session = ctx
    session_id = session.session_id
    ticker = session.ticker

    # Fetch user's LLM settings
    llm_config = await get_user_llm_config(user.id)

    # Add user message
    with session_manager.session_context(session_id) as sess:
        if sess:
            sess.add_message("user", message)

    def generate():
        try:
            cost_tracker = CostTracker()
            rag_engine = RAGEngine()
            logger.info(f"Chat request for {session_id}, ticker {ticker}")

            # Classify intent
            intent = classify_intent(message, use_llm=False)
            logger.info(f"Intent: {intent.intent.value}")

            # Handle report edit intent
            if intent.intent == UserIntent.REPORT_EDIT:
                yield _sse_json(
                    {"status": f"Editing {intent.target_section or 'report'}..."}
                )

                api_key = os.getenv("OPENROUTER_API_KEY")
                model = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")

                with session_manager.session_context(session_id) as sess:
                    if not sess:
                        yield _sse_json({"status": "Session expired"})
                        yield "data: [DONE]\n\n"
                        return

                    if api_key:
                        edit_result = edit_section(
                            session=sess,
                            intent=intent,
                            llm_func=call_llm,
                            api_key=api_key,
                            model=model,
                        )
                        cost_tracker.add_llm_call(model, 1500, 800)
                        response_text = generate_edit_confirmation(intent, edit_result)
                        report_updated = edit_result.success
                    else:
                        response_text = "API key not configured."
                        report_updated = False

                    yield from _stream_response_words(response_text)
                    yield _sse_json({"text_done": True})

                    sess.add_message(
                        "assistant",
                        response_text,
                        metadata={
                            "intent": "report_edit",
                            "edit_action": intent.edit_action.value
                            if intent.edit_action
                            else None,
                            "target_section": intent.target_section,
                        },
                    )

                    prev_cost = sess.metadata.get("chat_cost_usd", 0.0)
                    turn_cost = cost_tracker.get_total_cost()
                    sess.metadata["chat_cost_usd"] = prev_cost + turn_cost

                yield _sse_json(
                    {"cost_usd": round(sess.metadata.get("chat_cost_usd", 0.0), 4)}
                )

                if report_updated:
                    yield _sse_json(
                        {
                            "event": "report_edited",
                            "section": intent.target_section,
                        }
                    )

                yield "data: [DONE]\n\n"
                return

            # Standard research/belief flow
            current_session = session_manager.get_session(session_id)
            if not current_session:
                yield _sse_json({"status": "Session expired"})
                yield "data: [DONE]\n\n"
                return

            # Build context
            report_summary = _build_report_summary(current_session)
            rag_context = rag_engine.retrieve_context(
                query=message,
                ticker=current_session.ticker,
                company_name=current_session.metadata.get(
                    "company_name", current_session.ticker
                ),
            )
            additional_context = rag_engine.format_context_for_llm(rag_context)
            report_rag_context = _execute_report_rag(message, current_session)

            if rag_context.search_performed:
                yield _sse_json(
                    {"status": "Constant is looking up some new information..."}
                )

            # Build system prompt
            system_prompt = f"""You are a financial analyst assistant named Constant, analyzing {current_session.ticker}.

Be concise, factual, and cite specific numbers when possible.

Analysis overview:
{report_summary}

{report_rag_context}

{additional_context}"""

            # Build conversation context
            model = current_session.metadata.get("model", "default")
            context_mgr = ContextManager(model=model)
            context = context_mgr.build_context(current_session, message, system_prompt)

            conversation_context = "\n".join(
                [f"{msg['role']}: {msg['content']}" for msg in context["messages"]]
            )
            full_system_prompt = (
                f"{system_prompt}\n\nPrevious conversation:\n{conversation_context}"
            )

            # Get LLM response using user's settings (with ACTUAL token counts)
            logger.info(
                f"Calling LLM with model={llm_config.model}, temp={llm_config.temperature}..."
            )
            llm_result = get_llm_response_with_usage(
                prompt=message, system_prompt=full_system_prompt, llm_config=llm_config
            )
            response_text = (
                llm_result.content
                if llm_result.success
                else f"Error: {llm_result.error}"
            )
            logger.info(
                f"LLM response received: {len(response_text)} chars, "
                f"tokens: {llm_result.total_tokens} (in: {llm_result.input_tokens}, out: {llm_result.output_tokens})"
            )

            # Track ACTUAL cost from API response (not estimates!)
            input_tokens = llm_result.input_tokens
            output_tokens = llm_result.output_tokens
            model_name = llm_config.model or os.getenv(
                "OPENROUTER_MODEL", "moonshotai/kimi-k2.5"
            )
            cost_tracker.add_llm_call(model_name, input_tokens, output_tokens)

            # Stream response
            yield from _stream_response_words(response_text)
            yield _sse_json({"text_done": True})

            citations = rag_engine.get_source_citations(rag_context)

            # Thread-safe session updates
            with session_manager.session_context(session_id) as sess:
                if not sess:
                    yield _sse_json({"status": "Session expired"})
                    yield "data: [DONE]\n\n"
                    return

                sess.add_message(
                    "assistant",
                    response_text,
                    metadata={
                        "sources": citations,
                        "rag_search_performed": rag_context.search_performed,
                        "intent": intent.intent.value,
                    },
                )

                sources_added = _add_rag_sources_to_report(
                    sess, rag_context.sources
                )
                extracted_beliefs = _extract_and_store_beliefs(
                    sess, message, response_text, cost_tracker
                )
                report_updated = update_report_from_conversation(
                    message, response_text, sess
                )

                prev_cost = sess.metadata.get("chat_cost_usd", 0.0)
                turn_cost = cost_tracker.get_total_cost()
                sess.metadata["chat_cost_usd"] = prev_cost + turn_cost
                chat_cost = sess.metadata["chat_cost_usd"]

            # Send final events
            if sources_added:
                yield _sse_json({"sources_added": sources_added})

            yield _sse_json({"cost_usd": round(chat_cost, 4)})

            if report_updated or extracted_beliefs:
                yield _sse_json(
                    {
                        "event": "report_updated",
                        "beliefs_extracted": len(extracted_beliefs),
                    }
                )

            if citations:
                yield _sse_json({"sources": citations})

            if extracted_beliefs:
                yield _sse_json(
                    {"new_beliefs": _format_beliefs_for_frontend(extracted_beliefs)}
                )

            yield "data: [DONE]\n\n"
            logger.info("Chat response completed")

            # Track usage asynchronously
            asyncio.create_task(
                track_request(
                    user=user,
                    endpoint="/api/chat/stream",
                    method="GET",
                    ticker=ticker,
                    session_id=session_id,
                    cost_usd=chat_cost,
                    tokens_used=input_tokens + output_tokens,
                )
            )

        except Exception as e:  # Broad catch: SSE generator must not crash
            import traceback

            logger.error(f"Chat error: {traceback.format_exc()}")
            yield f"data: Chat error: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/message")
async def send_message(
    request: ChatMessageRequest, user: User = Depends(get_current_user)
):
    """
    Send a message and get complete response (non-streaming).

    User must own the session. This endpoint provides the same functionality as /stream but returns
    the complete response at once instead of streaming word-by-word.
    Useful for programmatic access or when SSE is not supported.
    """
    session = session_manager.get_session_for_user(request.session_id, user.id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch user's LLM settings
    llm_config = await get_user_llm_config(user.id)

    # Add user message first
    with session_manager.session_context(request.session_id) as sess:
        if sess:
            sess.add_message("user", request.message)

    cost_tracker = CostTracker()
    rag_engine = RAGEngine()

    # Classify intent
    intent = classify_intent(request.message, use_llm=False)

    # Handle report edit intent
    if intent.intent == UserIntent.REPORT_EDIT:
        load_dotenv()
        api_key = os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")

        with session_manager.session_context(request.session_id) as sess:
            if not sess:
                raise HTTPException(status_code=404, detail="Session expired")

            if api_key:
                edit_result = edit_section(
                    session=sess,
                    intent=intent,
                    llm_func=call_llm,
                    api_key=api_key,
                    model=model,
                )
                cost_tracker.add_llm_call(model, 1500, 800)
                response_text = generate_edit_confirmation(intent, edit_result)
                report_updated = edit_result.success
            else:
                response_text = "API key not configured."
                report_updated = False

            sess.add_message(
                "assistant",
                response_text,
                metadata={
                    "intent": "report_edit",
                    "edit_action": intent.edit_action.value
                    if intent.edit_action
                    else None,
                    "target_section": intent.target_section,
                },
            )

            prev_cost = sess.metadata.get("chat_cost_usd", 0.0)
            turn_cost = cost_tracker.get_total_cost()
            sess.metadata["chat_cost_usd"] = prev_cost + turn_cost
            message_count = len(sess.conversation_history)

        return {
            "response": response_text,
            "session_id": request.session_id,
            "metadata": {
                "message_count": message_count,
                "intent": "report_edit",
                "report_updated": report_updated,
                "cost_usd": round(cost_tracker.get_total_cost(), 4),
            },
        }

    # Standard research/belief flow
    current_session = session_manager.get_session(request.session_id)
    if not current_session:
        raise HTTPException(status_code=404, detail="Session expired")

    # Build context
    report_summary = _build_report_summary(current_session)
    rag_context = rag_engine.retrieve_context(
        query=request.message,
        ticker=current_session.ticker,
        company_name=current_session.metadata.get(
            "company_name", current_session.ticker
        ),
    )
    additional_context = rag_engine.format_context_for_llm(rag_context)
    report_rag_context = _execute_report_rag(request.message, current_session)

    # Build system prompt
    system_prompt = f"""You are a financial analyst assistant named Constant, analyzing {current_session.ticker}.

Be concise, factual, and cite specific numbers when possible.

Analysis overview:
{report_summary}

{report_rag_context}

{additional_context}"""

    # Build conversation context
    model = current_session.metadata.get("model", "default")
    context_mgr = ContextManager(model=model)
    context = context_mgr.build_context(current_session, request.message, system_prompt)

    conversation_context = "\n".join(
        [f"{msg['role']}: {msg['content']}" for msg in context["messages"]]
    )
    full_system_prompt = (
        f"{system_prompt}\n\nPrevious conversation:\n{conversation_context}"
    )

    # Get LLM response using user's settings (with ACTUAL token counts)
    llm_result = get_llm_response_with_usage(
        prompt=request.message, system_prompt=full_system_prompt, llm_config=llm_config
    )
    response_text = (
        llm_result.content if llm_result.success else f"Error: {llm_result.error}"
    )

    # Track ACTUAL cost from API response (not estimates!)
    input_tokens = llm_result.input_tokens
    output_tokens = llm_result.output_tokens
    model_name = llm_config.model or os.getenv(
        "OPENROUTER_MODEL", "moonshotai/kimi-k2.5"
    )
    cost_tracker.add_llm_call(model_name, input_tokens, output_tokens)

    citations = rag_engine.get_source_citations(rag_context)

    # Thread-safe session updates
    with session_manager.session_context(request.session_id) as sess:
        if not sess:
            raise HTTPException(status_code=404, detail="Session expired")

        sess.add_message(
            "assistant",
            response_text,
            metadata={
                "sources": citations,
                "rag_search_performed": rag_context.search_performed,
                "intent": intent.intent.value,
            },
        )

        _add_rag_sources_to_report(sess, rag_context.sources)
        extracted_beliefs = _extract_and_store_beliefs(
            sess, request.message, response_text, cost_tracker
        )
        report_updated = update_report_from_conversation(
            request.message, response_text, sess
        )

        prev_cost = sess.metadata.get("chat_cost_usd", 0.0)
        turn_cost = cost_tracker.get_total_cost()
        sess.metadata["chat_cost_usd"] = prev_cost + turn_cost
        message_count = len(sess.conversation_history)

    # Track usage
    await track_request(
        user=user,
        endpoint="/api/chat/message",
        method="POST",
        ticker=current_session.ticker,
        session_id=request.session_id,
        cost_usd=cost_tracker.get_total_cost(),
        tokens_used=input_tokens + output_tokens,
    )

    return {
        "response": response_text,
        "session_id": request.session_id,
        "sources": citations,
        "beliefs_extracted": _format_beliefs_for_frontend(extracted_beliefs)
        if extracted_beliefs
        else [],
        "metadata": {
            "message_count": message_count,
            "intent": intent.intent.value,
            "report_updated": report_updated or bool(extracted_beliefs),
            "rag_search_performed": rag_context.search_performed,
            "cost_usd": round(cost_tracker.get_total_cost(), 4),
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
