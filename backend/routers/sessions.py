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
    POST   /{session_id}/regenerate-report - Regenerate Investment Thesis (narrative only)
    POST   /{session_id}/update-analysis   - Selective re-analysis with analyst overrides (SSE)
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

from backend.agents.llm_wrapper import call_llm

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_SESSION_LIMIT = 50


def _format_conviction_summary(conviction_data: dict) -> str:
    """Format conviction data as a one-line summary for the investment thesis LLM context.

    Canonical implementation lives in orchestrator_wrapper._format_conviction_summary.
    This wrapper avoids a circular import at module load time (sessions -> orchestrator_wrapper
    -> session_manager -> sessions).
    """
    from backend.agents.orchestrator_wrapper import _format_conviction_summary as _impl
    return _impl(conviction_data)


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
    """Regenerate the Investment Thesis narrative with current beliefs. User must own the session."""
    sections = session.report_state.sections
    content_sections = [s for s in sections.values() if hasattr(s, "content") and s.content]
    if not content_sections:
        raise HTTPException(status_code=400, detail="Report has no content. Run analysis first.")

    from backend.agents.orchestrator_wrapper import synthesize_investment_thesis

    ticker = session.ticker
    beliefs = session.belief_graph.get_all_beliefs()
    analyst_sources = session.analyst_sources.copy() if session.analyst_sources else []

    analyst_notes = [
        {
            "content": belief.content,
            "section": belief.source.split(":", 1)[1] if belief.source.startswith("chat:") else "general",
            "confidence": belief.confidence,
        }
        for belief in beliefs
    ]

    with session_manager.session_context(session.session_id) as sess:
        if not sess or not sess.report_state:
            raise HTTPException(status_code=404, detail="Session expired")

        thesis_cost = synthesize_investment_thesis(
            sess.report_state, sess.metadata, ticker,
            analyst_notes=analyst_notes,
            analyst_sources=analyst_sources,
        )
        prev_cost = sess.metadata.get("total_cost_usd", 0.0)
        sess.metadata["total_cost_usd"] = prev_cost + thesis_cost

    return {
        "success": True,
        "message": f"Report regenerated with {len(analyst_notes)} analyst notes",
        "cost_usd": round(thesis_cost, 4),
    }


@router.post("/{session_id}/update-analysis")
async def update_analysis(
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Selective re-analysis driven by analyst beliefs.

    Unlike regenerate-report (which only rewrites narrative prose), this
    endpoint re-runs the pipeline stages that are affected by the analyst's
    beliefs. Numeric valuation views hard-override DCF assumptions.
    Qualitative beliefs become non-negotiable directives for agents.

    Stages are re-run in dependency order:
    1. Strategy/moat (if dirty)
    2. DCF with numeric overrides (if VALUATION_VIEW beliefs)
    3. Sensitivity/scenarios/football field (pure math, if DCF changed)
    4. Bull/bear debate (if upstream changed or risk/opportunity beliefs)
    5. Conviction re-score (always)
    6. Contradiction re-detection
    7. Narrative report regeneration
    """
    import json as _json
    from fastapi.responses import StreamingResponse

    sections = session.report_state.sections
    content_sections = [s for s in sections.values() if hasattr(s, "content") and s.content]
    if not content_sections:
        raise HTTPException(status_code=400, detail="Report has no content. Run analysis first.")

    beliefs = session.belief_graph.get_all_beliefs()
    analyst_sources = session.analyst_sources.copy() if session.analyst_sources else []

    if not analyst_sources:
        raise HTTPException(status_code=400, detail="No analyst beliefs to incorporate.")

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM API key not configured")

    async def generate():
        """SSE generator for selective analysis update."""
        import asyncio

        total_cost = 0.0
        stages_updated = []

        def emit(event_type, data):
            return f"data: {_json.dumps({'event': event_type, **data})}\n\n"

        try:
            # --- Step 0: Parse overrides ---
            yield emit("stage", {"stage": "parsing_overrides", "message": "Parsing analyst overrides..."})
            await asyncio.sleep(0)

            from backend.core.belief_overrides import parse_analyst_overrides
            from backend.agents.llm_wrapper import call_llm as llm_func

            overrides = parse_analyst_overrides(
                beliefs=beliefs,
                analyst_sources=analyst_sources,
                llm_func=llm_func,
                api_key=api_key,
                model=model,
            )

            dirty = overrides.dirty_stages
            yield emit("overrides_parsed", {
                "dirty_stages": list(dirty),
                "dcf_overrides": {k: str(v) for k, v in overrides.dcf_overrides.items()},
                "warnings": overrides.warnings,
            })
            await asyncio.sleep(0)

            # Helper to get section content
            def get_content(section_id):
                s = sections.get(section_id)
                if s and hasattr(s, "content"):
                    return s.content
                return ""

            ticker = session.ticker
            stock_info = _build_stock_info_from_session(session)

            # --- Step 1: Re-run strategy if dirty ---
            strategy_content = get_content("strategy")
            if "strategy" in dirty:
                yield emit("stage", {"stage": "strategy", "message": "Re-running strategy analysis..."})
                await asyncio.sleep(0)

                from src_george_researcher.analysis_agents import analyze_strategy
                result = await asyncio.to_thread(
                    analyze_strategy,
                    api_key=api_key,
                    model=model,
                    stock_info=stock_info,
                    fundamentals_analysis=get_content("fundamentals"),
                    sentiment_report="",
                    analyst_directives=overrides.qualitative_directives,
                )
                if result.success:
                    strategy_content = result.content
                    total_cost += result.cost_usd
                    stages_updated.append("strategy")

            # --- Step 2: Re-run moat if dirty ---
            moat_content = get_content("moat")
            if "moat" in dirty:
                yield emit("stage", {"stage": "moat", "message": "Re-running moat analysis..."})
                await asyncio.sleep(0)

                from src_george_researcher.analysis_agents import analyze_moat
                result = await asyncio.to_thread(
                    analyze_moat,
                    api_key=api_key,
                    model=model,
                    stock_info=stock_info,
                    sentiment_report="",
                    analyst_directives=overrides.qualitative_directives,
                )
                if result.success:
                    moat_content = result.content
                    total_cost += result.cost_usd
                    stages_updated.append("moat")

            # --- Step 2b: Re-run strategic assessment if dirty ---
            external_forces_content = get_content("industry")
            if "strategic_assessment" in dirty:
                yield emit("stage", {"stage": "strategic_assessment", "message": "Re-running strategic assessment..."})
                await asyncio.sleep(0)

                from src_george_researcher.analysis.strategic_assessment import run_strategic_assessment
                sa_result, sa_analysis = await asyncio.to_thread(
                    run_strategic_assessment,
                    api_key=api_key,
                    model=model,
                    stock_info=stock_info,
                    fundamentals_analysis=get_content("fundamentals"),
                    sentiment_report="",
                )
                if sa_analysis.success:
                    external_forces_content = sa_analysis.content
                    total_cost += sa_analysis.cost_usd
                    stages_updated.append("strategic_assessment")

            # --- Step 2c: Fetch additional research if beliefs suggest it ---
            research_triggering_types = {"competitive", "risk_identified", "opportunity"}
            research_triggering_sections = {"strategy", "industry"}
            needs_research = any(
                src.insight_type in research_triggering_types
                or src.section in research_triggering_sections
                for src in analyst_sources
            )
            if needs_research:
                yield emit("stage", {"stage": "research_fetch", "message": "Fetching additional research..."})
                await asyncio.sleep(0)

                try:
                    from src_george_researcher.analysis_agents import identify_research_topics
                    from src_george_researcher.data_fetchers.gemini_search import search_with_gemini

                    belief_text = "\n".join(src.belief_content for src in analyst_sources)
                    company_name = stock_info.name or ticker
                    sector = stock_info.sector or ""

                    topics = await asyncio.to_thread(
                        identify_research_topics,
                        api_key=api_key,
                        company_name=company_name,
                        sector=sector,
                        initial_research=belief_text,
                    )

                    google_api_key = os.getenv("GOOGLE_API_KEY", "")
                    new_sources = []
                    for query in topics[:3]:
                        results, err = await asyncio.to_thread(
                            search_with_gemini,
                            symbol=ticker,
                            company_name=company_name,
                            api_key=google_api_key,
                            query=query,
                            max_results=3,
                        )
                        if results and results.sources:
                            new_sources.extend(results.sources)

                    if new_sources:
                        yield emit("research_fetched", {"new_sources": len(new_sources)})
                        await asyncio.sleep(0)
                except Exception as e:
                    logger.warning(f"Research fetching during update failed (non-fatal): {e}")

            # --- Steps 3-4: Re-run DCF + downstream valuation (if dirty) ---
            reprop_outcome = None
            if "dcf" in dirty and overrides.dcf_overrides:
                yield emit("stage", {"stage": "dcf", "message": "Recalculating valuation with analyst overrides..."})
                await asyncio.sleep(0)

                from backend.core.valuation_repropagation import run_valuation_repropagation

                reprop_outcome = await asyncio.to_thread(
                    run_valuation_repropagation,
                    session_metadata=session.metadata,
                    dcf_overrides=overrides.dcf_overrides,
                )

                if reprop_outcome:
                    stages_updated.extend(["dcf", "sensitivity", "scenarios", "football_field"])

                    # Append assumption changelog
                    if reprop_outcome.assumption_changes:
                        changelog = session.metadata.setdefault("assumption_changelog", [])
                        changelog.extend(reprop_outcome.assumption_changes)

                    yield emit("dcf_updated", {
                        "fair_value": round(reprop_outcome.fair_value_per_share, 2) if reprop_outcome.fair_value_per_share else None,
                    })
                    await asyncio.sleep(0)

            # --- Step 5: Re-run bull/bear if dirty ---
            bull_content = get_content("bull_case")
            bear_content = get_content("bear_case")

            if "bull_bear" in dirty:
                yield emit("stage", {"stage": "bull_bear", "message": "Re-debating bull/bear theses..."})
                await asyncio.sleep(0)

                from src_george_researcher.analysis_agents import (
                    AnalysisContext as AC,
                    generate_bull_thesis,
                    generate_bear_thesis,
                )

                debate_context = AC(
                    api_key=api_key,
                    model=model,
                    stock_info=stock_info,
                    fundamentals_analysis=get_content("fundamentals"),
                    technicals_analysis=get_content("technicals"),
                    strategy_analysis=strategy_content,
                    moat_analysis=moat_content,
                    analyst_directives=overrides.qualitative_directives,
                )

                # Bull round 1
                bull_result = await asyncio.to_thread(generate_bull_thesis, debate_context)
                if bull_result.success:
                    bull_content = bull_result.content
                    total_cost += bull_result.cost_usd

                # Bear round 1 (with bull as counter-argument)
                from dataclasses import replace
                bear_ctx = AC(
                    api_key=api_key,
                    model=model,
                    stock_info=stock_info,
                    fundamentals_analysis=get_content("fundamentals"),
                    technicals_analysis=get_content("technicals"),
                    strategy_analysis=strategy_content,
                    moat_analysis=moat_content,
                    counter_argument=bull_content,
                    analyst_directives=overrides.qualitative_directives,
                )
                bear_result = await asyncio.to_thread(generate_bear_thesis, bear_ctx)
                if bear_result.success:
                    bear_content = bear_result.content
                    total_cost += bear_result.cost_usd

                stages_updated.append("bull_bear")

            # --- Step 6: Re-score conviction (always) ---
            conviction_result = None
            if "conviction" in dirty:
                yield emit("stage", {"stage": "conviction", "message": "Re-scoring conviction..."})
                await asyncio.sleep(0)

                from src_george_researcher.valuation.conviction import score_conviction
                conviction_result, conviction_analysis = await asyncio.to_thread(
                    score_conviction,
                    api_key=api_key,
                    model=model,
                    stock_info=stock_info,
                    fundamentals=get_content("fundamentals"),
                    technicals=get_content("technicals"),
                    bull_thesis=bull_content,
                    bear_thesis=bear_content,
                    dcf_result=None,  # DCF recalc handled by repropagation; conviction uses prose
                    sentiment_report="",
                )
                if conviction_analysis.success:
                    total_cost += conviction_analysis.cost_usd
                    stages_updated.append("conviction")

            # --- Step 6.5: Regenerate recommendation if dirty ---
            recommendation_content = get_content("recommendation")
            if "recommendation" in dirty:
                yield emit("stage", {"stage": "recommendation", "message": "Regenerating recommendation..."})
                await asyncio.sleep(0)

                from src_george_researcher.analysis_agents import (
                    AnalysisContext as RecContext,
                    synthesize_recommendation,
                )

                update_conviction_data = conviction_result.to_dict() if conviction_result else session.metadata.get("conviction", {})
                rec_conviction_summary = _format_conviction_summary(update_conviction_data)

                rec_context = RecContext(
                    api_key=api_key,
                    model=model,
                    stock_info=stock_info,
                    fundamentals_analysis=get_content("fundamentals"),
                    technicals_analysis=get_content("technicals"),
                    strategy_analysis=strategy_content,
                    moat_analysis=moat_content,
                    bull_thesis=bull_content,
                    bear_thesis=bear_content,
                    analyst_directives=overrides.qualitative_directives,
                    conviction_summary=rec_conviction_summary,
                )

                rec_result = await asyncio.to_thread(synthesize_recommendation, rec_context)
                if rec_result.success:
                    recommendation_content = rec_result.content
                    total_cost += rec_result.cost_usd
                    stages_updated.append("recommendation")

            # --- Step 7: Contradiction re-detection ---
            yield emit("stage", {"stage": "contradictions", "message": "Refreshing contradictions..."})
            await asyncio.sleep(0)

            # --- Step 8: Persist sections, then regenerate narrative ---
            yield emit("stage", {"stage": "saving", "message": "Saving updated sections..."})
            await asyncio.sleep(0)

            analyst_notes = [
                {"content": src.belief_content, "section": src.section, "confidence": 0.8}
                for src in analyst_sources
            ]

            with session_manager.session_context(session.session_id) as sess:
                if not sess or not sess.report_state:
                    yield emit("error", {"message": "Session expired during update"})
                    return

                # Update sections in report_state before thesis synthesis
                if "strategy" in stages_updated:
                    sess.report_state.update_section("strategy", strategy_content)
                if "strategic_assessment" in stages_updated:
                    sess.report_state.update_section("industry", external_forces_content)
                if "moat" in stages_updated:
                    sess.report_state.update_section("moat", moat_content)
                if "bull_bear" in stages_updated:
                    sess.report_state.update_section("bull_case", bull_content)
                    sess.report_state.update_section("bear_case", bear_content)
                if "recommendation" in stages_updated:
                    sess.report_state.update_section("recommendation", recommendation_content)

                # Update structured valuation data (from repropagation)
                if reprop_outcome:
                    sess.metadata.update(reprop_outcome.metadata_updates)
                    total_cost += reprop_outcome.cost_usd
                if conviction_result:
                    sess.metadata["conviction"] = conviction_result.to_dict()
                    if conviction_analysis.success:
                        sess.report_state.update_section("conviction", conviction_analysis.content)

                # Synthesize thesis from updated sections (reads report_state + metadata)
                yield emit("stage", {"stage": "narrative", "message": "Regenerating narrative report..."})

                from backend.agents.orchestrator_wrapper import synthesize_investment_thesis
                thesis_cost = await asyncio.to_thread(
                    synthesize_investment_thesis,
                    sess.report_state, sess.metadata, session.ticker,
                    analyst_notes=analyst_notes,
                    analyst_sources=analyst_sources,
                )
                total_cost += thesis_cost

                # Update cost
                prev_cost = sess.metadata.get("total_cost_usd", 0.0)
                sess.metadata["total_cost_usd"] = prev_cost + total_cost
                sess.metadata["last_update_analysis"] = datetime.now().isoformat()

            yield emit("complete", {
                "stages_updated": stages_updated,
                "total_cost_usd": round(total_cost, 4),
                "warnings": overrides.warnings,
            })

        except Exception as e:
            logger.exception(f"Update analysis failed: {e}")
            yield emit("error", {"message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")


def _build_stock_info_from_session(session: AnalysisSession):
    """Reconstruct a minimal StockInfo from session metadata for re-analysis.

    The initial analysis stores stock_info fields in session.metadata.
    We rebuild just enough for agent prompts to produce coherent output.
    """
    from src_george_researcher.data_fetchers.stock_data import StockInfo

    meta = session.metadata
    ticker = session.ticker

    # stock_info may be stored as a nested dict or flat in metadata
    si = meta.get("stock_info", {})
    get = lambda k, default=None: si.get(k) or meta.get(k, default)

    return StockInfo(
        symbol=ticker,
        name=get("company_name", ticker),
        sector=get("sector", ""),
        industry=get("industry", ""),
        country=get("country", "US"),
        business_summary=get("business_summary", ""),
        current_price=get("current_price"),
        market_cap=get("market_cap"),
        pe_ratio=get("pe_ratio"),
        forward_pe=get("forward_pe"),
        profit_margin=get("profit_margin"),
        operating_margin=get("operating_margin"),
        roe=get("roe"),
        revenue_growth=get("revenue_growth"),
        beta=get("beta"),
    )
