"""
Sessions API router.

Handles session management: listing, resuming, deleting, and finalizing.
All endpoints require authentication and sessions are scoped to the authenticated user.

Endpoints:
    GET    /                      - List user's sessions
    GET    /{session_id}          - Get session details (user must own it)
    DELETE /{session_id}          - Delete session (user must own it)
    POST   /{session_id}/resume   - Resume session (user must own it)
    GET    /{session_id}/beliefs  - Get all beliefs (user must own it)
    POST   /{session_id}/finalize - Rewrite sections with beliefs
    POST   /{session_id}/regenerate-report - Regenerate Full Report
"""

import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends

from backend.core.session import session_manager, AnalysisSession
from backend.core.auth_db import User
from backend.middleware.auth_middleware import get_current_user
from backend.dependencies import get_user_session, get_user_session_with_report
from backend.core.belief_classifier import (
    rewrite_section_with_beliefs,
    ExtractedBelief,
    InsightType,
)
from backend.core.report_builder import SectionType
from backend.agents.llm_wrapper import call_llm

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_SESSION_LIMIT = 50


@router.get("/")
async def list_sessions(
    limit: int = Query(default=DEFAULT_SESSION_LIMIT),
    user: User = Depends(get_current_user)
):
    """Get list of sessions for the authenticated user."""
    sessions = session_manager.list_sessions(user_id=user.id, limit=limit)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/{session_id}")
async def get_session_detail(
    session: AnalysisSession = Depends(get_user_session),
):
    """Get full session details (user must own the session)."""
    return {
        "session_id": session.session_id,
        "ticker": session.ticker,
        "user_id": session.user_id,
        "created_at": session.created_at.isoformat(),
        "message_count": len(session.conversation_history),
        "has_report": session.report_state is not None,
        "last_message": (
            session.conversation_history[-1].content if session.conversation_history else None
        ),
        "metadata": session.metadata,
    }


@router.delete("/{session_id}")
async def delete_session(
    session: AnalysisSession = Depends(get_user_session),
):
    """Delete a session and its file (user must own the session)."""
    # Get the file path before deleting from memory
    session_file = session_manager._get_session_file_path(session)

    success = session_manager.delete_session(session.session_id)

    if success and session_file.exists():
        try:
            session_file.unlink()
        except OSError as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to delete session file: {e}"
            )

    return {"success": True, "message": "Session deleted"}


@router.post("/{session_id}/resume")
async def resume_session(
    session: AnalysisSession = Depends(get_user_session),
):
    """Resume a session (returns full state for frontend). User must own the session."""
    return {
        "session_id": session.session_id,
        "ticker": session.ticker,
        "user_id": session.user_id,
        "created_at": session.created_at.isoformat(),
        "conversation_history": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata,
            }
            for msg in session.conversation_history
        ],
        "report": session.report_state.to_dict() if session.report_state else None,
        "metadata": session.metadata,
    }


@router.get("/{session_id}/beliefs")
async def get_session_beliefs(
    session: AnalysisSession = Depends(get_user_session),
):
    """Get all analyst notes/beliefs for a session. User must own the session."""
    beliefs = session.belief_graph.get_all_beliefs()

    by_section = {}
    for belief in beliefs:
        section = "general"
        if belief.source.startswith("chat:"):
            section = belief.source.split(":", 1)[1]

        if section not in by_section:
            by_section[section] = []
        by_section[section].append(belief.to_dict())

    return {
        "session_id": session.session_id,
        "beliefs": [b.to_dict() for b in beliefs],
        "count": len(beliefs),
        "by_section": by_section,
    }


@router.post("/{session_id}/finalize")
async def finalize_session(
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Finalize an analysis session by rewriting sections with analyst notes. User must own the session."""
    beliefs = session.belief_graph.get_all_beliefs()

    if not beliefs:
        return {
            "success": True,
            "sections_updated": 0,
            "total_beliefs_incorporated": 0,
            "message": "No analyst notes to incorporate",
        }

    # Group beliefs by target section
    beliefs_by_section = {}
    for belief in beliefs:
        section = "recommendation"
        if belief.source.startswith("chat:"):
            section = belief.source.split(":", 1)[1]

        if section not in beliefs_by_section:
            beliefs_by_section[section] = []

        beliefs_by_section[section].append(
            ExtractedBelief(
                content=belief.content,
                insight_type=InsightType.CONFIRMED_FACT,
                target_section=section,
                confidence=belief.confidence,
                supporting_quote="",
            )
        )

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")

    if not api_key:
        raise HTTPException(status_code=500, detail="LLM API key not configured")

    sections_updated = 0
    total_beliefs = 0

    with session_manager.session_context(session.session_id) as sess:
        if not sess or not sess.report_state:
            raise HTTPException(status_code=404, detail="Session expired or no report")

        for section_id, section_beliefs in beliefs_by_section.items():
            section = sess.report_state.get_section(section_id)

            if not section:
                logger.warning(f"Section {section_id} not found, skipping")
                continue

            rewritten = rewrite_section_with_beliefs(
                section_id=section_id,
                section_title=section.title,
                original_content=section.content,
                beliefs=section_beliefs,
                llm_func=call_llm,
                api_key=api_key,
                model=model,
            )

            if rewritten:
                sess.report_state.update_section(section_id, rewritten)
                sections_updated += 1
                total_beliefs += len(section_beliefs)

        sess.metadata["finalized"] = True
        sess.metadata["finalized_at"] = datetime.now().isoformat()
        sess.metadata["beliefs_incorporated"] = total_beliefs

    return {
        "success": True,
        "sections_updated": sections_updated,
        "total_beliefs_incorporated": total_beliefs,
        "message": f"Analysis finalized: {sections_updated} sections updated with {total_beliefs} analyst notes",
    }


@router.post("/{session_id}/regenerate-report")
async def regenerate_report(
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Regenerate the Full Report narrative with current beliefs. User must own the session."""
    sections = session.report_state.sections
    content_sections = [s for s in sections.values() if hasattr(s, "content") and s.content]
    if not content_sections:
        raise HTTPException(status_code=400, detail="Report has no content. Run analysis first.")

    ticker = session.ticker
    beliefs = session.belief_graph.get_all_beliefs()
    analyst_sources = session.analyst_sources.copy() if session.analyst_sources else []

    fundamentals = sections.get("fundamentals", {})
    technicals = sections.get("technicals", {})
    bull_case = sections.get("bull_case", {})
    bear_case = sections.get("bear_case", {})
    moat_analysis = sections.get("moat_analysis", {})
    strategy = sections.get("strategy", {})

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")

    if not api_key:
        raise HTTPException(status_code=500, detail="LLM API key not configured")

    from backend.agents.orchestrator_wrapper import generate_full_report, AnalysisContext, StockInfo

    analyst_notes = []
    for belief in beliefs:
        analyst_notes.append(
            {
                "content": belief.content,
                "section": (
                    belief.source.split(":", 1)[1] if belief.source.startswith("chat:") else "general"
                ),
                "confidence": belief.confidence,
            }
        )

    analyst_citations = ""
    if analyst_sources:
        analyst_citations = "\n\nANALYST BELIEFS (cite as [A1], [A2], etc.):\n"
        for src in analyst_sources:
            analyst_citations += f"[{src.id}] {src.belief_content}\n"

    def get_content(section):
        if hasattr(section, "content"):
            return section.content
        return str(section.get("content", ""))

    minimal_stock_info = StockInfo(
        symbol=ticker,
        name=ticker,
        sector="",
        industry="",
        country="",
        business_summary="",
        current_price=None,
        market_cap=None,
        pe_ratio=None,
        forward_pe=None,
        peg_ratio=None,
        price_to_book=None,
        profit_margin=None,
        operating_margin=None,
        roe=None,
        roa=None,
        revenue_growth=None,
        earnings_growth=None,
        debt_to_equity=None,
        current_ratio=None,
        dividend_yield=None,
        beta=None,
        fifty_two_week_high=None,
        fifty_two_week_low=None,
        analyst_target_price=None,
        analyst_recommendation=None,
    )

    report_context = AnalysisContext(
        api_key=api_key,
        model=model,
        stock_info=minimal_stock_info,
        fundamentals_analysis=get_content(fundamentals),
        technicals_analysis=get_content(technicals),
        strategy_analysis=get_content(strategy),
        moat_analysis=get_content(moat_analysis),
        sentiment_report="",
        bull_thesis=get_content(bull_case),
        bear_thesis=get_content(bear_case),
    )

    result = generate_full_report(
        context=report_context,
        analyst_notes=analyst_notes,
        analyst_citations=analyst_citations,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {result.error}")

    with session_manager.session_context(session.session_id) as sess:
        if not sess or not sess.report_state:
            raise HTTPException(status_code=404, detail="Session expired")

        sess.report_state.add_section(
            "full_report", "Full Report", result.content, SectionType.EXECUTIVE_SUMMARY
        )

        try:
            from backend.core.pdf_formatting import (
                extract_highlights,
                extract_recommendation,
            )
            from backend.core.pdf_generator_v2 import generate_report_headline

            company_name = sess.metadata.get("company_name", ticker)
            rating = extract_recommendation(sess.report_state)
            highlights = extract_highlights(result.content)
            headline = generate_report_headline(company_name, rating, result.content, highlights)
            sess.report_state.metadata["headline"] = headline
        except Exception as e:
            logger.warning(f"Failed to pre-generate headline: {e}")

        prev_cost = sess.metadata.get("total_cost_usd", 0.0)
        sess.metadata["total_cost_usd"] = prev_cost + result.cost_usd

    return {
        "success": True,
        "message": f"Report regenerated with {len(analyst_notes)} analyst notes",
        "cost_usd": round(result.cost_usd, 4),
    }
