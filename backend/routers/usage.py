"""
Usage tracking API endpoints.

Provides endpoints for users to view their API usage and costs.
"""

import logging

from fastapi import APIRouter, Depends, Query

from backend.core.auth_db import User
from backend.core.usage_db import usage_db
from backend.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me")
async def get_my_usage(
    user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
):
    """
    Get recent usage records for the current user.

    Returns a list of individual API usage records.
    """
    records = await usage_db.get_user_usage(user.id, days=days, limit=limit)
    return {
        "user_id": user.id,
        "email": user.email,
        "records": [r.to_dict() for r in records],
        "count": len(records),
        "days": days,
    }


@router.get("/summary")
async def get_my_summary(
    user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Days to aggregate"),
):
    """
    Get aggregated usage summary for the current user.

    Returns totals, breakdowns by endpoint and ticker.
    """
    summary = await usage_db.get_user_summary(user.id, days=days)
    return {
        "user_id": user.id,
        "email": user.email,
        "summary": summary.to_dict(),
    }


@router.get("/daily")
async def get_daily_breakdown(
    user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Days to show"),
):
    """
    Get daily usage breakdown for the current user.

    Returns per-day stats for charting.
    """
    daily = await usage_db.get_daily_breakdown(user.id, days=days)
    return {
        "user_id": user.id,
        "email": user.email,
        "daily": daily,
        "days": days,
    }


@router.get("/costs")
async def get_cost_breakdown(
    user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Days to aggregate"),
):
    """
    Get cost breakdown by category for the current user.

    Categories: analysis, chat, reports, other
    """
    costs = await usage_db.get_cost_by_category(user.id, days=days)
    summary = await usage_db.get_user_summary(user.id, days=days)

    return {
        "user_id": user.id,
        "email": user.email,
        "total_cost_usd": round(summary.total_cost_usd, 4),
        "by_category": costs,
        "days": days,
    }


@router.get("/stats")
async def get_usage_stats(
    user: User = Depends(get_current_user),
):
    """
    Get quick usage stats for the current user.

    Returns summary for current month and all-time.
    """
    # Current month (last 30 days)
    month_summary = await usage_db.get_user_summary(user.id, days=30)

    # All time (365 days max for performance)
    all_time_summary = await usage_db.get_user_summary(user.id, days=365)

    return {
        "user_id": user.id,
        "email": user.email,
        "current_month": {
            "requests": month_summary.total_requests,
            "cost_usd": round(month_summary.total_cost_usd, 4),
            "tokens": month_summary.total_tokens,
            "cache_hit_rate": round(month_summary.cache_hit_rate, 1),
        },
        "all_time": {
            "requests": all_time_summary.total_requests,
            "cost_usd": round(all_time_summary.total_cost_usd, 4),
            "tokens": all_time_summary.total_tokens,
            "top_tickers": list(all_time_summary.by_ticker.keys())[:5],
        },
    }
