"""
Shared types for data fetchers.

This module defines common types used across US and Global data fetchers,
enabling routing and graceful degradation based on company region.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class CompanyRegion(Enum):
    """Company region classification for data routing."""
    US = "us"          # Full FinancialDatasets.ai support
    NON_US = "non_us"  # Degraded mode - yfinance + Gemini only


@dataclass(frozen=True)
class DataAvailability:
    """
    Describes what data is available for a company based on region.

    US companies get full data via FinancialDatasets.ai.
    Non-US companies have limited data via yfinance + Gemini Search.
    """
    # Available for all companies
    stock_info: bool = True
    historical_prices: bool = True
    technical_indicators: bool = True
    news_sentiment: bool = True
    web_research: bool = True  # Gemini Search

    # US-only features (FinancialDatasets.ai)
    detailed_financials: bool = False      # Income/Balance/Cash Flow statements
    insider_trades: bool = False           # Insider trading activity
    analyst_estimates: bool = False        # Consensus EPS estimates
    sec_filings: bool = False              # SEC 10-K, 10-Q, 8-K filings
    segmented_revenues: bool = False       # Revenue by segment/geography

    @classmethod
    def us_full(cls) -> "DataAvailability":
        """Full data availability for US companies."""
        return cls(
            detailed_financials=True,
            insider_trades=True,
            analyst_estimates=True,
            sec_filings=True,
            segmented_revenues=True,
        )

    @classmethod
    def non_us_limited(cls) -> "DataAvailability":
        """Limited data availability for non-US companies."""
        return cls()  # All US-only features default to False

    def get_unavailable_features(self) -> list:
        """Return list of unavailable feature names."""
        unavailable = []
        if not self.detailed_financials:
            unavailable.append("Detailed Financial Statements")
        if not self.insider_trades:
            unavailable.append("Insider Trading Activity")
        if not self.analyst_estimates:
            unavailable.append("Analyst Consensus Estimates")
        if not self.sec_filings:
            unavailable.append("SEC Filings")
        if not self.segmented_revenues:
            unavailable.append("Segmented Revenue Data")
        return unavailable


@dataclass
class CompanyClassification:
    """
    Classification result for a company ticker.

    Used by DataRouter to determine which data sources to use.
    """
    ticker: str
    region: CompanyRegion
    is_us: bool
    cik: Optional[str] = None  # SEC CIK for US companies
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    data_availability: DataAvailability = None

    def __post_init__(self):
        """Set data availability based on region if not provided."""
        if self.data_availability is None:
            if self.is_us:
                self.data_availability = DataAvailability.us_full()
            else:
                self.data_availability = DataAvailability.non_us_limited()

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "ticker": self.ticker,
            "region": self.region.value,
            "is_us": self.is_us,
            "cik": self.cik,
            "company_name": self.company_name,
            "exchange": self.exchange,
            "data_availability": {
                "stock_info": self.data_availability.stock_info,
                "historical_prices": self.data_availability.historical_prices,
                "technical_indicators": self.data_availability.technical_indicators,
                "news_sentiment": self.data_availability.news_sentiment,
                "web_research": self.data_availability.web_research,
                "detailed_financials": self.data_availability.detailed_financials,
                "insider_trades": self.data_availability.insider_trades,
                "analyst_estimates": self.data_availability.analyst_estimates,
                "sec_filings": self.data_availability.sec_filings,
                "segmented_revenues": self.data_availability.segmented_revenues,
            },
            "unavailable_features": self.data_availability.get_unavailable_features(),
        }
