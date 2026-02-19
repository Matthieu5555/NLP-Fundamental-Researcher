"""
Main orchestrator for running strategic analysis.
Coordinates all analysis functions in a pipeline.
News sentiment is fetched and passed to ALL agents as context.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable
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
from .data_fetchers.gemini_search import (
    GeminiSearchResults,
    search_with_gemini,
    format_search_report,
)
from .analysis.shared.parsing import extract_json_from_llm_response
from .analysis_agents import (
    AnalysisResult,
    AnalysisContext,
    analyze_fundamentals,
    analyze_technicals,
    generate_bull_thesis,
    generate_bear_thesis,
    analyze_moat,
    analyze_strategy,
    synthesize_recommendation,
    identify_research_topics,
)
from .llm import call_llm
from .prompts import SOURCE_RELEVANCE_SYSTEM
import logging

logger = logging.getLogger(__name__)


def filter_relevant_sources(sources: list, symbol: str, company_name: str, api_key: str = None, model: str = None) -> tuple[list, float]:
    """
    Use LLM as a judge to filter sources for relevance to the target company.
    Falls back to basic filtering if LLM call fails.

    Returns:
        tuple: (filtered_sources, cost_usd)
    """
    if not sources or not company_name:
        return sources, 0.0

    # If no API key provided, use basic string matching as fallback
    if not api_key or not model:
        return _basic_filter(sources, symbol, company_name), 0.0

    # Build prompt for LLM judge
    sources_text = ""
    for i, src in enumerate(sources):
        title = src.get('title', 'Unknown')
        snippet = src.get('snippet', '')
        sources_text += f"[{i}] {title}\n"
        if snippet:
            sources_text += f"    {snippet[:200]}\n"

    user_prompt = f"""Target company: {company_name} ({symbol})

Sources to evaluate:
{sources_text}

Return ONLY the JSON array of relevant source indices (e.g., [0, 1, 3]):"""

    try:
        response = call_llm(
            api_key=api_key,
            model=model,
            system_prompt=SOURCE_RELEVANCE_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=100,
        )

        cost = response.cost_usd if response.success else 0.0

        if response.success:
            # Parse the JSON array from response (handles markdown code blocks)
            relevant_indices = extract_json_from_llm_response(response.content)

            if isinstance(relevant_indices, list):
                filtered = [sources[i] for i in relevant_indices if 0 <= i < len(sources)]
                if filtered:
                    logger.info(f"LLM filtered sources: kept {len(filtered)}/{len(sources)}")
                    return filtered, cost

        # Fallback to basic filter if LLM fails or returns empty
        logger.warning("LLM source filter failed or returned empty, using basic filter")
        return _basic_filter(sources, symbol, company_name), cost

    except Exception as e:
        logger.warning(f"LLM source filter error: {e}, using basic filter")
        return _basic_filter(sources, symbol, company_name), 0.0


def _basic_filter(sources: list, symbol: str, company_name: str) -> list:
    """Basic string-matching filter as fallback."""
    symbol_lower = symbol.lower()
    name_lower = company_name.lower()
    name_first_word = name_lower.split()[0] if name_lower else ""

    filtered = []
    for src in sources:
        text = f"{src.get('title', '')} {src.get('snippet', '')}".lower()
        if symbol_lower in text or name_lower in text or (name_first_word and name_first_word in text):
            filtered.append(src)

    return filtered if filtered else sources


@dataclass
class FetchedData:
    """Container for all fetched data sources (Non-US workflow)."""
    stock_info: Optional[StockInfo] = None
    technicals: Optional[TechnicalIndicators] = None
    news_sentiment: Optional[NewsSentiment] = None
    web_research: Optional[GeminiSearchResults] = None
    sentiment_report: str = ""
    errors: List[str] = field(default_factory=list)
    sources: List[Any] = field(default_factory=list)
    total_cost_usd: float = 0.0


@dataclass
class AnalysisResults:
    """Container for all analysis agent outputs."""
    fundamentals: Optional[AnalysisResult] = None
    technicals: Optional[AnalysisResult] = None
    strategy: Optional[AnalysisResult] = None
    moat: Optional[AnalysisResult] = None
    bull_thesis: Optional[AnalysisResult] = None
    bear_thesis: Optional[AnalysisResult] = None
    recommendation: Optional[AnalysisResult] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0


@dataclass(frozen=True)
class FullAnalysis:
    """Complete analysis result container (Non-US workflow)."""
    symbol: str
    timestamp: str
    stock_info: Optional[StockInfo]
    technicals: Optional[TechnicalIndicators]
    news_sentiment: Optional[NewsSentiment]
    web_search: Optional[GeminiSearchResults]
    sentiment_report: str
    fundamentals_analysis: Optional[AnalysisResult]
    technical_analysis: Optional[AnalysisResult]
    bull_thesis: Optional[AnalysisResult]
    bear_thesis: Optional[AnalysisResult]
    moat_analysis: Optional[AnalysisResult]
    strategy_analysis: Optional[AnalysisResult]
    recommendation: Optional[AnalysisResult]
    total_tokens: int
    total_cost_usd: float
    success: bool
    errors: list[str]
    sources_collected: list = None  # List of source dicts: {title, url, source_type, date}


def _fetch_all_data_sources(
    symbol: str,
    config: Config,
    progress_callback: Optional[Callable] = None,
) -> FetchedData:
    """
    Fetch all external data sources for analysis.

    Returns FetchedData container with stock info, technicals, news,
    reddit, web search, and SEC filing data.
    """
    def report_progress(message: str, step: int = None):
        if progress_callback:
            progress_callback(message, step)

    fetched = FetchedData()

    # Fetch stock data (no API cost)
    report_progress("Fetching stock data...", 1)
    stock_info, stock_error = fetch_stock_info(symbol)
    if stock_error:
        fetched.errors.append(f"Stock data: {stock_error}")
    fetched.stock_info = stock_info

    company_name = stock_info.name if stock_info else ""

    # Collect Yahoo Finance as source
    if stock_info:
        fetched.sources.append({
            "title": f"Yahoo Finance - {stock_info.name or symbol}",
            "url": f"https://finance.yahoo.com/quote/{symbol}",
            "source_type": "api",
            "date": datetime.now().strftime("%Y-%m-%d"),
        })

    # Fetch technicals (no API cost)
    technicals, tech_error = calculate_technical_indicators(symbol)
    if tech_error:
        fetched.errors.append(f"Technicals: {tech_error}")
    fetched.technicals = technicals

    # Fetch news sentiment (uses EODHD/Alpha Vantage)
    report_progress("Fetching news sentiment...", 2)
    news_sentiment, news_error = fetch_combined_news(
        symbol,
        alpha_vantage_key=config.alpha_vantage_key or "",
        eodhd_key=config.eodhd_key or "",
        limit=10,
        company_name=company_name,
    )
    if news_error:
        fetched.errors.append(f"News: {news_error}")
    fetched.news_sentiment = news_sentiment

    if news_sentiment:
        fetched.sentiment_report = format_sentiment_report(news_sentiment)
        for i, article in enumerate(news_sentiment.articles[:5], 1):
            fetched.sources.append({
                "title": article.title[:100] if article.title else f"News Article {i}",
                "url": article.url,
                "source_type": "news",
                "date": article.published,
            })

    # Fetch breaking news via Gemini Search Grounding (Round 1)
    report_progress("Searching web for breaking news...", 4)
    if config.google_api_key and stock_info:
        logger.info(f"Round 1 Gemini search: {symbol} ({stock_info.name})")
        web_search, search_error = search_with_gemini(
            symbol,
            stock_info.name or symbol,
            config.google_api_key,
            max_results=5,
        )
        if search_error:
            logger.warning(f"Round 1 Gemini search error: {search_error}")
            fetched.errors.append(f"Web search: {search_error}")
        if web_search:
            logger.info(f"Round 1 Gemini search: {len(web_search.results)} results")
            fetched.web_research = web_search
            fetched.total_cost_usd += web_search.cost_usd
            search_report = format_search_report(web_search)
            fetched.sentiment_report = (
                fetched.sentiment_report + "\n\n" + search_report
                if fetched.sentiment_report else search_report
            )
            if hasattr(web_search, 'grounding_chunks') and web_search.grounding_chunks:
                for chunk in web_search.grounding_chunks:
                    fetched.sources.append({
                        "title": chunk.get('title', 'Web Search Result'),
                        "url": chunk.get('uri', chunk.get('url', '')),
                        "source_type": "search",
                        "date": "recent",
                    })

    # Follow-up research based on initial findings (Round 2)
    if fetched.sentiment_report and config.google_api_key and stock_info:
        report_progress("Identifying follow-up research topics...", 5)
        logger.info("Round 2: Identifying follow-up research topics...")
        try:
            followup_topics = identify_research_topics(
                api_key=config.openrouter_api_key,
                company_name=stock_info.name or symbol,
                sector=stock_info.sector or "Unknown",
                initial_research=fetched.sentiment_report,
            )
            logger.info(f"Round 2: Identified {len(followup_topics) if followup_topics else 0} topics: {followup_topics}")
            if followup_topics:
                report_progress(f"Researching {len(followup_topics)} additional topics...", 5)
                for topic in followup_topics[:4]:
                    topic_results, topic_error = search_with_gemini(
                        symbol=symbol,
                        company_name=topic,
                        api_key=config.google_api_key,
                        max_results=3,
                    )
                    if topic_results and not topic_error:
                        fetched.total_cost_usd += topic_results.cost_usd
                        topic_report = format_search_report(topic_results)
                        fetched.sentiment_report += f"\n\n## Follow-up Research: {topic}\n{topic_report}"
                        logger.info(f"Added follow-up research: {topic[:50]}...")
                        if hasattr(topic_results, 'grounding_chunks') and topic_results.grounding_chunks:
                            for chunk in topic_results.grounding_chunks[:2]:
                                fetched.sources.append({
                                    "title": chunk.get('title', f'Research: {topic[:30]}'),
                                    "url": chunk.get('uri', chunk.get('url', '')),
                                    "source_type": "research",
                                    "date": "recent",
                                })
        except Exception as e:
            logger.warning(f"Follow-up research failed: {e}")
            fetched.errors.append(f"Follow-up research: {str(e)}")

    return fetched


def _run_individual_analyses(
    stock_info: StockInfo,
    technicals: Optional[TechnicalIndicators],
    sentiment_report: str,
    config: Config,
    include_moat: bool,
    include_strategy: bool,
    progress_callback: Optional[Callable] = None,
) -> AnalysisResults:
    """
    Run fundamentals, technicals, Strategy, and moat analyses.

    Returns AnalysisResults container with individual analysis outputs.
    """
    def report_progress(message: str, step: int = None):
        if progress_callback:
            progress_callback(message, step)

    results = AnalysisResults()
    api_key = config.openrouter_api_key
    model = config.openrouter_model

    # Fundamentals analysis
    report_progress("Running Fundamentals Agent...", 6)
    fundamentals_result = analyze_fundamentals(api_key, model, stock_info, sentiment_report)
    results.fundamentals = fundamentals_result
    results.total_tokens += fundamentals_result.tokens_used
    results.total_cost_usd += fundamentals_result.cost_usd

    # Technical analysis
    report_progress("Running Technical Analysis Agent...", 7)
    if technicals:
        technical_result = analyze_technicals(api_key, model, stock_info.symbol, technicals, sentiment_report)
        results.technicals = technical_result
        results.total_tokens += technical_result.tokens_used
        results.total_cost_usd += technical_result.cost_usd

    # Strategy analysis
    report_progress("Running Strategy Analysis Agent...", 8)
    if include_strategy and fundamentals_result.success:
        strategy_result = analyze_strategy(api_key, model, stock_info, fundamentals_result.content, sentiment_report)
        results.strategy = strategy_result
        results.total_tokens += strategy_result.tokens_used
        results.total_cost_usd += strategy_result.cost_usd

    # Moat analysis
    report_progress("Running Moat Analysis Agent...", 9)
    if include_moat:
        moat_result = analyze_moat(api_key, model, stock_info, sentiment_report)
        results.moat = moat_result
        results.total_tokens += moat_result.tokens_used
        results.total_cost_usd += moat_result.cost_usd

    return results


def _run_bull_bear_debate(
    stock_info: StockInfo,
    individual_results: AnalysisResults,
    sentiment_report: str,
    config: Config,
    progress_callback: Optional[Callable] = None,
) -> tuple[Optional[AnalysisResult], Optional[AnalysisResult], int, float]:
    """
    Run bull/bear debate with 2 rounds.

    Returns (bull_result, bear_result, tokens_used, cost_usd).
    """
    def report_progress(message: str, step: int = None):
        if progress_callback:
            progress_callback(message, step)

    api_key = config.openrouter_api_key
    model = config.openrouter_model
    total_tokens = 0
    total_cost = 0.0

    # Get content from individual analyses
    fundamentals_content = individual_results.fundamentals.content if individual_results.fundamentals else ""
    technicals_content = individual_results.technicals.content if individual_results.technicals and individual_results.technicals.success else ""
    strategy_content = individual_results.strategy.content if individual_results.strategy and individual_results.strategy.success else ""
    moat_content = individual_results.moat.content if individual_results.moat and individual_results.moat.success else ""

    # Build base context
    base_context = AnalysisContext(
        api_key=api_key,
        model=model,
        stock_info=stock_info,
        fundamentals_analysis=fundamentals_content,
        technicals_analysis=technicals_content,
        strategy_analysis=strategy_content,
        moat_analysis=moat_content,
        sentiment_report=sentiment_report,
        counter_argument="",
    )

    # Round 1: Initial arguments
    report_progress("Running Bull Case Agent (Round 1)...", 10)
    bull_result = generate_bull_thesis(base_context)
    total_tokens += bull_result.tokens_used
    total_cost += bull_result.cost_usd

    bear_context_r1 = AnalysisContext(
        api_key=api_key,
        model=model,
        stock_info=stock_info,
        fundamentals_analysis=fundamentals_content,
        technicals_analysis=technicals_content,
        strategy_analysis=strategy_content,
        moat_analysis=moat_content,
        sentiment_report=sentiment_report,
        counter_argument=bull_result.content if bull_result.success else "",
    )

    report_progress("Running Bear Case Agent (Round 1)...", 11)
    bear_result = generate_bear_thesis(bear_context_r1)
    total_tokens += bear_result.tokens_used
    total_cost += bear_result.cost_usd

    # Round 2: Cross-rebuttals
    if bull_result.success and bear_result.success:
        bull_context_r2 = AnalysisContext(
            api_key=api_key,
            model=model,
            stock_info=stock_info,
            fundamentals_analysis=fundamentals_content,
            technicals_analysis=technicals_content,
            strategy_analysis=strategy_content,
            moat_analysis=moat_content,
            sentiment_report=sentiment_report,
            counter_argument=bear_result.content,
        )

        report_progress("Running Bull Case Agent (Round 2 - Rebuttal)...", 12)
        bull_result_r2 = generate_bull_thesis(bull_context_r2)
        total_tokens += bull_result_r2.tokens_used
        total_cost += bull_result_r2.cost_usd

        bear_context_r2 = AnalysisContext(
            api_key=api_key,
            model=model,
            stock_info=stock_info,
            fundamentals_analysis=fundamentals_content,
            technicals_analysis=technicals_content,
            strategy_analysis=strategy_content,
            moat_analysis=moat_content,
            sentiment_report=sentiment_report,
            counter_argument=bull_result_r2.content if bull_result_r2.success else bull_result.content,
        )

        report_progress("Running Bear Case Agent (Round 2 - Rebuttal)...", 13)
        bear_result_r2 = generate_bear_thesis(bear_context_r2)
        total_tokens += bear_result_r2.tokens_used
        total_cost += bear_result_r2.cost_usd

        # Use Round 2 results
        if bull_result_r2.success:
            bull_result = bull_result_r2
        if bear_result_r2.success:
            bear_result = bear_result_r2

    return bull_result, bear_result, total_tokens, total_cost


def _create_error_result(symbol: str, errors: list, fetched: FetchedData = None) -> FullAnalysis:
    """Create a FullAnalysis result for error cases."""
    return FullAnalysis(
        symbol=symbol,
        timestamp=datetime.now().isoformat(),
        stock_info=fetched.stock_info if fetched else None,
        technicals=fetched.technicals if fetched else None,
        news_sentiment=fetched.news_sentiment if fetched else None,
        web_search=fetched.web_research if fetched else None,
        sentiment_report=fetched.sentiment_report if fetched else "",
        fundamentals_analysis=None,
        technical_analysis=None,
        bull_thesis=None,
        bear_thesis=None,
        moat_analysis=None,
        strategy_analysis=None,
        recommendation=None,
        total_tokens=0,
        total_cost_usd=fetched.total_cost_usd if fetched else 0.0,
        success=False,
        errors=errors,
        sources_collected=fetched.sources if fetched else [],
    )


def run_analysis(
    symbol: str,
    config: Optional[Config] = None,
    include_debate: bool = True,
    include_moat: bool = True,
    include_strategy: bool = True,
    debate_rounds: int = 1,
    progress_callback=None,
) -> FullAnalysis:
    """
    Run complete strategic analysis for a stock.

    Pipeline:
    1. Validate config and setup
    2. Fetch all external data sources
    3. Run individual analyses (fundamentals, technicals, Strategy, moat)
    4. Run bull/bear debate (if enabled)
    5. Synthesize recommendation
    6. Filter and return results

    Args:
        symbol: Stock ticker symbol
        config: Optional Config object (loads from env if None)
        include_debate: Run bull/bear thesis debate
        include_moat: Run moat analysis
        include_strategy: Run Strategy analysis
        debate_rounds: Number of debate rounds (unused, always 2)
        progress_callback: Optional callable(message, step) for progress updates

    Returns:
        FullAnalysis with all results
    """
    # Step 1: Validate config
    if config is None:
        config = load_config()

    is_valid, validation_errors = validate_config(config)
    if not is_valid:
        return _create_error_result(symbol, validation_errors)

    ensure_directories(config)

    # Step 2: Fetch all external data sources
    fetched = _fetch_all_data_sources(symbol, config, progress_callback)

    # Early exit if no stock data
    if fetched.stock_info is None:
        return _create_error_result(symbol, fetched.errors, fetched)

    # Step 3: Run individual analyses
    individual_results = _run_individual_analyses(
        fetched.stock_info,
        fetched.technicals,
        fetched.sentiment_report,
        config,
        include_moat,
        include_strategy,
        progress_callback,
    )

    # Collect errors from individual analyses
    errors = list(fetched.errors)
    if individual_results.fundamentals and not individual_results.fundamentals.success:
        errors.append(f"Fundamentals: {individual_results.fundamentals.error}")
    if individual_results.technicals and not individual_results.technicals.success:
        errors.append(f"Technical: {individual_results.technicals.error}")
    if individual_results.strategy and not individual_results.strategy.success:
        errors.append(f"Strategy: {individual_results.strategy.error}")
    if individual_results.moat and not individual_results.moat.success:
        errors.append(f"Moat: {individual_results.moat.error}")

    # Step 4: Run bull/bear debate (if enabled)
    bull_result = None
    bear_result = None
    debate_tokens = 0
    debate_cost = 0.0

    if include_debate and individual_results.fundamentals and individual_results.fundamentals.success:
        bull_result, bear_result, debate_tokens, debate_cost = _run_bull_bear_debate(
            fetched.stock_info,
            individual_results,
            fetched.sentiment_report,
            config,
            progress_callback,
        )

    # Step 5: Synthesize recommendation
    def report_progress(message: str, step: int = None):
        if progress_callback:
            progress_callback(message, step)

    report_progress("Running Recommendation Synthesis...", 14)
    recommendation_result = None
    recommendation_tokens = 0
    recommendation_cost = 0.0

    if individual_results.fundamentals and individual_results.fundamentals.success:
        synthesis_context = AnalysisContext(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=fetched.stock_info,
            fundamentals_analysis=individual_results.fundamentals.content,
            technicals_analysis=individual_results.technicals.content if individual_results.technicals and individual_results.technicals.success else "Not available",
            strategy_analysis=individual_results.strategy.content if individual_results.strategy and individual_results.strategy.success else "",
            moat_analysis=individual_results.moat.content if individual_results.moat and individual_results.moat.success else "Not available",
            sentiment_report=fetched.sentiment_report,
            bull_thesis=bull_result.content if bull_result and bull_result.success else "Not available",
            bear_thesis=bear_result.content if bear_result and bear_result.success else "Not available",
        )
        recommendation_result = synthesize_recommendation(synthesis_context)
        recommendation_tokens = recommendation_result.tokens_used
        recommendation_cost = recommendation_result.cost_usd

    # Step 6: Filter sources and build final result
    company_name = fetched.stock_info.name if fetched.stock_info else ""
    sources_collected, filter_cost = filter_relevant_sources(
        fetched.sources, symbol, company_name,
        config.openrouter_api_key, config.openrouter_model
    )

    # Calculate totals
    total_tokens = (
        individual_results.total_tokens +
        debate_tokens +
        recommendation_tokens
    )
    total_cost = (
        fetched.total_cost_usd +
        individual_results.total_cost_usd +
        debate_cost +
        recommendation_cost +
        filter_cost
    )

    return FullAnalysis(
        symbol=symbol,
        timestamp=datetime.now().isoformat(),
        stock_info=fetched.stock_info,
        technicals=fetched.technicals,
        news_sentiment=fetched.news_sentiment,
        web_search=fetched.web_research,
        sentiment_report=fetched.sentiment_report,
        fundamentals_analysis=individual_results.fundamentals,
        technical_analysis=individual_results.technicals,
        bull_thesis=bull_result,
        bear_thesis=bear_result,
        moat_analysis=individual_results.moat,
        strategy_analysis=individual_results.strategy,
        recommendation=recommendation_result,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
        success=len(errors) == 0 or (individual_results.fundamentals and individual_results.fundamentals.success),
        errors=errors,
        sources_collected=sources_collected,
    )


def run_quick_analysis(
    symbol: str,
    config: Optional[Config] = None,
) -> FullAnalysis:
    """
    Run quick analysis (fundamentals only, no debate/moat/strategy).
    Minimal API usage.
    """
    return run_analysis(
        symbol=symbol,
        config=config,
        include_debate=False,
        include_moat=False,
        include_strategy=False,
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

    if analysis.strategy_analysis and analysis.strategy_analysis.success:
        lines.extend([
            "",
            "STRATEGY ANALYSIS AGENT",
            "-" * 40,
            analysis.strategy_analysis.content,
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
        f"Estimated cost: ${analysis.total_cost_usd:.4f}",
    ])

    if analysis.errors:
        lines.append("\nWarnings:")
        for error in analysis.errors:
            lines.append(f"  - {error}")

    return "\n".join(lines)
