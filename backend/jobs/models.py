"""
Job data models for the background queue system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class JobStatus(str, Enum):
    """Status of a background job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class QueueType(str, Enum):
    """Queue assignment for a job."""
    US = "us"          # FinancialDatasets.ai - fast
    NON_US = "non_us"  # Alpha Vantage - rate limited


@dataclass
class Job:
    """
    Represents a background analysis job.

    Jobs persist to SQLite and survive server restarts.
    Progress is updated in real-time as analysis proceeds.
    """
    job_id: str
    session_id: str
    ticker: str
    queue_type: QueueType
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0  # 0-100
    progress_message: str = "Queued"
    current_step: int = 0
    total_steps: int = 14
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "ticker": self.ticker,
            "queue_type": self.queue_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create Job from dictionary."""
        return cls(
            job_id=data["job_id"],
            session_id=data["session_id"],
            ticker=data["ticker"],
            queue_type=QueueType(data["queue_type"]),
            status=JobStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            progress=data.get("progress", 0),
            progress_message=data.get("progress_message", ""),
            current_step=data.get("current_step", 0),
            total_steps=data.get("total_steps", 14),
            result=data.get("result"),
            error=data.get("error"),
        )
