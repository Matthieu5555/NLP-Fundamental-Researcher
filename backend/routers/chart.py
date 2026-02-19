"""
Chart API router.

Provides OHLCV data with technical indicators for interactive charting.

Endpoints:
    GET /{ticker}/data - Get chart data for a ticker with timeframe
    GET /timeframes    - List available timeframes

Timeframe Mapping:
    1W  → 5m intervals (7 days)
    1M  → 30m intervals (1 month)
    3M  → 1h intervals (3 months)
    6M  → 1d intervals (6 months)
    YTD → 1d intervals (year to date)
    1Y  → 1d intervals (1 year)
    2Y  → 1d intervals (2 years)
    5Y  → 1wk intervals (5 years)
    10Y → 1wk intervals (10 years)
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from src_george_researcher.data_fetchers.stock_data import fetch_chart_data

logger = logging.getLogger(__name__)

router = APIRouter()

# Timeframe to yfinance period/interval mapping
TIMEFRAME_CONFIG = {
    "1W": {"period": "7d", "interval": "5m"},
    "1M": {"period": "1mo", "interval": "30m"},
    "3M": {"period": "3mo", "interval": "1h"},
    "6M": {"period": "6mo", "interval": "1d"},
    "YTD": {"period": "ytd", "interval": "1d"},
    "1Y": {"period": "1y", "interval": "1d"},
    "2Y": {"period": "2y", "interval": "1d"},
    "5Y": {"period": "5y", "interval": "1wk"},
    "10Y": {"period": "10y", "interval": "1wk"},
}


@router.get("/{ticker}/data")
async def get_chart_data(
    ticker: str,
    timeframe: str = Query(default="1Y", description="Chart timeframe"),
):
    """
    Get chart data for a ticker.

    Returns OHLCV data with technical indicators (SMA, Bollinger, RSI, MACD).
    """
    ticker = ticker.upper()
    timeframe = timeframe.upper()

    # Validate timeframe
    if timeframe not in TIMEFRAME_CONFIG:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Invalid timeframe: {timeframe}",
                "valid_timeframes": list(TIMEFRAME_CONFIG.keys()),
            },
        )

    config = TIMEFRAME_CONFIG[timeframe]
    logger.info(
        f"Fetching chart data for {ticker}, timeframe={timeframe}, "
        f"period={config['period']}, interval={config['interval']}"
    )

    # Fetch chart data
    data, error = fetch_chart_data(
        symbol=ticker, period=config["period"], interval=config["interval"]
    )

    if error:
        logger.error(f"Chart data fetch failed for {ticker}: {error}")
        raise HTTPException(status_code=404, detail=error)

    logger.info(f"Chart data fetched: {len(data['ohlcv'])} candles")
    return data


@router.get("/timeframes")
async def get_timeframes():
    """
    Get available timeframes.

    Returns list of valid timeframe options for chart data requests.
    """
    return {"timeframes": list(TIMEFRAME_CONFIG.keys())}
