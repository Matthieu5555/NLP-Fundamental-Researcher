"""
Analysis functions for strategic company evaluation.
All agents receive news sentiment as context for informed analysis.
"""
from dataclasses import dataclass
from typing import Optional

from .data_fetchers.stock_data import StockInfo, TechnicalIndicators, format_stock_info
from .llm import call_llm, LLMResponse
from .prompts import (
    FUNDAMENTALS_SYSTEM,
    TECHNICALS_SYSTEM,
    BULL_CASE_SYSTEM,
    BEAR_CASE_SYSTEM,
    MOAT_SYSTEM,
    SWOT_SYSTEM,
    SYNTHESIS_SYSTEM,
)


@dataclass(frozen=True)
class AnalysisResult:
    """Container for analysis results."""
    section: str
    content: str
    tokens_used: int
    success: bool
    error: Optional[str] = None


def analyze_fundamentals(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    sentiment_report: str = "",
) -> AnalysisResult:
    """Analyze company fundamentals with news sentiment context."""
    sentiment_context = f"\n\nNEWS SENTIMENT CONTEXT:\n{sentiment_report[:500]}" if sentiment_report else ""

    user_prompt = f"""Analyze these fundamentals for {stock_info.symbol}:

{format_stock_info(stock_info)}

Business: {stock_info.business_summary[:500] if stock_info.business_summary else 'N/A'}{sentiment_context}"""

    response = call_llm(api_key, model, FUNDAMENTALS_SYSTEM, user_prompt)

    return AnalysisResult(
        section="Fundamentals",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
    )


def analyze_technicals(
    api_key: str,
    model: str,
    symbol: str,
    technicals: TechnicalIndicators,
    sentiment_report: str = "",
) -> AnalysisResult:
    """Analyze technical indicators with news sentiment context."""
    sentiment_context = f"\n\nNEWS SENTIMENT:\n{sentiment_report[:400]}" if sentiment_report else ""

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
    )


def generate_bull_thesis(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    fundamentals_analysis: str,
    sentiment_report: str = "",
    counter_argument: str = "",
) -> AnalysisResult:
    """Generate bullish investment thesis using news sentiment."""
    sentiment_context = f"\n\nNEWS SENTIMENT:\n{sentiment_report[:500]}" if sentiment_report else ""

    price = f"${stock_info.current_price:.2f}" if stock_info.current_price else "N/A"
    mcap = f"${stock_info.market_cap/1e9:.1f}B" if stock_info.market_cap else "N/A"
    pe = f"{stock_info.pe_ratio:.1f}" if stock_info.pe_ratio else "N/A"
    counter = f"\n\nAddress the bear argument: {counter_argument[:500]}" if counter_argument else ""

    user_prompt = f"""Compile the bull case for {stock_info.symbol}:

Company: {stock_info.name}
Sector: {stock_info.sector}
Price: {price}
Market Cap: {mcap}
P/E: {pe}

Fundamentals Analysis:
{fundamentals_analysis[:600]}{sentiment_context}{counter}

What arguments would bulls make?"""

    response = call_llm(api_key, model, BULL_CASE_SYSTEM, user_prompt, temperature=0.3)

    return AnalysisResult(
        section="Bull Thesis",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
    )


def generate_bear_thesis(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    fundamentals_analysis: str,
    sentiment_report: str = "",
    counter_argument: str = "",
) -> AnalysisResult:
    """Generate bearish investment thesis using news sentiment."""
    sentiment_context = f"\n\nNEWS SENTIMENT:\n{sentiment_report[:500]}" if sentiment_report else ""

    price = f"${stock_info.current_price:.2f}" if stock_info.current_price else "N/A"
    mcap = f"${stock_info.market_cap/1e9:.1f}B" if stock_info.market_cap else "N/A"
    pe = f"{stock_info.pe_ratio:.1f}" if stock_info.pe_ratio else "N/A"
    counter = f"\n\nAddress the bull argument: {counter_argument[:500]}" if counter_argument else ""

    user_prompt = f"""Compile the bear case for {stock_info.symbol}:

Company: {stock_info.name}
Sector: {stock_info.sector}
Price: {price}
Market Cap: {mcap}
P/E: {pe}

Fundamentals Analysis:
{fundamentals_analysis[:600]}{sentiment_context}{counter}

What arguments would bears/short-sellers make?"""

    response = call_llm(api_key, model, BEAR_CASE_SYSTEM, user_prompt, temperature=0.3)

    return AnalysisResult(
        section="Bear Thesis",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
    )


def analyze_moat(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    sentiment_report: str = "",
) -> AnalysisResult:
    """Warren Buffett-style economic moat analysis with news context."""
    sentiment_context = f"\n\nNEWS CONTEXT:\n{sentiment_report[:400]}" if sentiment_report else ""

    mcap = f"${stock_info.market_cap/1e9:.1f}B" if stock_info.market_cap else "N/A"
    margin = f"{stock_info.profit_margin*100:.1f}%" if stock_info.profit_margin else "N/A"
    roe = f"{stock_info.roe*100:.1f}%" if stock_info.roe else "N/A"
    business = stock_info.business_summary[:600] if stock_info.business_summary else "N/A"

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
    )


def analyze_swot(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    fundamentals_analysis: str,
    sentiment_report: str = "",
) -> AnalysisResult:
    """SWOT analysis with news sentiment informing Opportunities and Threats."""
    sentiment_context = f"\n\nNEWS SENTIMENT:\n{sentiment_report[:500]}" if sentiment_report else ""

    mcap = f"${stock_info.market_cap/1e9:.1f}B" if stock_info.market_cap else "N/A"
    margin = f"{stock_info.profit_margin*100:.1f}%" if stock_info.profit_margin else "N/A"
    growth = f"{stock_info.revenue_growth*100:.1f}%" if stock_info.revenue_growth else "N/A"
    business = stock_info.business_summary[:400] if stock_info.business_summary else "N/A"

    user_prompt = f"""Compile a SWOT analysis for {stock_info.symbol}:

Company: {stock_info.name}
Sector: {stock_info.sector}
Industry: {stock_info.industry}

Business: {business}

Key Financials:
- Market Cap: {mcap}
- Profit Margin: {margin}
- Revenue Growth: {growth}

Fundamentals Summary:
{fundamentals_analysis[:400]}{sentiment_context}

Organize findings into SWOT framework."""

    response = call_llm(api_key, model, SWOT_SYSTEM, user_prompt)

    return AnalysisResult(
        section="SWOT Analysis",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
    )


def synthesize_recommendation(
    api_key: str,
    model: str,
    symbol: str,
    fundamentals: str,
    technicals: str,
    bull_thesis: str,
    bear_thesis: str,
    moat_analysis: str,
    swot_analysis: str = "",
    sentiment_report: str = "",
) -> AnalysisResult:
    """Synthesize all analysis into research summary (not a recommendation)."""
    sentiment_section = f"\n\nNEWS SENTIMENT:\n{sentiment_report[:400]}" if sentiment_report else ""
    swot_section = f"\n\nSWOT ANALYSIS:\n{swot_analysis[:400]}" if swot_analysis else ""

    user_prompt = f"""Synthesize the research for {symbol}:

FUNDAMENTALS:
{fundamentals[:500]}

TECHNICALS:
{technicals[:300]}

BULL CASE:
{bull_thesis[:400]}

BEAR CASE:
{bear_thesis[:400]}

MOAT ANALYSIS:
{moat_analysis[:300]}{swot_section}{sentiment_section}

Provide a research summary for the analyst."""

    response = call_llm(api_key, model, SYNTHESIS_SYSTEM, user_prompt)

    return AnalysisResult(
        section="Research Summary",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
    )
