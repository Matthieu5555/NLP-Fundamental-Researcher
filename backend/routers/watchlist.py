"""
Watchlist API router.

Endpoints:
    GET    /api/watchlist          - List all watchlist items with current prices
    POST   /api/watchlist/{ticker} - Add to watchlist
    DELETE /api/watchlist/{ticker} - Remove from watchlist
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth_db import User
from backend.core.watchlist_db import watchlist_db
from backend.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_yf_executor = ThreadPoolExecutor(max_workers=10)


class AddToWatchlistRequest(BaseModel):
    company_name: Optional[str] = None
    fair_value: Optional[float] = None
    session_id: Optional[str] = None


def _fetch_ticker_info(symbol: str) -> dict:
    """Fetch price and name for a single ticker (runs in thread pool)."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "current_price": info.get("currentPrice", info.get("regularMarketPrice")),
            "company_name": info.get("longName", info.get("shortName")),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch price for {symbol}: {e}")
        return {"current_price": None, "company_name": None}


@router.get("")
async def get_watchlist(user: User = Depends(get_current_user)):
    """Get all watchlist items for the authenticated user."""
    items = await watchlist_db.get_watchlist(user.id)

    if not items:
        return {"items": []}

    # Fetch all prices concurrently via thread pool
    loop = asyncio.get_running_loop()
    futures = [
        loop.run_in_executor(_yf_executor, _fetch_ticker_info, item.ticker)
        for item in items
    ]
    price_results = await asyncio.gather(*futures)

    result_items = []
    for item, price_data in zip(items, price_results):
        item_dict = item.to_dict()
        item_dict["current_price"] = price_data["current_price"]
        item_dict["company_name"] = item_dict["company_name"] or price_data["company_name"]

        # Calculate gap
        if item_dict.get("current_price") and item_dict.get("last_fair_value"):
            gap = ((item_dict["last_fair_value"] / item_dict["current_price"]) - 1) * 100
            item_dict["fair_value_gap_pct"] = round(gap, 1)
        else:
            item_dict["fair_value_gap_pct"] = None

        result_items.append(item_dict)

    return {"items": result_items}


@router.post("/{ticker}")
async def add_to_watchlist(
    ticker: str,
    request: AddToWatchlistRequest = None,
    user: User = Depends(get_current_user),
):
    """Add a ticker to the user's watchlist."""
    request = request or AddToWatchlistRequest()
    item = await watchlist_db.add_to_watchlist(
        user_id=user.id,
        ticker=ticker,
        company_name=request.company_name,
        fair_value=request.fair_value,
        session_id=request.session_id,
    )
    return {"success": True, "item": item.to_dict()}


@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    user: User = Depends(get_current_user),
):
    """Remove a ticker from the user's watchlist."""
    removed = await watchlist_db.remove_from_watchlist(user.id, ticker)
    if not removed:
        raise HTTPException(status_code=404, detail="Ticker not found in watchlist")
    return {"success": True}
