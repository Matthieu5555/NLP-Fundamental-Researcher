"""
Data Router for US/Non-US company data fetching.

Routes data fetch requests to appropriate sources based on company region:
- US companies: FinancialDatasets.ai for rich financial data
- Non-US companies: yfinance, Alpha Vantage, etc.

This module also provides backward-compatible wrapper functions for
existing code that imports directly from data fetchers.
"""

import logging
from typing import Optional, Tuple, Any, List

from .types import CompanyClassification
from .company_registry import get_company_registry

logger = logging.getLogger(__name__)


class DataRouter:
    """
    Routes data fetching to appropriate source based on company region.

    Provides a unified interface for fetching stock data, routing to either
    US-specific (FinancialDatasets.ai) or global (yfinance) data sources.
    """

    def __init__(self):
        self._registry = get_company_registry()

    def classify(self, ticker: str) -> CompanyClassification:
        """
        Classify a ticker as US or Non-US.

        Args:
            ticker: Stock ticker symbol

        Returns:
            CompanyClassification with region and data availability info
        """
        return self._registry.classify(ticker)

    def is_us_company(self, ticker: str) -> bool:
        """Quick check if ticker is a US company."""
        return self._registry.is_us_company(ticker)

    def fetch_stock_info(self, ticker: str) -> Tuple[Optional[Any], Optional[str]]:
        """
        Fetch basic stock info, routing to appropriate source.

        US companies use FinancialDatasets.ai for richer data.
        Non-US companies use yfinance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            (StockInfo or CompanyFacts, error) tuple - error is None on success
        """
        classification = self.classify(ticker)

        if classification.is_us:
            # Try FDS first for US companies
            result, error = self._fetch_stock_info_fds(ticker)
            if result:
                logger.debug(f"US company {ticker}: Using FinancialDatasets.ai")
                return result, None
            # Fall back to yfinance if FDS fails
            logger.debug(f"US company {ticker}: FDS failed ({error}), falling back to yfinance")
            return self._fetch_stock_info_yfinance(ticker)
        else:
            logger.debug(f"Non-US company {ticker}: Using yfinance")
            return self._fetch_stock_info_yfinance(ticker)

    def _fetch_stock_info_fds(self, ticker: str) -> Tuple[Optional[Any], Optional[str]]:
        """Fetch stock info using FinancialDatasets.ai."""
        from .us.financial_datasets_client import get_fds_client
        client = get_fds_client()
        if not client.is_available:
            return None, "FDS API key not configured"
        return client.get_company_facts(ticker)

    def _fetch_stock_info_yfinance(self, ticker: str) -> Tuple[Optional[Any], Optional[str]]:
        """Fetch stock info using yfinance."""
        from .stock_data import fetch_stock_info
        return fetch_stock_info(ticker)

    def fetch_historical_prices(
        self,
        ticker: str,
        period: str = "1y"
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Fetch historical price data, routing to appropriate source.

        Args:
            ticker: Stock ticker symbol
            period: Time period (e.g., "1y", "6mo", "3mo")

        Returns:
            (DataFrame or List[PriceData], error) tuple - error is None on success
        """
        classification = self.classify(ticker)

        if classification.is_us:
            # Try FDS first for US companies
            result, error = self._fetch_historical_fds(ticker, period)
            if result:
                logger.debug(f"US company {ticker}: Using FinancialDatasets.ai for prices")
                return result, None
            # Fall back to yfinance if FDS fails
            logger.debug(f"US company {ticker}: FDS prices failed ({error}), falling back to yfinance")
            return self._fetch_historical_yfinance(ticker, period)
        else:
            logger.debug(f"Non-US company {ticker}: Using yfinance for prices")
            return self._fetch_historical_yfinance(ticker, period)

    def _fetch_historical_fds(
        self,
        ticker: str,
        period: str
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Fetch historical prices using FinancialDatasets.ai."""
        from .us.financial_datasets_client import get_fds_client
        client = get_fds_client()
        if not client.is_available:
            return None, "FDS API key not configured"

        # Convert period to limit (days)
        period_map = {"1y": 365, "6mo": 180, "3mo": 90, "1mo": 30, "5d": 5}
        limit = period_map.get(period, 365)

        return client.get_prices(ticker, limit=limit)

    def _fetch_historical_yfinance(
        self,
        ticker: str,
        period: str
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Fetch historical prices using yfinance."""
        from .stock_data import fetch_historical_data
        return fetch_historical_data(ticker, period)

    def fetch_technical_indicators(
        self,
        ticker: str,
        period: str = "1y"
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Fetch technical indicators, routing to appropriate source.

        Technical indicators are calculated the same way regardless of source.
        """
        from .stock_data import calculate_technical_indicators
        return calculate_technical_indicators(ticker, period)

    def fetch_news(
        self,
        ticker: str,
        limit: int = 10
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Fetch news for a ticker.

        US companies use FDS news endpoint with sentiment.
        Non-US companies use Gemini search or other sources.
        """
        classification = self.classify(ticker)

        if classification.is_us:
            # Try FDS first for US companies
            result, error = self._fetch_news_fds(ticker, limit)
            if result:
                logger.debug(f"US company {ticker}: Using FinancialDatasets.ai for news")
                return result, None
            # Fall back to combined news fetcher
            logger.debug(f"US company {ticker}: FDS news failed ({error}), falling back to combined")
            return self._fetch_news_combined(ticker, limit)
        else:
            logger.debug(f"Non-US company {ticker}: Using combined news sources")
            return self._fetch_news_combined(ticker, limit)

    def _fetch_news_fds(
        self,
        ticker: str,
        limit: int
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Fetch news using FinancialDatasets.ai."""
        from .us.financial_datasets_client import get_fds_client
        client = get_fds_client()
        if not client.is_available:
            return None, "FDS API key not configured"
        return client.get_news(ticker, limit=limit)

    def _fetch_news_combined(
        self,
        ticker: str,
        limit: int
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Fetch news using existing combined news fetcher."""
        from .news import fetch_combined_news
        return fetch_combined_news(ticker, max_results=limit)

    # =========================================================================
    # US-Only Data Methods (FinancialDatasets.ai)
    # =========================================================================

    def fetch_financials(
        self,
        ticker: str,
        period: str = "annual",
        limit: int = 5
    ) -> Tuple[Optional[List], Optional[str]]:
        """
        Fetch detailed financial statements (US companies only).

        Args:
            ticker: Stock ticker symbol
            period: "annual" or "quarterly"
            limit: Number of periods to fetch

        Returns:
            (List[FinancialStatement], error) tuple
        """
        classification = self.classify(ticker)

        if not classification.is_us:
            return None, f"{ticker} is not a US company - detailed financials not available"

        from .us.financial_datasets_client import get_fds_client
        client = get_fds_client()
        if not client.is_available:
            return None, "FDS API key not configured"

        return client.get_financials(ticker, period=period, limit=limit)

    def fetch_insider_trades(
        self,
        ticker: str,
        limit: int = 50
    ) -> Tuple[Optional[List], Optional[str]]:
        """
        Fetch insider trading activity (US companies only).

        Args:
            ticker: Stock ticker symbol
            limit: Number of trades to fetch

        Returns:
            (List[InsiderTrade], error) tuple
        """
        classification = self.classify(ticker)

        if not classification.is_us:
            return None, f"{ticker} is not a US company - insider trades not available"

        from .us.financial_datasets_client import get_fds_client
        client = get_fds_client()
        if not client.is_available:
            return None, "FDS API key not configured"

        return client.get_insider_trades(ticker, limit=limit)

    def fetch_analyst_estimates(
        self,
        ticker: str,
        limit: int = 8
    ) -> Tuple[Optional[List], Optional[str]]:
        """
        Fetch analyst consensus estimates (US companies only).

        Args:
            ticker: Stock ticker symbol
            limit: Number of periods to fetch

        Returns:
            (List[AnalystEstimate], error) tuple
        """
        classification = self.classify(ticker)

        if not classification.is_us:
            return None, f"{ticker} is not a US company - analyst estimates not available"

        from .us.financial_datasets_client import get_fds_client
        client = get_fds_client()
        if not client.is_available:
            return None, "FDS API key not configured"

        return client.get_analyst_estimates(ticker, limit=limit)

    def fetch_sec_filings(
        self,
        ticker: str
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Fetch SEC filings for a US company.

        Returns error for non-US companies.
        """
        classification = self.classify(ticker)

        if not classification.is_us:
            return None, f"{ticker} is not a US company - SEC filings not available"

        # TODO: After FDS integration, use FDS SEC endpoint
        # For now, use existing SEC EDGAR fetcher
        from .sec_filings import fetch_sec_filing
        return fetch_sec_filing(ticker)

    def get_data_availability(self, ticker: str) -> dict:
        """
        Get data availability info for a ticker.

        Returns dict with available/unavailable features.
        """
        classification = self.classify(ticker)
        return classification.to_dict()


# Module-level singleton
_ROUTER_INSTANCE: Optional[DataRouter] = None


def get_data_router() -> DataRouter:
    """Get the singleton DataRouter instance."""
    global _ROUTER_INSTANCE
    if _ROUTER_INSTANCE is None:
        _ROUTER_INSTANCE = DataRouter()
    return _ROUTER_INSTANCE


# =============================================================================
# Backward Compatibility Functions
# =============================================================================
# These functions allow existing code to continue working while we migrate
# to the router-based approach.

def classify_company(ticker: str) -> CompanyClassification:
    """
    Classify a ticker as US or Non-US.

    Backward-compatible wrapper for DataRouter.classify().
    """
    return get_data_router().classify(ticker)


def is_us_company(ticker: str) -> bool:
    """
    Check if a ticker is a US company.

    Backward-compatible wrapper for DataRouter.is_us_company().
    """
    return get_data_router().is_us_company(ticker)


def get_data_availability(ticker: str) -> dict:
    """
    Get data availability info for a ticker.

    Backward-compatible wrapper for DataRouter.get_data_availability().
    """
    return get_data_router().get_data_availability(ticker)
