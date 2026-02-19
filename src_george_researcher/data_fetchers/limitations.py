"""
Data Availability Limitations by Region.

This module documents the data limitations for different company regions
and provides utilities for communicating these limitations to users.

Data Sources:
- US Companies: FinancialDatasets.ai + yfinance + Gemini Search
- Non-US Companies: yfinance + Gemini Search only

See types.py for DataAvailability and CompanyClassification dataclasses.
"""

from typing import Dict, List

# Feature descriptions for user-facing messages
FEATURE_DESCRIPTIONS: Dict[str, str] = {
    "detailed_financials": (
        "Detailed Financial Statements: Income statements, balance sheets, "
        "and cash flow statements with multi-year history and quarterly breakdowns."
    ),
    "insider_trades": (
        "Insider Trading Activity: Recent insider buy/sell transactions, "
        "including transaction sizes, prices, and insider roles."
    ),
    "analyst_estimates": (
        "Analyst Consensus Estimates: Wall Street analyst EPS and revenue "
        "estimates for upcoming quarters and fiscal years."
    ),
    "sec_filings": (
        "SEC Filings: Direct access to 10-K, 10-Q, and 8-K filings "
        "with semantic search capabilities."
    ),
    "segmented_revenues": (
        "Segmented Revenue Data: Revenue breakdown by business segment "
        "and geographic region."
    ),
}

# What's available for each region
US_AVAILABLE_FEATURES: List[str] = [
    "Stock price and volume data",
    "Technical indicators (SMA, RSI, MACD, Bollinger Bands)",
    "Detailed financial statements (Income, Balance Sheet, Cash Flow)",
    "Insider trading activity",
    "Analyst consensus estimates",
    "SEC filings with semantic search",
    "Segmented revenue data",
    "News sentiment analysis",
    "Real-time web research via Gemini Search",
]

NON_US_AVAILABLE_FEATURES: List[str] = [
    "Stock price and volume data",
    "Technical indicators (SMA, RSI, MACD, Bollinger Bands)",
    "Basic financial data (via Yahoo Finance)",
    "News sentiment analysis",
    "Real-time web research via Gemini Search",
]

NON_US_UNAVAILABLE_FEATURES: List[str] = [
    "Detailed Financial Statements",
    "Insider Trading Activity",
    "Analyst Consensus Estimates",
    "SEC Filings",
    "Segmented Revenue Data",
]


def get_limitation_message(is_us: bool, ticker: str, company_name: str = None) -> str:
    """
    Generate a user-friendly limitation message.

    Args:
        is_us: Whether the company is US-based
        ticker: Stock ticker symbol
        company_name: Optional company name

    Returns:
        Human-readable limitation message
    """
    name = company_name or ticker

    if is_us:
        return f"{name} ({ticker}) is a US company with full data access."

    unavailable = ", ".join(NON_US_UNAVAILABLE_FEATURES)
    return (
        f"{name} ({ticker}) is classified as a non-US company. "
        f"The following premium data sources are not available: {unavailable}. "
        f"Analysis will use publicly available data from Yahoo Finance and web research."
    )


def get_analysis_disclaimer(is_us: bool) -> str:
    """
    Generate a disclaimer for the analysis based on data availability.

    Args:
        is_us: Whether the company is US-based

    Returns:
        Disclaimer text to include in analysis
    """
    if is_us:
        return (
            "This analysis uses comprehensive data from FinancialDatasets.ai, "
            "including detailed financials, insider trading, analyst estimates, "
            "and SEC filings."
        )

    return (
        "Note: This analysis is based on limited data sources. "
        "Detailed financial statements, insider trading activity, "
        "analyst estimates, and SEC filings are not available for non-US companies. "
        "Conclusions should be validated with additional research."
    )


def get_available_features(is_us: bool) -> List[str]:
    """Get list of available features for a region."""
    return US_AVAILABLE_FEATURES if is_us else NON_US_AVAILABLE_FEATURES


def get_unavailable_features(is_us: bool) -> List[str]:
    """Get list of unavailable features for a region."""
    return [] if is_us else NON_US_UNAVAILABLE_FEATURES
