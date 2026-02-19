"""
Companies API router.

Provides company classification and lookup services.

Endpoints:
    GET /classify/{ticker}     - Classify company as US or Non-US
    GET /us-tickers            - List all US tickers (for autocomplete)
    GET /search                - Search tickers by name/symbol
    GET /stats                 - Get registry statistics
    GET /availability/{ticker} - Get data availability for a ticker
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from src_george_researcher.data_fetchers.company_registry import get_company_registry
from src_george_researcher.data_fetchers.data_router import (
    classify_company,
    get_data_availability,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/classify/{ticker}")
async def classify_ticker(ticker: str):
    """
    Classify a company ticker as US or Non-US.

    Returns classification with data availability information.
    For non-US companies, unavailable_features lists features not available.
    """
    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker")

    try:
        classification = classify_company(ticker)
        return classification.to_dict()
    except Exception as e:
        logger.error(f"Error classifying {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.get("/us-tickers")
async def list_us_tickers(limit: int = Query(default=1000, le=10000)):
    """
    Get list of all US-listed tickers.

    Useful for autocomplete/validation in frontend.
    """
    try:
        registry = get_company_registry()
        all_tickers = registry.get_all_us_tickers()

        return {
            "tickers": all_tickers[:limit],
            "count": min(len(all_tickers), limit),
            "total": len(all_tickers),
        }
    except Exception as e:
        logger.error(f"Error listing US tickers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tickers: {str(e)}")


@router.get("/search")
async def search_tickers(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, le=100),
):
    """
    Search for tickers by symbol or company name.

    Returns matching tickers with company names and CIK numbers.
    """
    try:
        registry = get_company_registry()
        results = registry.search_tickers(q, limit=limit)

        return {
            "results": results,
            "count": len(results),
            "query": q,
        }
    except Exception as e:
        logger.error(f"Error searching tickers for '{q}': {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/stats")
async def get_registry_stats():
    """
    Get company registry statistics.

    Useful for monitoring/debugging.
    """
    try:
        registry = get_company_registry()
        stats = registry.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting registry stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/availability/{ticker}")
async def get_ticker_availability(ticker: str):
    """
    Get data availability for a specific ticker.

    Returns which data sources are available for analysis.
    """
    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker")

    try:
        availability = get_data_availability(ticker)
        return availability
    except Exception as e:
        logger.error(f"Error getting availability for {ticker}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get availability: {str(e)}"
        )
