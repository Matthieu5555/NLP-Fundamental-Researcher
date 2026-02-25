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
"""

import logging
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


def run_full_analysis(
    ticker: str,
    session_id: str,
    is_us: bool = True,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    Unified analysis function that routes to US or Non-US orchestrator.

    Args:
        ticker: Stock ticker symbol
        session_id: Session ID for tracking
        is_us: True for US companies (use FDS), False for Non-US (use yfinance)
        progress_callback: Optional callback for progress updates (step, total, message)

    Returns:
        dict with analysis results and cost breakdown
    """
    from backend.core.session import session_manager

    config = load_config()

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
                    session.metadata["dcf_model"] = result.dcf_result.to_dict()

                if result.sensitivity_result:
                    session.metadata["sensitivity_data"] = result.sensitivity_result.to_dict()

                if result.conviction_result:
                    session.metadata["conviction_data"] = result.conviction_result.to_dict()

                if result.scenario_result:
                    session.metadata["scenario_data"] = result.scenario_result.to_dict()

                if result.football_field_result:
                    session.metadata["football_field_data"] = result.football_field_result.to_dict()

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
        "sources": result.sources_collected,
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
        # Valuation content
        "dcf_valuation": result.dcf_analysis.content if result.dcf_analysis else None,
        "comp_table": result.comp_analysis.content if result.comp_analysis else None,
        "earnings_model": result.earnings_model.content if result.earnings_model else None,
        "sensitivity": result.sensitivity_analysis.content if result.sensitivity_analysis else None,
        "conviction": result.conviction_analysis.content if result.conviction_analysis else None,
        "scenario_analysis": result.scenario_analysis.content if result.scenario_analysis else None,
        "precedent_transactions": result.precedent_analysis.content if result.precedent_analysis else None,
        "football_field": result.football_field_analysis.content if result.football_field_analysis else None,
        "external_forces": result.strategic_assessment_analysis.content if result.strategic_assessment_analysis else None,
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
        "sources": result.sources_collected or [],
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

    # Valuation sections
    if result.dcf_analysis and result.dcf_analysis.success:
        report.update_section("dcf_valuation", result.dcf_analysis.content)

    if result.comp_analysis and result.comp_analysis.success:
        report.update_section("comp_table", result.comp_analysis.content)

    if result.earnings_model and result.earnings_model.success:
        report.update_section("earnings_model", result.earnings_model.content)

    if result.sensitivity_analysis and result.sensitivity_analysis.success:
        report.update_section("sensitivity", result.sensitivity_analysis.content)

    if result.conviction_analysis and result.conviction_analysis.success:
        report.update_section("conviction", result.conviction_analysis.content)

    # New valuation sections
    if result.scenario_analysis and result.scenario_analysis.success:
        report.update_section("scenario_analysis", result.scenario_analysis.content)

    if result.precedent_analysis and result.precedent_analysis.success:
        report.update_section("precedent_transactions", result.precedent_analysis.content)

    if result.football_field_analysis and result.football_field_analysis.success:
        report.update_section("football_field", result.football_field_analysis.content)

    if result.strategic_assessment_analysis and result.strategic_assessment_analysis.content:
        report.update_section("external_forces", result.strategic_assessment_analysis.content)

    # Add sources
    for source in result.sources_collected:
        report.add_source(
            title=source.get("title", "Unknown"),
            url=source.get("url", ""),
            source_type=source.get("source_type", "unknown"),
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
                title=source.get("title", "Unknown"),
                url=source.get("url", ""),
                source_type=source.get("source_type", "unknown"),
            )
