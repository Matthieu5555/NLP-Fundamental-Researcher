"""
Analysis functions for strategic company evaluation.
All agents receive news sentiment as context for informed analysis.
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional, List

from .analysis.shared.source_link import SourceLink
from .data_fetchers.stock_data import StockInfo, TechnicalIndicators, format_stock_info
from .llm import call_llm
from .analysis.shared.parsing import extract_json_from_llm_response
from .prompts import (
    FUNDAMENTALS_SYSTEM,
    TECHNICALS_SYSTEM,
    BULL_CASE_SYSTEM,
    BEAR_CASE_SYSTEM,
    MOAT_SYSTEM,
    STRATEGY_SYSTEM,
    SYNTHESIS_SYSTEM,
    FULL_REPORT_SYSTEM,
)

logger = logging.getLogger(__name__)

# Cheap model for classification tasks (topic identification, JSON extraction)
CLASSIFICATION_MODEL = "moonshotai/kimi-k2.5"

# =============================================================================
# CONTEXT LIMITS FOR LLM PROMPTS
# =============================================================================
# These limits control how much context (in characters) is passed to each agent.
# They are the primary tuning knobs for report quality vs. cost tradeoff.
#
# TUNING GUIDANCE:
#   - INCREASING a limit: More context but higher token cost (~$0.001 per 1000 chars)
#     May improve coherence but risks hitting model context limits
#   - DECREASING a limit: Faster/cheaper but agents may miss important context
#     May cause disjointed analysis if key facts are truncated
#
# These limits are tuned for Claude 3 Haiku (200K context) and Claude Sonnet.
# For smaller context models (e.g., GPT-3.5), reduce all limits by 50%.
#
# Key insight: Bull/Bear debate quality depends on seeing full counter-arguments,
# so FUNDAMENTALS_CONTEXT_LIMIT and COUNTER_ARGUMENT_LIMIT are critical.
# =============================================================================

# Initial research - used when identifying follow-up topics
# Higher = more topics identified, but diminishing returns after ~3000
INITIAL_RESEARCH_LIMIT = 2500

# Full report section limits - controls density of final report
# These are the primary tuning knobs for report length
FULL_REPORT_FUNDAMENTALS_LIMIT = 1500  # Core financial metrics
FULL_REPORT_THESIS_LIMIT = 1200        # Bull/bear arguments
FULL_REPORT_MOAT_LIMIT = 1000          # Competitive analysis
FULL_REPORT_STRATEGY_LIMIT = 1000      # Strategic outlook
FULL_REPORT_SENTIMENT_LIMIT = 800      # News sentiment summary
FULL_REPORT_TECHNICALS_LIMIT = 800     # Technical indicators

# Cross-agent context - how much one agent sees of another's output
# CRITICAL for debate quality: bull/bear agents need full counter-arguments
FUNDAMENTALS_CONTEXT_LIMIT = 1500      # Fundamentals passed to thesis agents
COUNTER_ARGUMENT_LIMIT = 1500          # Counter-argument in debate rounds
MOAT_CONTEXT_LIMIT = 1000              # Moat analysis in thesis
STRATEGY_CONTEXT_LIMIT = 1000          # Strategy in thesis
TECHNICALS_CONTEXT_LIMIT = 1000        # Technicals context

# Sentiment/news context - news and sentiment passed to various agents
SENTIMENT_LIMIT = 800                  # General sentiment context
NEWS_CONTEXT_LIMIT = 800               # News headlines/summaries

# Business description limits - company descriptions passed to agents
BUSINESS_SUMMARY_LIMIT = 800           # Company description
MOAT_SUMMARY_LIMIT = 1000              # Business summary in moat analysis

# Recommendation synthesis - what the final recommendation agent sees
# Lower limits here since recommendation synthesizes already-summarized content
RECOMMENDATION_BULL_BEAR_LIMIT = 800   # Bull/bear summaries
RECOMMENDATION_STRATEGY_LIMIT = 800    # Strategy summary
RECOMMENDATION_SENTIMENT_LIMIT = 600   # Sentiment summary
RECOMMENDATION_FUNDAMENTALS_LIMIT = 800  # Fundamentals summary
RECOMMENDATION_MOAT_LIMIT = 600        # Moat summary
RECOMMENDATION_TECHNICALS_LIMIT = 600  # Technicals summary

# Strategy agent context - what strategy analysis agent receives
STRATEGY_FUNDAMENTALS_LIMIT = 800      # Fundamentals in strategy analysis


@dataclass(frozen=True)
class AnalysisResult:
    """Container for analysis results."""
    section: str
    content: str
    tokens_used: int
    success: bool
    error: Optional[str] = None
    cost_usd: float = 0.0


@dataclass(frozen=True)
class AnalysisContext:
    """
    Consolidated context for all analysis functions.
    Replaces multiple individual parameters for cleaner function signatures.
    """
    api_key: str
    model: str
    stock_info: StockInfo
    fundamentals_analysis: str = ""
    technicals_analysis: str = ""
    strategy_analysis: str = ""
    moat_analysis: str = ""
    sentiment_report: str = ""
    counter_argument: str = ""  # For debate rounds
    bull_thesis: str = ""  # For synthesis
    bear_thesis: str = ""  # For synthesis


def identify_research_topics(
    api_key: str,
    company_name: str,
    sector: str,
    initial_research: str,
) -> List[str]:
    """
    Analyze initial research and identify topics needing deeper investigation.

    Uses Haiku for cheap classification. Returns list of search queries
    for follow-up research (e.g., industry trends, legal issues, technology developments).

    Args:
        api_key: OpenRouter API key
        company_name: Company name
        sector: Company sector
        initial_research: Combined initial research findings

    Returns:
        List of search queries for follow-up research (max 4)
    """
    prompt = f"""You are analyzing {company_name} in the {sector} sector.

Initial research findings:
{initial_research[:INITIAL_RESEARCH_LIMIT]}

Based on these findings, identify 2-4 specific topics that would significantly impact the company's valuation and need deeper research.

Think about:
- Industry/technology trends mentioned (e.g., "5G deployment timeline Europe 2024-2025")
- Legal or regulatory issues (e.g., "{company_name} antitrust investigation details")
- Competitive threats mentioned (e.g., "competitor X market share growth")
- New products or markets (e.g., "new product adoption rates")
- Macro factors specific to their business

Return ONLY a JSON array of search queries, no other text:
["query 1", "query 2", "query 3"]"""

    try:
        response = call_llm(
            api_key=api_key,
            model=CLASSIFICATION_MODEL,
            system_prompt="You identify research topics. Respond only with a JSON array.",
            user_prompt=prompt,
            temperature=0.0,
            max_tokens=200
        )

        if not response.success:
            logger.warning(f"Research topic identification failed: {response.error}")
            return []

        # Parse JSON response (handles markdown code blocks)
        topics = extract_json_from_llm_response(response.content)

        if isinstance(topics, list):
            logger.info(f"Identified {len(topics)} follow-up research topics")
            return topics[:4]  # Max 4 topics
        return []

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse research topics JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Research topic identification error: {e}")
        return []


def analyze_fundamentals(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    sentiment_report: str = "",
) -> AnalysisResult:
    """Analyze company fundamentals with news sentiment context."""
    sentiment_context = f"\n\nNEWS SENTIMENT CONTEXT:\n{sentiment_report[:SENTIMENT_LIMIT]}" if sentiment_report else ""
    business = stock_info.business_summary[:BUSINESS_SUMMARY_LIMIT] if stock_info.business_summary else "N/A"

    user_prompt = f"""Analyze these fundamentals for {stock_info.symbol}:

{format_stock_info(stock_info)}

Business: {business}{sentiment_context}"""

    response = call_llm(api_key, model, FUNDAMENTALS_SYSTEM, user_prompt)

    return AnalysisResult(
        section="Fundamentals",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
        cost_usd=response.cost_usd,
    )


def analyze_technicals(
    api_key: str,
    model: str,
    symbol: str,
    technicals: TechnicalIndicators,
    sentiment_report: str = "",
) -> AnalysisResult:
    """Analyze technical indicators with news sentiment context."""
    sentiment_context = f"\n\nNEWS SENTIMENT:\n{sentiment_report[:NEWS_CONTEXT_LIMIT]}" if sentiment_report else ""

    def fmt(v: Optional[float]) -> str:
        return f"{v:.2f}" if v is not None else "N/A"

    user_prompt = f"""Technical indicators for {symbol}:

Price: ${technicals.current_price:.2f}
Trend: {technicals.trend}
SMA 20: {fmt(technicals.sma_20)}
SMA 50: {fmt(technicals.sma_50)}
SMA 200: {fmt(technicals.sma_200)}
RSI: {fmt(technicals.rsi)}
MACD: {fmt(technicals.macd)}
ATR: {fmt(technicals.atr)}
Volume Ratio: {fmt(technicals.volume_ratio)}x{sentiment_context}"""

    response = call_llm(api_key, model, TECHNICALS_SYSTEM, user_prompt)

    return AnalysisResult(
        section="Technical Analysis",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
        cost_usd=response.cost_usd,
    )


def _generate_thesis(context: AnalysisContext, direction: str) -> AnalysisResult:
    """
    Generate an investment thesis (bull or bear) with full context.

    Args:
        context: AnalysisContext containing all analysis data and LLM config.
        direction: "bull" or "bear" — determines the system prompt and framing.

    Returns:
        AnalysisResult with thesis content.
    """
    is_bull = direction == "bull"
    system_prompt = BULL_CASE_SYSTEM if is_bull else BEAR_CASE_SYSTEM
    section_name = "Bull Thesis" if is_bull else "Bear Thesis"

    stock_info = context.stock_info
    sentiment_context = (
        f"\n\nNEWS SENTIMENT:\n{context.sentiment_report[:SENTIMENT_LIMIT]}"
        if context.sentiment_report else ""
    )

    price = f"${stock_info.current_price:.2f}" if stock_info.current_price else "N/A"
    mcap = f"${stock_info.market_cap/1e9:.1f}B" if stock_info.market_cap else "N/A"
    pe = f"{stock_info.pe_ratio:.1f}" if stock_info.pe_ratio else "N/A"

    counter_label = "bear" if is_bull else "bull"
    counter = (
        f"\n\nAddress the {counter_label} argument: {context.counter_argument[:COUNTER_ARGUMENT_LIMIT]}"
        if context.counter_argument else ""
    )

    technicals_section = (
        f"\n\nTechnical Analysis:\n{context.technicals_analysis[:TECHNICALS_CONTEXT_LIMIT]}"
        if context.technicals_analysis else ""
    )
    strategy_section = (
        f"\n\nStrategy Analysis:\n{context.strategy_analysis[:STRATEGY_CONTEXT_LIMIT]}"
        if context.strategy_analysis else ""
    )
    moat_section = (
        f"\n\nMoat Analysis:\n{context.moat_analysis[:MOAT_CONTEXT_LIMIT]}"
        if context.moat_analysis else ""
    )

    closing_question = (
        "Based on ALL the above analyses, what arguments would bulls make for this investment?"
        if is_bull else
        "Based on ALL the above analyses (especially weaknesses and threats from Strategy analysis, moat vulnerabilities), what arguments would bears/short-sellers make?"
    )

    user_prompt = f"""Compile the {direction} case for {stock_info.symbol}:

Company: {stock_info.name}
Sector: {stock_info.sector}
Price: {price}
Market Cap: {mcap}
P/E: {pe}

Fundamentals Analysis:
{context.fundamentals_analysis[:FUNDAMENTALS_CONTEXT_LIMIT]}{technicals_section}{strategy_section}{moat_section}{sentiment_context}{counter}

{closing_question}"""

    response = call_llm(context.api_key, context.model, system_prompt, user_prompt, temperature=0.3)

    return AnalysisResult(
        section=section_name,
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
        cost_usd=response.cost_usd,
    )


def generate_bull_thesis(context: AnalysisContext) -> AnalysisResult:
    """Generate bullish investment thesis with full context."""
    return _generate_thesis(context, "bull")


def generate_bear_thesis(context: AnalysisContext) -> AnalysisResult:
    """Generate bearish investment thesis with full context."""
    return _generate_thesis(context, "bear")


def analyze_moat(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    sentiment_report: str = "",
) -> AnalysisResult:
    """Warren Buffett-style economic moat analysis with news context."""
    sentiment_context = f"\n\nNEWS CONTEXT:\n{sentiment_report[:NEWS_CONTEXT_LIMIT]}" if sentiment_report else ""

    mcap = f"${stock_info.market_cap/1e9:.1f}B" if stock_info.market_cap else "N/A"
    margin = f"{stock_info.profit_margin*100:.1f}%" if stock_info.profit_margin else "N/A"
    roe = f"{stock_info.roe*100:.1f}%" if stock_info.roe else "N/A"
    business = stock_info.business_summary[:MOAT_SUMMARY_LIMIT] if stock_info.business_summary else "N/A"

    user_prompt = f"""Analyze the economic moat for {stock_info.symbol}:

Company: {stock_info.name}
Sector: {stock_info.sector}
Industry: {stock_info.industry}

Business: {business}

Financials:
- Market Cap: {mcap}
- Profit Margin: {margin}
- ROE: {roe}{sentiment_context}

Evaluate the competitive position."""

    response = call_llm(api_key, model, MOAT_SYSTEM, user_prompt)

    return AnalysisResult(
        section="Economic Moat",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
        cost_usd=response.cost_usd,
    )


def analyze_strategy(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    fundamentals_analysis: str,
    sentiment_report: str = "",
) -> AnalysisResult:
    """Strategic analysis (SWOT + Future Outlook) with news sentiment context."""
    sentiment_context = f"\n\nNEWS SENTIMENT:\n{sentiment_report[:SENTIMENT_LIMIT]}" if sentiment_report else ""

    mcap = f"${stock_info.market_cap/1e9:.1f}B" if stock_info.market_cap else "N/A"
    margin = f"{stock_info.profit_margin*100:.1f}%" if stock_info.profit_margin else "N/A"
    growth = f"{stock_info.revenue_growth*100:.1f}%" if stock_info.revenue_growth else "N/A"
    business = stock_info.business_summary[:NEWS_CONTEXT_LIMIT] if stock_info.business_summary else "N/A"

    user_prompt = f"""Compile a strategic analysis for {stock_info.symbol}:

Company: {stock_info.name}
Sector: {stock_info.sector}
Industry: {stock_info.industry}

Business: {business}

Key Financials:
- Market Cap: {mcap}
- Profit Margin: {margin}
- Revenue Growth: {growth}

Fundamentals Summary:
{fundamentals_analysis[:STRATEGY_FUNDAMENTALS_LIMIT]}{sentiment_context}

Organize findings into SWOT framework with Future Outlook."""

    response = call_llm(api_key, model, STRATEGY_SYSTEM, user_prompt)

    return AnalysisResult(
        section="Strategy",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
        cost_usd=response.cost_usd,
    )


# Legacy alias for backwards compatibility
analyze_swot = analyze_strategy


def synthesize_recommendation(context: AnalysisContext) -> AnalysisResult:
    """
    Synthesize all analysis into research summary.

    Args:
        context: AnalysisContext containing all analysis data including
                 bull/bear theses for final synthesis.

    Returns:
        AnalysisResult with research summary.
    """
    sentiment_section = (
        f"\n\nNEWS SENTIMENT:\n{context.sentiment_report[:RECOMMENDATION_SENTIMENT_LIMIT]}"
        if context.sentiment_report else ""
    )
    strategy_section = (
        f"\n\nSTRATEGY ANALYSIS:\n{context.strategy_analysis[:RECOMMENDATION_STRATEGY_LIMIT]}"
        if context.strategy_analysis else ""
    )

    user_prompt = f"""Synthesize the research for {context.stock_info.symbol}:

FUNDAMENTALS:
{context.fundamentals_analysis[:RECOMMENDATION_FUNDAMENTALS_LIMIT]}

TECHNICALS:
{context.technicals_analysis[:RECOMMENDATION_TECHNICALS_LIMIT]}

BULL CASE:
{context.bull_thesis[:RECOMMENDATION_BULL_BEAR_LIMIT]}

BEAR CASE:
{context.bear_thesis[:RECOMMENDATION_BULL_BEAR_LIMIT]}

MOAT ANALYSIS:
{context.moat_analysis[:RECOMMENDATION_MOAT_LIMIT]}{strategy_section}{sentiment_section}

Provide a research summary for the analyst."""

    response = call_llm(context.api_key, context.model, SYNTHESIS_SYSTEM, user_prompt)

    return AnalysisResult(
        section="Research Summary",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
        cost_usd=response.cost_usd,
    )


def generate_full_report(
    context: AnalysisContext,
    sources: List[SourceLink] = None,
    analyst_notes: list = None,
    analyst_citations: str = "",
) -> AnalysisResult:
    """
    Generate synthesized narrative full report incorporating all analyses.

    This creates a flowing 1000-1500 word narrative that reads like a
    professional research note, not a collection of bullet points.

    Args:
        context: AnalysisContext with all analysis data.
        sources: List of SourceLink instances for citations.
        analyst_notes: List of analyst belief dicts.
        analyst_citations: Pre-formatted [A1], [A2] analyst belief citations.

    Returns:
        AnalysisResult with full narrative report.
    """
    # Build analyst notes section if available
    notes_section = ""
    if analyst_notes:
        notes_section = "\n\nANALYST PERSPECTIVE (these are the analyst's confirmed judgments - weave them naturally throughout as the guiding thesis):\n"
        for note in analyst_notes:
            content = note.get('content', '') if isinstance(note, dict) else str(note)
            notes_section += f"- {content}\n"

    # Build sources list for citations
    sources_section = ""
    if sources:
        sources_section = "\n\nAVAILABLE SOURCES (use [N] for inline citations):\n"
        for i, src in enumerate(sources, 1):
            sources_section += f"[{i}] {src.title} ({src.source_type})\n"

    # Add analyst citations section if available
    analyst_section = ""
    if analyst_citations:
        analyst_section = analyst_citations

    # Build comprehensive context for the LLM
    symbol = context.stock_info.symbol
    user_prompt = f"""Create a comprehensive investment thesis narrative for {symbol}:

FUNDAMENTALS ANALYSIS:
{context.fundamentals_analysis[:FULL_REPORT_FUNDAMENTALS_LIMIT]}

TECHNICAL ANALYSIS:
{context.technicals_analysis[:FULL_REPORT_TECHNICALS_LIMIT]}

BULL CASE:
{context.bull_thesis[:FULL_REPORT_THESIS_LIMIT]}

BEAR CASE:
{context.bear_thesis[:FULL_REPORT_THESIS_LIMIT]}

MOAT ANALYSIS:
{context.moat_analysis[:FULL_REPORT_MOAT_LIMIT]}

STRATEGY ANALYSIS:
{context.strategy_analysis[:FULL_REPORT_STRATEGY_LIMIT] if context.strategy_analysis else 'Not available'}

NEWS SENTIMENT:
{context.sentiment_report[:FULL_REPORT_SENTIMENT_LIMIT] if context.sentiment_report else 'Not available'}{notes_section}{sources_section}{analyst_section}

Write the complete investment narrative report (1000-1500 words). Include inline citations [1], [2], etc. when referencing specific facts from research sources, and [A1], [A2], etc. when referencing analyst beliefs:"""

    response = call_llm(context.api_key, context.model, FULL_REPORT_SYSTEM, user_prompt, max_tokens=3000, temperature=0.4)

    return AnalysisResult(
        section="Full Report",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
        cost_usd=response.cost_usd,
    )
