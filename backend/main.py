"""
FastAPI application entry point for George Research.

This module sets up the FastAPI server with CORS support, SSE streaming,
background job queue workers, and routes for stock analysis and chat.

API Routes:
    /api/analysis/*  - Stock analysis initiation, status, and job queue
    /api/chat/*      - Conversational chat with analyst (SSE streaming)
    /api/companies/* - Company classification and lookup (US/Non-US)
    /api/reports/*   - Report retrieval and export (PDF, markdown)
    /api/sessions/*  - Session management (list, resume, delete)
    /api/chart/*     - Technical chart generation

Environment Variables:
    CORS_ORIGINS        - Comma-separated allowed origins (default: http://localhost:5173)
    PORT                - Server port (default: 5001)
    OPENROUTER_API_KEY  - Required for LLM calls
    GOOGLE_API_KEY      - Required for Gemini search grounding

Features:
    - Dual job queue system for browser-independent analysis
    - US Queue: Fast processing via FinancialDatasets.ai
    - Non-US Queue: Rate-limited processing via Alpha Vantage
    - SQLite persistence for job state
    - Server-Sent Events for real-time progress
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Add project root to path for sibling module imports (src_george_researcher)
# This centralizes the path manipulation that was previously done in individual wrappers
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Track server start time for uptime reporting
_start_time = datetime.now()


def validate_config() -> dict:
    """
    Validate required environment variables at startup.

    Returns a dict with:
        - valid: bool - True if all required vars are present
        - missing: list - Missing required variables
        - warnings: list - Missing optional variables that may limit functionality
    """
    required = {
        "OPENROUTER_API_KEY": "Required for all LLM calls (chat, analysis)",
    }

    recommended = {
        "GOOGLE_API_KEY": "Enables Gemini search grounding for real-time news",
        "FDS_API_KEY": "Enables detailed US company financials (FinancialDatasets.ai)",
        "JWT_SECRET": "Secret key for JWT tokens (defaults to dev secret)",
    }

    missing = []
    warnings = []

    for var, desc in required.items():
        if not os.getenv(var):
            missing.append(f"{var}: {desc}")

    for var, desc in recommended.items():
        if not os.getenv(var):
            warnings.append(f"{var}: {desc}")

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "warnings": warnings,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.

    On startup:
    - Validate configuration
    - Initialize job queue database
    - Start worker pool for background analysis

    On shutdown:
    - Stop worker pool gracefully
    """
    from backend.jobs import job_queue, worker_pool
    from backend.core.auth_db import auth_db
    from backend.core.usage_db import usage_db
    from backend.core.settings_db import settings_db

    logger.info("Starting George Research API")

    # Validate configuration
    config_status = validate_config()
    if not config_status["valid"]:
        logger.error("=" * 60)
        logger.error("CONFIGURATION ERROR - Missing required environment variables:")
        for missing in config_status["missing"]:
            logger.error(f"  ✗ {missing}")
        logger.error("=" * 60)
        logger.error("Copy backend/.env.example to backend/.env and fill in the values")
        raise RuntimeError("Missing required configuration. See logs above.")

    if config_status["warnings"]:
        logger.warning("-" * 60)
        logger.warning("Optional configuration missing (some features disabled):")
        for warn in config_status["warnings"]:
            logger.warning(f"  ⚠ {warn}")
        logger.warning("-" * 60)

    logger.info("Configuration validated ✓")

    # Initialize job queue database
    await job_queue.initialize()
    logger.info("Job queue initialized")

    # Initialize auth database
    await auth_db.initialize()
    logger.info("Auth database initialized")

    # Initialize usage database
    await usage_db.initialize()
    logger.info("Usage database initialized")

    # Initialize settings database
    await settings_db.initialize()
    logger.info("Settings database initialized")

    # Start worker pool
    await worker_pool.start()
    logger.info("Worker pool started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await worker_pool.stop()
    logger.info("Worker pool stopped")


def create_app() -> FastAPI:
    """
    Application factory function.

    Creates and configures the FastAPI application with CORS,
    routers, and the job queue system.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="George Research API",
        description="AI-powered strategic company analysis with multi-agent debate",
        version="2.1.0",
        lifespan=lifespan,
    )

    # CORS configuration
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Import and register routers
    from backend.routers import analysis, auth, cache, chart, chat, companies, reports, sessions, settings, usage, watchlist

    app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(cache.router, prefix="/api/cache", tags=["cache"])
    app.include_router(chart.router, prefix="/api/chart", tags=["chart"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
    app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
    app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
    app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])

    @app.get("/")
    async def root():
        """Root endpoint - basic status."""
        return {"status": "ok", "message": "George Research API"}

    @app.get("/health")
    async def health():
        """Health check endpoint with version, uptime, and worker status."""
        from backend.jobs import worker_pool, job_queue

        uptime = datetime.now() - _start_time
        queue_stats = await job_queue.get_queue_stats()

        return {
            "status": "healthy",
            "version": "2.1.0",
            "uptime_seconds": int(uptime.total_seconds()),
            "workers": worker_pool.get_status(),
            "queues": queue_stats,
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 5001))
    logger.info(f"Starting server on port {port}")

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("FASTAPI_ENV") == "development",
    )
