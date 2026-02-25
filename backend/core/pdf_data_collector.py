"""
PDF Data Collector for First Page.

Collects all metrics needed for the information-dense first page:
- Period returns (1M, YTD, 1Y, 5Y, 10Y)
- Extended statistics from StockInfo
- Formatted values ready for PDF rendering
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging

# sys.path configured in backend/main.py
from src_george_researcher.data_fetchers.stock_data import (
    fetch_stock_info,
    fetch_historical_data,
    StockInfo
)

logger = logging.getLogger(__name__)


@dataclass
class PeriodReturns:
    """Period return metrics."""
    return_1m: Optional[float] = None
    return_ytd: Optional[float] = None
    return_1y: Optional[float] = None
    return_5y: Optional[float] = None
    return_10y: Optional[float] = None


@dataclass
class FirstPageData:
    """All data needed for the first page of the PDF report."""
    # Basic info
    ticker: str
    company_name: str
    exchange: str
    country: str
    sector: str
    industry: str

    # Key Metrics Bar
    current_price: Optional[float]
    market_cap: Optional[float]
    eps: Optional[float]
    rating: str  # BUY/HOLD/SELL

    # Period Returns
    returns: PeriodReturns

    # Key Statistics (15+)
    shares_outstanding: Optional[float]
    dividend_yield: Optional[float]
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    price_to_book: Optional[float]
    price_to_fcf: Optional[float]
    ev_to_ebitda: Optional[float]
    ev_to_revenue: Optional[float]
    roe: Optional[float]
    roa: Optional[float]
    roi: Optional[float]
    profit_margin: Optional[float]
    gross_margin: Optional[float]
    debt_to_equity: Optional[float]
    beta: Optional[float]
    week_52_high: Optional[float]
    week_52_low: Optional[float]

    # Full StockInfo for additional data
    stock_info: Optional[StockInfo] = None


def calculate_period_returns(ticker: str) -> PeriodReturns:
    """
    Calculate returns for multiple time periods.

    Args:
        ticker: Stock ticker symbol

    Returns:
        PeriodReturns with 1M, YTD, 1Y, 5Y, 10Y returns as percentages
    """
    returns = PeriodReturns()

    try:
        # Fetch max history for all calculations
        df, error = fetch_historical_data(ticker, period='max', interval='1d')
        if error or df is None or df.empty:
            logger.warning(f"Could not fetch historical data for {ticker}: {error}")
            return returns

        current_price = df['Close'].iloc[-1]
        current_date = df.index[-1]

        # Helper to find price at a date
        def get_price_at_date(target_date):
            """Get closing price at or before target date."""
            mask = df.index <= target_date
            if mask.any():
                return df.loc[mask, 'Close'].iloc[-1]
            return None

        # 1 Month return
        one_month_ago = current_date - timedelta(days=30)
        price_1m = get_price_at_date(one_month_ago)
        if price_1m and price_1m > 0:
            returns.return_1m = ((current_price - price_1m) / price_1m) * 100

        # YTD return (from Jan 1 of current year)
        year_start = datetime(current_date.year, 1, 1)
        # Convert to timezone-aware if needed
        if hasattr(current_date, 'tz') and current_date.tz is not None:
            import pandas as pd
            year_start = pd.Timestamp(year_start, tz=current_date.tz)
        price_ytd = get_price_at_date(year_start)
        if price_ytd and price_ytd > 0:
            returns.return_ytd = ((current_price - price_ytd) / price_ytd) * 100

        # 1 Year return
        one_year_ago = current_date - timedelta(days=365)
        price_1y = get_price_at_date(one_year_ago)
        if price_1y and price_1y > 0:
            returns.return_1y = ((current_price - price_1y) / price_1y) * 100

        # 5 Year return
        five_years_ago = current_date - timedelta(days=365*5)
        price_5y = get_price_at_date(five_years_ago)
        if price_5y and price_5y > 0:
            returns.return_5y = ((current_price - price_5y) / price_5y) * 100

        # 10 Year return
        ten_years_ago = current_date - timedelta(days=365*10)
        price_10y = get_price_at_date(ten_years_ago)
        if price_10y and price_10y > 0:
            returns.return_10y = ((current_price - price_10y) / price_10y) * 100

    except Exception as e:
        logger.error(f"Error calculating returns for {ticker}: {e}")

    return returns


def collect_first_page_data(ticker: str, stock_info: Optional[StockInfo] = None) -> Optional[FirstPageData]:
    """
    Collect all data needed for the first page of the PDF report.

    Args:
        ticker: Stock ticker symbol
        stock_info: Optional pre-fetched StockInfo (will fetch if not provided)

    Returns:
        FirstPageData with all metrics, or None on error
    """
    # Fetch stock info if not provided
    if stock_info is None:
        stock_info, error = fetch_stock_info(ticker)
        if error or stock_info is None:
            logger.error(f"Could not fetch stock info for {ticker}: {error}")
            return None

    # Calculate period returns
    returns = calculate_period_returns(ticker)

    # Determine rating from recommendation
    rec = stock_info.recommendation
    if rec:
        rec_upper = rec.upper()
        if 'STRONG' in rec_upper and 'BUY' in rec_upper:
            rating = 'STRONG BUY'
        elif 'BUY' in rec_upper:
            rating = 'BUY'
        elif 'STRONG' in rec_upper and 'SELL' in rec_upper:
            rating = 'STRONG SELL'
        elif 'SELL' in rec_upper:
            rating = 'SELL'
        elif 'HOLD' in rec_upper or 'NEUTRAL' in rec_upper:
            rating = 'HOLD'
        else:
            rating = rec.upper()
    else:
        rating = 'N/A'

    return FirstPageData(
        ticker=ticker,
        company_name=stock_info.name,
        exchange=stock_info.exchange or 'N/A',
        country=stock_info.country,
        sector=stock_info.sector,
        industry=stock_info.industry,
        current_price=stock_info.current_price,
        market_cap=stock_info.market_cap,
        eps=stock_info.eps,
        rating=rating,
        returns=returns,
        shares_outstanding=stock_info.shares_outstanding,
        dividend_yield=stock_info.dividend_yield,
        pe_ratio=stock_info.pe_ratio,
        forward_pe=stock_info.forward_pe,
        price_to_book=stock_info.price_to_book,
        price_to_fcf=stock_info.price_to_fcf,
        ev_to_ebitda=stock_info.ev_to_ebitda,
        ev_to_revenue=stock_info.ev_to_revenue,
        roe=stock_info.roe,
        roa=stock_info.roa,
        roi=stock_info.roi,
        profit_margin=stock_info.profit_margin,
        gross_margin=stock_info.gross_margin,
        debt_to_equity=stock_info.debt_to_equity,
        beta=stock_info.beta,
        week_52_high=stock_info.week_52_high,
        week_52_low=stock_info.week_52_low,
        stock_info=stock_info,
    )


# Formatting utilities for PDF display

def format_price(value: Optional[float]) -> str:
    """Format price as currency."""
    if value is None:
        return 'N/A'
    return f'${value:,.2f}'


def format_market_cap(value: Optional[float]) -> str:
    """Format market cap in human readable form (B, T)."""
    if value is None:
        return 'N/A'
    if value >= 1e12:
        return f'{value/1e12:.2f}T USD'
    elif value >= 1e9:
        return f'{value/1e9:.2f}B USD'
    elif value >= 1e6:
        return f'{value/1e6:.2f}M USD'
    else:
        return f'${value:,.0f}'


def format_shares(value: Optional[float]) -> str:
    """Format shares outstanding."""
    if value is None:
        return 'N/A'
    if value >= 1e9:
        return f'{value/1e9:.2f}B'
    elif value >= 1e6:
        return f'{value/1e6:.2f}M'
    else:
        return f'{value:,.0f}'


def format_percentage(value: Optional[float], multiply: bool = False) -> str:
    """
    Format as percentage.

    Args:
        value: The value to format
        multiply: If True, multiply by 100 (for decimals like 0.15 -> 15%)
    """
    if value is None:
        return 'N/A'
    if multiply:
        return f'{value * 100:.2f}%'
    return f'{value:.2f}%'


def format_ratio(value: Optional[float], suffix: str = 'x') -> str:
    """Format ratio with suffix."""
    if value is None:
        return 'N/A'
    return f'{value:.2f}{suffix}'


def format_return(value: Optional[float]) -> str:
    """Format return with + or - sign."""
    if value is None:
        return 'N/A'
    sign = '+' if value >= 0 else ''
    return f'{sign}{value:.1f}%'
