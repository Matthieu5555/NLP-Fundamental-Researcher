"""
RAG Engine for Smart Data Access.

Provides unified interface for:
- Gemini Search Grounding (breaking news via Google Search)
- SEC filing semantic search (FAISS)
- Query classification (LLM-based with keyword fallback)

Query Classification:
Uses Claude 3 Haiku for fast, cheap classification (50 tokens max).
Falls back to keyword matching if LLM unavailable or fails.

Classifications determine which data sources to search:
- "web_search": Breaking news, recent events, earnings announcements
- "sec_filings": Financial statements, risk factors, 10-K/10-Q content
- Both can be true for comprehensive queries

Data Flow:
1. classify_query_with_llm() or _keyword_classify() → search flags
2. _search_news() → Gemini Search Grounding → formatted news list
3. _search_filings() → SEC FAISS search → formatted filing chunks
4. format_context_for_llm() → context block for chat system prompt

Caching:
SEC filing data is cached in-memory per RAGEngine instance.
No expiration - cleared when instance is destroyed.
"""

import logging
import os
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

import httpx


@dataclass
class SearchClassification:
    """Query classification result for RAG routing."""
    news: bool = False
    filings: bool = False


@dataclass
class RAGSource:
    """A single RAG search result."""
    content: str
    source_type: str  # "news" or "sec_filing"
    relevance: float = 0.0
    title: str = ""
    url: str = ""
    date: str = ""
    section: str = ""
    filing_date: str = ""
    source: str = ""


@dataclass
class RAGResult:
    """Complete RAG retrieval result."""
    sources: List[RAGSource] = field(default_factory=list)
    search_performed: bool = False
    errors: List[str] = field(default_factory=list)

logger = logging.getLogger(__name__)

# sys.path configured in backend/main.py

# Haiku model for cheap classification
HAIKU_MODEL = "moonshotai/kimi-k2.5"

# Classification prompt
SEARCH_CLASSIFICATION_PROMPT = """You are a query classifier for a financial analysis chatbot.

The user is analyzing {ticker}. They asked: "{query}"

Determine what data sources are needed:
1. web_search: Does this need current news, recent announcements, or external data? (e.g., "what's happening with 5G in Europe", "any recent news", "current market sentiment")
2. sec_filings: Does this need SEC filing data like 10-K, financial statements, risk factors? (e.g., "what are their revenues", "debt levels", "risk factors")

Respond ONLY with valid JSON, no other text:
{{"web_search": true/false, "sec_filings": true/false}}"""


class RAGEngine:
    """
    Unified RAG engine for smart data retrieval.

    Uses keyword-based query classification to decide which data sources to search.
    Integrates Gemini Search Grounding (Google Search) and SEC filings (FAISS semantic search).

    Relevance Thresholds:
    - SEC filings: min_relevance=0.3 (filters out low-quality FAISS matches)
    - News: No threshold (Gemini already ranks by relevance)
    """

    # Keywords that trigger specific searches
    NEWS_KEYWORDS = [
        'news', 'recent', 'latest', 'announced', 'earnings', 'today',
        'yesterday', 'this week', 'this month', 'breaking', 'update'
    ]

    FILING_KEYWORDS = [
        '10-k', 'sec', 'filing', 'revenue', 'risk', 'financial statement',
        'balance sheet', 'income statement', 'cash flow', 'assets',
        'liabilities', 'debt', 'competition', 'business model', 'strategy'
    ]

    # Minimum relevance thresholds (0-1, higher = stricter)
    MIN_SEC_RELEVANCE = 0.3  # Filter out weak semantic matches
    MIN_NEWS_RELEVANCE = 0.0  # Gemini handles its own ranking

    def __init__(self):
        """Initialize RAG engine."""
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        self.search_enabled = bool(self.google_api_key)
        self.llm_classification_enabled = bool(self.openrouter_api_key)

        # Cache for SEC filings (in-memory for session)
        self.sec_filing_cache = {}

        # Directories for data and embeddings
        self.data_dir = Path(__file__).parent.parent.parent / "data"
        self.embeddings_dir = self.data_dir / "embeddings"
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"RAGEngine initialized. Gemini Search: {self.search_enabled}, LLM Classification: {self.llm_classification_enabled}")

    def classify_query_with_llm(self, query: str, ticker: str) -> SearchClassification:
        """
        Use Haiku to classify if query needs external research.

        Args:
            query: User query string
            ticker: Stock ticker being analyzed

        Returns:
            SearchClassification with news and filings boolean flags
        """
        if not self.openrouter_api_key:
            logger.warning("No OpenRouter API key, falling back to keyword classification")
            return self._keyword_classify(query)

        try:
            from src_george_researcher.llm import call_llm

            prompt = SEARCH_CLASSIFICATION_PROMPT.format(ticker=ticker, query=query)

            response = call_llm(
                api_key=self.openrouter_api_key,
                model=HAIKU_MODEL,
                system_prompt="You are a query classifier. Respond only with JSON.",
                user_prompt=prompt,
                temperature=0.0,
                max_tokens=50
            )

            if not response.success:
                logger.warning(f"LLM classification failed: {response.error}, falling back to keywords")
                return self._keyword_classify(query)

            # Parse JSON response
            result = json.loads(response.content.strip())
            logger.info(f"LLM classified query: web_search={result.get('web_search')}, sec_filings={result.get('sec_filings')}")

            return SearchClassification(
                news=result.get("web_search", False),
                filings=result.get("sec_filings", False),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM classification response: {e}")
            return self._keyword_classify(query)
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"LLM classification error: {e}")
            return self._keyword_classify(query)

    def _keyword_classify(self, query: str) -> SearchClassification:
        """
        Fallback keyword-based classification.

        Args:
            query: User query string

        Returns:
            SearchClassification with news and filings boolean flags
        """
        query_lower = query.lower()
        return SearchClassification(
            news=any(kw in query_lower for kw in self.NEWS_KEYWORDS),
            filings=any(kw in query_lower for kw in self.FILING_KEYWORDS),
        )

    def should_search(self, query: str, ticker: str = None, use_llm: bool = True) -> SearchClassification:
        """
        Determine which searches to run.

        Uses LLM classification by default, falls back to keywords.

        Args:
            query: User query string
            ticker: Stock ticker (required for LLM classification)
            use_llm: Whether to use LLM classification (default True)

        Returns:
            SearchClassification with news and filings boolean flags
        """
        if use_llm and ticker and self.llm_classification_enabled:
            return self.classify_query_with_llm(query, ticker)
        return self._keyword_classify(query)

    def retrieve_context(
        self,
        query: str,
        ticker: str,
        company_name: str = None,
        max_results: int = 5
    ) -> RAGResult:
        """
        Retrieve relevant context from all applicable sources.

        Args:
            query: User query
            ticker: Stock ticker symbol
            company_name: Company name (optional, will use ticker if not provided)
            max_results: Maximum number of results per source

        Returns:
            RAGResult with sources, search_performed flag, and any errors
        """
        search_flags = self.should_search(query, ticker=ticker)
        result = RAGResult()

        if not company_name:
            company_name = ticker

        # Search news if relevant
        if search_flags.news and self.search_enabled:
            news_results, news_error = self._search_news(ticker, company_name, query, max_results)
            if news_results:
                result.sources.extend(news_results)
                result.search_performed = True
            elif news_error:
                result.errors.append(f"News search: {news_error}")

        # Search SEC filings if relevant
        if search_flags.filings:
            filing_results, filing_error = self._search_filings(ticker, query, max_results=3)
            if filing_results:
                result.sources.extend(filing_results)
                result.search_performed = True
            elif filing_error:
                result.errors.append(f"SEC filing search: {filing_error}")

        return result

    # Minimum confidence for Gemini sources
    MIN_GEMINI_CONFIDENCE = 0.5

    def _search_news(
        self,
        ticker: str,
        company_name: str,
        query: str,
        max_results: int = 5
    ) -> tuple[List[RAGSource], Optional[str]]:
        """
        Search recent news via Gemini Search Grounding (Google Search).

        Args:
            ticker: Stock ticker
            company_name: Full company name
            query: Analyst's specific question (passed to Gemini for relevance)
            max_results: Maximum results to return

        Returns:
            Tuple of (list of RAGSource objects, error message or None)
        """
        try:
            from src_george_researcher.data_fetchers.gemini_search import search_with_gemini

            results, error = search_with_gemini(
                symbol=ticker,
                company_name=company_name,
                api_key=self.google_api_key,
                query=query,  # Pass analyst's question for targeted search
                max_results=max_results,
                min_confidence=self.MIN_GEMINI_CONFIDENCE
            )

            if error:
                return ([], error)

            if not results:
                return ([], None)

            formatted = [
                RAGSource(
                    content=r.content,
                    source_type="news",
                    relevance=r.score,
                    title=r.title,
                    url=r.url,
                )
                for r in results.results
            ]

            logger.info(f"News search returned {len(formatted)} sources (min_confidence={self.MIN_GEMINI_CONFIDENCE})")
            return (formatted, None)

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"News search failed: {e}")
            return ([], str(e))

    def _search_filings(
        self,
        ticker: str,
        query: str,
        max_results: int = 3
    ) -> tuple[List[RAGSource], Optional[str]]:
        """
        Search SEC filings via existing RAG infrastructure.

        Returns:
            Tuple of (list of RAGSource objects, error message or None)
        """
        try:
            # Check cache first
            if ticker not in self.sec_filing_cache:
                # Fetch and cache filing
                filing_data, error = self._fetch_sec_filing(ticker)
                if error:
                    return ([], error)
                if filing_data:
                    self.sec_filing_cache[ticker] = filing_data

            filing_data = self.sec_filing_cache.get(ticker)
            if not filing_data:
                return ([], "No SEC filing data available")

            # Search the filing with relevance threshold
            from src_george_researcher.data_fetchers.sec_filings import search_sec_filing

            chunks = search_sec_filing(
                filing=filing_data,
                query=query,
                embeddings_dir=self.embeddings_dir,
                k=max_results,
                min_relevance=self.MIN_SEC_RELEVANCE
            )

            formatted = [
                RAGSource(
                    content=chunk.text[:600],  # Truncate to 600 chars
                    source_type="sec_filing",
                    relevance=chunk.relevance_score,
                    section=chunk.section,
                    filing_date=chunk.filing_date,
                    source=chunk.source,
                )
                for chunk in chunks
            ]

            logger.info(f"SEC search returned {len(chunks)} chunks above threshold {self.MIN_SEC_RELEVANCE}")
            return (formatted, None)

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"SEC filing search failed: {e}")
            return ([], str(e))

    def _fetch_sec_filing(self, ticker: str) -> tuple[Optional[object], Optional[str]]:
        """
        Fetch SEC 10-K filing for a ticker.

        Uses SEC Edgar API via sec_filings module to download and parse
        the most recent 10-K filing. Results are cached in self.sec_filing_cache
        to avoid repeated API calls.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            tuple: (filing_data, error_message)
                - On success: (SECFilingData object, None)
                - On failure: (None, error description string)
        """
        try:
            from src_george_researcher.data_fetchers.sec_filings import fetch_sec_filing

            filing_data, error = fetch_sec_filing(
                symbol=ticker,
                data_dir=self.data_dir
            )

            return (filing_data, error)

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError, OSError) as e:
            logger.error(f"SEC filing fetch failed: {e}")
            return (None, str(e))

    def format_context_for_llm(self, context: RAGResult) -> str:
        """
        Format search results as context block for LLM.

        Args:
            context: RAGResult from retrieve_context()

        Returns:
            Formatted string for LLM system prompt
        """
        if not context.sources:
            return ""

        formatted_parts = ["## Additional Context from Research\n"]

        # Add news results
        news_results = [s for s in context.sources if s.source_type == "news"]
        if news_results:
            formatted_parts.append("### Recent News:\n")
            for source in news_results[:3]:  # Top 3 news items
                formatted_parts.append(f"**{source.title}**")
                formatted_parts.append(f"{source.content[:300]}...")
                formatted_parts.append(f"Source: {source.url}\n")

        # Add SEC filing results
        filing_results = [s for s in context.sources if s.source_type == "sec_filing"]
        if filing_results:
            formatted_parts.append("\n### From SEC 10-K Filing:\n")
            for source in filing_results[:3]:  # Top 3 excerpts
                formatted_parts.append(f"**[{source.section}]** (Filed: {source.filing_date})")
                formatted_parts.append(f"{source.content[:400]}...\n")

        return "\n".join(formatted_parts)

    def get_source_citations(self, context: RAGResult) -> List[Dict]:
        """
        Extract source citations for display in UI.

        Args:
            context: RAGResult from retrieve_context()

        Returns:
            List of citation dicts with type, title, url, date
        """
        citations = []

        for source in context.sources:
            if source.source_type == "news":
                citations.append({
                    "type": "news",
                    "title": source.title,
                    "url": source.url,
                    "date": "recent"
                })
            elif source.source_type == "sec_filing":
                citations.append({
                    "type": "filing",
                    "title": f"SEC 10-K: {source.section}",
                    "url": source.source or "SEC EDGAR",
                    "date": source.filing_date
                })

        return citations[:5]  # Return top 5 citations
