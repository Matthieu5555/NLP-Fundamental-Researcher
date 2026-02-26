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
from src_george_researcher.analysis.shared.source_link import SourceLink
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
from src_george_researcher.valuation.dcf_engine import DCFResult
from src_george_researcher.valuation.comp_table import CompTableResult
from src_george_researcher.valuation.conviction import ConvictionResult
from src_george_researcher.valuation.sensitivity import SensitivityResult, GrowthMarginSensitivityResult
from src_george_researcher.valuation.scenarios import ScenarioResult
from src_george_researcher.valuation.precedent_transactions import PrecedentTransactionResult
from src_george_researcher.valuation.football_field import FootballFieldResult
from src_george_researcher.valuation.earnings_model import EarningsModelRow
from src_george_researcher.analysis.strategic_assessment import (
    StrategicAssessment,
    run_strategic_assessment,
)
from src_george_researcher.analysis.pipeline_config import USStep, US_TOTAL_STEPS
from src_george_researcher.data_fetchers.price_resolver import resolve_current_price
from src_george_researcher.data_fetchers.accounting_standard import (
    NormalizationResult,
    detect_and_flag,
)

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
    sources: List[SourceLink] = field(default_factory=list)
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
    strategic_assessment: Optional[StrategicAssessment] = None
    strategic_assessment_analysis: Optional[AnalysisResult] = None
    bull_thesis: Optional[AnalysisResult] = None
    bear_thesis: Optional[AnalysisResult] = None
    recommendation: Optional[AnalysisResult] = None
    # Valuation
    dcf_analysis: Optional[AnalysisResult] = None
    dcf_result: Optional[DCFResult] = None
    comp_analysis: Optional[AnalysisResult] = None
    comp_result: Optional[CompTableResult] = None
    earnings_model: Optional[AnalysisResult] = None
    earnings_rows: Optional[List[EarningsModelRow]] = None
    sensitivity_analysis: Optional[AnalysisResult] = None
    sensitivity_result: Optional[SensitivityResult] = None
    growth_margin_sensitivity: Optional[GrowthMarginSensitivityResult] = None
    scenario_analysis: Optional[AnalysisResult] = None
    scenario_result: Optional[ScenarioResult] = None
    precedent_analysis: Optional[AnalysisResult] = None
    precedent_result: Optional[PrecedentTransactionResult] = None
    football_field_analysis: Optional[AnalysisResult] = None
    football_field_result: Optional[FootballFieldResult] = None
    conviction_analysis: Optional[AnalysisResult] = None
    conviction_result: Optional[ConvictionResult] = None
    # Accounting
    normalization: Optional[NormalizationResult] = None


@dataclass(frozen=True)
class USFullAnalysis:
    """Complete US analysis result."""
    # Required fields (no defaults) — must come first
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
    fundamentals_analysis: Optional[AnalysisResult]  # Combined quant + synthesis
    insider_analysis: Optional[AnalysisResult]
    technical_analysis: Optional[AnalysisResult]
    total_tokens: int
    total_cost_usd: float
    cost_breakdown: CostBreakdown
    success: bool
    errors: List[str]
    sources_collected: List[SourceLink]

    # Optional fields (with defaults)
    strategic_assessment_analysis: Optional[AnalysisResult] = None
    strategic_assessment: Optional[StrategicAssessment] = None
    bull_thesis: Optional[AnalysisResult] = None
    bear_thesis: Optional[AnalysisResult] = None
    moat_analysis: Optional[AnalysisResult] = None
    strategy_analysis: Optional[AnalysisResult] = None
    recommendation: Optional[AnalysisResult] = None
    dcf_analysis: Optional[AnalysisResult] = None
    dcf_result: Optional[DCFResult] = None
    comp_analysis: Optional[AnalysisResult] = None
    comp_result: Optional[CompTableResult] = None
    earnings_model: Optional[AnalysisResult] = None
    earnings_rows: Optional[List[EarningsModelRow]] = None
    sensitivity_analysis: Optional[AnalysisResult] = None
    sensitivity_result: Optional[SensitivityResult] = None
    growth_margin_sensitivity: Optional[GrowthMarginSensitivityResult] = None
    scenario_analysis: Optional[AnalysisResult] = None
    scenario_result: Optional[ScenarioResult] = None
    precedent_analysis: Optional[AnalysisResult] = None
    precedent_result: Optional[PrecedentTransactionResult] = None
    football_field_analysis: Optional[AnalysisResult] = None
    football_field_result: Optional[FootballFieldResult] = None
    conviction_analysis: Optional[AnalysisResult] = None
    conviction_result: Optional[ConvictionResult] = None
    normalization: Optional[NormalizationResult] = None


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
    report_progress("Fetching company facts...", USStep.FETCH_COMPANY_FACTS)
    company_facts, error = fds.get_company_facts(symbol)
    if error:
        fetched.errors.append(f"Company facts: {error}")
    else:
        fetched.company_facts = company_facts
        fetched.cost.add_fds_cost("company_facts")
        fetched.sources.append(SourceLink(
            title=f"FinancialDatasets.ai - {company_facts.name}",
            url=f"https://financialdatasets.ai/company/{symbol}",
            source_type="api",
            date=datetime.now().strftime("%Y-%m-%d"),
        ))

    company_name = company_facts.name if company_facts else symbol

    # Step 2: Financial Statements ($0.02)
    report_progress("Fetching financial statements...", USStep.FETCH_FINANCIALS)
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
    report_progress("Fetching price history...", USStep.FETCH_PRICES)
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
    report_progress("Fetching insider trades...", USStep.FETCH_INSIDER_TRADES)
    insider_trades, error = fds.get_insider_trades(symbol, limit=50)
    if error:
        fetched.errors.append(f"Insider trades: {error}")
    else:
        fetched.insider_trades = insider_trades
        fetched.cost.add_fds_cost("insider_trades")

    # Step 5: Analyst Estimates ($0.02)
    report_progress("Fetching analyst estimates...", USStep.FETCH_ANALYST_ESTIMATES)
    estimates, error = fds.get_analyst_estimates(symbol, limit=8)
    if error:
        fetched.errors.append(f"Analyst estimates: {error}")
    else:
        fetched.analyst_estimates = estimates
        fetched.cost.add_fds_cost("analyst_estimates")

    # Step 6: FDS News ($0.02)
    report_progress("Fetching company news...", USStep.FETCH_NEWS)
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
            fetched.sources.append(SourceLink(
                title=title,
                url=url,
                source_type="news",
                date=date,
            ))

    # Step 7: Gemini Search - Web Research (Round 1)
    report_progress("Searching web for recent developments...", USStep.WEB_SEARCH_1)
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
                    fetched.sources.append(SourceLink(
                        title=chunk.get('title', 'Web Search Result'),
                        url=chunk.get('uri', chunk.get('url', '')),
                        source_type="search",
                        date="recent",
                    ))

    # Step 8: Follow-up Research (Round 2)
    if fetched.sentiment_report and config.google_api_key:
        report_progress("Researching follow-up topics...", USStep.WEB_SEARCH_2)
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

    # Current price from most recent close (may be 0 if FDS data is incomplete;
    # the price_resolver handles fallback — technicals just reports what FDS gave us)
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
    report_progress("Running Fundamentals Agent...", USStep.FUNDAMENTALS)

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

    # =============================================================================
    # Phase A: Fundamentals & Technicals (Steps 3-5)
    # =============================================================================

    # Step 3: Unified Fundamentals Analysis (includes insider and estimates data)
    fundamentals_result, _, fund_cost = _analyze_fundamentals_us(
        fetched.enriched_financials,
        fetched.insider_trades or [],
        fetched.analyst_estimates or [],
        config,
        progress_callback,
    )
    total_cost = total_cost.merge(fund_cost)
    combined_fundamentals = fundamentals_result

    # Step 4: Insider Analysis
    report_progress("Analyzing insider activity...", USStep.INSIDER_ANALYSIS)
    insider_result = _analyze_insider_signals(fetched.insider_trades or [], config)
    total_cost.add_llm_cost(insider_result.cost_usd)

    # Step 5: Technical Analysis
    report_progress("Running Technical Analysis Agent...", USStep.TECHNICAL_ANALYSIS)
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
        logger.warning(f"No technical indicators available for {symbol}")
        technical_result = AnalysisResult(
            section="Technical Analysis",
            content="**Technical Analysis Unavailable**\n\nSufficient price history data was not available to calculate technical indicators.",
            tokens_used=0, success=True, error=None, cost_usd=0.0,
        )

    # =============================================================================
    # Phase B: Strategic Assessment (Steps 6-8) — runs BEFORE valuation
    # =============================================================================

    # Step 6: Accounting Standard Detection
    normalization_result = detect_and_flag(
        exchange=stock_info.exchange,
        country=stock_info.country,
    )

    # Step 7: Strategic Assessment (PESTEL, Porter's, Market Sizing)
    report_progress("Running Strategic Assessment (PESTEL, Porter's, Market Sizing)...", USStep.STRATEGIC_ASSESSMENT)
    strategic_assessment_obj = None
    strategic_assessment_result = None
    try:
        strategic_assessment_obj, strategic_assessment_result = run_strategic_assessment(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=stock_info,
            fundamentals_analysis=combined_fundamentals.content,
            sentiment_report=fetched.sentiment_report,
        )
        total_cost.add_llm_cost(strategic_assessment_result.cost_usd)
    except Exception as e:
        logger.warning(f"Strategic assessment failed: {e}")
        sector = stock_info.sector or "Unknown"
        industry = stock_info.industry or "Unknown"
        strategic_assessment_result = AnalysisResult(
            section="External Forces",
            content=(
                f"## External Forces — {stock_info.name}\n\n"
                f"*Automated fallback: the full PESTEL/Porter's assessment could not be completed.*\n\n"
                f"### Industry Context\n\n"
                f"{stock_info.name} operates in the **{industry}** industry within the **{sector}** sector. "
                f"Investors should consider the standard external forces affecting this space:\n\n"
                f"**Political & Regulatory:** Government policy, trade regulations, and industry-specific compliance requirements.\n\n"
                f"**Economic:** Interest rate environment, inflation trends, consumer/enterprise spending cycles, and currency exposure.\n\n"
                f"**Technological:** Pace of innovation, R&D intensity, and disruption risk from emerging technologies.\n\n"
                f"**Competitive:** Barrier to entry, supplier/buyer power, and threat of substitutes within {industry}.\n\n"
                f"*A full strategic assessment with market sizing (TAM/SAM/SOM) and competitive positioning "
                f"was not available for this analysis run. Re-running the analysis may resolve this.*"
            ),
            tokens_used=0,
            success=True,
            cost_usd=0.0,
        )

    # Step 8: Strategy Analysis (SWOT + outlook, informed by strategic assessment)
    report_progress("Running Strategy Analysis Agent...", USStep.STRATEGY_ANALYSIS)
    strategy_result = analyze_strategy(
        config.openrouter_api_key,
        config.openrouter_model,
        stock_info,
        combined_fundamentals.content,
        fetched.sentiment_report,
    )
    total_cost.add_llm_cost(strategy_result.cost_usd)

    # Step 9: Moat Analysis
    report_progress("Running Moat Analysis Agent...", USStep.MOAT_ANALYSIS)
    moat_result = analyze_moat(
        config.openrouter_api_key,
        config.openrouter_model,
        stock_info,
        fetched.sentiment_report,
    )
    total_cost.add_llm_cost(moat_result.cost_usd)

    # =============================================================================
    # Phase C: Strategy-Informed Valuation (Steps 10-14)
    # =============================================================================

    # Step 10: DCF Valuation (now informed by strategic assessment)
    dcf_result_obj = None
    dcf_analysis_result = None
    report_progress("Running strategy-informed DCF valuation...", USStep.DCF_VALUATION)
    try:
        from src_george_researcher.valuation.dcf_agent import run_dcf_analysis
        dcf_result_obj, dcf_analysis_result = run_dcf_analysis(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=stock_info,
            enriched_financials=fetched.enriched_financials,
            financials=fetched.financials,
            analyst_estimates=fetched.analyst_estimates,
            sentiment_report=fetched.sentiment_report,
            strategic_assessment=strategic_assessment_obj,
        )
        total_cost.add_llm_cost(dcf_analysis_result.cost_usd)
    except Exception as e:
        logger.warning(f"DCF analysis failed: {e}")
        dcf_analysis_result = AnalysisResult(
            section="DCF Valuation", content=f"DCF analysis could not be completed: {e}",
            tokens_used=0, success=False, error=str(e),
        )

    # Step 11: Comparable Company Table
    comp_result_obj = None
    comp_analysis_result = None
    report_progress("Building comparable company table...", USStep.COMP_TABLE)
    try:
        from src_george_researcher.valuation.comp_agent import run_comp_analysis
        comp_result_obj, comp_analysis_result = run_comp_analysis(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=stock_info,
        )
        total_cost.add_llm_cost(comp_analysis_result.cost_usd)
    except Exception as e:
        logger.warning(f"Comp analysis failed: {e}")
        comp_analysis_result = AnalysisResult(
            section="Comparable Companies", content=f"Comparable analysis could not be completed: {e}",
            tokens_used=0, success=False, error=str(e),
        )

    # Step 12: Earnings Model (no LLM)
    earnings_model_result = None
    earnings_rows_obj = None
    report_progress("Building earnings model...", USStep.EARNINGS_MODEL)
    try:
        from src_george_researcher.valuation.earnings_model import run_earnings_model
        earnings_rows_obj, earnings_model_result = run_earnings_model(
            enriched_financials=fetched.enriched_financials,
            analyst_estimates=fetched.analyst_estimates,
        )
    except Exception as e:
        logger.warning(f"Earnings model failed: {e}")

    # Step 13: Sensitivity Analysis (no LLM, depends on DCF)
    sensitivity_result_obj = None
    growth_margin_sensitivity_obj = None
    sensitivity_analysis_result = None
    if dcf_result_obj:
        report_progress("Running sensitivity analysis...", USStep.SENSITIVITY)
        try:
            from src_george_researcher.valuation.sensitivity import run_sensitivity_analysis
            sensitivity_result_obj, growth_margin_sensitivity_obj, sensitivity_analysis_result = run_sensitivity_analysis(dcf_result_obj)
        except Exception as e:
            logger.warning(f"Sensitivity analysis failed: {e}")

    # Step 13b: Scenario Analysis (no LLM, depends on DCF)
    scenario_result_obj = None
    scenario_analysis_result = None
    if dcf_result_obj:
        report_progress("Running bull/base/bear scenario modeling...", USStep.SCENARIOS)
        try:
            from src_george_researcher.valuation.scenarios import run_scenarios, format_scenarios_markdown
            scenario_result_obj = run_scenarios(
                base_revenue=dcf_result_obj.base_revenue,
                net_debt=dcf_result_obj.net_debt,
                shares_outstanding=dcf_result_obj.shares_outstanding,
                current_price=dcf_result_obj.current_price,
                base_assumptions=dcf_result_obj.assumptions,
            )
            scenario_analysis_result = AnalysisResult(
                section="Scenario Analysis",
                content=format_scenarios_markdown(scenario_result_obj),
                tokens_used=0,
                success=True,
                cost_usd=0.0,
            )
        except Exception as e:
            logger.warning(f"Scenario analysis failed: {e}")

    # Step 14: Precedent Transactions (1 LLM call, uses existing web search)
    precedent_result_obj = None
    precedent_analysis_result = None
    if fetched.sentiment_report and stock_info.industry:
        report_progress("Analyzing precedent M&A transactions...", USStep.PRECEDENT_MA)
        try:
            from src_george_researcher.valuation.precedent_transactions import run_precedent_analysis

            # Derive EBITDA from enriched financials if available
            target_ebitda = None
            if fetched.enriched_financials and fetched.enriched_financials.periods:
                latest_period = fetched.enriched_financials.periods[0]
                if hasattr(latest_period, 'ebitda') and latest_period.ebitda:
                    target_ebitda = latest_period.ebitda.current_value

            precedent_result_obj, precedent_analysis_result = run_precedent_analysis(
                api_key=config.openrouter_api_key,
                model=config.openrouter_model,
                company_name=stock_info.name,
                industry=stock_info.industry or "Unknown",
                sector=stock_info.sector or "Unknown",
                revenue=stock_info.revenue,
                ebitda=target_ebitda,
                net_debt=stock_info.net_debt,
                shares_outstanding=stock_info.shares_outstanding,
                search_results=fetched.sentiment_report,
            )
            if precedent_analysis_result:
                total_cost.add_llm_cost(precedent_analysis_result.cost_usd)
        except Exception as e:
            logger.warning(f"Precedent transaction analysis failed: {e}")

    # Step 15: Football Field (no LLM, aggregates all valuation methods)
    football_field_obj = None
    football_field_analysis = None
    report_progress("Building valuation football field...", USStep.FOOTBALL_FIELD)
    try:
        from src_george_researcher.valuation.football_field import build_football_field, format_football_field_markdown

        # Gather comp implied values
        comp_implied = comp_result_obj.implied_values if comp_result_obj else {}

        football_field_obj = build_football_field(
            current_price=stock_info.current_price or 0,
            dcf_bear=scenario_result_obj.bear.result.fair_value_per_share if scenario_result_obj else None,
            dcf_base=scenario_result_obj.base.result.fair_value_per_share if scenario_result_obj else (dcf_result_obj.fair_value_per_share if dcf_result_obj else None),
            dcf_bull=scenario_result_obj.bull.result.fair_value_per_share if scenario_result_obj else None,
            weighted_fair_value=scenario_result_obj.weighted_fair_value if scenario_result_obj else None,
            comp_pe_implied=comp_implied.get("pe_implied"),
            comp_fwd_pe_implied=comp_implied.get("forward_pe_implied"),
            comp_ev_revenue_implied=comp_implied.get("ev_revenue_implied"),
            comp_ev_ebitda_implied=comp_implied.get("ev_ebitda_implied"),
            precedent_ev_revenue=precedent_result_obj.implied_value_from_revenue if precedent_result_obj else None,
            precedent_ev_ebitda=precedent_result_obj.implied_value_from_ebitda if precedent_result_obj else None,
            consensus_target=stock_info.target_price,
        )
        football_field_analysis = AnalysisResult(
            section="Valuation Summary",
            content=format_football_field_markdown(football_field_obj),
            tokens_used=0,
            success=True,
            cost_usd=0.0,
        )
    except Exception as e:
        logger.warning(f"Football field construction failed: {e}")

    # =============================================================================
    # Phase D: Bull/Bear Debate AFTER Valuation (Steps 16-20)
    # Bull/bear now critique the valuation assumptions, not just the story
    # =============================================================================

    # Build valuation context for bull/bear
    valuation_context = ""
    if dcf_analysis_result and dcf_analysis_result.success:
        valuation_context = f"\n\nValuation Analysis:\n{dcf_analysis_result.content[:1500]}"
    if comp_analysis_result and comp_analysis_result.success:
        valuation_context += f"\n\nComparable Companies:\n{comp_analysis_result.content[:800]}"
    if scenario_analysis_result and scenario_analysis_result.success:
        valuation_context += f"\n\nScenario Analysis:\n{scenario_analysis_result.content[:800]}"

    report_progress("Running Bull Case Agent (Round 1)...", USStep.BULL_ROUND_1)
    base_context = AnalysisContext(
        api_key=config.openrouter_api_key,
        model=config.openrouter_model,
        stock_info=stock_info,
        fundamentals_analysis=combined_fundamentals.content + valuation_context,
        technicals_analysis=technical_result.content if technical_result else "",
        strategy_analysis=strategy_result.content if strategy_result.success else "",
        moat_analysis=moat_result.content if moat_result.success else "",
        sentiment_report=fetched.sentiment_report,
        counter_argument="",
    )

    bull_result = generate_bull_thesis(base_context)
    total_cost.add_llm_cost(bull_result.cost_usd)

    report_progress("Running Bear Case Agent (Round 1)...", USStep.BEAR_ROUND_1)
    bear_context = AnalysisContext(
        api_key=config.openrouter_api_key,
        model=config.openrouter_model,
        stock_info=stock_info,
        fundamentals_analysis=combined_fundamentals.content + valuation_context,
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
        report_progress("Running Bull Case Agent (Round 2)...", USStep.BULL_ROUND_2)
        bull_context_r2 = AnalysisContext(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=stock_info,
            fundamentals_analysis=combined_fundamentals.content + valuation_context,
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

        report_progress("Running Bear Case Agent (Round 2)...", USStep.BEAR_ROUND_2)
        bear_context_r2 = AnalysisContext(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=stock_info,
            fundamentals_analysis=combined_fundamentals.content + valuation_context,
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

    # Step 18: Recommendation Synthesis
    report_progress("Synthesizing final recommendation...", USStep.RECOMMENDATION)
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

    # =============================================================================
    # Phase E: Conviction Scoring (Step 19)
    # =============================================================================

    conviction_result_obj = None
    conviction_analysis_result = None
    report_progress("Scoring investment conviction...", USStep.CONVICTION)
    try:
        from src_george_researcher.valuation.conviction import score_conviction
        conviction_result_obj, conviction_analysis_result = score_conviction(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            stock_info=stock_info,
            fundamentals=combined_fundamentals.content,
            technicals=technical_result.content if technical_result else "",
            bull_thesis=bull_result.content if bull_result.success else "",
            bear_thesis=bear_result.content if bear_result.success else "",
            dcf_result=dcf_result_obj,
            comp_result=comp_result_obj,
            sentiment_report=fetched.sentiment_report,
        )
        total_cost.add_llm_cost(conviction_analysis_result.cost_usd)
    except Exception as e:
        logger.warning(f"Conviction scoring failed: {e}")

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
        strategic_assessment_analysis=strategic_assessment_result,
        strategic_assessment=strategic_assessment_obj,
        bull_thesis=bull_result,
        bear_thesis=bear_result,
        moat_analysis=moat_result,
        strategy_analysis=strategy_result,
        recommendation=recommendation_result,
        # Valuation
        dcf_analysis=dcf_analysis_result,
        dcf_result=dcf_result_obj,
        comp_analysis=comp_analysis_result,
        comp_result=comp_result_obj,
        earnings_model=earnings_model_result,
        earnings_rows=earnings_rows_obj,
        sensitivity_analysis=sensitivity_analysis_result,
        sensitivity_result=sensitivity_result_obj,
        growth_margin_sensitivity=growth_margin_sensitivity_obj,
        scenario_analysis=scenario_analysis_result,
        scenario_result=scenario_result_obj,
        precedent_analysis=precedent_analysis_result,
        precedent_result=precedent_result_obj,
        football_field_analysis=football_field_analysis,
        football_field_result=football_field_obj,
        conviction_analysis=conviction_analysis_result,
        conviction_result=conviction_result_obj,
        normalization=normalization_result,
        # Metadata
        total_tokens=total_tokens,
        total_cost_usd=total_cost.total,
        cost_breakdown=total_cost,
        success=combined_fundamentals.success,
        errors=fetched.errors,
        sources_collected=fetched.sources,
    )


def _build_stock_info_from_fds(fetched: USFetchedData) -> StockInfo:
    """Build StockInfo from FDS data for compatibility with existing agents.

    Supplements with yfinance data for fields FDS doesn't provide
    (shares_outstanding, beta, forward_pe, etc.).
    """
    from src_george_researcher.data_fetchers.stock_data import fetch_stock_info as yf_fetch

    facts = fetched.company_facts
    technicals = fetched.technicals

    # Get latest financials for ratios
    latest = None
    latest_stmt = None
    if fetched.enriched_financials and fetched.enriched_financials.periods:
        latest = fetched.enriched_financials.periods[0]
    if fetched.financials:
        latest_stmt = fetched.financials[0]

    eps = latest.eps.current_value if latest and latest.eps else None

    # Compute net debt from balance sheet
    net_debt = None
    if latest_stmt:
        total_debt = latest_stmt.total_debt or 0
        cash = latest_stmt.cash_and_equivalents or 0
        net_debt = total_debt - cash

    # Fetch supplemental data from yfinance for fields FDS doesn't provide
    yf_info = None
    symbol = facts.ticker if facts else ""
    if symbol:
        try:
            yf_info, yf_error = yf_fetch(symbol)
            if yf_error:
                logger.warning(f"yfinance supplement failed for {symbol}: {yf_error}")
                yf_info = None
        except Exception as e:
            logger.warning(f"yfinance supplement error for {symbol}: {e}")

    # Resolve current price through cascading fallback (FDS → yfinance → derivation)
    yf_shares = yf_info.shares_outstanding if yf_info else None
    resolved = resolve_current_price(
        symbol=symbol,
        fds_prices=fetched.prices,
        yf_info=yf_info,
        market_cap=facts.market_cap if facts else None,
        shares_outstanding=yf_shares,
    )
    current_price = resolved.price if resolved.success else None

    # Derive shares_outstanding from market_cap / price when yfinance unavailable
    derived_shares = None
    if not yf_shares and facts and facts.market_cap and current_price and current_price > 0:
        derived_shares = facts.market_cap / current_price
        logger.info(
            f"[{symbol}] Derived shares_outstanding from market_cap/price: {derived_shares:,.0f}"
        )

    return StockInfo(
        symbol=symbol,
        name=facts.name if facts else "",
        sector=facts.sector if facts else None,
        industry=facts.industry if facts else None,
        country="United States",
        exchange=facts.exchange if facts else None,
        currency="USD",
        current_price=current_price,
        market_cap=facts.market_cap if facts else None,
        enterprise_value=yf_info.enterprise_value if yf_info else None,
        pe_ratio=(current_price / eps) if current_price and eps and eps > 0 else None,
        forward_pe=yf_info.forward_pe if yf_info else None,
        peg_ratio=yf_info.peg_ratio if yf_info else None,
        pb_ratio=None,
        ps_ratio=yf_info.ps_ratio if yf_info else None,
        price_to_fcf=yf_info.price_to_fcf if yf_info else None,
        ev_to_ebitda=yf_info.ev_to_ebitda if yf_info else None,
        ev_to_revenue=yf_info.ev_to_revenue if yf_info else None,
        dividend_yield=yf_info.dividend_yield if yf_info else None,
        profit_margin=latest.net_margin.current_value if latest and latest.net_margin else None,
        operating_margin=latest.operating_margin.current_value if latest and latest.operating_margin else None,
        gross_margin=latest.gross_margin.current_value if latest and latest.gross_margin else None,
        roe=yf_info.roe if yf_info else None,
        roa=yf_info.roa if yf_info else None,
        debt_to_equity=latest.debt_to_equity.current_value if latest and latest.debt_to_equity else None,
        current_ratio=yf_info.current_ratio if yf_info else None,
        quick_ratio=None,
        revenue=latest.revenue.current_value if latest and latest.revenue else None,
        revenue_growth=latest.revenue.yoy_change if latest and latest.revenue else None,
        earnings_growth=latest.net_income.yoy_change if latest and latest.net_income else None,
        free_cash_flow=latest.free_cash_flow.current_value if latest and latest.free_cash_flow else None,
        beta=yf_info.beta if yf_info else None,
        high_52w=technicals.high_52w if technicals else None,
        low_52w=technicals.low_52w if technicals else None,
        avg_volume=technicals.avg_volume_20d if technicals else None,
        shares_outstanding=yf_shares or derived_shares,
        float_shares=yf_info.float_shares if yf_info else None,
        held_by_institutions=yf_info.held_by_institutions if yf_info else None,
        held_by_insiders=yf_info.held_by_insiders if yf_info else None,
        short_ratio=yf_info.short_ratio if yf_info else None,
        short_percent=yf_info.short_percent if yf_info else None,
        target_price=yf_info.target_price if yf_info else None,
        analyst_rating=yf_info.analyst_rating if yf_info else None,
        num_analysts=yf_info.num_analysts if yf_info else None,
        eps=eps,
        business_summary=facts.description if facts else None,
        website=facts.website_url if facts else None,
        employees=facts.number_of_employees if facts else None,
        net_debt=net_debt,
        interest_expense=getattr(latest_stmt, 'interest_expense', None) if latest_stmt else None,
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
