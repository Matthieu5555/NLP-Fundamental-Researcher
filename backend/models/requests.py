"""
Pydantic request models for FastAPI endpoints.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class StartAnalysisRequest(BaseModel):
    """Request body for starting a new analysis."""

    ticker: str = Field(..., description="Stock ticker symbol", min_length=1, max_length=10)
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Analysis options (include_moat, include_strategy, debate_rounds)",
    )


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    session_id: str = Field(..., description="Analysis session ID")
    message: str = Field(..., description="User message", min_length=1)


class UpdateSectionRequest(BaseModel):
    """Request body for updating a report section."""

    content: str = Field(..., description="New section content", min_length=1)
    sources: Optional[List[str]] = Field(default=None, description="Source URLs")


class ExportPdfRequest(BaseModel):
    """Request body for PDF export with branding options."""

    firm_id: Optional[str] = Field(default="george", description="Firm branding ID")
    analyst_id: Optional[str] = Field(default="default", description="Analyst attribution ID")


class ClassifyTickerRequest(BaseModel):
    """Request body for ticker classification."""

    ticker: str = Field(..., description="Stock ticker to classify", min_length=1, max_length=10)


class SearchTickersRequest(BaseModel):
    """Request body for ticker search."""

    query: str = Field(..., description="Search query", min_length=1)
    limit: Optional[int] = Field(default=20, ge=1, le=100, description="Max results")
