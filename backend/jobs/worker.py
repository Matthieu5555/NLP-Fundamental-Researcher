"""
Worker implementation for the dual job queue system.

Workers poll their assigned queue and execute analysis jobs.
US workers use FinancialDatasets.ai (fast), Non-US workers use Alpha Vantage (rate-limited).

Usage Tracking:
    After each analysis completes, the worker records ACTUAL token counts
    and costs to the usage database. These values come from the LLM API
    responses, not estimates.
"""

import asyncio
import logging
import time
from typing import Optional
from datetime import datetime

from .models import Job, QueueType
from .queue import job_queue

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    """

    def __init__(
        self, requests_per_minute: int, requests_per_day: Optional[int] = None
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self.minute_tokens = requests_per_minute
        self.day_tokens = requests_per_day or float("inf")
        self.last_refill = time.time()
        self.day_start = datetime.now().date()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a request can be made."""
        async with self._lock:
            await self._refill()

            while self.minute_tokens <= 0 or self.day_tokens <= 0:
                # Wait for refill
                wait_time = 60.0 / self.requests_per_minute
                await asyncio.sleep(wait_time)
                await self._refill()

            self.minute_tokens -= 1
            if self.requests_per_day:
                self.day_tokens -= 1

    async def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Refill minute tokens
        refill_amount = elapsed * (self.requests_per_minute / 60.0)
        self.minute_tokens = min(
            self.requests_per_minute, self.minute_tokens + refill_amount
        )
        self.last_refill = now

        # Reset daily tokens at midnight
        today = datetime.now().date()
        if today > self.day_start:
            self.day_start = today
            self.day_tokens = self.requests_per_day or float("inf")


# Pre-configured rate limiters
US_RATE_LIMITER = RateLimiter(requests_per_minute=1000)  # FDS: generous limits
NON_US_RATE_LIMITER = RateLimiter(
    requests_per_minute=5, requests_per_day=500
)  # Alpha Vantage: strict limits


class Worker:
    """
    Worker that processes jobs from a specific queue.

    Features:
    - Polls SQLite for pending jobs
    - Executes analysis using existing orchestrator
    - Updates progress in real-time
    - Respects rate limits
    """

    def __init__(
        self,
        worker_id: str,
        queue_type: QueueType,
        rate_limiter: RateLimiter,
    ):
        self.worker_id = worker_id
        self.queue_type = queue_type
        self.rate_limiter = rate_limiter
        self.running = False
        self._current_job: Optional[Job] = None

    async def start(self):
        """Start the worker loop."""
        self.running = True
        logger.info(
            f"Worker {self.worker_id} started for {self.queue_type.value} queue"
        )

        while self.running:
            try:
                # Atomically claim the next pending job
                # This prevents race conditions between workers
                job = await job_queue.claim_job(self.queue_type)

                if job:
                    await self._execute_job(job)
                else:
                    # No jobs available, wait before polling again
                    await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
                await asyncio.sleep(5)  # Back off on error

    async def stop(self):
        """Stop the worker gracefully."""
        self.running = False
        logger.info(f"Worker {self.worker_id} stopping")

    async def _execute_job(self, job: Job):
        """Execute a single analysis job."""
        self._current_job = job
        logger.info(
            f"Worker {self.worker_id} executing job {job.job_id} for {job.ticker}"
        )

        try:
            # Job is already marked as running by claim_job()

            # Respect rate limits before making API calls
            await self.rate_limiter.acquire()

            # Run the analysis
            result = await self._run_analysis(job)

            # Mark job as complete
            await job_queue.complete_job(job.job_id, result)
            logger.info(f"Worker {self.worker_id} completed job {job.job_id}")

            # Update watchlist fair value if DCF completed
            fair_value = result.get("_fair_value_per_share") if result else None
            if fair_value is not None:
                try:
                    from backend.core.watchlist_db import watchlist_db
                    await watchlist_db.broadcast_fair_value(
                        job.ticker, fair_value, job.session_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to update watchlist fair value: {e}")

            # Track ACTUAL usage (real tokens and costs from LLM responses)
            await self._track_usage(job)

        except Exception as e:
            logger.error(f"Worker {self.worker_id} job {job.job_id} failed: {e}")
            await job_queue.fail_job(job.job_id, str(e))

        finally:
            self._current_job = None

    async def _track_usage(self, job: Job):
        """
        Track ACTUAL usage after analysis completes.

        Reads real token counts and costs from session metadata
        (populated by the orchestrator from LLM API responses).
        """
        from backend.core.session import session_manager
        from backend.middleware.usage_tracker import track_request
        from backend.core.auth_db import auth_db

        try:
            session = session_manager.get_session(job.session_id)
            if not session:
                logger.warning(
                    f"Cannot track usage: session {job.session_id} not found"
                )
                return

            # Get user for tracking
            user_id = session.user_id
            if not user_id:
                logger.warning(
                    f"Cannot track usage: no user_id in session {job.session_id}"
                )
                return

            user = await auth_db.get_user_by_id(user_id)
            if not user:
                logger.warning(f"Cannot track usage: user {user_id} not found")
                return

            # Read ACTUAL costs from session metadata (set by orchestrator)
            actual_cost = session.metadata.get("total_cost_usd", 0.0)
            actual_tokens = session.metadata.get("total_tokens", 0)

            # Record real usage
            await track_request(
                user=user,
                endpoint="/api/analysis/complete",
                method="POST",
                ticker=job.ticker,
                session_id=job.session_id,
                cost_usd=actual_cost,
                tokens_used=actual_tokens,
            )

            logger.info(
                f"Usage tracked for {job.ticker}: ${actual_cost:.4f}, {actual_tokens} tokens"
            )

        except Exception as e:
            # Don't fail the job if usage tracking fails
            logger.warning(f"Failed to track usage for job {job.job_id}: {e}")

    async def _run_analysis(self, job: Job) -> dict:
        """
        Run the actual analysis for a job.

        Routes to US or Non-US orchestrator based on job queue type:
        - US Queue: Uses FinancialDatasets.ai (fast, comprehensive)
        - Non-US Queue: Uses yfinance + Alpha Vantage (rate limited)
        """
        # Import here to avoid circular imports
        from backend.agents.orchestrator_wrapper import run_full_analysis
        from backend.core.session import session_manager
        from backend.core.report_builder import ReportState

        # Get session - try memory first, then load from disk if not found
        session = session_manager.get_session(job.session_id)
        if not session:
            # Session not in memory - try loading from disk
            # This can happen after server restart or in reload mode
            logger.warning(
                f"Session {job.session_id} not in memory, attempting to load from disk"
            )
            session_file = session_manager.storage_dir / f"{job.session_id}.json"
            if session_file.exists():
                try:
                    loaded_session = session_manager._load_session_from_file(
                        session_file
                    )
                    # Add to in-memory cache
                    with session_manager._lock:
                        session_manager._sessions[job.session_id] = loaded_session
                        session_manager._session_locks[job.session_id] = __import__(
                            "threading"
                        ).Lock()
                    session = loaded_session
                    logger.info(f"Loaded session {job.session_id} from disk")
                except Exception as e:
                    logger.error(f"Failed to load session from disk: {e}")

            if not session:
                raise ValueError(
                    f"Session {job.session_id} not found (checked memory and disk)"
                )

        # Ensure report_state exists (may be missing if session was just created)
        if not session.report_state:
            session.report_state = ReportState(ticker=job.ticker)
            session_manager._save_session(session)

        # Determine if this is a US company based on queue type
        is_us = job.queue_type == QueueType.US

        # Progress callback that updates the job queue
        async def progress_callback(step: int, total: int, message: str):
            progress = int((step / total) * 100)
            await job_queue.update_progress(job.job_id, progress, message, step)

        # Run analysis in thread pool to not block event loop
        # The orchestrator is synchronous, so we use asyncio.to_thread
        def sync_analysis():
            return run_full_analysis(
                ticker=job.ticker,
                session_id=job.session_id,
                is_us=is_us,
                progress_callback=lambda s, t, m: asyncio.run(
                    progress_callback(s, t, m)
                ),
            )

        result = await asyncio.to_thread(sync_analysis)

        return result


class WorkerPool:
    """
    Manages multiple workers across both queues.

    Default configuration:
    - US Queue: 3 workers (fast API, can parallelize)
    - Non-US Queue: 2 workers (rate-limited, careful parallelization)
    """

    def __init__(self, us_workers: int = 3, non_us_workers: int = 2):
        self.us_worker_count = us_workers
        self.non_us_worker_count = non_us_workers
        self.workers: list[Worker] = []
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        """Start all workers."""
        logger.info(
            f"Starting worker pool: {self.us_worker_count} US, {self.non_us_worker_count} Non-US"
        )

        # Create US workers
        for i in range(self.us_worker_count):
            worker = Worker(
                worker_id=f"us-{i + 1}",
                queue_type=QueueType.US,
                rate_limiter=US_RATE_LIMITER,
            )
            self.workers.append(worker)
            task = asyncio.create_task(worker.start())
            self._tasks.append(task)

        # Create Non-US workers
        for i in range(self.non_us_worker_count):
            worker = Worker(
                worker_id=f"non-us-{i + 1}",
                queue_type=QueueType.NON_US,
                rate_limiter=NON_US_RATE_LIMITER,
            )
            self.workers.append(worker)
            task = asyncio.create_task(worker.start())
            self._tasks.append(task)

        logger.info("Worker pool started")

    async def stop(self):
        """Stop all workers gracefully."""
        logger.info("Stopping worker pool")

        # Signal all workers to stop
        for worker in self.workers:
            await worker.stop()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self.workers.clear()
        self._tasks.clear()
        logger.info("Worker pool stopped")

    def get_status(self) -> dict:
        """Get status of all workers."""
        return {
            "total_workers": len(self.workers),
            "us_workers": self.us_worker_count,
            "non_us_workers": self.non_us_worker_count,
            "workers": [
                {
                    "id": w.worker_id,
                    "queue": w.queue_type.value,
                    "running": w.running,
                    "current_job": w._current_job.job_id if w._current_job else None,
                }
                for w in self.workers
            ],
        }


# Global worker pool instance
worker_pool = WorkerPool()
