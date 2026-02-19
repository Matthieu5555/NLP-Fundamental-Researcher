"""
US Company Data Fetchers (FinancialDatasets.ai)

This module provides data fetching for US companies using FinancialDatasets.ai,
which offers comprehensive financial data including:
- Company facts and info
- Financial statements (income, balance, cash flow)
- Historical prices
- Insider trades
- Analyst estimates
- News with sentiment
"""

from .financial_datasets_client import (
    FDSClient,
    get_fds_client,
    fetch_company_facts,
    fetch_financials,
    fetch_prices,
    fetch_insider_trades,
    fetch_analyst_estimates,
    fetch_news,
)

__all__ = [
    "FDSClient",
    "get_fds_client",
    "fetch_company_facts",
    "fetch_financials",
    "fetch_prices",
    "fetch_insider_trades",
    "fetch_analyst_estimates",
    "fetch_news",
]
