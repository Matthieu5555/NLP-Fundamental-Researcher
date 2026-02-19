"""
Pydantic response models for FastAPI endpoints.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class StartAnalysisResponse(BaseModel):
    """Response for starting a new analysis."""

    session_id: str
    job_id: str
    ticker: str
    queue_type: str  # "us" or "non_us"
    status: str  # "queued"
    message: str


class JobStatus(BaseModel):
    """Job status details."""

    job_id: str
    status: str  # "pending", "running", "complete", "failed"
    progress: int = Field(ge=0, le=100)
    progress_message: str
    current_step: int
    total_steps: int
    queue_type: str
    queue_position: Optional[int] = None
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response for session/job status."""

    session_id: str
    ticker: str
    status: str  # "queued", "running", "ready", "failed"
    message_count: int
    report_sections: int
    beliefs_count: int
    created_at: str
    total_tokens: int
    total_cost_usd: float
    job: Optional[JobStatus] = None


class SessionSummary(BaseModel):
    """Summary of a session for listing."""

    session_id: str
    ticker: str
    created_at: str
    message_count: int
    preview: Optional[str] = None


class SessionResponse(BaseModel):
    """Full session details response."""

    session_id: str
    ticker: str
    created_at: str
    message_count: int
    has_report: bool
    last_message: Optional[str] = None
    metadata: Dict[str, Any]


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    sessions: List[SessionSummary]
    count: int


class ReportSection(BaseModel):
    """A report section."""

    section_id: str
    title: str
    content: str
    section_type: str
    sources: List[Dict[str, Any]] = []


class ReportResponse(BaseModel):
    """Response for getting a report."""

    ticker: str
    sections: Dict[str, ReportSection]
    stats: Dict[str, Any]
    contradictions: List[Dict[str, Any]] = []
    research_gaps: List[Dict[str, Any]] = []
    excluded_source_ids: List[int] = []


class CompanyClassification(BaseModel):
    """Company classification response."""

    ticker: str
    region: str  # "us" or "non_us"
    is_us: bool
    cik: Optional[str] = None
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    data_availability: Dict[str, bool]
    unavailable_features: List[str] = []


class TickerSearchResult(BaseModel):
    """A single ticker search result."""

    ticker: str
    name: str
    cik: Optional[str] = None


class TickerSearchResponse(BaseModel):
    """Response for ticker search."""

    results: List[TickerSearchResult]
    count: int
    query: str


class BeliefResponse(BaseModel):
    """A single belief."""

    id: str
    content: str
    confidence: float
    source: str
    timestamp: str


class BeliefsResponse(BaseModel):
    """Response for getting beliefs."""

    session_id: str
    beliefs: List[BeliefResponse]
    count: int
    by_section: Dict[str, List[BeliefResponse]]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    uptime_seconds: int
    workers: Dict[str, Any]
    queues: Dict[str, Any]


class QueueStatsResponse(BaseModel):
    """Queue statistics response."""

    us: Dict[str, int]
    non_us: Dict[str, int]
