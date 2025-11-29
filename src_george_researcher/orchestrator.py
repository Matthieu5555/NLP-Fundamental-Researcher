"""
Main orchestrator for running strategic analysis.
Coordinates all analysis functions in a pipeline.
News sentiment is fetched and passed to ALL agents as context.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from .config import Config, load_config, validate_config, ensure_directories
from .data_fetchers.stock_data import (
    StockInfo,
    TechnicalIndicators,
    fetch_stock_info,
    calculate_technical_indicators,
)
from .data_fetchers.news import (
    NewsSentiment,
    fetch_combined_news,
    format_sentiment_report,
)
from .data_fetchers.reddit import (
    RedditSentiment,
    fetch_reddit_sentiment,
    format_reddit_report,
)
from .data_fetchers.web_search import (
    WebSearchResults,
    search_breaking_news,
    format_search_report,
)
from .data_fetchers.sec_filings import (
    SECFilingData,
    fetch_sec_filing,
    search_sec_filing,
    format_sec_context,
)
from .analysis import (
    AnalysisResult,
    analyze_fundamentals,
    analyze_technicals,
    generate_bull_thesis,
    generate_bear_thesis,
    analyze_moat,
    analyze_swot,
    synthesize_recommendation,
)


@dataclass(frozen=True)
class FullAnalysis:
    """Complete analysis result container."""
    symbol: str
    timestamp: str
    stock_info: Optional[StockInfo]
    technicals: Optional[TechnicalIndicators]
    news_sentiment: Optional[NewsSentiment]
    reddit_sentiment: Optional[RedditSentiment]
    web_search: Optional[WebSearchResults]
    sec_filing: Optional[SECFilingData]
    sentiment_report: str
    fundamentals_analysis: Optional[AnalysisResult]
    technical_analysis: Optional[AnalysisResult]
    bull_thesis: Optional[AnalysisResult]
    bear_thesis: Optional[AnalysisResult]
    moat_analysis: Optional[AnalysisResult]
    swot_analysis: Optional[AnalysisResult]
    recommendation: Optional[AnalysisResult]
    total_tokens: int
    success: bool
    errors: list[str]


def run_analysis(
    symbol: str,
    config: Optional[Config] = None,
    include_debate: bool = True,
    include_moat: bool = True,
    include_swot: bool = True,
    debate_rounds: int = 1,
) -> FullAnalysis:
    """
    Run complete strategic analysis for a stock.
    News sentiment is fetched first and passed to all agents.
    """
    if config is None:
        config = load_config()

    is_valid, validation_errors = validate_config(config)
    if not is_valid:
        return FullAnalysis(
            symbol=symbol,
            timestamp=datetime.now().isoformat(),
            stock_info=None,
            technicals=None,
            news_sentiment=None,
            reddit_sentiment=None,
            web_search=None,
            sec_filing=None,
            sentiment_report="",
            fundamentals_analysis=None,
            technical_analysis=None,
            bull_thesis=None,
            bear_thesis=None,
            moat_analysis=None,
            swot_analysis=None,
            recommendation=None,
            total_tokens=0,
            success=False,
            errors=validation_errors,
        )

    ensure_directories(config)
    errors = []
    total_tokens = 0

    # Fetch stock data (no API cost)
    stock_info, stock_error = fetch_stock_info(symbol)
    if stock_error:
        errors.append(f"Stock data: {stock_error}")

    # Get company name for better search results
    company_name = stock_info.name if stock_info else ""

    # Fetch technicals (no API cost)
    technicals, tech_error = calculate_technical_indicators(symbol)
    if tech_error:
        errors.append(f"Technicals: {tech_error}")

    # Fetch news sentiment (uses EODHD/Alpha Vantage)
    news_sentiment, news_error = fetch_combined_news(
        symbol,
        alpha_vantage_key=config.alpha_vantage_key or "",
        eodhd_key=config.eodhd_key or "",
        limit=10,
        company_name=company_name,
    )
    sentiment_report = ""
    if news_error:
        errors.append(f"News: {news_error}")
    if news_sentiment:
        sentiment_report = format_sentiment_report(news_sentiment)

    # Fetch Reddit sentiment (free, no API key)
    reddit_sentiment, reddit_error = fetch_reddit_sentiment(symbol, limit=10, company_name=company_name)
    if reddit_error:
        errors.append(f"Reddit: {reddit_error}")
    if reddit_sentiment:
        reddit_report = format_reddit_report(reddit_sentiment)
        sentiment_report = sentiment_report + "\n\n" + reddit_report if sentiment_report else reddit_report

    # Fetch breaking news via web search (Tavily)
    web_search = None
    if config.tavily_key and stock_info:
        web_search, search_error = search_breaking_news(
            symbol,
            stock_info.name or symbol,
            config.tavily_key,
            max_results=5,
        )
        if search_error:
            errors.append(f"Web search: {search_error}")
        if web_search:
            search_report = format_search_report(web_search)
            sentiment_report = sentiment_report + "\n\n" + search_report if sentiment_report else search_report

    # Fetch SEC 10-K filing (optional, can be slow)
    sec_filing = None
    try:
        sec_filing, sec_error = fetch_sec_filing(symbol, config.data_dir)
        if sec_error:
            errors.append(f"SEC filing: {sec_error}")
    except Exception as e:
        errors.append(f"SEC filing: {str(e)}")

    # If no stock data, return early
    if stock_info is None:
        return FullAnalysis(
            symbol=symbol,
            timestamp=datetime.now().isoformat(),
            stock_info=None,
            technicals=technicals,
            news_sentiment=news_sentiment,
            reddit_sentiment=reddit_sentiment,
            web_search=web_search,
            sec_filing=sec_filing,
            sentiment_report=sentiment_report,
            fundamentals_analysis=None,
            technical_analysis=None,
            bull_thesis=None,
            bear_thesis=None,
            moat_analysis=None,
            swot_analysis=None,
            recommendation=None,
            total_tokens=0,
            success=False,
            errors=errors,
        )

    # LLM Analysis - all agents receive sentiment_report as context
    api_key = config.openrouter_api_key
    model = config.openrouter_model

    # Fundamentals analysis (with sentiment context)
    fundamentals_result = analyze_fundamentals(api_key, model, stock_info, sentiment_report)
    total_tokens += fundamentals_result.tokens_used
    if not fundamentals_result.success:
        errors.append(f"Fundamentals: {fundamentals_result.error}")

    # Technical analysis (with sentiment context)
    technical_result = None
    if technicals:
        technical_result = analyze_technicals(api_key, model, symbol, technicals, sentiment_report)
        total_tokens += technical_result.tokens_used
        if not technical_result.success:
            errors.append(f"Technical: {technical_result.error}")

    # Bull/Bear debate (sentiment is critical here)
    bull_result = None
    bear_result = None
    if include_debate and fundamentals_result.success:
        bull_counter = ""
        bear_counter = ""

        for _ in range(debate_rounds):
            bull_result = generate_bull_thesis(
                api_key, model, stock_info, fundamentals_result.content,
                sentiment_report, bear_counter
            )
            total_tokens += bull_result.tokens_used

            bear_result = generate_bear_thesis(
                api_key, model, stock_info, fundamentals_result.content,
                sentiment_report, bull_result.content if bull_result.success else ""
            )
            total_tokens += bear_result.tokens_used

            bear_counter = bear_result.content if bear_result.success else ""

    # Moat analysis (with sentiment context)
    moat_result = None
    if include_moat:
        moat_result = analyze_moat(api_key, model, stock_info, sentiment_report)
        total_tokens += moat_result.tokens_used
        if not moat_result.success:
            errors.append(f"Moat: {moat_result.error}")

    # SWOT analysis (with sentiment context)
    swot_result = None
    if include_swot and fundamentals_result.success:
        swot_result = analyze_swot(api_key, model, stock_info, fundamentals_result.content, sentiment_report)
        total_tokens += swot_result.tokens_used
        if not swot_result.success:
            errors.append(f"SWOT: {swot_result.error}")

    # Final recommendation (receives all reports including sentiment)
    recommendation_result = None
    if fundamentals_result.success:
        recommendation_result = synthesize_recommendation(
            api_key,
            model,
            symbol,
            fundamentals_result.content,
            technical_result.content if technical_result and technical_result.success else "Not available",
            bull_result.content if bull_result and bull_result.success else "Not available",
            bear_result.content if bear_result and bear_result.success else "Not available",
            moat_result.content if moat_result and moat_result.success else "Not available",
            swot_result.content if swot_result and swot_result.success else "",
            sentiment_report,
        )
        total_tokens += recommendation_result.tokens_used

    return FullAnalysis(
        symbol=symbol,
        timestamp=datetime.now().isoformat(),
        stock_info=stock_info,
        technicals=technicals,
        news_sentiment=news_sentiment,
        reddit_sentiment=reddit_sentiment,
        web_search=web_search,
        sec_filing=sec_filing,
        sentiment_report=sentiment_report,
        fundamentals_analysis=fundamentals_result,
        technical_analysis=technical_result,
        bull_thesis=bull_result,
        bear_thesis=bear_result,
        moat_analysis=moat_result,
        swot_analysis=swot_result,
        recommendation=recommendation_result,
        total_tokens=total_tokens,
        success=len(errors) == 0 or (fundamentals_result and fundamentals_result.success),
        errors=errors,
    )


def run_quick_analysis(
    symbol: str,
    config: Optional[Config] = None,
) -> FullAnalysis:
    """
    Run quick analysis (fundamentals only, no debate/moat/swot).
    Minimal API usage.
    """
    return run_analysis(
        symbol=symbol,
        config=config,
        include_debate=False,
        include_moat=False,
        include_swot=False,
    )


def format_analysis_report(analysis: FullAnalysis) -> str:
    """Format full analysis as a readable report."""
    lines = [
        "=" * 60,
        f"GEORGE'S STRATEGIC ANALYSIS: {analysis.symbol}",
        f"Generated: {analysis.timestamp}",
        "=" * 60,
    ]

    if not analysis.success:
        lines.append("\nAnalysis failed with errors:")
        for error in analysis.errors:
            lines.append(f"  - {error}")
        return "\n".join(lines)

    if analysis.recommendation:
        lines.extend([
            "",
            "GEORGE'S OVERALL RECOMMENDATION",
            "-" * 40,
            analysis.recommendation.content,
        ])

    if analysis.sentiment_report:
        lines.extend([
            "",
            "NEWS SENTIMENT",
            "-" * 40,
            analysis.sentiment_report,
        ])

    if analysis.fundamentals_analysis and analysis.fundamentals_analysis.success:
        lines.extend([
            "",
            "FUNDAMENTAL ANALYSIS AGENT",
            "-" * 40,
            analysis.fundamentals_analysis.content,
        ])

    if analysis.technical_analysis and analysis.technical_analysis.success:
        lines.extend([
            "",
            "TECHNICAL ANALYSIS AGENT",
            "-" * 40,
            analysis.technical_analysis.content,
        ])

    if analysis.moat_analysis and analysis.moat_analysis.success:
        lines.extend([
            "",
            "MOAT ANALYSIS AGENT",
            "-" * 40,
            analysis.moat_analysis.content,
        ])

    if analysis.swot_analysis and analysis.swot_analysis.success:
        lines.extend([
            "",
            "SWOT SPECIALIST AGENT",
            "-" * 40,
            analysis.swot_analysis.content,
        ])

    if analysis.bull_thesis and analysis.bull_thesis.success:
        lines.extend([
            "",
            "BULL CASE AGENT",
            "-" * 40,
            analysis.bull_thesis.content,
        ])

    if analysis.bear_thesis and analysis.bear_thesis.success:
        lines.extend([
            "",
            "BEAR CASE AGENT",
            "-" * 40,
            analysis.bear_thesis.content,
        ])

    lines.extend([
        "",
        "=" * 60,
        f"Total tokens used: {analysis.total_tokens}",
    ])

    if analysis.errors:
        lines.append("\nWarnings:")
        for error in analysis.errors:
            lines.append(f"  - {error}")

    return "\n".join(lines)
