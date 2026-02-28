"""Tests for RateLimiter token bucket implementation.

Covers:
- Initial token count
- Token decrement on acquire
- Refill based on elapsed time
- Daily reset on date change

Uses importlib to load worker.py directly, avoiding the heavy import chain
in backend.jobs.__init__ (which pulls in pipeline_config -> yfinance).
"""

import importlib.util
import sys
import time
import types
from datetime import date
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

_WORKER_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / "jobs" / "worker.py"

# Snapshot modules we're about to touch so we can restore them after loading.
_TOUCH = [
    "backend.jobs",
    "backend.jobs.models",
    "backend.jobs.queue",
    "backend.jobs.worker",
]
_ORIGINALS = {name: sys.modules.get(name) for name in _TOUCH}

# Provide a fake backend.jobs package with the minimal symbols worker.py needs.
_jobs_pkg = types.ModuleType("backend.jobs")
_jobs_pkg.__path__ = [str(_WORKER_PATH.parent)]
_jobs_pkg.__package__ = "backend.jobs"
sys.modules["backend.jobs"] = _jobs_pkg

_models = types.ModuleType("backend.jobs.models")
_models.Job = type("Job", (), {})
_models.JobStatus = type(
    "JobStatus", (), {"RUNNING": "running", "COMPLETE": "complete", "ERROR": "error"}
)
_models.QueueType = type("QueueType", (), {})
sys.modules["backend.jobs.models"] = _models

_queue = types.ModuleType("backend.jobs.queue")
_queue.job_queue = None
sys.modules["backend.jobs.queue"] = _queue

# Load worker.py under its real name so relative imports resolve.
_spec = importlib.util.spec_from_file_location(
    "backend.jobs.worker", _WORKER_PATH,
    submodule_search_locations=[],
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "backend.jobs"
sys.modules["backend.jobs.worker"] = _mod
_spec.loader.exec_module(_mod)

RateLimiter = _mod.RateLimiter

# Restore original sys.modules state so other tests (test_imports.py) still
# get the real modules.
for _name in _TOUCH:
    if _ORIGINALS[_name] is not None:
        sys.modules[_name] = _ORIGINALS[_name]
    else:
        sys.modules.pop(_name, None)


@pytest.mark.asyncio
class TestRateLimiter:
    """Token bucket rate limiter for API calls."""

    async def test_initial_tokens(self):
        rl = RateLimiter(requests_per_minute=60)
        assert rl.minute_tokens == 60

    async def test_initial_day_tokens_none(self):
        rl = RateLimiter(requests_per_minute=60)
        assert rl.day_tokens == float("inf")

    async def test_initial_day_tokens_configured(self):
        rl = RateLimiter(requests_per_minute=60, requests_per_day=500)
        assert rl.day_tokens == 500

    async def test_acquire_decrements_minute_tokens(self):
        rl = RateLimiter(requests_per_minute=60)
        rl.last_refill = time.time()
        rl.minute_tokens = 60

        await rl.acquire()
        assert rl.minute_tokens < 60

    async def test_acquire_decrements_day_tokens(self):
        rl = RateLimiter(requests_per_minute=60, requests_per_day=500)
        rl.last_refill = time.time()
        rl.minute_tokens = 60
        rl.day_tokens = 500

        await rl.acquire()
        assert rl.day_tokens == 499

    async def test_refill_restores_tokens(self):
        rl = RateLimiter(requests_per_minute=60)
        rl.minute_tokens = 0
        rl.last_refill = time.time() - 1.0

        await rl._refill()
        assert rl.minute_tokens >= 0.9

    async def test_refill_caps_at_max(self):
        rl = RateLimiter(requests_per_minute=60)
        rl.minute_tokens = 59
        rl.last_refill = time.time() - 10.0

        await rl._refill()
        assert rl.minute_tokens == 60

    async def test_daily_reset(self):
        rl = RateLimiter(requests_per_minute=60, requests_per_day=500)
        rl.day_tokens = 0
        rl.day_start = date(2020, 1, 1)

        await rl._refill()
        assert rl.day_tokens == 500

    async def test_acquire_waits_when_exhausted(self):
        rl = RateLimiter(requests_per_minute=60)
        rl.minute_tokens = 0
        rl.last_refill = time.time()

        call_count = 0
        original_refill = rl._refill

        async def mock_refill():
            nonlocal call_count
            call_count += 1
            await original_refill()
            if call_count >= 1:
                rl.minute_tokens = 1

        with patch.object(rl, '_refill', side_effect=mock_refill):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await rl.acquire()

        assert call_count >= 1
