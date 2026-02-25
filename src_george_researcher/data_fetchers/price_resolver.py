"""
Price resolution with cascading fallback.

Deep module: one entry point, three fallback layers, never returns 0.
For any actively traded stock, current_price should always resolve.
If all three sources fail, that's a hard error worth surfacing.

Fallback chain:
  1. FDS price history (most recent non-zero close)
  2. yfinance real-time quote
  3. market_cap / shares_outstanding derivation
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from src_george_researcher.data_fetchers.stock_data import StockInfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedPrice:
    """Immutable price resolution result."""
    price: float
    source: str         # "fds_prices" | "yfinance" | "derived"
    success: bool
    error: Optional[str] = None


def resolve_current_price(
    symbol: str,
    fds_prices: Optional[list] = None,
    yf_info: Optional[StockInfo] = None,
    market_cap: Optional[float] = None,
    shares_outstanding: Optional[float] = None,
) -> ResolvedPrice:
    """
    Resolve current price through cascading fallback. Never returns 0.

    Args:
        symbol: Ticker symbol (for logging).
        fds_prices: List of PriceData from FinancialDatasets.ai.
        yf_info: StockInfo from yfinance supplement fetch.
        market_cap: Company market cap (for derivation fallback).
        shares_outstanding: Share count (for derivation fallback).

    Returns:
        ResolvedPrice with price > 0 on success, or success=False with error.
    """
    # Layer 1: Most recent non-zero FDS close price
    if fds_prices:
        sorted_by_date = sorted(fds_prices, key=lambda p: p.date, reverse=True)
        for p in sorted_by_date:
            if p.close and p.close > 0:
                logger.debug(f"[{symbol}] Price resolved from FDS: ${p.close:.2f} ({p.date})")
                return ResolvedPrice(price=p.close, source="fds_prices", success=True)
        logger.warning(f"[{symbol}] FDS returned {len(fds_prices)} prices but none had valid close > 0")

    # Layer 2: yfinance current price
    if yf_info and yf_info.current_price and yf_info.current_price > 0:
        logger.info(f"[{symbol}] Price resolved from yfinance fallback: ${yf_info.current_price:.2f}")
        return ResolvedPrice(price=yf_info.current_price, source="yfinance", success=True)

    # Layer 3: Derive from market_cap / shares_outstanding
    if market_cap and market_cap > 0 and shares_outstanding and shares_outstanding > 0:
        derived = market_cap / shares_outstanding
        logger.info(f"[{symbol}] Price derived from market_cap/shares: ${derived:.2f}")
        return ResolvedPrice(price=derived, source="derived", success=True)

    # All layers failed
    sources_tried = []
    if fds_prices is not None:
        sources_tried.append(f"FDS ({len(fds_prices)} prices, all zero/missing)")
    else:
        sources_tried.append("FDS (no data)")
    if yf_info is not None:
        sources_tried.append(f"yfinance (current_price={yf_info.current_price})")
    else:
        sources_tried.append("yfinance (unavailable)")
    if market_cap is not None and shares_outstanding is not None:
        sources_tried.append(f"derivation (mcap={market_cap}, shares={shares_outstanding})")
    else:
        sources_tried.append("derivation (missing inputs)")

    error_msg = f"All price sources failed for {symbol}: {'; '.join(sources_tried)}"
    logger.error(error_msg)
    return ResolvedPrice(price=0.0, source="none", success=False, error=error_msg)
