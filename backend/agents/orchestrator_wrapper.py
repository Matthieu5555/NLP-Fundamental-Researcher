"""
Wrapper for the analysis orchestrators.

Provides unified interface for:
- US Analysis: Uses FinancialDatasets.ai (fast, no rate limits)
- Non-US Analysis: Uses yfinance + Alpha Vantage (rate limited)

Note: Path setup for src_george_researcher imports is centralized in backend/main.py.
The fallback here ensures this module works when imported directly (e.g., tests).

Re-exports:
    run_analysis         - Non-US analysis (legacy)
    run_us_analysis      - US analysis with FDS
    run_full_analysis    - Unified function that routes based on queue type
    generate_full_report - Generate narrative report from analysis
    AnalysisContext      - Dataclass for report generation context
    Config               - Configuration dataclass
    load_config          - Load config from environment
    StockInfo            - Stock information dataclass
    CostBreakdown        - Per-API cost tracking
    synthesize_investment_thesis - Single entry point for thesis generation
"""

import logging
from dataclasses import replace
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)

# sys.path configured in backend/main.py
from src_george_researcher import orchestrator as orch
from src_george_researcher import config as cfg
from src_george_researcher import analysis_agents as anlys
from src_george_researcher.data_fetchers import stock_data as sd
from src_george_researcher.analysis.us.orchestrator import run_us_analysis, USFullAnalysis
from src_george_researcher.analysis.shared.cost_tracking import CostBreakdown
from src_george_researcher.analysis.pipeline_config import US_TOTAL_STEPS, NON_US_TOTAL_STEPS
from backend.core.contradiction_detector import (
    get_structured_contradictions,
    detect_contradictions_and_research_items
)

# Re-export for use by backend API
run_analysis = orch.run_analysis  # Non-US orchestrator
Config = cfg.Config
load_config = cfg.load_config
generate_full_report = anlys.generate_full_report
AnalysisContext = anlys.AnalysisContext
StockInfo = sd.StockInfo


def _format_conviction_summary(conviction_data: dict) -> str:
    """Format conviction data as a one-line summary for the investment thesis LLM context."""
    if not conviction_data:
        return ""
    score = conviction_data.get("overall_score", "")
    rec = conviction_data.get("recommendation", "")
    conf = conviction_data.get("confidence", "")
    summary = conviction_data.get("summary", "")
    parts = []
    if rec:
        parts.append(f"Rating: {rec}")
    if score:
        parts.append(f"Conviction: {score}/100")
    if conf:
        parts.append(f"Confidence: {conf}%")
    if summary:
        parts.append(summary)
    return " | ".join(parts)


def synthesize_investment_thesis(
    report_state: Any,
    session_metadata: dict,
    ticker: str,
    analyst_notes: list | None = None,
    analyst_sources: list | None = None,
) -> float:
    """Synthesize investment thesis from completed analysis sections.

    Reads all narrative sections from report_state, calls generate_full_report(),
    and stores the result back. Returns LLM cost in USD.

    On failure, populates investment_thesis with recommendation content so the
    contract (thesis always exists) holds. Callers never need fallback logic.
    """
    import os
    from backend.core.report_builder import SectionType

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")

    if not api_key:
        logger.warning("No OPENROUTER_API_KEY set; falling back to recommendation for thesis")
        _fallback_thesis_from_recommendation(report_state)
        return 0.0

    sections = report_state.sections

    def get_content(section_id: str) -> str:
        s = sections.get(section_id)
        if s is None:
            return ""
        if hasattr(s, "content"):
            return s.content or ""
        return str(s.get("content", ""))

    # Build minimal StockInfo for the context
    minimal_stock_info = StockInfo(
        symbol=ticker,
        name=session_metadata.get("company_name", ticker),
        sector=session_metadata.get("stock_info", {}).get("sector", ""),
        industry=session_metadata.get("stock_info", {}).get("industry", ""),
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

    context = AnalysisContext(
        api_key=api_key,
        model=model,
        stock_info=minimal_stock_info,
        fundamentals_analysis=get_content("fundamentals"),
        technicals_analysis=get_content("technicals"),
        strategy_analysis=get_content("strategy"),
        moat_analysis=get_content("moat"),
        sentiment_report="",
        bull_thesis=get_content("bull_case"),
        bear_thesis=get_content("bear_case"),
    )

    # Build analyst notes list if sources provided
    formatted_notes = None
    analyst_citations = ""
    if analyst_notes:
        formatted_notes = analyst_notes
    elif analyst_sources:
        formatted_notes = [
            {"content": src.belief_content, "section": src.section, "confidence": 0.8}
            for src in analyst_sources
        ]

    if analyst_sources:
        analyst_citations = "\n\nANALYST BELIEFS (cite as [A1], [A2], etc.):\n"
        for src in analyst_sources:
            analyst_citations += f"[{src.id}] {src.belief_content}\n"

    conviction_data = session_metadata.get("conviction", {})
    conviction_summary = _format_conviction_summary(conviction_data)

    try:
        result = generate_full_report(
            context=context,
            analyst_notes=formatted_notes,
            analyst_citations=analyst_citations,
            conviction_summary=conviction_summary,
        )
    except Exception as e:
        logger.warning("Investment thesis LLM call failed: %s", e)
        _fallback_thesis_from_recommendation(report_state)
        return 0.0

    if not result.success:
        logger.warning("Investment thesis generation unsuccessful: %s", result.error)
        _fallback_thesis_from_recommendation(report_state)
        return 0.0

    report_state.add_section(
        "investment_thesis", "Investment Thesis", result.content,
        SectionType.INVESTMENT_THESIS,
    )

    # Pre-generate headline (non-blocking: failure leaves headline unset)
    try:
        from backend.core.pdf_formatting import extract_highlights, extract_recommendation
        from backend.core.pdf_generator_v2 import generate_report_headline

        company_name = session_metadata.get("company_name", ticker)
        rating = extract_recommendation(report_state)
        highlights = extract_highlights(result.content)
        headline = generate_report_headline(company_name, rating, result.content, highlights)
        report_state.metadata["headline"] = headline
    except Exception as e:
        logger.warning("Failed to pre-generate headline: %s", e)

    return result.cost_usd


def _fallback_thesis_from_recommendation(report_state: Any) -> None:
    """Populate investment_thesis with recommendation content as degraded fallback."""
    from backend.core.report_builder import SectionType

    rec = report_state.sections.get("recommendation")
    if rec and hasattr(rec, "content") and rec.content:
        report_state.add_section(
            "investment_thesis", "Investment Thesis", rec.content,
            SectionType.INVESTMENT_THESIS,
        )
    else:
        report_state.add_section(
            "investment_thesis", "Investment Thesis",
            "Investment thesis could not be generated.",
            SectionType.INVESTMENT_THESIS,
        )


def run_full_analysis(
    ticker: str,
    session_id: str,
    is_us: bool = True,
    progress_callback: Optional[Callable] = None,
    model_override: Optional[str] = None,
) -> dict:
    """
    Unified analysis function that routes to US or Non-US orchestrator.

    Args:
        ticker: Stock ticker symbol
        session_id: Session ID for tracking
        is_us: True for US companies (use FDS), False for Non-US (use yfinance)
        progress_callback: Optional callback for progress updates (step, total, message)
        model_override: If provided, replaces the env-loaded openrouter_model in config

    Returns:
        dict with analysis results and cost breakdown
    """
    from backend.core.session import session_manager

    config = load_config()
    if model_override:
        config = replace(config, openrouter_model=model_override)

    # Wrap progress callback to match orchestrator signature
    def wrapped_progress(message: str, step: int = None):
        if progress_callback:
            total = US_TOTAL_STEPS if is_us else NON_US_TOTAL_STEPS
            progress_callback(step or 1, total, message)

    if is_us:
        # Run US analysis with FDS
        logger.info(f"Running US analysis for {ticker}")
        result = run_us_analysis(
            symbol=ticker,
            config=config,
            progress_callback=wrapped_progress,
        )

        # Convert USFullAnalysis to dict for session storage
        analysis_dict = _convert_us_result(result)

        # Run contradiction detection for Further Research section
        logger.info("Running contradiction detection...")
        try:
            structured_data = get_structured_contradictions(result)
            further_research_md = detect_contradictions_and_research_items(result)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Contradiction detection failed: {e}")
            structured_data = {"contradictions": [], "research_gaps": []}
            further_research_md = "Contradiction analysis could not be completed."

        # Update session with results
        with session_manager.session_context(session_id) as session:
            if session and session.report_state:
                _populate_report_us(session.report_state, result)
                # Add Further Research section
                session.report_state.update_section("further_research", further_research_md)
                session.metadata["total_cost_usd"] = result.total_cost_usd
                session.metadata["total_tokens"] = result.total_tokens
                session.metadata["cost_breakdown"] = result.cost_breakdown.to_display_dict()
                session.metadata["is_us"] = True
                session.metadata["contradictions"] = structured_data["contradictions"]
                session.metadata["research_gaps"] = structured_data["research_gaps"]

                # Store structured valuation data for frontend interactive components
                if result.dcf_result:
                    session.metadata["dcf"] = result.dcf_result.to_dict()

                if result.sensitivity_result:
                    session.metadata["sensitivity"] = result.sensitivity_result.to_dict()

                if result.conviction_result:
                    session.metadata["conviction"] = result.conviction_result.to_dict()

                if result.scenario_result:
                    session.metadata["scenarios"] = result.scenario_result.to_dict()

                if result.football_field_result:
                    session.metadata["football_field"] = result.football_field_result.to_dict()

                if result.comp_result:
                    session.metadata["comps"] = result.comp_result.to_dict()

                if result.precedent_result:
                    session.metadata["precedents"] = result.precedent_result.to_dict()

                if result.earnings_rows:
                    from src_george_researcher.valuation.earnings_model import earnings_rows_to_dict
                    session.metadata["earnings_model"] = earnings_rows_to_dict(result.earnings_rows)

                if result.growth_margin_sensitivity:
                    session.metadata["sensitivity_operating"] = result.growth_margin_sensitivity.to_dict()

                if result.ddm_result:
                    session.metadata["ddm"] = result.ddm_result

                if result.earnings_quality:
                    session.metadata["earnings_quality_data"] = result.earnings_quality

                if result.investment_context:
                    session.metadata["investment_context"] = result.investment_context.to_dict()

                # Run model auditor (non-blocking: failures produce empty audit)
                try:
                    from src_george_researcher.valuation.model_auditor import audit_valuation_model
                    facts = result.company_facts
                    dcf_data = session.metadata.get("dcf", {})
                    company_ctx = {
                        "ticker": ticker,
                        "name": facts.name if facts else ticker,
                        "market_cap": facts.market_cap if facts else None,
                        "sector": facts.sector if facts else None,
                        "current_price": dcf_data.get("current_price", 0),
                        "revenue": dcf_data.get("base_revenue"),
                    }
                    audit = audit_valuation_model(
                        company_context=company_ctx,
                        valuation_results=session.metadata,
                        api_key=config.openrouter_api_key,
                        model=config.openrouter_model,
                    )
                    session.metadata["model_audit"] = audit.to_dict()
                except Exception as e:
                    logger.warning("Model audit failed (non-blocking): %s", e)
                    session.metadata["model_audit"] = {}

                # Synthesize investment thesis (guarantees section always exists)
                if progress_callback:
                    from src_george_researcher.analysis.pipeline_config import USStep
                    wrapped_progress("Synthesizing investment thesis...", USStep.INVESTMENT_THESIS)
                thesis_cost = synthesize_investment_thesis(
                    session.report_state, session.metadata, ticker,
                )
                session.metadata["total_cost_usd"] += thesis_cost

        # Include fair value in result for async watchlist update by the worker
        if result.dcf_result:
            analysis_dict["_fair_value_per_share"] = result.dcf_result.fair_value_per_share

        return analysis_dict

    else:
        # Run Non-US analysis with yfinance
        logger.info(f"Running Non-US analysis for {ticker}")
        result = run_analysis(
            symbol=ticker,
            config=config,
            include_debate=True,
            include_moat=True,
            include_strategy=True,
            progress_callback=wrapped_progress,
        )

        # Convert FullAnalysis to dict
        analysis_dict = _convert_non_us_result(result)

        # Run contradiction detection for Further Research section
        logger.info("Running contradiction detection...")
        try:
            structured_data = get_structured_contradictions(result)
            further_research_md = detect_contradictions_and_research_items(result)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Contradiction detection failed: {e}")
            structured_data = {"contradictions": [], "research_gaps": []}
            further_research_md = "Contradiction analysis could not be completed."

        # Update session with results
        with session_manager.session_context(session_id) as session:
            if session and session.report_state:
                _populate_report_non_us(session.report_state, result)
                # Add Further Research section
                session.report_state.update_section("further_research", further_research_md)
                session.metadata["total_cost_usd"] = result.total_cost_usd
                session.metadata["total_tokens"] = result.total_tokens
                # Create cost breakdown for non-US
                cost = CostBreakdown()
                cost.openrouter_llm = result.total_cost_usd * 0.3  # Estimate LLM portion
                cost.gemini_search = result.total_cost_usd * 0.5   # Estimate Gemini portion
                cost.alpha_vantage = 0.0  # Free tier
                session.metadata["cost_breakdown"] = cost.to_display_dict()
                session.metadata["is_us"] = False
                session.metadata["contradictions"] = structured_data["contradictions"]
                session.metadata["research_gaps"] = structured_data["research_gaps"]

                # Run model auditor (same logic as US path; auditor is model-agnostic)
                try:
                    from src_george_researcher.valuation.model_auditor import audit_valuation_model
                    company_ctx = {
                        "ticker": ticker,
                        "name": ticker,
                        "market_cap": None,
                        "sector": None,
                        "current_price": session.metadata.get("dcf", {}).get("current_price", 0),
                        "revenue": session.metadata.get("dcf", {}).get("base_revenue"),
                    }
                    audit = audit_valuation_model(
                        company_context=company_ctx,
                        valuation_results=session.metadata,
                        api_key=config.openrouter_api_key,
                        model=config.openrouter_model,
                    )
                    session.metadata["model_audit"] = audit.to_dict()
                except Exception as e:
                    logger.warning("Model audit failed (non-blocking): %s", e)
                    session.metadata["model_audit"] = {}

                # Synthesize investment thesis (guarantees section always exists)
                thesis_cost = synthesize_investment_thesis(
                    session.report_state, session.metadata, ticker,
                )
                session.metadata["total_cost_usd"] += thesis_cost

        return analysis_dict


def _convert_us_result(result: USFullAnalysis) -> dict:
    """Convert USFullAnalysis to dict for JSON serialization."""
    return {
        "symbol": result.symbol,
        "timestamp": result.timestamp,
        "success": result.success,
        "errors": result.errors,
        "total_tokens": result.total_tokens,
        "total_cost_usd": result.total_cost_usd,
        "cost_breakdown": result.cost_breakdown.to_display_dict(),
        "sources": [s.to_dict() for s in result.sources_collected] if result.sources_collected else [],
        "is_us": True,
        # Include analysis content for report building
        "fundamentals": result.fundamentals_analysis.content if result.fundamentals_analysis else None,
        "insider_analysis": result.insider_analysis.content if result.insider_analysis else None,
        "technicals": result.technical_analysis.content if result.technical_analysis else None,
        "bull_thesis": result.bull_thesis.content if result.bull_thesis else None,
        "bear_thesis": result.bear_thesis.content if result.bear_thesis else None,
        "moat": result.moat_analysis.content if result.moat_analysis else None,
        "strategy": result.strategy_analysis.content if result.strategy_analysis else None,
        "recommendation": result.recommendation.content if result.recommendation else None,
        # Valuation content — only include successful results
        "dcf": result.dcf_analysis.content if result.dcf_analysis and result.dcf_analysis.success else None,
        "comps": result.comp_analysis.content if result.comp_analysis and result.comp_analysis.success else None,
        "earnings_model": result.earnings_model.content if result.earnings_model and result.earnings_model.success else None,
        "sensitivity": result.sensitivity_analysis.content if result.sensitivity_analysis and result.sensitivity_analysis.success else None,
        "conviction": result.conviction_analysis.content if result.conviction_analysis and result.conviction_analysis.success else None,
        "scenarios": result.scenario_analysis.content if result.scenario_analysis and result.scenario_analysis.success else None,
        "precedents": result.precedent_analysis.content if result.precedent_analysis and result.precedent_analysis.success else None,
        "football_field": result.football_field_analysis.content if result.football_field_analysis and result.football_field_analysis.success else None,
        "industry": result.strategic_assessment_analysis.content if result.strategic_assessment_analysis and result.strategic_assessment_analysis.success else None,
    }


def _convert_non_us_result(result: Any) -> dict:
    """Convert FullAnalysis to dict for JSON serialization."""
    return {
        "symbol": result.symbol,
        "timestamp": result.timestamp,
        "success": result.success,
        "errors": result.errors,
        "total_tokens": result.total_tokens,
        "total_cost_usd": result.total_cost_usd,
        "cost_breakdown": result.cost_breakdown.to_display_dict() if hasattr(result, 'cost_breakdown') and result.cost_breakdown else {},
        "sources": [s.to_dict() for s in result.sources_collected] if result.sources_collected else [],
        "is_us": False,
        # Include analysis content
        "fundamentals": result.fundamentals_analysis.content if result.fundamentals_analysis else None,
        "technicals": result.technical_analysis.content if result.technical_analysis else None,
        "bull_thesis": result.bull_thesis.content if result.bull_thesis else None,
        "bear_thesis": result.bear_thesis.content if result.bear_thesis else None,
        "moat": result.moat_analysis.content if result.moat_analysis else None,
        "strategy": result.strategy_analysis.content if result.strategy_analysis else None,
        "recommendation": result.recommendation.content if result.recommendation else None,
    }


def _populate_report_us(report: Any, result: USFullAnalysis):
    """Populate report sections from US analysis results."""
    if result.recommendation:
        report.update_section("recommendation", result.recommendation.content)

    if result.fundamentals_analysis:
        report.update_section("fundamentals", result.fundamentals_analysis.content)

    if result.insider_analysis:
        report.update_section("insider_activity", result.insider_analysis.content)

    if result.technical_analysis:
        report.update_section("technicals", result.technical_analysis.content)

    if result.bull_thesis:
        report.update_section("bull_case", result.bull_thesis.content)

    if result.bear_thesis:
        report.update_section("bear_case", result.bear_thesis.content)

    if result.moat_analysis:
        report.update_section("moat", result.moat_analysis.content)

    if result.strategy_analysis:
        report.update_section("strategy", result.strategy_analysis.content)

    # Valuation sections — only store successful results to avoid rendering
    # "could not be performed" messages in PDF/frontend
    if result.dcf_analysis and result.dcf_analysis.success:
        report.update_section("dcf", result.dcf_analysis.content)

    if result.comp_analysis and result.comp_analysis.success:
        report.update_section("comps", result.comp_analysis.content)

    if result.earnings_model and result.earnings_model.success:
        report.update_section("earnings_model", result.earnings_model.content)

    if result.sensitivity_analysis and result.sensitivity_analysis.success:
        report.update_section("sensitivity", result.sensitivity_analysis.content)

    if result.conviction_analysis and result.conviction_analysis.success:
        report.update_section("conviction", result.conviction_analysis.content)

    if result.scenario_analysis and result.scenario_analysis.success:
        report.update_section("scenarios", result.scenario_analysis.content)

    if result.precedent_analysis and result.precedent_analysis.success:
        report.update_section("precedents", result.precedent_analysis.content)

    if result.football_field_analysis and result.football_field_analysis.success:
        report.update_section("football_field", result.football_field_analysis.content)

    if result.strategic_assessment_analysis and result.strategic_assessment_analysis.content:
        report.update_section("industry", result.strategic_assessment_analysis.content)

    # Add sources
    for source in result.sources_collected:
        report.add_source(
            title=source.title,
            url=source.url,
            source_type=source.source_type,
        )


def _populate_report_non_us(report: Any, result: Any):
    """Populate report sections from Non-US analysis results."""
    if result.recommendation:
        report.update_section("recommendation", result.recommendation.content)

    if result.fundamentals_analysis:
        report.update_section("fundamentals", result.fundamentals_analysis.content)

    if result.technical_analysis:
        report.update_section("technicals", result.technical_analysis.content)

    if result.bull_thesis:
        report.update_section("bull_case", result.bull_thesis.content)

    if result.bear_thesis:
        report.update_section("bear_case", result.bear_thesis.content)

    if result.moat_analysis:
        report.update_section("moat", result.moat_analysis.content)

    if result.strategy_analysis:
        report.update_section("strategy", result.strategy_analysis.content)

    # Add sources
    if result.sources_collected:
        for source in result.sources_collected:
            report.add_source(
                title=source.title,
                url=source.url,
                source_type=source.source_type,
            )
