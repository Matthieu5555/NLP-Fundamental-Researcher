"""
FinancialDatasets.ai API Client

Provides access to comprehensive US company financial data including:
- Company facts (FREE)
- Financial statements ($0.02/req)
- Historical prices ($0.01/req)
- Insider trades ($0.02/req)
- Analyst estimates ($0.02/req)
- News with sentiment ($0.02/req)

API Documentation: https://docs.financialdatasets.ai/
Rate Limits: 1,000 requests/minute
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List
import requests

from ..cache import cached

logger = logging.getLogger(__name__)

# API Configuration
FDS_BASE_URL = "https://api.financialdatasets.ai"
FDS_TIMEOUT = 30  # seconds


@dataclass
class CompanyFacts:
    """Company facts from FinancialDatasets.ai"""
    ticker: str
    name: str
    cik: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    exchange: Optional[str] = None
    is_active: bool = True
    market_cap: Optional[float] = None
    number_of_employees: Optional[int] = None
    website_url: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "cik": self.cik,
            "industry": self.industry,
            "sector": self.sector,
            "exchange": self.exchange,
            "is_active": self.is_active,
            "market_cap": self.market_cap,
            "number_of_employees": self.number_of_employees,
            "website_url": self.website_url,
            "description": self.description,
        }


@dataclass
class FinancialStatement:
    """Financial statement data"""
    ticker: str
    report_period: str
    period: str  # "annual" or "quarterly"
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None

    # Income Statement
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_expenses: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    earnings_per_share: Optional[float] = None
    earnings_per_share_diluted: Optional[float] = None
    depreciation_and_amortization: Optional[float] = None
    interest_expense: Optional[float] = None
    stock_based_compensation: Optional[float] = None

    # Balance Sheet
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    total_debt: Optional[float] = None

    # Cash Flow
    operating_cash_flow: Optional[float] = None
    investing_cash_flow: Optional[float] = None
    financing_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None
    capital_expenditure: Optional[float] = None


@dataclass
class PriceData:
    """Historical price data"""
    ticker: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: Optional[float] = None


@dataclass
class InsiderTrade:
    """Insider trading activity"""
    ticker: str
    filing_date: str
    insider_name: str
    transaction_type: str  # "buy", "sell", "gift", etc.
    shares: float
    trade_date: Optional[str] = None
    insider_title: Optional[str] = None
    price_per_share: Optional[float] = None
    total_value: Optional[float] = None


@dataclass
class AnalystEstimate:
    """Analyst consensus estimates"""
    ticker: str
    fiscal_year: int
    period_end_date: str
    fiscal_quarter: Optional[int] = None
    eps_estimate_avg: Optional[float] = None
    eps_estimate_high: Optional[float] = None
    eps_estimate_low: Optional[float] = None
    eps_estimate_count: Optional[int] = None
    revenue_estimate_avg: Optional[float] = None
    revenue_estimate_high: Optional[float] = None
    revenue_estimate_low: Optional[float] = None


@dataclass
class NewsArticle:
    """News article with sentiment"""
    ticker: str
    title: str
    url: str
    published_at: str
    source: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[str] = None  # "positive", "negative", "neutral"
    sentiment_score: Optional[float] = None


class FDSClient:
    """
    FinancialDatasets.ai API Client

    Usage:
        client = FDSClient(api_key="your-key")
        facts, error = client.get_company_facts("AAPL")
        financials, error = client.get_financials("AAPL", period="annual")
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FDS client.

        Args:
            api_key: FDS API key. If not provided, reads from FDS_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("FDS_API_KEY")
        if not self.api_key:
            logger.warning("FDS_API_KEY not set - FinancialDatasets.ai features disabled")

        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            })

    @property
    def is_available(self) -> bool:
        """Check if FDS API is available (API key configured)."""
        return bool(self.api_key)

    def _request(
        self,
        endpoint: str,
        params: Optional[dict] = None
    ) -> Tuple[Optional[dict], Optional[str]]:
        """
        Make API request to FDS.

        Args:
            endpoint: API endpoint (e.g., "/company/facts")
            params: Query parameters

        Returns:
            (response_data, error) tuple
        """
        if not self.is_available:
            return None, "FDS API key not configured"

        url = f"{FDS_BASE_URL}{endpoint}"

        try:
            response = self._session.get(url, params=params, timeout=FDS_TIMEOUT)

            if response.status_code == 401:
                return None, "Invalid FDS API key"
            elif response.status_code == 404:
                return None, f"Not found: {endpoint}"
            elif response.status_code == 429:
                return None, "Rate limit exceeded (1000/min)"
            elif response.status_code != 200:
                return None, f"API error: {response.status_code} - {response.text}"

            return response.json(), None

        except requests.exceptions.Timeout:
            return None, f"Request timeout after {FDS_TIMEOUT}s"
        except requests.exceptions.RequestException as e:
            return None, f"Request failed: {str(e)}"
        except ValueError as e:
            return None, f"Invalid JSON response: {str(e)}"

    def get_company_facts(self, ticker: str) -> Tuple[Optional[CompanyFacts], Optional[str]]:
        """
        Fetch company facts (FREE endpoint).

        Args:
            ticker: Stock ticker symbol

        Returns:
            (CompanyFacts, error) tuple
        """
        data, error = self._request("/company/facts", {"ticker": ticker})

        if error:
            return None, error

        if not data or "company_facts" not in data:
            return None, f"No company facts found for {ticker}"

        facts = data["company_facts"]
        return CompanyFacts(
            ticker=facts.get("ticker", ticker),
            name=facts.get("name", ticker),
            cik=facts.get("cik"),
            industry=facts.get("industry"),
            sector=facts.get("sector"),
            exchange=facts.get("exchange"),
            is_active=facts.get("is_active", True),
            market_cap=facts.get("market_cap"),
            number_of_employees=facts.get("number_of_employees"),
            website_url=facts.get("website_url"),
            description=facts.get("description"),
        ), None

    def get_financials(
        self,
        ticker: str,
        period: str = "annual",
        limit: int = 5
    ) -> Tuple[Optional[List[FinancialStatement]], Optional[str]]:
        """
        Fetch financial statements ($0.02/request).

        Args:
            ticker: Stock ticker symbol
            period: "annual" or "quarterly"
            limit: Number of periods to fetch

        Returns:
            (List[FinancialStatement], error) tuple
        """
        data, error = self._request("/financials", {
            "ticker": ticker,
            "period": period,
            "limit": limit,
        })

        if error:
            return None, error

        if not data or "financials" not in data:
            return None, f"No financials found for {ticker}"

        financials_data = data["financials"]
        statements = []

        # Parse income statements
        income_stmts = financials_data.get("income_statements", [])
        balance_sheets = financials_data.get("balance_sheets", [])
        cash_flows = financials_data.get("cash_flow_statements", [])

        # Merge by report_period
        periods = {}
        for stmt in income_stmts:
            period_key = stmt.get("report_period")
            if period_key:
                periods[period_key] = {
                    "ticker": ticker,
                    "report_period": period_key,
                    "period": stmt.get("period", period),
                    "fiscal_year": stmt.get("fiscal_year"),
                    "fiscal_quarter": stmt.get("fiscal_quarter"),
                    "revenue": stmt.get("revenue"),
                    "cost_of_revenue": stmt.get("cost_of_revenue"),
                    "gross_profit": stmt.get("gross_profit"),
                    "operating_expenses": stmt.get("operating_expenses"),
                    "operating_income": stmt.get("operating_income"),
                    "net_income": stmt.get("net_income"),
                    "earnings_per_share": stmt.get("earnings_per_share"),
                    "earnings_per_share_diluted": stmt.get("earnings_per_share_diluted"),
                    "depreciation_and_amortization": stmt.get("depreciation_and_amortization"),
                    "interest_expense": stmt.get("interest_expense"),
                    "stock_based_compensation": stmt.get("stock_based_compensation"),
                }

        for stmt in balance_sheets:
            period_key = stmt.get("report_period")
            if period_key and period_key in periods:
                periods[period_key].update({
                    "total_assets": stmt.get("total_assets"),
                    "total_liabilities": stmt.get("total_liabilities"),
                    "total_equity": stmt.get("total_equity"),
                    "cash_and_equivalents": stmt.get("cash_and_equivalents"),
                    "total_debt": stmt.get("total_debt"),
                })

        for stmt in cash_flows:
            period_key = stmt.get("report_period")
            if period_key and period_key in periods:
                periods[period_key].update({
                    "operating_cash_flow": stmt.get("operating_cash_flow"),
                    "investing_cash_flow": stmt.get("investing_cash_flow"),
                    "financing_cash_flow": stmt.get("financing_cash_flow"),
                    "free_cash_flow": stmt.get("free_cash_flow"),
                    "capital_expenditure": stmt.get("capital_expenditure"),
                })
                # D&A and SBC often come from cash flow statements if not on income statement
                if not periods[period_key].get("depreciation_and_amortization"):
                    periods[period_key]["depreciation_and_amortization"] = stmt.get("depreciation_and_amortization")
                if not periods[period_key].get("stock_based_compensation"):
                    periods[period_key]["stock_based_compensation"] = stmt.get("stock_based_compensation")

        for period_data in periods.values():
            statements.append(FinancialStatement(**period_data))

        return sorted(statements, key=lambda x: x.report_period, reverse=True), None

    def get_prices(
        self,
        ticker: str,
        limit: int = 365,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Tuple[Optional[List[PriceData]], Optional[str]]:
        """
        Fetch historical prices ($0.01/request).

        Args:
            ticker: Stock ticker symbol
            limit: Number of days to fetch
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            (List[PriceData], error) tuple
        """
        params = {"ticker": ticker, "limit": limit}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data, error = self._request("/prices", params)

        if error:
            return None, error

        if not data or "prices" not in data:
            return None, f"No price data found for {ticker}"

        prices = []
        for p in data["prices"]:
            prices.append(PriceData(
                ticker=ticker,
                date=p.get("date", ""),
                open=p.get("open", 0),
                high=p.get("high", 0),
                low=p.get("low", 0),
                close=p.get("close", 0),
                volume=p.get("volume", 0),
                adjusted_close=p.get("adj_close"),
            ))

        return sorted(prices, key=lambda x: x.date, reverse=True), None

    def get_insider_trades(
        self,
        ticker: str,
        limit: int = 50
    ) -> Tuple[Optional[List[InsiderTrade]], Optional[str]]:
        """
        Fetch insider trading activity ($0.02/request).

        Args:
            ticker: Stock ticker symbol
            limit: Number of trades to fetch

        Returns:
            (List[InsiderTrade], error) tuple
        """
        data, error = self._request("/insider-trades", {
            "ticker": ticker,
            "limit": limit,
        })

        if error:
            return None, error

        if not data or "insider_trades" not in data:
            return None, f"No insider trades found for {ticker}"

        trades = []
        for t in data["insider_trades"]:
            trades.append(InsiderTrade(
                ticker=ticker,
                filing_date=t.get("filing_date", ""),
                trade_date=t.get("trade_date"),
                insider_name=t.get("insider_name", "Unknown"),
                insider_title=t.get("insider_title"),
                transaction_type=t.get("transaction_type", "unknown"),
                shares=t.get("shares", 0),
                price_per_share=t.get("price_per_share"),
                total_value=t.get("total_value"),
            ))

        return sorted(trades, key=lambda x: x.filing_date, reverse=True), None

    def get_analyst_estimates(
        self,
        ticker: str,
        limit: int = 8
    ) -> Tuple[Optional[List[AnalystEstimate]], Optional[str]]:
        """
        Fetch analyst consensus estimates ($0.02/request).

        Args:
            ticker: Stock ticker symbol
            limit: Number of periods to fetch

        Returns:
            (List[AnalystEstimate], error) tuple
        """
        data, error = self._request("/analyst-estimates", {
            "ticker": ticker,
            "limit": limit,
        })

        if error:
            return None, error

        if not data or "analyst_estimates" not in data:
            return None, f"No analyst estimates found for {ticker}"

        estimates = []
        for e in data["analyst_estimates"]:
            estimates.append(AnalystEstimate(
                ticker=ticker,
                fiscal_year=e.get("fiscal_year", 0),
                fiscal_quarter=e.get("fiscal_quarter"),
                period_end_date=e.get("period_end_date", ""),
                eps_estimate_avg=e.get("eps_estimate_avg"),
                eps_estimate_high=e.get("eps_estimate_high"),
                eps_estimate_low=e.get("eps_estimate_low"),
                eps_estimate_count=e.get("eps_estimate_count"),
                revenue_estimate_avg=e.get("revenue_estimate_avg"),
                revenue_estimate_high=e.get("revenue_estimate_high"),
                revenue_estimate_low=e.get("revenue_estimate_low"),
            ))

        return sorted(estimates, key=lambda x: (x.fiscal_year, x.fiscal_quarter or 0), reverse=True), None

    def get_news(
        self,
        ticker: str,
        limit: int = 10
    ) -> Tuple[Optional[List[NewsArticle]], Optional[str]]:
        """
        Fetch company news with sentiment ($0.02/request).

        Args:
            ticker: Stock ticker symbol
            limit: Number of articles to fetch

        Returns:
            (List[NewsArticle], error) tuple
        """
        data, error = self._request("/news", {
            "ticker": ticker,
            "limit": limit,
        })

        if error:
            return None, error

        if not data or "news" not in data:
            return None, f"No news found for {ticker}"

        articles = []
        for n in data["news"]:
            articles.append(NewsArticle(
                ticker=ticker,
                title=n.get("title", ""),
                url=n.get("url", ""),
                published_at=n.get("published_at", ""),
                source=n.get("source"),
                summary=n.get("summary"),
                sentiment=n.get("sentiment"),
                sentiment_score=n.get("sentiment_score"),
            ))

        return sorted(articles, key=lambda x: x.published_at, reverse=True), None

    def get_available_tickers(self) -> Tuple[Optional[List[str]], Optional[str]]:
        """
        Fetch list of available US tickers (FREE endpoint).

        Returns:
            (List[str], error) tuple
        """
        data, error = self._request("/analyst-estimates/tickers/")

        if error:
            return None, error

        if not data or "tickers" not in data:
            return None, "Could not fetch available tickers"

        return data["tickers"], None


# Module-level singleton
_CLIENT_INSTANCE: Optional[FDSClient] = None


def get_fds_client() -> FDSClient:
    """Get the singleton FDS client instance."""
    global _CLIENT_INSTANCE
    if _CLIENT_INSTANCE is None:
        _CLIENT_INSTANCE = FDSClient()
    return _CLIENT_INSTANCE


# =============================================================================
# Convenience Functions
# =============================================================================

@cached("fds_company_facts", ticker_param="ticker")
def fetch_company_facts(ticker: str) -> Tuple[Optional[CompanyFacts], Optional[str]]:
    """Fetch company facts for a US company."""
    return get_fds_client().get_company_facts(ticker)


@cached("fds_financials", ticker_param="ticker")
def fetch_financials(
    ticker: str,
    period: str = "annual",
    limit: int = 5
) -> Tuple[Optional[List[FinancialStatement]], Optional[str]]:
    """Fetch financial statements for a US company."""
    return get_fds_client().get_financials(ticker, period, limit)


@cached("fds_prices", ticker_param="ticker")
def fetch_prices(
    ticker: str,
    limit: int = 365
) -> Tuple[Optional[List[PriceData]], Optional[str]]:
    """Fetch historical prices for a US company."""
    return get_fds_client().get_prices(ticker, limit)


@cached("fds_insider_trades", ticker_param="ticker")
def fetch_insider_trades(
    ticker: str,
    limit: int = 50
) -> Tuple[Optional[List[InsiderTrade]], Optional[str]]:
    """Fetch insider trades for a US company."""
    return get_fds_client().get_insider_trades(ticker, limit)


@cached("fds_analyst_estimates", ticker_param="ticker")
def fetch_analyst_estimates(
    ticker: str,
    limit: int = 8
) -> Tuple[Optional[List[AnalystEstimate]], Optional[str]]:
    """Fetch analyst estimates for a US company."""
    return get_fds_client().get_analyst_estimates(ticker, limit)


@cached("fds_news", ticker_param="ticker")
def fetch_news(
    ticker: str,
    limit: int = 10
) -> Tuple[Optional[List[NewsArticle]], Optional[str]]:
    """Fetch news for a US company."""
    return get_fds_client().get_news(ticker, limit)
