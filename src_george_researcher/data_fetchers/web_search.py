"""
Web search for breaking news using Tavily API.
"""
import httpx
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SearchResult:
    """Single search result."""
    title: str
    url: str
    content: str
    score: float


@dataclass(frozen=True)
class WebSearchResults:
    """Collection of web search results."""
    query: str
    results: list[SearchResult]
    answer: str  # Tavily provides an AI-generated answer


def search_breaking_news(
    symbol: str,
    company_name: str,
    api_key: str,
    max_results: int = 5,
) -> tuple[Optional[WebSearchResults], Optional[str]]:
    """
    Search for breaking news about a stock using Tavily.

    Args:
        symbol: Stock ticker (e.g., "AAPL")
        company_name: Full company name (e.g., "Apple Inc")
        api_key: Tavily API key
        max_results: Maximum number of results

    Returns:
        Tuple of (WebSearchResults or None, error message or None)
    """
    if not api_key:
        return (None, "Tavily API key not configured")

    # Build search query
    query = f"{symbol} {company_name} stock news latest"

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "include_raw_content": False,
        "max_results": max_results,
        "include_domains": [
            "reuters.com",
            "bloomberg.com",
            "cnbc.com",
            "wsj.com",
            "marketwatch.com",
            "seekingalpha.com",
            "finance.yahoo.com",
            "fool.com",
            "barrons.com",
        ],
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, json=payload)

        if response.status_code != 200:
            return (None, f"Tavily API error: HTTP {response.status_code}")

        data = response.json()

        if "error" in data:
            return (None, data["error"])

        results = []
        for item in data.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", "")[:400],
                score=item.get("score", 0.0),
            ))

        return (
            WebSearchResults(
                query=query,
                results=results,
                answer=data.get("answer", ""),
            ),
            None,
        )

    except httpx.TimeoutException:
        return (None, "Tavily request timed out")
    except Exception as e:
        return (None, f"Tavily error: {str(e)}")


def format_search_report(results: WebSearchResults) -> str:
    """
    Format web search results as a report string for LLM agents.
    """
    lines = [
        "Breaking News Search Results",
        "-" * 30,
        "",
    ]

    if results.answer:
        lines.append("Summary:")
        lines.append(results.answer)
        lines.append("")

    lines.append("Top Results:")
    for i, result in enumerate(results.results, 1):
        lines.append(f"{i}. {result.title}")
        lines.append(f"   Source: {result.url}")
        lines.append(f"   {result.content[:200]}...")
        lines.append("")

    return "\n".join(lines)
