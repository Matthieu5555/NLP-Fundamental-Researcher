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
        "id": "moonshotai/kimi-k2.5",
        "name": "Kimi K2.5",
        "provider": "Moonshot AI",
        "input_price": 0.45,
        "output_price": 2.20,
        "tier": "budget",
        "description": "Cheap and capable, multimodal with agent swarm (default)",
    },
    {
        "id": "google/gemini-3-flash-preview",
        "name": "Gemini 3 Flash",
        "provider": "Google",
        "input_price": 0.50,
        "output_price": 3.00,
        "tier": "budget",
        "description": "Fast and affordable",
    },
    {
        "id": "openai/gpt-5-nano",
        "name": "GPT-5 Nano",
        "provider": "OpenAI",
        "input_price": 0.05,
        "output_price": 0.40,
        "tier": "budget",
        "description": "Ultra-cheap, simple tasks and high-frequency actions",
    },
    {
        "id": "meta-llama/llama-4-scout-17b-16e-instruct",
        "name": "Llama 4 Scout",
        "provider": "Meta",
        "input_price": 0.11,
        "output_price": 0.34,
        "tier": "budget",
        "description": "Open-weight, efficient",
    },
    {
        "id": "deepseek/deepseek-v3.2-20251201",
        "name": "DeepSeek V3.2",
        "provider": "DeepSeek",
        "input_price": 0.26,
        "output_price": 0.38,
        "tier": "budget",
        "description": "Ultra-cheap general purpose, mixture-of-experts",
    },
{
        "id": "qwen/qwen3.5-plus-02-15",
        "name": "Qwen 3.5 Plus",
        "provider": "Alibaba",
        "input_price": 0.40,
        "output_price": 2.40,
        "tier": "budget",
        "description": "Multimodal, enterprise efficiency",
    },
    {
        "id": "z-ai/glm-4.7-flash-20260119",
        "name": "GLM-4.7 Flash",
        "provider": "Zhipu AI",
        "input_price": 0.06,
        "output_price": 0.40,
        "tier": "budget",
        "description": "Ultra-cheap, maximum cost-effectiveness",
    },
    {
        "id": "z-ai/glm-5-20260211",
        "name": "GLM-5",
        "provider": "Zhipu AI",
        "input_price": 0.95,
        "output_price": 2.55,
        "tier": "budget",
        "description": "Capable and cost-effective",
    },
    {
        "id": "anthropic/claude-sonnet-4.6",
        "name": "Claude Sonnet 4.6",
        "provider": "Anthropic",
        "input_price": 3.00,
        "output_price": 15.00,
        "tier": "standard",
        "description": "Balanced performance and cost",
    },
    {
        "id": "google/gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro",
        "provider": "Google",
        "input_price": 2.00,
        "output_price": 12.00,
        "tier": "standard",
        "description": "Large context window, great for massive data",
    },
    {
        "id": "anthropic/claude-opus-4.6",
        "name": "Claude Opus 4.6",
        "provider": "Anthropic",
        "input_price": 5.00,
        "output_price": 25.00,
        "tier": "premium",
        "description": "Top-tier reasoning, best for complex analysis",
    },
    {
        "id": "openai/gpt-5.2-pro",
        "name": "GPT-5.2 Pro",
        "provider": "OpenAI",
        "input_price": 21.00,
        "output_price": 168.00,
        "tier": "premium",
        "description": "Enterprise precision",
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
