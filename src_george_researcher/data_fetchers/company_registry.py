"""
Company Registry for US/Non-US classification.

Uses SEC's company_tickers.json to determine if a ticker is a US company.
US companies are identified by having a CIK (Central Index Key) in the SEC database.
"""

import json
import threading
import logging
import httpx
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from .types import CompanyRegion, DataAvailability, CompanyClassification

logger = logging.getLogger(__name__)

# SEC's company tickers endpoint (free, public API)
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_USER_AGENT = "George Researcher (contact@example.com)"  # SEC requires user agent

# Cache settings
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
CACHE_FILE = CACHE_DIR / "sec_company_tickers.json"
CACHE_MAX_AGE_HOURS = 24 * 7  # Refresh weekly


class CompanyRegistry:
    """
    Registry for company classification (US vs Non-US).

    Uses SEC EDGAR data to identify US-listed companies by CIK.
    Thread-safe with lazy loading of the ticker database.
    """

    def __init__(self):
        self._tickers: Dict[str, dict] = {}  # ticker -> {cik, name, exchange}
        self._ciks: Dict[str, str] = {}  # cik -> ticker
        self._loaded = False
        self._lock = threading.Lock()
        self._load_timestamp: Optional[datetime] = None

    def _ensure_loaded(self):
        """Ensure ticker data is loaded (lazy initialization)."""
        if self._loaded:
            return

        with self._lock:
            if self._loaded:
                return

            # Try loading from cache first
            if self._load_from_cache():
                self._loaded = True
                return

            # Fetch from SEC
            if self._fetch_from_sec():
                self._loaded = True
                return

            # Fallback: Start with empty registry
            logger.warning("Could not load SEC ticker data. US classification may not work.")
            self._loaded = True

    def _load_from_cache(self) -> bool:
        """Load ticker data from local cache file."""
        try:
            if not CACHE_FILE.exists():
                return False

            # Check cache age
            cache_mtime = datetime.fromtimestamp(CACHE_FILE.stat().st_mtime)
            if datetime.now() - cache_mtime > timedelta(hours=CACHE_MAX_AGE_HOURS):
                logger.info("Cache expired, will refresh from SEC")
                return False

            with open(CACHE_FILE, "r") as f:
                data = json.load(f)

            self._parse_sec_data(data)
            self._load_timestamp = cache_mtime
            logger.info(f"Loaded {len(self._tickers)} tickers from cache")
            return True

        except Exception as e:
            logger.warning(f"Failed to load from cache: {e}")
            return False

    def _fetch_from_sec(self) -> bool:
        """Fetch ticker data from SEC EDGAR."""
        try:
            logger.info("Fetching company tickers from SEC EDGAR...")

            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    SEC_TICKERS_URL,
                    headers={"User-Agent": SEC_USER_AGENT}
                )
                response.raise_for_status()
                data = response.json()

            self._parse_sec_data(data)
            self._save_to_cache(data)
            self._load_timestamp = datetime.now()
            logger.info(f"Loaded {len(self._tickers)} tickers from SEC EDGAR")
            return True

        except Exception as e:
            logger.error(f"Failed to fetch from SEC: {e}")
            return False

    def _parse_sec_data(self, data: dict):
        """Parse SEC company_tickers.json format."""
        # Format: {"0": {"cik_str": "320193", "ticker": "AAPL", "title": "Apple Inc."}, ...}
        for entry in data.values():
            ticker = entry.get("ticker", "").upper()
            cik = str(entry.get("cik_str", "")).zfill(10)  # CIK is 10 digits with leading zeros
            name = entry.get("title", "")

            if ticker and cik:
                self._tickers[ticker] = {
                    "cik": cik,
                    "name": name,
                    "exchange": None  # SEC data doesn't include exchange
                }
                self._ciks[cik] = ticker

    def _save_to_cache(self, data: dict):
        """Save ticker data to cache file."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f)
            logger.debug(f"Saved ticker cache to {CACHE_FILE}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def classify(self, ticker: str) -> CompanyClassification:
        """
        Classify a ticker as US or Non-US.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL", "TSMC")

        Returns:
            CompanyClassification with region, CIK (if US), and data availability
        """
        self._ensure_loaded()
        ticker = ticker.upper().strip()

        # Check if ticker is in SEC database
        if ticker in self._tickers:
            info = self._tickers[ticker]
            return CompanyClassification(
                ticker=ticker,
                region=CompanyRegion.US,
                is_us=True,
                cik=info["cik"],
                company_name=info["name"],
                exchange=info.get("exchange"),
                data_availability=DataAvailability.us_full()
            )
        else:
            return CompanyClassification(
                ticker=ticker,
                region=CompanyRegion.NON_US,
                is_us=False,
                cik=None,
                company_name=None,
                exchange=None,
                data_availability=DataAvailability.non_us_limited()
            )

    def is_us_company(self, ticker: str) -> bool:
        """Quick check if ticker is a US company."""
        self._ensure_loaded()
        return ticker.upper().strip() in self._tickers

    def get_cik(self, ticker: str) -> Optional[str]:
        """Get CIK for a US company ticker."""
        self._ensure_loaded()
        info = self._tickers.get(ticker.upper().strip())
        return info["cik"] if info else None

    def get_ticker_by_cik(self, cik: str) -> Optional[str]:
        """Get ticker for a CIK."""
        self._ensure_loaded()
        return self._ciks.get(cik.zfill(10))

    def get_all_us_tickers(self) -> List[str]:
        """
        Get list of all US tickers.

        Useful for autocomplete/validation.
        Returns sorted list of tickers.
        """
        self._ensure_loaded()
        return sorted(self._tickers.keys())

    def search_tickers(self, query: str, limit: int = 20) -> List[dict]:
        """
        Search for tickers/company names matching query.

        Args:
            query: Search string (matches ticker or company name)
            limit: Maximum results to return

        Returns:
            List of {ticker, name, cik} dicts
        """
        self._ensure_loaded()
        query = query.upper().strip()
        results = []

        for ticker, info in self._tickers.items():
            # Match ticker prefix or company name contains
            if ticker.startswith(query) or query in info["name"].upper():
                results.append({
                    "ticker": ticker,
                    "name": info["name"],
                    "cik": info["cik"]
                })
                if len(results) >= limit:
                    break

        return results

    def get_stats(self) -> dict:
        """Get registry statistics."""
        self._ensure_loaded()
        return {
            "total_tickers": len(self._tickers),
            "loaded": self._loaded,
            "load_timestamp": self._load_timestamp.isoformat() if self._load_timestamp else None,
            "cache_file": str(CACHE_FILE),
        }


# Module-level singleton
_REGISTRY_INSTANCE: Optional[CompanyRegistry] = None
_registry_lock = threading.Lock()


def get_company_registry() -> CompanyRegistry:
    """Get the singleton CompanyRegistry instance."""
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        with _registry_lock:
            if _REGISTRY_INSTANCE is None:
                _REGISTRY_INSTANCE = CompanyRegistry()
    return _REGISTRY_INSTANCE
