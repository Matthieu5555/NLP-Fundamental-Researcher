"""
RAG Engine for Smart Data Access.

Provides unified interface for:
- Tavily web search (breaking news)
- SEC filing semantic search (FAISS)
- Query classification (keyword-based routing)
"""

import logging
import os
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Unified RAG engine for smart data retrieval.

    Uses keyword-based query classification to decide which data sources to search.
    Integrates Tavily (web search) and SEC filings (FAISS semantic search).
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

    def __init__(self):
        """Initialize RAG engine."""
        self.tavily_api_key = os.getenv('TAVILY_API_KEY')
        self.tavily_enabled = bool(self.tavily_api_key)

        # Cache for SEC filings (in-memory for session)
        self.sec_filing_cache = {}

        # Directories for data and embeddings
        self.data_dir = Path(__file__).parent.parent.parent / "data"
        self.embeddings_dir = self.data_dir / "embeddings"
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"RAGEngine initialized. Tavily: {self.tavily_enabled}")

    def should_search(self, query: str) -> Dict[str, bool]:
        """
        Determine which searches to run based on query keywords.

        Args:
            query: User query string

        Returns:
            Dict with 'news' and 'filings' boolean flags
        """
        query_lower = query.lower()

        return {
            "news": any(kw in query_lower for kw in self.NEWS_KEYWORDS),
            "filings": any(kw in query_lower for kw in self.FILING_KEYWORDS)
        }

    def retrieve_context(
        self,
        query: str,
        ticker: str,
        company_name: str = None,
        max_results: int = 5
    ) -> Dict:
        """
        Retrieve relevant context from all applicable sources.

        Args:
            query: User query
            ticker: Stock ticker symbol
            company_name: Company name (optional, will use ticker if not provided)
            max_results: Maximum number of results per source

        Returns:
            Dict containing:
                - sources: List of source dicts with type, content, url, etc.
                - search_performed: Boolean indicating if any search was done
                - errors: List of error messages (if any)
        """
        search_flags = self.should_search(query)
        context = {
            "sources": [],
            "search_performed": False,
            "errors": []
        }

        if not company_name:
            company_name = ticker

        # Search news if relevant
        if search_flags["news"] and self.tavily_enabled:
            news_results, news_error = self._search_news(ticker, company_name, max_results)
            if news_results:
                context["sources"].extend(news_results)
                context["search_performed"] = True
            elif news_error:
                context["errors"].append(f"News search: {news_error}")

        # Search SEC filings if relevant
        if search_flags["filings"]:
            filing_results, filing_error = self._search_filings(ticker, query, max_results=3)
            if filing_results:
                context["sources"].extend(filing_results)
                context["search_performed"] = True
            elif filing_error:
                context["errors"].append(f"SEC filing search: {filing_error}")

        return context

    def _search_news(
        self,
        ticker: str,
        company_name: str,
        max_results: int = 5
    ) -> tuple[List[Dict], Optional[str]]:
        """
        Search recent news via Tavily.

        Returns:
            Tuple of (list of news dicts, error message or None)
        """
        try:
            # Import here to avoid circular dependency
            import sys
            from pathlib import Path
            src_path = Path(__file__).parent.parent.parent / "src_george_researcher"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            from data_fetchers.web_search import search_breaking_news

            results, error = search_breaking_news(
                symbol=ticker,
                company_name=company_name,
                api_key=self.tavily_api_key,
                max_results=max_results
            )

            if error:
                return ([], error)

            if not results:
                return ([], None)

            # Format results
            formatted = []
            for result in results.results:
                formatted.append({
                    "type": "news",
                    "title": result.title,
                    "content": result.content,
                    "url": result.url,
                    "score": result.score
                })

            return (formatted, None)

        except Exception as e:
            logger.error(f"News search failed: {e}")
            return ([], str(e))

    def _search_filings(
        self,
        ticker: str,
        query: str,
        max_results: int = 3
    ) -> tuple[List[Dict], Optional[str]]:
        """
        Search SEC filings via existing RAG infrastructure.

        Returns:
            Tuple of (list of filing chunk dicts, error message or None)
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

            # Search the filing
            import sys
            from pathlib import Path
            src_path = Path(__file__).parent.parent.parent / "src_george_researcher"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            from data_fetchers.sec_filings import search_sec_filing

            chunks = search_sec_filing(
                filing=filing_data,
                query=query,
                embeddings_dir=self.embeddings_dir,
                k=max_results
            )

            # Format results
            formatted = []
            for chunk in chunks:
                formatted.append({
                    "type": "sec_filing",
                    "content": chunk.text[:600],  # Truncate to 600 chars
                    "section": chunk.section,
                    "filing_date": chunk.filing_date,
                    "source": chunk.source
                })

            return (formatted, None)

        except Exception as e:
            logger.error(f"SEC filing search failed: {e}")
            return ([], str(e))

    def _fetch_sec_filing(self, ticker: str):
        """
        Fetch SEC 10-K filing for a ticker.

        Returns:
            Tuple of (SECFilingData or None, error message or None)
        """
        try:
            import sys
            from pathlib import Path
            src_path = Path(__file__).parent.parent.parent / "src_george_researcher"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            from data_fetchers.sec_filings import fetch_sec_filing

            filing_data, error = fetch_sec_filing(
                symbol=ticker,
                data_dir=self.data_dir
            )

            return (filing_data, error)

        except Exception as e:
            logger.error(f"SEC filing fetch failed: {e}")
            return (None, str(e))

    def format_context_for_llm(self, context: Dict) -> str:
        """
        Format search results as context block for LLM.

        Args:
            context: Context dict from retrieve_context()

        Returns:
            Formatted string for LLM system prompt
        """
        if not context["sources"]:
            return ""

        formatted_parts = ["## Additional Context from Research\n"]

        # Add news results
        news_results = [s for s in context["sources"] if s["type"] == "news"]
        if news_results:
            formatted_parts.append("### Recent News:\n")
            for source in news_results[:3]:  # Top 3 news items
                formatted_parts.append(f"**{source['title']}**")
                formatted_parts.append(f"{source['content'][:300]}...")
                formatted_parts.append(f"Source: {source['url']}\n")

        # Add SEC filing results
        filing_results = [s for s in context["sources"] if s["type"] == "sec_filing"]
        if filing_results:
            formatted_parts.append("\n### From SEC 10-K Filing:\n")
            for source in filing_results[:3]:  # Top 3 excerpts
                formatted_parts.append(f"**[{source['section']}]** (Filed: {source['filing_date']})")
                formatted_parts.append(f"{source['content'][:400]}...\n")

        return "\n".join(formatted_parts)

    def get_source_citations(self, context: Dict) -> List[Dict]:
        """
        Extract source citations for display in UI.

        Args:
            context: Context dict from retrieve_context()

        Returns:
            List of citation dicts with type, title, url, date
        """
        citations = []

        for source in context["sources"]:
            if source["type"] == "news":
                citations.append({
                    "type": "news",
                    "title": source["title"],
                    "url": source["url"],
                    "date": "recent"
                })
            elif source["type"] == "sec_filing":
                citations.append({
                    "type": "filing",
                    "title": f"SEC 10-K: {source['section']}",
                    "url": source.get("source", "SEC EDGAR"),
                    "date": source["filing_date"]
                })

        return citations[:5]  # Return top 5 citations
