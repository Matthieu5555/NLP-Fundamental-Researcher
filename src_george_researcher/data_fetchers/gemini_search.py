"""
Web search using Google Gemini's native Search Grounding.

Uses Gemini API with google_search tool for grounded responses with citations.

API Info:
- Requires Google API key (from AI Studio)
- Cost: $0.035 per grounded query ($35 per 1,000 queries)
- Free tier: 1,500 requests per day (RPD)
- Timeout: 30 seconds
- Model: gemini-2.0-flash

All functions return (result, error) tuples for consistent error handling.
"""
import httpx
from dataclasses import dataclass
from typing import Optional

from .cache import cached


# Gemini Search Grounding pricing (per grounded prompt)
# Source: https://ai.google.dev/pricing
# Cost: $35 per 1,000 grounded prompts = $0.035 per query
# Free tier: 1,500 requests per day (RPD) available
GEMINI_SEARCH_COST_PER_QUERY = 0.035


@dataclass(frozen=True)
class SearchResult:
    """Single search result from grounding metadata."""
    title: str
    url: str
    content: str
    score: float


@dataclass(frozen=True)
class GeminiSearchResults:
    """Collection of Gemini search grounding results."""
    query: str
    results: list[SearchResult]
    answer: str  # AI-generated grounded response
    cost_usd: float = GEMINI_SEARCH_COST_PER_QUERY  # Cost for this search


import logging

logger = logging.getLogger(__name__)


@cached("gemini_search", ticker_param="symbol", exclude_params={"api_key"})
def search_with_gemini(
    symbol: str,
    company_name: str,
    api_key: str,
    query: str = None,
    max_results: int = 5,
    min_confidence: float = 0.5,
) -> tuple[Optional[GeminiSearchResults], Optional[str]]:
    """
    Search for news using Gemini's native Google Search grounding.

    Args:
        symbol: Stock ticker (e.g., "AAPL")
        company_name: Full company name (e.g., "Apple Inc")
        api_key: Google API key (from AI Studio)
        query: Specific search query from analyst (optional - uses generic if not provided)
        max_results: Maximum number of results to return
        min_confidence: Minimum confidence score (0-1) to include a source

    Returns:
        Tuple of (GeminiSearchResults or None, error message or None)
    """
    if not api_key:
        logger.warning("Gemini search skipped: Google API key not configured")
        return (None, "Google API key not configured")

    logger.info(f"Gemini search starting for {symbol} ({company_name}), query: {query or 'generic'}")

    # Build prompt based on whether analyst provided specific query
    if query:
        # Use analyst's specific question
        prompt_text = f"Research this question about {company_name} ({symbol}): {query}\n\nSearch for relevant recent information and provide a concise, factual answer with sources."
        search_query = query
    else:
        # Fall back to generic news search
        prompt_text = f"Search for the latest news and developments about {company_name} ({symbol}) stock. Focus on recent earnings, analyst updates, market movements, and significant company news. Provide a concise summary."
        search_query = f"{symbol} {company_name} stock news latest developments"

    # Gemini API endpoint with google_search tool
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt_text
                    }
                ]
            }
        ],
        "tools": [
            {
                "google_search": {}
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1024,
        }
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)

        if response.status_code == 400:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", "Bad request")
            return (None, f"Gemini API error: {error_msg}")

        if response.status_code == 403:
            return (None, "Gemini API error: Invalid API key or quota exceeded")

        if response.status_code != 200:
            return (None, f"Gemini API error: HTTP {response.status_code}")

        data = response.json()

        # Extract the generated answer
        answer = ""
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                answer = parts[0].get("text", "")

        # Extract grounding metadata (citations with confidence scores)
        results = []
        if candidates:
            grounding_metadata = candidates[0].get("groundingMetadata", {})
            grounding_chunks = grounding_metadata.get("groundingChunks", [])
            grounding_supports = grounding_metadata.get("groundingSupports", [])

            # Build chunk_id -> max_confidence mapping from groundingSupports
            # Each support links text segments to chunks with confidence scores
            chunk_confidence = {}
            for support in grounding_supports:
                indices = support.get("groundingChunkIndices", [])
                scores = support.get("confidenceScores", [])
                for idx, score in zip(indices, scores):
                    # Keep the highest confidence score for each chunk
                    chunk_confidence[idx] = max(chunk_confidence.get(idx, 0.0), score)

            logger.info(f"Gemini grounding: {len(grounding_chunks)} chunks, {len(grounding_supports)} supports, confidence map: {chunk_confidence}")

            # Build list of all chunks with their confidence scores
            all_results = []
            for i, chunk in enumerate(grounding_chunks):
                web_info = chunk.get("web", {})
                title = web_info.get("title", "")
                uri = web_info.get("uri", "")
                content_preview = title[:400] if title else ""

                # Get confidence from groundingSupports, or 0.0 if not referenced
                confidence = chunk_confidence.get(i, 0.0)

                all_results.append(SearchResult(
                    title=title,
                    url=uri,
                    content=content_preview,
                    score=confidence,
                ))

            # Sort by confidence score (highest first)
            all_results.sort(key=lambda x: x.score, reverse=True)

            # Filter by min_confidence, but fallback to top 2 if none pass
            filtered = [r for r in all_results if r.score >= min_confidence]

            if filtered:
                results = filtered[:max_results]
                logger.info(f"Gemini: {len(filtered)} sources above {min_confidence} threshold")
            elif all_results:
                # Fallback: return top 2 even if below threshold
                results = all_results[:2]
                logger.info(f"Gemini: No sources above {min_confidence}, falling back to top {len(results)}")
            else:
                results = []

        logger.info(f"Gemini search completed: {len(results)} results, answer length: {len(answer)}")
        return (
            GeminiSearchResults(
                query=search_query,
                results=results,
                answer=answer,
            ),
            None,
        )

    except httpx.TimeoutException:
        logger.error("Gemini request timed out")
        return (None, "Gemini request timed out")
    except Exception as e:
        logger.error(f"Gemini error: {str(e)}")
        return (None, f"Gemini error: {str(e)}")


def format_search_report(results: GeminiSearchResults) -> str:
    """
    Format Gemini search results as a report string for LLM agents.
    """
    lines = [
        "Breaking News Search Results (via Google Search)",
        "-" * 40,
        "",
    ]

    if results.answer:
        lines.append("Summary:")
        lines.append(results.answer)
        lines.append("")

    if results.results:
        lines.append("Sources:")
        for i, result in enumerate(results.results, 1):
            lines.append(f"{i}. {result.title}")
            lines.append(f"   URL: {result.url}")
            lines.append("")

    return "\n".join(lines)
