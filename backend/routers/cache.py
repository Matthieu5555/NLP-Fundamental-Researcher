"""
Cache management API router.

Provides cache statistics, invalidation, and cleanup endpoints.

Endpoints:
    GET  /stats       - Get cache statistics and cost savings
    POST /invalidate  - Invalidate cache entries by ticker/type
    POST /cleanup     - Remove expired cache entries
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from src_george_researcher.data_fetchers.cache import get_data_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
async def get_cache_stats():
    """
    Get cache statistics and cost savings.

    Returns:
        total_entries: Number of cached items
        total_size_mb: Total cache size in MB
        hits: Number of cache hits (session-wide)
        misses: Number of cache misses (session-wide)
        hit_rate: Cache hit rate percentage
        total_cost_saved_usd: Estimated cost savings from cache hits
        by_type: Breakdown of entries by data type
        expired_pending_cleanup: Number of expired entries awaiting cleanup
    """
    cache = get_data_cache()
    stats = cache.get_stats()

    total_requests = stats.hits + stats.misses
    hit_rate = round(stats.hits / max(total_requests, 1) * 100, 1)

    return {
        "total_entries": stats.total_entries,
        "total_size_mb": round(stats.total_size_bytes / (1024 * 1024), 2),
        "hits": stats.hits,
        "misses": stats.misses,
        "hit_rate": hit_rate,
        "total_cost_saved_usd": round(stats.total_cost_saved_usd, 4),
        "by_type": stats.by_type,
        "expired_pending_cleanup": stats.expired_count,
    }


@router.post("/invalidate")
async def invalidate_cache(
    ticker: Optional[str] = Query(None, description="Ticker to invalidate (e.g., AAPL)"),
    data_type: Optional[str] = Query(None, description="Data type to invalidate (e.g., fds_prices)"),
):
    """
    Invalidate cache entries.

    Args:
        ticker: Invalidate all entries for this ticker
        data_type: Invalidate all entries of this type

    If both provided, invalidates entries matching both.
    If neither provided, invalidates ALL cache entries.
    """
    cache = get_data_cache()
    deleted = cache.invalidate(ticker=ticker, data_type=data_type)

    if ticker and data_type:
        scope = f"ticker={ticker}, type={data_type}"
    elif ticker:
        scope = f"ticker={ticker}"
    elif data_type:
        scope = f"type={data_type}"
    else:
        scope = "ALL entries"

    logger.info(f"Cache invalidation: {deleted} entries deleted ({scope})")

    return {
        "deleted": deleted,
        "scope": scope,
        "message": f"Invalidated {deleted} cache entries",
    }


@router.post("/cleanup")
async def cleanup_expired():
    """
    Remove expired cache entries.

    Call periodically to free up space from expired data.
    Expired entries are automatically skipped on cache reads,
    but this endpoint removes them from storage.
    """
    cache = get_data_cache()
    deleted = cache.cleanup_expired()

    logger.info(f"Cache cleanup: {deleted} expired entries removed")

    return {
        "deleted": deleted,
        "message": f"Cleaned up {deleted} expired entries",
    }


@router.get("/health")
async def cache_health():
    """
    Check cache health and configuration.

    Returns cache configuration and current state.
    """
    from src_george_researcher.data_fetchers.cache import TTL_CONFIG, COST_CONFIG

    cache = get_data_cache()
    stats = cache.get_stats()

    return {
        "status": "healthy",
        "db_path": str(cache.db_path),
        "total_entries": stats.total_entries,
        "ttl_config": {k: f"{v // 3600}h" for k, v in TTL_CONFIG.items()},
        "cost_config": COST_CONFIG,
    }
