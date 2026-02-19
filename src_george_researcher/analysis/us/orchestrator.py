"""
US Company Analysis Orchestrator.

Uses FinancialDatasets.ai for comprehensive data, with two-round fundamentals
analysis for deeper insights. No rate limiting bottlenecks.

Data Sources (all FDS):
- Company Facts (FREE)
- Financials ($0.02) - 5 years with YoY/QoQ computed
- Prices ($0.01) - for technicals
- News ($0.02) - with sentiment scores
- Insider Trades ($0.02) - management signals
- Analyst Estimates ($0.02) - consensus forecasts
- Gemini Search (~$0.17) - web research

Total FDS cost: ~$0.11 per analysis
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any, Callable

from src_george_researcher.config import Config, load_config, validate_config
from src_george_researcher.data_fetchers.us.financial_datasets_client import (
    get_fds_client,
    CompanyFacts,
    FinancialStatement,
    PriceData,
    InsiderTrade,
    AnalystEstimate,
    NewsArticle,
)
from src_george_researcher.data_fetchers.gemini_search import (
    search_with_gemini,
    format_search_report,
)
from src_george_researcher.data_fetchers.stock_data import (
    StockInfo,
    TechnicalIndicators,
    calculate_technical_indicators,
)
from src_george_researcher.analysis.shared.cost_tracking import CostBreakdown
from src_george_researcher.analysis.shared.growth_metrics import (
    compute_growth_metrics,
    EnrichedFinancials,
)
from src_george_researcher.analysis_agents import (
    AnalysisResult,
    AnalysisContext,
    analyze_technicals,
    generate_bull_thesis,
    generate_bear_thesis,
    analyze_moat,
    analyze_strategy,
    synthesize_recommendation,
    identify_research_topics,
)
from src_george_researcher.llm import call_llm

logger = logging.getLogger(__name__)


# =============================================================================
# US-specific Prompts (use centralized NARRATIVE_STYLE)
# =============================================================================

from src_george_researcher.prompts import NARRATIVE_STYLE, NARRATIVE_STYLE_SHORT

FUNDAMENTALS_UNIFIED_SYSTEM = f"""{NARRATIVE_STYLE}

You are a senior equity research analyst writing a comprehensive fundamental analysis for a portfolio manager. This should read as ONE unified chapter, not separate sections pasted together.

Your analysis should WEAVE together:
- Financial statement data (revenue, margins, cash flow, balance sheet)
- Insider trading activity (what management is doing with their own money)
- Analyst expectations (how the Street views this company)

Structure your unified analysis with these sections (use **bold headers**):

**The Financial Picture**
Open with 2-3 paragraphs telling the complete financial story. Start with revenue trajectory and growth story. Transition to profitability (margins - are they expanding or compressing?). Then discuss cash flow quality - is the company generating real cash or accounting profits? Close this section by addressing balance sheet strength. Use transitions to connect these ideas into a flowing narrative. Cite specific numbers but always explain what they MEAN.

**What Management Is Telling Us**
Write 1-2 paragraphs weaving together insider trading patterns with analyst expectations. What are insiders doing with their own money, and what does this signal about their confidence? How do analyst estimates compare to actual performance - is the company beating or missing expectations? Are there disconnects between what management sees and what the Street expects? Connect these qualitative signals to the financial picture you painted above.

**Investment Implications**
Close with a paragraph synthesizing the key investment factors. What are the 3-5 most important questions or metrics investors should monitor? What would confirm or challenge the investment case? Be direct about implications - don't hedge unnecessarily.

This should read as ONE continuous analysis. Use strong transitions throughout. Target length: 600-800 words.

Begin with The Financial Picture:"""

INSIDER_ANALYSIS_SYSTEM = f"""{NARRATIVE_STYLE_SHORT}

You are a senior equity research analyst writing about insider trading patterns.

Structure your analysis with these sections (use **bold headers**):

**The Insider Picture**
Write a paragraph summarizing the overall pattern of insider activity. Is there net buying or selling? What does this tell us about management's confidence? Are executives putting their own money where their mouth is, or are they quietly reducing exposure?

**Notable Transactions**
Write a paragraph highlighting the most significant individual trades. Focus on C-suite executives (CEO, CFO) over directors. Mention specific dollar amounts and the context around timing. Were trades clustered around any particular events or announcements?

**Investment Signal**
Close with a sentence or two interpreting what this insider activity means for the investment case. Be direct: is this a bullish, bearish, or neutral signal?

If the data is limited or uninformative, say so directly rather than speculating. Target length: 150-250 words.

Begin with The Insider Picture:"""


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class USFetchedData:
    """Container for all US company data from FDS."""
    company_facts: Optional[CompanyFacts] = None
    financials: Optional[List[FinancialStatement]] = None
    enriched_financials: Optional[EnrichedFinancials] = None
    prices: Optional[List[PriceData]] = None
    technicals: Optional[TechnicalIndicators] = None
    insider_trades: Optional[List[InsiderTrade]] = None
    analyst_estimates: Optional[List[AnalystEstimate]] = None
    news: Optional[List[NewsArticle]] = None
    web_research: Optional[Any] = None
    sentiment_report: str = ""
    errors: List[str] = field(default_factory=list)
    sources: List[dict] = field(default_factory=list)
    cost: CostBreakdown = field(default_factory=CostBreakdown)


@dataclass
class USAnalysisResults:
    """Container for US analysis agent outputs."""
    fundamentals_quant: Optional[AnalysisResult] = None
    fundamentals_synthesis: Optional[AnalysisResult] = None
    insider_analysis: Optional[AnalysisResult] = None
    technicals: Optional[AnalysisResult] = None
    strategy: Optional[AnalysisResult] = None
    moat: Optional[AnalysisResult] = None
    bull_thesis: Optional[AnalysisResult] = None
    bear_thesis: Optional[AnalysisResult] = None
    recommendation: Optional[AnalysisResult] = None


@dataclass(frozen=True)
class USFullAnalysis:
    """Complete US analysis result."""
    symbol: str
    timestamp: str
    company_facts: Optional[CompanyFacts]
    enriched_financials: Optional[EnrichedFinancials]
    technicals: Optional[TechnicalIndicators]
    insider_trades: Optional[List[InsiderTrade]]
    analyst_estimates: Optional[List[AnalystEstimate]]
    news: Optional[List[NewsArticle]]
    web_research: Optional[Any]
    sentiment_report: str

    # Analysis results
    fundamentals_analysis: Optional[AnalysisResult]  # Combined quant + synthesis
    insider_analysis: Optional[AnalysisResult]
    technical_analysis: Optional[AnalysisResult]
    bull_thesis: Optional[AnalysisResult]
    bear_thesis: Optional[AnalysisResult]
    moat_analysis: Optional[AnalysisResult]
    strategy_analysis: Optional[AnalysisResult]
    recommendation: Optional[AnalysisResult]

    # Metadata
    total_tokens: int
    total_cost_usd: float
    cost_breakdown: CostBreakdown
    success: bool
    errors: List[str]
    sources_collected: List[dict]


# =============================================================================
# Data Fetching
# =============================================================================

def _fetch_all_data_us(
    symbol: str,
    config: Config,
    progress_callback: Optional[Callable] = None,
) -> USFetchedData:
    """
    Fetch all data for a US company using FinancialDatasets.ai.

    No rate limiting concerns - FDS allows 1000 req/min.
    """
    def report_progress(message: str, step: int = None):
        if progress_callback:
            progress_callback(message, step)

    fetched = USFetchedData()
    fetched.cost.set_model(config.openrouter_model)  # Set display name
    fds = get_fds_client()

    if not fds.is_available:
        fetched.errors.append("FDS API key not configured")
        return fetched

    # Step 1: Company Facts (FREE)
    report_progress("Fetching company facts...", 1)
    company_facts, error = fds.get_company_facts(symbol)
    if error:
        fetched.errors.append(f"Company facts: {error}")
    else:
        fetched.company_facts = company_facts
        fetched.cost.add_fds_cost("company_facts")
        fetched.sources.append({
            "title": f"FinancialDatasets.ai - {company_facts.name}",
            "url": f"https://financialdatasets.ai/company/{symbol}",
            "source_type": "api",
            "date": datetime.now().strftime("%Y-%m-%d"),
        })

    company_name = company_facts.name if company_facts else symbol

    # Step 2: Financial Statements ($0.02)
    report_progress("Fetching financial statements...", 2)
    financials, error = fds.get_financials(symbol, period="annual", limit=5)
    if error:
        fetched.errors.append(f"Financials: {error}")
    else:
        fetched.financials = financials
        fetched.cost.add_fds_cost("financials")
        # Compute YoY/QoQ metrics
        fetched.enriched_financials = compute_growth_metrics(
            financials, symbol, company_name
        )

    # Step 3: Prices for Technicals ($0.01)
    report_progress("Fetching price history...", 3)
    prices, error = fds.get_prices(symbol, limit=365)
    if error:
        fetched.errors.append(f"Prices: {error}")
    else:
        fetched.prices = prices
        fetched.cost.add_fds_cost("prices")
        # Calculate technicals from FDS prices
        fetched.technicals = _calculate_technicals_from_fds(prices)

    # Fallback: If FDS prices failed or returned insufficient data, use yfinance
    if fetched.technicals is None:
        logger.info(f"FDS prices unavailable or insufficient for {symbol}, falling back to yfinance")
        yf_technicals, yf_error = calculate_technical_indicators(symbol, period="1y")
        if yf_technicals:
            fetched.technicals = yf_technicals
            logger.info(f"Successfully calculated technicals from yfinance for {symbol}")
        elif yf_error:
            logger.warning(f"yfinance fallback also failed for {symbol}: {yf_error}")

    # Step 4: Insider Trades ($0.02)
    report_progress("Fetching insider trades...", 4)
    insider_trades, error = fds.get_insider_trades(symbol, limit=50)
    if error:
        fetched.errors.append(f"Insider trades: {error}")
    else:
        fetched.insider_trades = insider_trades
        fetched.cost.add_fds_cost("insider_trades")

    # Step 5: Analyst Estimates ($0.02)
    report_progress("Fetching analyst estimates...", 5)
    estimates, error = fds.get_analyst_estimates(symbol, limit=8)
    if error:
        fetched.errors.append(f"Analyst estimates: {error}")
    else:
        fetched.analyst_estimates = estimates
        fetched.cost.add_fds_cost("analyst_estimates")

    # Step 6: FDS News ($0.02)
    report_progress("Fetching company news...", 6)
    news, error = fds.get_news(symbol, limit=10)
    if error:
        fetched.errors.append(f"News: {error}")
    else:
        fetched.news = news
        fetched.cost.add_fds_cost("news")
        fetched.sentiment_report = _format_fds_news(news)
        for article in news[:5]:
            # Handle both object (from API) and dict (from cache) formats
            if isinstance(article, dict):
                title = article.get("title", "")[:100]
                url = article.get("url", "")
                date = article.get("published_at", "")
            else:
                title = article.title[:100]
                url = article.url
                date = article.published_at
            fetched.sources.append({
                "title": title,
                "url": url,
                "source_type": "news",
                "date": date,
            })

    # Step 7: Gemini Search - Web Research (Round 1)
    report_progress("Searching web for recent developments...", 7)
    if config.google_api_key:
        web_search, search_error = search_with_gemini(
            symbol,
            company_name,
            config.google_api_key,
            max_results=5,
        )
        if search_error:
            fetched.errors.append(f"Web search: {search_error}")
        if web_search:
            fetched.web_research = web_search
            fetched.cost.add_gemini_cost(web_search.cost_usd)
            search_report = format_search_report(web_search)
            fetched.sentiment_report += f"\n\n## Web Research\n{search_report}"

            if hasattr(web_search, 'grounding_chunks') and web_search.grounding_chunks:
                for chunk in web_search.grounding_chunks:
                    fetched.sources.append({
                        "title": chunk.get('title', 'Web Search Result'),
                        "url": chunk.get('uri', chunk.get('url', '')),
                        "source_type": "search",
                        "date": "recent",
                    })

    # Step 8: Follow-up Research (Round 2)
    if fetched.sentiment_report and config.google_api_key:
        report_progress("Researching follow-up topics...", 8)
        try:
            followup_topics = identify_research_topics(
                api_key=config.openrouter_api_key,
                company_name=company_name,
                sector=company_facts.sector if company_facts else "Unknown",
                initial_research=fetched.sentiment_report,
            )
            if followup_topics:
                for topic in followup_topics[:3]:  # Max 3 follow-ups
                    topic_results, _ = search_with_gemini(
                        symbol=symbol,
                        company_name=topic,
                        api_key=config.google_api_key,
                        max_results=3,
                    )
                    if topic_results:
                        fetched.cost.add_gemini_cost(topic_results.cost_usd)
                        topic_report = format_search_report(topic_results)
                        fetched.sentiment_report += f"\n\n## Follow-up: {topic}\n{topic_report}"
        except Exception as e:
            logger.warning(f"Follow-up research failed: {e}")

    return fetched


def _calculate_technicals_from_fds(prices: List[PriceData]) -> Optional[TechnicalIndicators]:
    """Calculate technical indicators from FDS price data."""
    if not prices or len(prices) < 20:
        return None

    # Sort by date ascending for calculations
    sorted_prices = sorted(prices, key=lambda x: x.date)
    closes = [p.close for p in sorted_prices]

    # Current price
    current_price = closes[-1]

    # Moving averages
    sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
    sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    sma_200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None

    # RSI (14-day)
    rsi = _calculate_rsi(closes, 14) if len(closes) >= 15 else None

    # MACD
    macd, signal, histogram = _calculate_macd(closes)

    # 52-week high/low
    year_prices = closes[-252:] if len(closes) >= 252 else closes
    high_52w = max(year_prices)
    low_52w = min(year_prices)

    # Volume (average)
    volumes = [p.volume for p in sorted_prices[-20:]]
    avg_volume = sum(volumes) / len(volumes) if volumes else 0

    return TechnicalIndicators(
        symbol=prices[0].ticker if prices else "",
        current_price=current_price,
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=sma_200,
        rsi_14=rsi,
        macd=macd,
        macd_signal=signal,
        macd_histogram=histogram,
        high_52w=high_52w,
        low_52w=low_52w,
        avg_volume_20d=int(avg_volume),
        price_change_1d=((closes[-1] / closes[-2]) - 1) * 100 if len(closes) >= 2 else None,
        price_change_1w=((closes[-1] / closes[-5]) - 1) * 100 if len(closes) >= 5 else None,
        price_change_1m=((closes[-1] / closes[-21]) - 1) * 100 if len(closes) >= 21 else None,
        price_change_3m=((closes[-1] / closes[-63]) - 1) * 100 if len(closes) >= 63 else None,
        price_change_ytd=None,  # Would need year start date
    )


def _calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Calculate RSI."""
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _calculate_macd(closes: List[float]) -> tuple:
    """Calculate MACD, Signal, and Histogram."""
    if len(closes) < 26:
        return None, None, None

    def ema(data, period):
        multiplier = 2 / (period + 1)
        ema_val = sum(data[:period]) / period
        for price in data[period:]:
            ema_val = (price - ema_val) * multiplier + ema_val
        return ema_val

    ema_12 = ema(closes, 12)
    ema_26 = ema(closes, 26)
    macd = ema_12 - ema_26

    # Signal line (9-day EMA of MACD) - simplified
    signal = macd * 0.9  # Approximation

    histogram = macd - signal

    return macd, signal, histogram


def _get_article_attr(article, attr: str, default=""):
    """Get attribute from article (handles both dict and object formats)."""
    if isinstance(article, dict):
        return article.get(attr, default)
    return getattr(article, attr, default)


def _format_fds_news(news: List[NewsArticle]) -> str:
    """Format FDS news for sentiment report."""
    if not news:
        return ""

    lines = ["## Recent News (FinancialDatasets.ai)", ""]

    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    for article in news:
        sentiment = _get_article_attr(article, "sentiment")
        if sentiment:
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

    total = sum(sentiment_counts.values())
    if total > 0:
        lines.append(f"**Sentiment Distribution**: "
                    f"{sentiment_counts.get('positive', 0)} positive, "
                    f"{sentiment_counts.get('negative', 0)} negative, "
                    f"{sentiment_counts.get('neutral', 0)} neutral")
        lines.append("")

    for article in news[:7]:
        sentiment = _get_article_attr(article, "sentiment")
        title = _get_article_attr(article, "title", "Untitled")
        summary = _get_article_attr(article, "summary")
        source = _get_article_attr(article, "source", "Unknown")
        published_at = _get_article_attr(article, "published_at", "")

        sentiment_badge = ""
        if sentiment == "positive":
            sentiment_badge = "[+] "
        elif sentiment == "negative":
            sentiment_badge = "[-] "

        lines.append(f"- {sentiment_badge}**{title}**")
        if summary:
            lines.append(f"  {summary[:200]}...")
        lines.append(f"  *{source} - {published_at}*")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Analysis Agents
# =============================================================================

def _analyze_fundamentals_us(
    enriched: EnrichedFinancials,
    insider_trades: List[InsiderTrade],
    analyst_estimates: List[AnalystEstimate],
    config: Config,
    progress_callback: Optional[Callable] = None,
) -> tuple[AnalysisResult, AnalysisResult, CostBreakdown]:
    """
    Two-round fundamentals analysis for US companies.

    Round 1: Quantitative analysis of financials with YoY/QoQ
    Round 2: Synthesis with insider activity and analyst estimates
    """
    def report_progress(message: str, step: int = None):
        if progress_callback:
            progress_callback(message, step)

    cost = CostBreakdown()
    cost.set_model(config.openrouter_model)  # Set display name
    api_key = config.openrouter_api_key
    model = config.openrouter_model

    # Unified Fundamentals Analysis - ONE comprehensive analysis
    report_progress("Running Fundamentals Agent...", 9)

    # Build comprehensive prompt with all data
    unified_prompt = f"""## Financial Statement Data (5-Year History)
{enriched.format_for_agent() if enriched else "No financial data available."}

## Insider Trading Activity (Last 6 Months)
{_format_insider_trades(insider_trades)}

## Analyst Consensus Estimates
{_format_analyst_estimates(analyst_estimates)}

Analyze all of this data and write a unified fundamental analysis."""

    unified_response = call_llm(
        api_key=api_key,
        model=model,
        system_prompt=FUNDAMENTALS_UNIFIED_SYSTEM,
        user_prompt=unified_prompt,
    )
    cost.add_llm_cost(unified_response.cost_usd)

    unified_result = AnalysisResult(
        section="Fundamentals",
        content=unified_response.content if unified_response.success else f"Error: {unified_response.error}",
        tokens_used=unified_response.tokens_used,
        success=unified_response.success,
        error=unified_response.error,
        cost_usd=unified_response.cost_usd,
    )

    # Return single result (keeping return signature for compatibility but with empty second result)
    empty_result = AnalysisResult(
        section="",
        content="",
        tokens_used=0,
        success=True,
        error=None,
        cost_usd=0.0,
    )

    return unified_result, empty_result, cost


def _format_insider_trades(trades: List[InsiderTrade]) -> str:
    """Format insider trades for LLM consumption."""
    if not trades:
        return "No insider trading data available."

    lines = []

    # Summary stats
    buys = [t for t in trades if t.transaction_type.lower() in ("buy", "purchase", "p")]
    sells = [t for t in trades if t.transaction_type.lower() in ("sell", "sale", "s")]

    buy_value = sum(t.total_value or 0 for t in buys)
    sell_value = sum(t.total_value or 0 for t in sells)

    lines.append(f"**Summary**: {len(buys)} buys (${buy_value:,.0f}), {len(sells)} sells (${sell_value:,.0f})")

    if buy_value > sell_value * 1.5:
        lines.append("**Signal**: Net BUYING - Management showing confidence")
    elif sell_value > buy_value * 1.5:
        lines.append("**Signal**: Net SELLING - Management reducing exposure")
    else:
        lines.append("**Signal**: Mixed activity")

    lines.append("")
    lines.append("**Recent Transactions:**")

    for trade in trades[:10]:
        value_str = f"${trade.total_value:,.0f}" if trade.total_value else f"{trade.shares:,.0f} shares"
        lines.append(f"- {trade.filing_date}: {trade.insider_name} ({trade.insider_title or 'Insider'}) "
                    f"{trade.transaction_type.upper()} {value_str}")

    return "\n".join(lines)


def _format_analyst_estimates(estimates: List[AnalystEstimate]) -> str:
    """Format analyst estimates for LLM consumption."""
    if not estimates:
        return "No analyst estimates available."

    lines = []

    # Group by fiscal year
    by_year = {}
    for est in estimates:
        year = est.fiscal_year
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(est)

    for year in sorted(by_year.keys(), reverse=True)[:3]:
        year_ests = by_year[year]
        annual = [e for e in year_ests if e.fiscal_quarter is None]

        if annual:
            est = annual[0]
            lines.append(f"**FY{year} Consensus:**")
            if est.eps_estimate_avg is not None:
                eps_line = f"  - EPS: ${est.eps_estimate_avg:.2f}"
                if est.eps_estimate_low is not None and est.eps_estimate_high is not None:
                    eps_line += f" (range: ${est.eps_estimate_low:.2f} - ${est.eps_estimate_high:.2f})"
                lines.append(eps_line)
            if est.revenue_estimate_avg is not None:
                rev_b = est.revenue_estimate_avg / 1e9
                lines.append(f"  - Revenue: ${rev_b:.1f}B")
            if est.eps_estimate_count:
                lines.append(f"  - Analyst coverage: {est.eps_estimate_count} analysts")
            lines.append("")

    return "\n".join(lines) if lines else "No analyst estimates available."


def _analyze_insider_signals(
    insider_trades: List[InsiderTrade],
    config: Config,
) -> AnalysisResult:
    """Analyze insider trading for investment signals."""
    if not insider_trades:
        return AnalysisResult(
            section="Insider Activity",
            content="No insider trading data available for analysis.",
            tokens_used=0,
            success=True,
            cost_usd=0.0,
        )

    prompt = _format_insider_trades(insider_trades)

    response = call_llm(
        api_key=config.openrouter_api_key,
        model=config.openrouter_model,
        system_prompt=INSIDER_ANALYSIS_SYSTEM,
        user_prompt=prompt,
    )

    return AnalysisResult(
        section="Insider Activity",
        content=response.content if response.success else f"Error: {response.error}",
        tokens_used=response.tokens_used,
        success=response.success,
        error=response.error,
        cost_usd=response.cost_usd,
    )


# =============================================================================
# Main Orchestrator
# =============================================================================

def run_us_analysis(
    symbol: str,
    config: Optional[Config] = None,
    progress_callback: Optional[Callable] = None,
) -> USFullAnalysis:
    """
    Run complete US company analysis using FinancialDatasets.ai.

    Pipeline:
    1. Fetch all FDS data (company facts, financials, prices, insider, estimates, news)
    2. Compute YoY/QoQ metrics on financials
    3. Fetch web research via Gemini (2 rounds)
    4. Run two-round fundamentals agent
    5. Run insider analysis agent
    6. Run technical, SWOT, moat agents
    7. Run bull/bear debate (2 rounds each)
    8. Synthesize recommendation

    Returns USFullAnalysis with CostBreakdown for frontend display.
    """
    def report_progress(message: str, step: int = None):
        if progress_callback:
            progress_callback(message, step)

    # Step 1: Validate config
    if config is None:
        config = load_config()

    is_valid, validation_errors = validate_config(config)
    if not is_valid:
        return _create_error_result(symbol, validation_errors, CostBreakdown())

    # Step 2: Fetch all data
    fetched = _fetch_all_data_us(symbol, config, progress_callback)
    total_cost = fetched.cost

    if not fetched.company_facts:
        return _create_error_result(symbol, fetched.errors, total_cost)

    # Build StockInfo for compatibility with existing agents
    stock_info = _build_stock_info_from_fds(fetched)

    # Step 3: Unified Fundamentals Analysis (includes insider and estimates data)
    fundamentals_result, _, fund_cost = _analyze_fundamentals_us(
        fetched.enriched_financials,
        fetched.insider_trades or [],
        fetched.analyst_estimates or [],
        config,
        progress_callback,
    )
    total_cost = total_cost.merge(fund_cost)

    # Use the unified fundamentals result directly
    combined_fundamentals = fundamentals_result

    # Step 4: Insider Analysis
    report_progress("Analyzing insider activity...", 11)
    insider_result = _analyze_insider_signals(fetched.insider_trades or [], config)
    total_cost.add_llm_cost(insider_result.cost_usd)

    # Step 5: Technical Analysis
    report_progress("Running Technical Analysis Agent...", 12)
    technical_result = None
    if fetched.technicals:
        technical_result = analyze_technicals(
            config.openrouter_api_key,
            config.openrouter_model,
            symbol,
            fetched.technicals,
            fetched.sentiment_report,
        )
        total_cost.add_llm_cost(technical_result.cost_usd)
    else:
        # Create a placeholder result explaining why technicals aren't available
        logger.warning(f"No technical indicators available for {symbol} - price data may be missing or insufficient")
        technical_result = AnalysisResult(
            section="Technical Analysis",
            content="**Technical Analysis Unavailable**\n\nSufficient price history data was not available to calculate technical indicators. This may occur for newly listed companies or when the data source experiences issues.",
            tokens_used=0,
            success=True,
            error=None,
            cost_usd=0.0,
        )

    # Step 6: Strategy Analysis
    report_progress("Running Strategy Analysis Agent...", 13)
    strategy_result = analyze_strategy(
        config.openrouter_api_key,
        config.openrouter_model,
        stock_info,
        combined_fundamentals.content,
        fetched.sentiment_report,
    )
    total_cost.add_llm_cost(strategy_result.cost_usd)

    # Step 7: Moat Analysis
    report_progress("Running Moat Analysis Agent...", 14)
    moat_result = analyze_moat(
        config.openrouter_api_key,
        config.openrouter_model,
        stock_info,
        fetched.sentiment_report,
    )
    total_cost.add_llm_cost(moat_result.cost_usd)

    # Step 8: Bull/Bear Debate (2 rounds)
    report_progress("Running Bull Case Agent (Round 1)...", 15)

    base_context = AnalysisContext(
        api_key=config.openrouter_api_key,
        model=config.openrouter_model,
        stock_info=stock_info,
        fundamentals_analysis=combined_fundamentals.content,
        technicals_analysis=technical_result.content if technical_result else "",
        strategy_analysis=strategy_result.content if strategy_result.success else "",
        moat_analysis=moat_result.content if moat_result.success else "",
        sentiment_report=fetched.sentiment_report,
        counter_argument="",
    )

    bull_result = generate_bull_thesis(base_context)
    total_cost.add_llm_cost(bull_result.cost_usd)

    report_progress("Running Bear Case Agent (Round 1)...", 16)
    bear_context = AnalysisContext(
        api_key=config.openrouter_api_key,
        model=config.openrouter_model,
        stock_info=stock_info,
        fundamentals_analysis=combined_fundamentals.content,
        technicals_analysis=technical_result.content if technical_result else "",
        strategy_analysis=strategy_result.content if strategy_result.success else "",
        moat_analysis=moat_result.content if moat_result.success else "",
        sentiment_report=fetched.sentiment_report,
        counter_argument=bull_result.content if bull_result.success else "",
    )
    bear_result = generate_bear_thesis(bear_context)
    total_cost.add_llm_cost(bear_result.cost_usd)

    # Round 2 rebuttals
    if bull_result.success and bear_result.success:
        report_progress("Running Bull Case Agent (Round 2)...", 17)
        bull_context_r2 = AnalysisContext(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=stock_info,
            fundamentals_analysis=combined_fundamentals.content,
            technicals_analysis=technical_result.content if technical_result else "",
            strategy_analysis=strategy_result.content if strategy_result.success else "",
            moat_analysis=moat_result.content if moat_result.success else "",
            sentiment_report=fetched.sentiment_report,
            counter_argument=bear_result.content,
        )
        bull_result_r2 = generate_bull_thesis(bull_context_r2)
        total_cost.add_llm_cost(bull_result_r2.cost_usd)
        if bull_result_r2.success:
            bull_result = bull_result_r2

        report_progress("Running Bear Case Agent (Round 2)...", 18)
        bear_context_r2 = AnalysisContext(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=stock_info,
            fundamentals_analysis=combined_fundamentals.content,
            technicals_analysis=technical_result.content if technical_result else "",
            strategy_analysis=strategy_result.content if strategy_result.success else "",
            moat_analysis=moat_result.content if moat_result.success else "",
            sentiment_report=fetched.sentiment_report,
            counter_argument=bull_result.content,
        )
        bear_result_r2 = generate_bear_thesis(bear_context_r2)
        total_cost.add_llm_cost(bear_result_r2.cost_usd)
        if bear_result_r2.success:
            bear_result = bear_result_r2

    # Step 9: Recommendation Synthesis
    report_progress("Synthesizing final recommendation...", 19)
    synthesis_context = AnalysisContext(
        api_key=config.openrouter_api_key,
        model=config.openrouter_model,
        stock_info=stock_info,
        fundamentals_analysis=combined_fundamentals.content,
        technicals_analysis=technical_result.content if technical_result else "Not available",
        strategy_analysis=strategy_result.content if strategy_result.success else "",
        moat_analysis=moat_result.content if moat_result.success else "Not available",
        sentiment_report=fetched.sentiment_report,
        bull_thesis=bull_result.content if bull_result.success else "Not available",
        bear_thesis=bear_result.content if bear_result.success else "Not available",
    )
    recommendation_result = synthesize_recommendation(synthesis_context)
    total_cost.add_llm_cost(recommendation_result.cost_usd)

    # Build final result
    total_tokens = (
        (insider_result.tokens_used if insider_result else 0) +
        (technical_result.tokens_used if technical_result else 0) +
        (strategy_result.tokens_used if strategy_result else 0) +
        (moat_result.tokens_used if moat_result else 0) +
        (bull_result.tokens_used if bull_result else 0) +
        (bear_result.tokens_used if bear_result else 0) +
        (recommendation_result.tokens_used if recommendation_result else 0)
    )

    return USFullAnalysis(
        symbol=symbol,
        timestamp=datetime.now().isoformat(),
        company_facts=fetched.company_facts,
        enriched_financials=fetched.enriched_financials,
        technicals=fetched.technicals,
        insider_trades=fetched.insider_trades,
        analyst_estimates=fetched.analyst_estimates,
        news=fetched.news,
        web_research=fetched.web_research,
        sentiment_report=fetched.sentiment_report,
        fundamentals_analysis=combined_fundamentals,
        insider_analysis=insider_result,
        technical_analysis=technical_result,
        bull_thesis=bull_result,
        bear_thesis=bear_result,
        moat_analysis=moat_result,
        strategy_analysis=strategy_result,
        recommendation=recommendation_result,
        total_tokens=total_tokens,
        total_cost_usd=total_cost.total,
        cost_breakdown=total_cost,
        success=combined_fundamentals.success,
        errors=fetched.errors,
        sources_collected=fetched.sources,
    )


def _build_stock_info_from_fds(fetched: USFetchedData) -> StockInfo:
    """Build StockInfo from FDS data for compatibility with existing agents."""
    facts = fetched.company_facts
    technicals = fetched.technicals

    # Get latest financials for ratios
    latest = None
    if fetched.enriched_financials and fetched.enriched_financials.periods:
        latest = fetched.enriched_financials.periods[0]

    current_price = technicals.current_price if technicals else None
    eps = latest.eps.current_value if latest and latest.eps else None

    return StockInfo(
        symbol=facts.ticker if facts else "",
        name=facts.name if facts else "",
        sector=facts.sector if facts else None,
        industry=facts.industry if facts else None,
        country="United States",
        exchange=facts.exchange if facts else None,
        currency="USD",
        market_cap=facts.market_cap if facts else None,
        enterprise_value=None,
        pe_ratio=(current_price / eps) if current_price and eps and eps > 0 else None,
        forward_pe=None,
        peg_ratio=None,
        pb_ratio=None,
        ps_ratio=None,
        dividend_yield=None,
        profit_margin=latest.net_margin.current_value if latest and latest.net_margin else None,
        operating_margin=latest.operating_margin.current_value if latest and latest.operating_margin else None,
        gross_margin=latest.gross_margin.current_value if latest and latest.gross_margin else None,
        roe=None,
        roa=None,
        debt_to_equity=latest.debt_to_equity.current_value if latest and latest.debt_to_equity else None,
        current_ratio=None,
        quick_ratio=None,
        revenue=latest.revenue.current_value if latest and latest.revenue else None,
        revenue_growth=latest.revenue.yoy_change if latest and latest.revenue else None,
        earnings_growth=latest.net_income.yoy_change if latest and latest.net_income else None,
        free_cash_flow=latest.free_cash_flow.current_value if latest and latest.free_cash_flow else None,
        beta=None,
        high_52w=technicals.high_52w if technicals else None,
        low_52w=technicals.low_52w if technicals else None,
        avg_volume=technicals.avg_volume_20d if technicals else None,
        shares_outstanding=None,
        float_shares=None,
        held_by_institutions=None,
        held_by_insiders=None,
        short_ratio=None,
        short_percent=None,
        target_price=None,
        analyst_rating=None,
        num_analysts=None,
        business_summary=facts.description if facts else None,
        website=facts.website_url if facts else None,
        employees=facts.number_of_employees if facts else None,
    )


def _create_error_result(symbol: str, errors: List[str], cost: CostBreakdown) -> USFullAnalysis:
    """Create error result for failed analysis."""
    return USFullAnalysis(
        symbol=symbol,
        timestamp=datetime.now().isoformat(),
        company_facts=None,
        enriched_financials=None,
        technicals=None,
        insider_trades=None,
        analyst_estimates=None,
        news=None,
        web_research=None,
        sentiment_report="",
        fundamentals_analysis=None,
        insider_analysis=None,
        technical_analysis=None,
        bull_thesis=None,
        bear_thesis=None,
        moat_analysis=None,
        strategy_analysis=None,
        recommendation=None,
        total_tokens=0,
        total_cost_usd=cost.total,
        cost_breakdown=cost,
        success=False,
        errors=errors,
        sources_collected=[],
    )
