"""
User settings API endpoints.

Provides endpoints for users to manage their preferences and configuration.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.core.auth_db import User
from backend.core.settings_db import settings_db
from backend.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# Available models with pricing (from src_george_researcher/llm.py)
AVAILABLE_MODELS = [
    {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "provider": "Anthropic",
        "input_price": 0.25,
        "output_price": 1.25,
        "tier": "budget",
        "description": "Fast and affordable, good for simple tasks",
    },
    {
        "id": "anthropic/claude-3.5-haiku",
        "name": "Claude 3.5 Haiku",
        "provider": "Anthropic",
        "input_price": 0.80,
        "output_price": 4.00,
        "tier": "budget",
        "description": "Improved Haiku with better reasoning",
    },
    {
        "id": "anthropic/claude-sonnet-4",
        "name": "Claude Sonnet 4",
        "provider": "Anthropic",
        "input_price": 3.00,
        "output_price": 15.00,
        "tier": "standard",
        "description": "Balanced performance and cost (recommended)",
    },
    {
        "id": "anthropic/claude-opus-4",
        "name": "Claude Opus 4",
        "provider": "Anthropic",
        "input_price": 15.00,
        "output_price": 75.00,
        "tier": "premium",
        "description": "Most capable, best for complex analysis",
    },
    {
        "id": "google/gemini-2.0-flash",
        "name": "Gemini 2.0 Flash",
        "provider": "Google",
        "input_price": 0.10,
        "output_price": 0.40,
        "tier": "budget",
        "description": "Very fast and cheap, good for quick tasks",
    },
    {
        "id": "google/gemini-2.0-flash-exp",
        "name": "Gemini 2.0 Flash (Free)",
        "provider": "Google",
        "input_price": 0.00,
        "output_price": 0.00,
        "tier": "free",
        "description": "Free experimental model, rate limited",
    },
]


class SettingsUpdate(BaseModel):
    """Request model for updating settings."""
    master_system_prompt: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)
    theme: Optional[str] = Field(None, pattern="^(light|dark)$")
    show_cost_tracking: Optional[bool] = None
    default_chart_timeframe: Optional[str] = Field(
        None, pattern="^(1m|3m|6m|1y|5y)$"
    )
    analysis_depth: Optional[str] = Field(
        None, pattern="^(quick|standard|deep)$"
    )
    auto_run_analysis: Optional[bool] = None


class AvailableModel(BaseModel):
    """Model information for the frontend."""
    id: str
    name: str
    provider: str
    input_price: float
    output_price: float
    tier: str
    description: str


@router.get("/")
async def get_settings(
    user: User = Depends(get_current_user),
):
    """
    Get current user settings.

    Creates default settings if none exist.
    """
    settings = await settings_db.get_settings(user.id)
    return settings.to_dict()


@router.put("/")
async def update_settings(
    updates: SettingsUpdate,
    user: User = Depends(get_current_user),
):
    """
    Update user settings (partial update).

    Only provided fields will be updated.
    """
    # Validate model if provided
    if updates.llm_model:
        valid_model_ids = [m["id"] for m in AVAILABLE_MODELS]
        if updates.llm_model not in valid_model_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model. Available: {valid_model_ids}",
            )

    settings = await settings_db.update_settings(
        user.id,
        **updates.model_dump(exclude_none=True),
    )
    logger.info(f"Updated settings for user {user.id}")
    return settings.to_dict()


@router.post("/reset")
async def reset_settings(
    user: User = Depends(get_current_user),
):
    """
    Reset all settings to defaults.
    """
    settings = await settings_db.reset_to_defaults(user.id)
    logger.info(f"Reset settings to defaults for user {user.id}")
    return settings.to_dict()


@router.get("/available-models")
async def get_available_models():
    """
    Get list of available LLM models with pricing.

    This endpoint is public (no auth required) for display purposes.
    """
    return {"models": AVAILABLE_MODELS}
