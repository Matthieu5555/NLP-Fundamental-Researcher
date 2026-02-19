"""
News and sentiment data fetching from Alpha Vantage and EODHD.

API Info:
- Alpha Vantage NEWS_SENTIMENT API
  - Requires API key (free tier available)
  - Rate limit: 5 calls/minute, 500 calls/day on free tier
  - Premium tiers available for higher limits
  - Timeout: 30 seconds

- EODHD News API
  - Requires API key (free tier available)
  - Rate limit: ~1000 calls/day on free tier
  - Timeout: 30 seconds

All functions return (result, error) tuples for consistent error handling.
"""
import httpx
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _extract_source_from_url(url: str) -> str:
    """Extract domain name as source from URL when source not provided."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        # Get first part of domain (e.g., "reuters" from "reuters.com")
        name = domain.split(".")[0] if domain else ""
        return name.title() if name else "Unknown"
    except Exception as e:
        logger.debug(f"Failed to extract source from URL {url}: {e}")
        return "Unknown"


@dataclass(frozen=True)
class NewsItem:
    """Single news article with sentiment."""
    title: str
    url: str
    source: str
    published: str
    summary: str
    sentiment_score: float
    sentiment_label: str


@dataclass(frozen=True)
class NewsSentiment:
    """Aggregated news sentiment for a symbol."""
    symbol: str
    articles: list[NewsItem]
    overall_sentiment: float
    overall_label: str
    bullish_count: int
    bearish_count: int
    neutral_count: int


def _score_to_label(score: float) -> str:
    """Convert sentiment score to a grade out of 5."""
    if score <= -0.35:
        return "1/5"
    elif score <= -0.15:
        return "2/5"
    elif score < 0.15:
        return "3/5"
    elif score < 0.35:
        return "4/5"
    else:
        return "5/5"


def fetch_alpha_vantage_news(
    symbol: str,
    api_key: str,
    limit: int = 10,
    company_name: str = "",
) -> tuple[Optional[NewsSentiment], Optional[str]]:
    """Fetch news sentiment from Alpha Vantage."""
    if not api_key:
        return (None, "Alpha Vantage API key not configured")

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": symbol,
        "limit": limit,
        "apikey": api_key,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)

        if response.status_code != 200:
            return (None, f"Alpha Vantage API error: HTTP {response.status_code}")

        data = response.json()

        if "Error Message" in data:
            return (None, data["Error Message"])
        if "Note" in data:
            return (None, f"API limit reached: {data['Note']}")
        if "Information" in data:
            return (None, data["Information"])

        feed = data.get("feed", [])
        if not feed:
            return (None, "No news articles found")

        articles = []
        total_score = 0.0
        bullish = 0
        bearish = 0
        neutral = 0

        for item in feed[:limit]:
            ticker_sentiment = None
            for ts in item.get("ticker_sentiment", []):
                if ts.get("ticker") == symbol:
                    ticker_sentiment = ts
                    break

            if ticker_sentiment:
                score = float(ticker_sentiment.get("ticker_sentiment_score", 0))
            else:
                score = float(item.get("overall_sentiment_score", 0))

            label = _score_to_label(score)
            total_score += score

            if score <= -0.15:
                bearish += 1
            elif score >= 0.15:
                bullish += 1
            else:
                neutral += 1

            articles.append(NewsItem(
                title=item.get("title", ""),
                url=item.get("url", ""),
                source=item.get("source", ""),
                published=item.get("time_published", "")[:8],
                summary=item.get("summary", "")[:300],
                sentiment_score=score,
                sentiment_label=label,
            ))

        avg_score = total_score / len(articles) if articles else 0.0

        return (
            NewsSentiment(
                symbol=symbol,
                articles=articles,
                overall_sentiment=avg_score,
                overall_label=_score_to_label(avg_score),
                bullish_count=bullish,
                bearish_count=bearish,
                neutral_count=neutral,
            ),
            None,
        )

    except httpx.TimeoutException:
        return (None, "Request timed out")
    except Exception as e:
        return (None, str(e))


def fetch_eodhd_news(
    symbol: str,
    api_key: str,
    limit: int = 10,
    company_name: str = "",
) -> tuple[Optional[NewsSentiment], Optional[str]]:
    """Fetch news sentiment from EODHD."""
    if not api_key:
        return (None, "EODHD API key not configured")

    # EODHD uses exchange suffix, default to US
    ticker = f"{symbol}.US" if "." not in symbol else symbol

    url = "https://eodhd.com/api/news"
    params = {
        "s": ticker,
        "limit": limit,
        "api_token": api_key,
        "fmt": "json",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)

        if response.status_code != 200:
            return (None, f"EODHD API error: HTTP {response.status_code}")

        data = response.json()

        if isinstance(data, dict) and "error" in data:
            return (None, data["error"])

        if not data:
            return (None, "No news articles found")

        articles = []
        total_score = 0.0
        bullish = 0
        bearish = 0
        neutral = 0

        for item in data[:limit]:
            # EODHD sentiment: polarity, neg, neu, pos
            sentiment = item.get("sentiment", {})
            polarity = float(sentiment.get("polarity", 0)) if sentiment else 0

            # EODHD polarity is already -1 to 1, scale to match our thresholds
            score = polarity * 0.5
            label = _score_to_label(score)
            total_score += score

            if score <= -0.15:
                bearish += 1
            elif score >= 0.15:
                bullish += 1
            else:
                neutral += 1

            # EODHD sometimes lacks source field, extract from URL
            link = item.get("link", "")
            source = item.get("source", "")
            if not source and link:
                source = _extract_source_from_url(link)

            articles.append(NewsItem(
                title=item.get("title", ""),
                url=link,
                source=source or "EODHD",
                published=item.get("date", "")[:10],
                summary=item.get("content", "")[:300] if item.get("content") else "",
                sentiment_score=score,
                sentiment_label=label,
            ))

        avg_score = total_score / len(articles) if articles else 0.0

        return (
            NewsSentiment(
                symbol=symbol,
                articles=articles,
                overall_sentiment=avg_score,
                overall_label=_score_to_label(avg_score),
                bullish_count=bullish,
                bearish_count=bearish,
                neutral_count=neutral,
            ),
            None,
        )

    except httpx.TimeoutException:
        return (None, "Request timed out")
    except Exception as e:
        return (None, str(e))


def fetch_combined_news(
    symbol: str,
    alpha_vantage_key: str = "",
    eodhd_key: str = "",
    limit: int = 10,
    company_name: str = "",
) -> tuple[Optional[NewsSentiment], Optional[str]]:
    """
    Fetch news from available sources with fallback.
    Tries EODHD first (better sentiment structure), then Alpha Vantage.

    Args:
        symbol: Stock ticker
        alpha_vantage_key: Alpha Vantage API key
        eodhd_key: EODHD API key
        limit: Max articles to fetch
        company_name: Company name for better search relevance
    """
    errors = []

    # Try EODHD first
    if eodhd_key:
        result, error = fetch_eodhd_news(symbol, eodhd_key, limit, company_name)
        if result:
            return (result, None)
        if error:
            errors.append(f"EODHD: {error}")

    # Fallback to Alpha Vantage
    if alpha_vantage_key:
        result, error = fetch_alpha_vantage_news(symbol, alpha_vantage_key, limit, company_name)
        if result:
            return (result, None)
        if error:
            errors.append(f"Alpha Vantage: {error}")

    if not alpha_vantage_key and not eodhd_key:
        return (None, "No news API keys configured")

    return (None, "; ".join(errors) if errors else "No news found")


def format_sentiment_report(news: NewsSentiment) -> str:
    """
    Format news sentiment as a report string for LLM agents.
    This is passed to all analysis agents as context.
    """
    lines = [
        f"News Sentiment for {news.symbol}",
        "-" * 30,
        "",
        f"Overall: {news.overall_label} (score: {news.overall_sentiment:.2f})",
        f"Breakdown: {news.bullish_count} positive, {news.bearish_count} negative, {news.neutral_count} neutral",
        "",
        "Recent Headlines:",
    ]

    for i, article in enumerate(news.articles[:7], 1):
        indicator = "[+]" if article.sentiment_score > 0.15 else "[-]" if article.sentiment_score < -0.15 else "[o]"
        lines.append(f"{i}. {indicator} {article.title}")
        lines.append(f"   {article.source} | {article.published} | {article.sentiment_label}")
        if article.summary:
            summary = article.summary[:150].replace('\n', ' ')
            lines.append(f"   {summary}...")
        lines.append("")

    lines.append("Observations:")
    if news.bullish_count > news.bearish_count * 2:
        lines.append("- Strong positive media coverage")
    elif news.bullish_count > news.bearish_count:
        lines.append("- Slightly positive media sentiment")
    elif news.bearish_count > news.bullish_count * 2:
        lines.append("- Strong negative media coverage")
    elif news.bearish_count > news.bullish_count:
        lines.append("- Slightly negative media sentiment")
    else:
        lines.append("- Mixed/neutral media sentiment")

    return "\n".join(lines)
