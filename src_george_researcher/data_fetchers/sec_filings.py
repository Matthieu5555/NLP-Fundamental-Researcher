"""
SEC 10-K Filing fetcher and RAG system using FAISS.
Downloads 10-K filings from SEC EDGAR and enables semantic search.

API Info:
- SEC EDGAR API (free, public)
- Requires valid User-Agent with company name and email
- Rate limit: 10 requests/second (we use 0.15s delay between requests)
- No API key required
- Timeout: 30-60 seconds depending on endpoint

Embedding Model:
- Model: all-MiniLM-L6-v2 (sentence-transformers)
- Dimension: 384
- Chosen for: small size (~80MB), fast inference, good quality for semantic search

Thread Safety:
- Global state used for lazy loading (FAISS, sentence-transformers)
- NOT thread-safe - use process-level parallelism if concurrent access needed
- Safe for sequential use within a single process

All functions return (result, error) tuples for consistent error handling.
"""
import httpx
import logging
import re
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
import numpy as np

# Lazy imports for heavy dependencies
# Why globals: FAISS and sentence-transformers have ~2-3s import time.
# Lazy loading avoids this cost when SEC features aren't used.
# Trade-off: Not thread-safe, but acceptable for our sequential use case.
_FAISS = None
_SENTENCE_TRANSFORMER = None

# SEC requires identifying User-Agent
SEC_USER_AGENT = "George Financial Researcher george@research-tool.com"


def _get_FAISS():
    global _FAISS
    if _FAISS is None:
        import faiss
        _FAISS = faiss
    return _FAISS


def _get_encoder():
    """
    Get or initialize the sentence transformer encoder.

    Model: all-MiniLM-L6-v2
    - 384 dimensions, ~80MB model size
    - Good balance of speed and quality for semantic search
    - Widely used, well-tested for document retrieval
    """
    global _SENTENCE_TRANSFORMER
    if _SENTENCE_TRANSFORMER is None:
        from sentence_transformers import SentenceTransformer
        _SENTENCE_TRANSFORMER = SentenceTransformer('all-MiniLM-L6-v2')
    return _SENTENCE_TRANSFORMER


@dataclass(frozen=True)
class FilingChunk:
    """A chunk of text from a SEC filing."""
    text: str
    section: str
    filing_date: str
    source: str
    relevance_score: float = 0.0  # 0-1, higher is more relevant (set during search)


@dataclass(frozen=True)
class SECFilingData:
    """SEC 10-K filing data."""
    symbol: str
    company_name: str
    filing_date: str
    fiscal_year: str
    chunks: list[FilingChunk]
    filing_url: str


def _get_company_tickers() -> dict:
    """Fetch SEC company tickers mapping."""
    try:
        headers = {"User-Agent": SEC_USER_AGENT}
        with httpx.Client(timeout=30.0, headers=headers) as client:
            response = client.get("https://www.sec.gov/files/company_tickers.json")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.debug(f"Failed to fetch SEC company tickers: {e}")
    return {}


def _get_cik_from_ticker(ticker: str) -> Optional[str]:
    """Get SEC CIK number from stock ticker using company tickers file."""
    try:
        tickers = _get_company_tickers()
        ticker_upper = ticker.upper()

        for entry in tickers.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                cik = str(entry.get("cik_str", ""))
                return cik.zfill(10)

        return None
    except Exception as e:
        logger.debug(f"Failed to get CIK for ticker: {e}")
        return None


def _fetch_10k_filing(ticker: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Fetch the most recent 10-K filing from SEC EDGAR.

    Returns:
        Tuple of (filing_text, filing_date, filing_url, company_name) or (None, None, None, None) on error
    """
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }

    try:
        # Get CIK from ticker
        cik = _get_cik_from_ticker(ticker)
        if not cik:
            return (None, None, None, None)

        # Rate limiting - SEC requires max 10 requests per second
        time.sleep(0.15)

        # Get company submissions
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"

        with httpx.Client(timeout=30.0, headers=headers) as client:
            response = client.get(submissions_url)

        if response.status_code != 200:
            return (None, None, None, None)

        data = response.json()
        company_name = data.get("name", ticker)
        filings = data.get("filings", {}).get("recent", {})

        # Find most recent 10-K
        forms = filings.get("form", [])
        accession_numbers = filings.get("accessionNumber", [])
        filing_dates = filings.get("filingDate", [])
        primary_docs = filings.get("primaryDocument", [])

        for i, form in enumerate(forms):
            if form == "10-K":
                accession = accession_numbers[i].replace("-", "")
                filing_date = filing_dates[i]
                primary_doc = primary_docs[i]
                cik_clean = cik.lstrip("0") or "0"

                # Construct document URL
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession}/{primary_doc}"

                # Rate limiting
                time.sleep(0.15)

                # Fetch the filing document
                doc_headers = {
                    "User-Agent": SEC_USER_AGENT,
                    "Accept-Encoding": "gzip, deflate",
                    "Host": "www.sec.gov",
                }

                with httpx.Client(timeout=60.0, headers=doc_headers) as client:
                    doc_response = client.get(doc_url)

                if doc_response.status_code == 200:
                    return (doc_response.text, filing_date, doc_url, company_name)

                break

        return (None, None, None, None)

    except Exception:
        return (None, None, None, None)


def _extract_sections_from_html(html_text: str) -> dict[str, str]:
    """Extract key sections from 10-K HTML using BeautifulSoup-like parsing."""
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = []

        def handle_data(self, data):
            self.text.append(data)

        def get_text(self):
            return ' '.join(self.text)

    # Extract text from HTML
    try:
        extractor = TextExtractor()
        extractor.feed(html_text[:1000000])  # Limit size
        text = extractor.get_text()
    except Exception as e:
        logger.debug(f"HTML parsing failed, using regex fallback: {e}")
        text = re.sub(r'<[^>]+>', ' ', html_text)

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text[:500000]

    sections = {}

    # Try to identify common 10-K sections using flexible patterns
    section_patterns = [
        (r'(?:Item|ITEM)\s*1\.?\s*(?:Business|BUSINESS)(.{3000,60000}?)(?=(?:Item|ITEM)\s*1A|(?:Item|ITEM)\s*2|$)', "Business"),
        (r'(?:Item|ITEM)\s*1A\.?\s*(?:Risk\s*Factors|RISK\s*FACTORS)(.{3000,80000}?)(?=(?:Item|ITEM)\s*1B|(?:Item|ITEM)\s*2|$)', "Risk Factors"),
        (r'(?:Item|ITEM)\s*7\.?\s*(?:Management|MANAGEMENT).{0,60}(?:Discussion|DISCUSSION)(.{3000,80000}?)(?=(?:Item|ITEM)\s*7A|(?:Item|ITEM)\s*8|$)', "MD&A"),
        (r'(?:Item|ITEM)\s*8\.?\s*(?:Financial\s*Statements|FINANCIAL\s*STATEMENTS)(.{3000,40000}?)(?=(?:Item|ITEM)\s*9|$)', "Financial Statements"),
    ]

    for pattern, section_name in section_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            content = match.group(1).strip()[:25000]
            if len(content) > 500:  # Only include if substantial
                sections[section_name] = content

    # If no sections found, just use the full text
    if not sections:
        if len(text) > 1000:
            sections["Full Filing"] = text[:80000]

    return sections


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """
    Split text into overlapping chunks for embedding.

    Chunking Strategy:
    - chunk_size=1000 chars (~200-250 tokens) fits well in embedding context
    - overlap=100 chars preserves context across chunk boundaries
    - Sentence boundary detection avoids mid-sentence splits when possible
    - Minimum chunk size of 50 chars filters out noise

    Args:
        text: Input text to chunk
        chunk_size: Target size per chunk in characters
        overlap: Overlap between consecutive chunks

    Returns:
        List of text chunks
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind('.')
            if last_period > chunk_size * 0.5:
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1

        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if len(c) > 50]


def fetch_sec_filing(
    symbol: str,
    data_dir: Path,
) -> tuple[Optional[SECFilingData], Optional[str]]:
    """
    Fetch and process SEC 10-K filing for a symbol.

    Args:
        symbol: Stock ticker
        data_dir: Directory to cache filings

    Returns:
        Tuple of (SECFilingData or None, error message or None)
    """
    cache_file = data_dir / f"{symbol.upper()}_10k_cache.json"

    # Check cache (valid for 30 days)
    if cache_file.exists():
        try:
            import os
            cache_age = time.time() - os.path.getmtime(cache_file)
            if cache_age < 30 * 24 * 3600:  # 30 days
                with open(cache_file) as f:
                    cached = json.load(f)
                    chunks = [FilingChunk(**c) for c in cached["chunks"]]
                    return (
                        SECFilingData(
                            symbol=cached["symbol"],
                            company_name=cached["company_name"],
                            filing_date=cached["filing_date"],
                            fiscal_year=cached["fiscal_year"],
                            chunks=chunks,
                            filing_url=cached["filing_url"],
                        ),
                        None,
                    )
        except Exception as e:
            logger.debug(f"SEC cache invalid, fetching fresh: {e}")

    # Fetch from SEC
    text, filing_date, url, company_name = _fetch_10k_filing(symbol)

    if not text:
        return (None, f"Could not fetch 10-K filing for {symbol}. The company may not have SEC filings or the ticker may be incorrect.")

    # Extract sections
    sections = _extract_sections_from_html(text)

    if not sections:
        return (None, f"Could not extract content from 10-K filing for {symbol}")

    # Create chunks
    all_chunks = []
    for section_name, section_text in sections.items():
        text_chunks = _chunk_text(section_text)
        for chunk_text in text_chunks:
            all_chunks.append(FilingChunk(
                text=chunk_text,
                section=section_name,
                filing_date=filing_date or "Unknown",
                source=url or "SEC EDGAR",
            ))

    if not all_chunks:
        return (None, "No content extracted from 10-K filing")

    filing_data = SECFilingData(
        symbol=symbol.upper(),
        company_name=company_name or symbol.upper(),
        filing_date=filing_date or "Unknown",
        fiscal_year=filing_date[:4] if filing_date else "Unknown",
        chunks=all_chunks,
        filing_url=url or "",
    )

    # Cache the result
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "symbol": filing_data.symbol,
            "company_name": filing_data.company_name,
            "filing_date": filing_data.filing_date,
            "fiscal_year": filing_data.fiscal_year,
            "filing_url": filing_data.filing_url,
            "chunks": [
                {"text": c.text, "section": c.section, "filing_date": c.filing_date, "source": c.source}
                for c in all_chunks
            ],
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        logger.debug(f"Failed to cache SEC filing: {e}")

    return (filing_data, None)


class SECVectorStore:
    """FAISS-based vector store for SEC filings."""

    def __init__(self, embeddings_dir: Path):
        self.embeddings_dir = embeddings_dir
        self.index = None
        self.chunks: list[FilingChunk] = []
        self.encoder = None

    def _get_encoder(self):
        if self.encoder is None:
            self.encoder = _get_encoder()
        return self.encoder

    def build_index(self, filing: SECFilingData) -> None:
        """Build FAISS index from filing chunks."""
        faiss = _get_FAISS()
        encoder = self._get_encoder()

        self.chunks = list(filing.chunks)

        # Generate embeddings
        texts = [c.text for c in self.chunks]
        embeddings = encoder.encode(texts, show_progress_bar=False)

        # Build FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings.astype('float32'))

    def search(self, query: str, k: int = 5, min_relevance: float = 0.0) -> list[FilingChunk]:
        """
        Search for relevant chunks with relevance scoring.

        Args:
            query: Search query
            k: Maximum number of results
            min_relevance: Minimum relevance score (0-1) to include results

        Returns:
            List of FilingChunks with relevance_score set, filtered by min_relevance
        """
        if self.index is None or not self.chunks:
            return []

        encoder = self._get_encoder()

        # Encode query
        query_embedding = encoder.encode([query], show_progress_bar=False)

        # Search - FAISS returns L2 distances (lower = more similar)
        distances, indices = self.index.search(query_embedding.astype('float32'), k)

        # Convert L2 distances to relevance scores (0-1, higher = better)
        # Using exponential decay: score = exp(-distance / scale)
        # Typical L2 distances for MiniLM range from 0 (identical) to ~2 (unrelated)
        results = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(self.chunks):
                distance = distances[0][i]
                # Convert distance to 0-1 relevance score
                # distance=0 -> score=1.0, distance=1.5 -> score~0.22, distance=2 -> score~0.13
                relevance_score = float(np.exp(-distance / 1.0))

                if relevance_score >= min_relevance:
                    chunk = self.chunks[idx]
                    # Create new chunk with relevance score
                    results.append(FilingChunk(
                        text=chunk.text,
                        section=chunk.section,
                        filing_date=chunk.filing_date,
                        source=chunk.source,
                        relevance_score=relevance_score
                    ))

        return results


def search_sec_filing(
    filing: SECFilingData,
    query: str,
    embeddings_dir: Path,
    k: int = 5,
    min_relevance: float = 0.0,
) -> list[FilingChunk]:
    """
    Search SEC filing for relevant content.

    Args:
        filing: SECFilingData to search
        query: Search query
        embeddings_dir: Directory for embeddings cache
        k: Number of results
        min_relevance: Minimum relevance score (0-1) to include results

    Returns:
        List of relevant FilingChunks with relevance_score set
    """
    store = SECVectorStore(embeddings_dir)
    store.build_index(filing)
    return store.search(query, k, min_relevance=min_relevance)


def format_sec_context(chunks: list[FilingChunk], max_chars: int = 3000) -> str:
    """Format SEC filing chunks as context for LLM."""
    lines = ["SEC 10-K Filing Excerpts", "-" * 30, ""]

    total_chars = 0
    for i, chunk in enumerate(chunks, 1):
        if total_chars >= max_chars:
            break

        section_header = f"[{chunk.section}] (Filed: {chunk.filing_date})"
        lines.append(section_header)
        lines.append(chunk.text[:800])
        lines.append("")

        total_chars += len(chunk.text[:800])

    return "\n".join(lines)
