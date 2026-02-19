"""
Dual job queue with SQLite persistence.

Manages two separate queues:
- US Queue: For US companies using FinancialDatasets.ai (fast, 1000 req/min)
- Non-US Queue: For non-US companies using Alpha Vantage (slow, 5 req/min)

Jobs persist to SQLite and survive server restarts.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List

import aiosqlite

from backend.core.base_db import AsyncSQLiteDB
from .models import Job, JobStatus, QueueType

logger = logging.getLogger(__name__)

# SQLite schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    queue_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    progress INTEGER DEFAULT 0,
    progress_message TEXT DEFAULT 'Queued',
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 14,
    result_json TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_queue_status ON jobs(queue_type, status);
CREATE INDEX IF NOT EXISTS idx_jobs_session ON jobs(session_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


class DualJobQueue(AsyncSQLiteDB):
    """
    Manages dual queues for US and non-US company analysis.

    Features:
    - SQLite persistence for browser independence
    - Separate queues to prevent rate limit contention
    - Progress tracking with callbacks
    - Job resumption after server restart
    """

    SCHEMA = SCHEMA
    _db_name = "Job queue"

    def __init__(self, db_path: str = "data/jobs.db"):
        super().__init__(db_path)

    async def enqueue(
        self,
        session_id: str,
        ticker: str,
        queue_type: QueueType,
    ) -> Job:
        """
        Add a new job to the appropriate queue.

        Args:
            session_id: The analysis session ID
            ticker: Stock ticker symbol
            queue_type: US or NON_US queue

        Returns:
            The created Job object
        """
        await self.initialize()

        job = Job(
            job_id=str(uuid.uuid4()),
            session_id=session_id,
            ticker=ticker.upper(),
            queue_type=queue_type,
            status=JobStatus.PENDING,
            created_at=datetime.now(),
        )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO jobs (
                    job_id, session_id, ticker, queue_type, status,
                    created_at, progress, progress_message, current_step, total_steps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.session_id,
                    job.ticker,
                    job.queue_type.value,
                    job.status.value,
                    job.created_at.isoformat(),
                    job.progress,
                    job.progress_message,
                    job.current_step,
                    job.total_steps,
                ),
            )
            await db.commit()

        logger.info(f"Enqueued job {job.job_id} for {ticker} in {queue_type.value} queue")
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_job(dict(row))
        return None

    async def get_job_by_session(self, session_id: str) -> Optional[Job]:
        """Get the most recent job for a session."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM jobs
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_job(dict(row))
        return None

    async def get_pending_jobs(self, queue_type: QueueType, limit: int = 10) -> List[Job]:
        """Get pending jobs from a specific queue."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM jobs
                WHERE queue_type = ? AND status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (queue_type.value, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_job(dict(row)) for row in rows]

    async def claim_job(self, queue_type: QueueType) -> Optional[Job]:
        """
        Atomically claim a pending job from the queue.

        Uses UPDATE ... RETURNING to atomically select and mark a job as running,
        preventing race conditions between workers.

        Returns:
            Job if one was claimed, None if no pending jobs available
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Use a transaction to atomically claim a job
            # SQLite doesn't have SELECT FOR UPDATE, but we can use
            # UPDATE with a subquery and check rowcount
            cursor = await db.execute(
                """
                UPDATE jobs
                SET status = 'running', started_at = ?
                WHERE job_id = (
                    SELECT job_id FROM jobs
                    WHERE queue_type = ? AND status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 1
                )
                RETURNING *
                """,
                (datetime.now().isoformat(), queue_type.value),
            )
            row = await cursor.fetchone()
            await db.commit()

            if row:
                job = self._row_to_job(dict(row))
                logger.info(f"Job {job.job_id} claimed and started")
                return job
            return None

    async def update_progress(
        self,
        job_id: str,
        progress: int,
        message: str,
        step: int = 0,
    ):
        """Update job progress."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE jobs
                SET progress = ?, progress_message = ?, current_step = ?
                WHERE job_id = ?
                """,
                (progress, message, step, job_id),
            )
            await db.commit()

    async def start_job(self, job_id: str):
        """Mark a job as running."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE jobs
                SET status = 'running', started_at = ?
                WHERE job_id = ?
                """,
                (datetime.now().isoformat(), job_id),
            )
            await db.commit()
        logger.info(f"Job {job_id} started")

    async def complete_job(self, job_id: str, result: dict):
        """Mark a job as complete with results."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE jobs
                SET status = 'complete', completed_at = ?,
                    progress = 100, progress_message = 'Complete',
                    result_json = ?
                WHERE job_id = ?
                """,
                (datetime.now().isoformat(), json.dumps(result), job_id),
            )
            await db.commit()
        logger.info(f"Job {job_id} completed")

    async def fail_job(self, job_id: str, error: str):
        """Mark a job as failed with error message."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE jobs
                SET status = 'failed', completed_at = ?, error = ?
                WHERE job_id = ?
                """,
                (datetime.now().isoformat(), error, job_id),
            )
            await db.commit()
        logger.error(f"Job {job_id} failed: {error}")

    async def get_queue_stats(self) -> dict:
        """Get statistics for both queues."""
        await self.initialize()

        stats = {"us": {}, "non_us": {}}

        async with aiosqlite.connect(self.db_path) as db:
            for queue_type in [QueueType.US, QueueType.NON_US]:
                async with db.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM jobs
                    WHERE queue_type = ?
                    GROUP BY status
                    """,
                    (queue_type.value,),
                ) as cursor:
                    rows = await cursor.fetchall()
                    stats[queue_type.value] = {row[0]: row[1] for row in rows}

        return stats

    async def get_queue_position(self, job_id: str) -> int:
        """Get the position of a job in its queue (1-indexed, 0 if not pending)."""
        job = await self.get_job(job_id)
        if not job or job.status != JobStatus.PENDING:
            return 0

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT COUNT(*) FROM jobs
                WHERE queue_type = ? AND status = 'pending'
                AND created_at < ?
                """,
                (job.queue_type.value, job.created_at.isoformat()),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] + 1 if row else 1

    async def cleanup_old_jobs(self, days: int = 7):
        """Remove completed/failed jobs older than specified days."""
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            result = await db.execute(
                """
                DELETE FROM jobs
                WHERE status IN ('complete', 'failed')
                AND completed_at < ?
                """,
                (cutoff,),
            )
            await db.commit()
            logger.info(f"Cleaned up {result.rowcount} old jobs")

    def _row_to_job(self, row: dict) -> Job:
        """Convert a database row to a Job object."""
        result = None
        if row.get("result_json"):
            try:
                result = json.loads(row["result_json"])
            except json.JSONDecodeError:
                pass

        return Job(
            job_id=row["job_id"],
            session_id=row["session_id"],
            ticker=row["ticker"],
            queue_type=QueueType(row["queue_type"]),
            status=JobStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row.get("started_at") else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
            progress=row.get("progress", 0),
            progress_message=row.get("progress_message", ""),
            current_step=row.get("current_step", 0),
            total_steps=row.get("total_steps", 14),
            result=result,
            error=row.get("error"),
        )


# Global job queue instance
job_queue = DualJobQueue()
