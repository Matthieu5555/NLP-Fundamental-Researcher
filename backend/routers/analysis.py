"""
Analysis API router.

Handles stock analysis initiation, job queue management, and status checking.
All endpoints require authentication and sessions are scoped to the authenticated user.

Endpoints:
    POST /start                          - Start new analysis (enqueue job)
    GET  /{session_id}/status            - Get session/job status
    GET  /{session_id}/progress          - SSE stream for progress updates
    POST /{session_id}/run               - Run analysis (legacy SSE stream)
    DELETE /{session_id}                 - Delete session
    GET  /sessions                        - List user's sessions
    GET  /{session_id}/financial-statements - Get financial statements
    GET  /{session_id}/company-info      - Get company classification info

Job Queue Integration:
    - POST /start creates a session AND enqueues a job to the appropriate queue
    - US companies go to US queue (fast FDS API)
    - Non-US companies go to Non-US queue (rate-limited Alpha Vantage)
    - Jobs persist to SQLite and survive server restarts
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.core.session import session_manager, AnalysisSession
from backend.core.report_builder import ReportState
from backend.core.auth_db import User
from backend.core.settings_db import settings_db
from backend.middleware.auth_middleware import get_current_user
from backend.dependencies import get_user_session
from backend.jobs import job_queue, QueueType, JobStatus
from src_george_researcher.data_fetchers.data_router import classify_company
from src_george_researcher.analysis.pipeline_config import US_TOTAL_STEPS, NON_US_TOTAL_STEPS

logger = logging.getLogger(__name__)

router = APIRouter()


class StartAnalysisRequest(BaseModel):
    """Request body for starting an analysis."""

    ticker: str
    options: Optional[dict] = None


class StartAnalysisResponse(BaseModel):
    """Response for start analysis endpoint."""

    session_id: str
    job_id: str
    ticker: str
    queue_type: str
    status: str
    message: str


@router.post("/start", response_model=StartAnalysisResponse)
async def start_analysis(
    request: StartAnalysisRequest, user: User = Depends(get_current_user)
):
    """
    Start a new stock analysis session and enqueue job.

    Requires authentication. Session will be owned by the authenticated user.

    Classifies the company to determine queue assignment:
    - US companies: Fast queue using FinancialDatasets.ai
    - Non-US companies: Slow queue using Alpha Vantage (rate-limited)

    The job will be processed by background workers and the browser
    can be closed - progress is tracked in SQLite.
    """
    ticker = request.ticker.upper()
    options = request.options or {}

    # Fetch user's LLM settings to pass to analysis workers
    user_settings = await settings_db.get_settings(user.id)
    llm_config = {
        "model": user_settings.llm_model,
        "temperature": user_settings.temperature,
        "master_prompt": user_settings.master_system_prompt,
        "analysis_depth": user_settings.analysis_depth,
    }

    # Classify company to determine queue
    classification = classify_company(ticker)
    queue_type = QueueType.US if classification.is_us else QueueType.NON_US

    # Create session with user ownership and LLM settings
    session = session_manager.create_session(
        ticker=ticker,
        user_id=user.id,
        metadata={"options": options, "llm_config": llm_config},
    )

    # Initialize report state
    with session_manager.session_context(session.session_id) as s:
        if s:
            s.report_state = ReportState(ticker=ticker)

    # Enqueue job
    job = await job_queue.enqueue(
        session_id=session.session_id,
        ticker=ticker,
        queue_type=queue_type,
    )

    logger.info(
        f"Analysis started: session={session.session_id}, job={job.job_id}, queue={queue_type.value}, user={user.id}"
    )

    # Note: Actual cost/token tracking happens in the worker when analysis completes
    # See backend/jobs/worker.py - we track real costs from LLM responses

    return StartAnalysisResponse(
        session_id=session.session_id,
        job_id=job.job_id,
        ticker=ticker,
        queue_type=queue_type.value,
        status="queued",
        message=f"Analysis queued for {ticker} ({queue_type.value} queue)",
    )


@router.get("/{session_id}/status")
async def get_status(
    session: AnalysisSession = Depends(get_user_session),
):
    """
    Get the status of an analysis session and its job.

    User must own the session. Works even after browser is closed - retrieves status from SQLite.
    """
    session_id = session.session_id

    # Get job status
    job = await job_queue.get_job_by_session(session_id)

    belief_stats = session.belief_graph.get_stats()
    report_stats = session.report_state.get_stats() if session.report_state else {}

    response = {
        "session_id": session.session_id,
        "ticker": session.ticker,
        "message_count": len(session.conversation_history),
        "report_sections": report_stats.get("section_count", 0),
        "beliefs_count": belief_stats["belief_count"],
        "created_at": session.created_at.isoformat(),
        "total_tokens": session.metadata.get("total_tokens", 0),
        "total_cost_usd": session.metadata.get("total_cost_usd", 0.0),
    }

    # Add job status if available
    if job:
        response["job"] = {
            "job_id": job.job_id,
            "status": job.status.value,
            "progress": job.progress,
            "progress_message": job.progress_message,
            "current_step": job.current_step,
            "total_steps": job.total_steps,
            "queue_type": job.queue_type.value,
            "error": job.error,
        }

        # Determine overall status from job
        if job.status == JobStatus.COMPLETE:
            response["status"] = "ready"
        elif job.status == JobStatus.FAILED:
            response["status"] = "failed"
        elif job.status == JobStatus.RUNNING:
            response["status"] = "running"
        else:
            response["status"] = "queued"
            # Get queue position
            position = await job_queue.get_queue_position(job.job_id)
            response["job"]["queue_position"] = position
    else:
        response["status"] = "ready"

    return response


@router.get("/{session_id}/progress")
async def stream_progress(
    token: Optional[str] = Query(None),  # For SSE which can't set headers
    session: AnalysisSession = Depends(get_user_session),
):
    """
    SSE stream for job progress updates.

    User must own the session. Polls SQLite for job status and streams updates.
    Alternative to polling /status endpoint.
    """
    session_id = session.session_id

    async def generate():
        while True:
            job = await job_queue.get_job_by_session(session_id)

            if not job:
                yield f"data: {json.dumps({'error': 'No job found'})}\n\n"
                yield "data: [DONE]\n\n"
                break

            data = {
                "status": job.status.value,
                "progress": job.progress,
                "message": job.progress_message,
                "step": job.current_step,
                "total": job.total_steps,
            }

            if job.status == JobStatus.COMPLETE:
                data["result"] = "complete"
                yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
                break
            elif job.status == JobStatus.FAILED:
                data["error"] = job.error
                yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
                break
            else:
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.delete("/{session_id}")
async def delete_session(
    session: AnalysisSession = Depends(get_user_session),
):
    """Delete an analysis session. User must own the session."""
    session_id = session.session_id

    # Get file path before deleting
    session_file = session_manager._get_session_file_path(session)

    success = session_manager.delete_session(session_id)

    if success and session_file.exists():
        try:
            session_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete session file: {e}")

    return {"message": "Session deleted"}


@router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user)):
    """List all active analysis sessions for the authenticated user."""
    sessions = session_manager.list_sessions(user_id=user.id)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/{session_id}/financial-statements")
async def get_financial_statements(
    session: AnalysisSession = Depends(get_user_session),
):
    """
    Get financial statements for a session's ticker.

    User must own the session. Returns detailed financial statements (US companies only).
    """
    session_id = session.session_id
    ticker = session.ticker
    classification = classify_company(ticker)

    if not classification.is_us:
        return {
            "is_available": False,
            "ticker": ticker,
            "company_name": classification.company_name or ticker,
            "region": classification.region.value,
            "message": "Financial statements are only available for US companies",
            "income_statements": [],
            "balance_sheets": [],
            "cash_flows": [],
            "ratios": [],
            "highlights": [],
            "summary": "",
            "error": "Not a US company - detailed financial statements require FinancialDatasets.ai (US only)",
        }

    try:
        from src_george_researcher.data_fetchers.data_router import get_data_router
        from src_george_researcher.analysis.us.financial_analysis import (
            analyze_financial_statements,
        )
        import yfinance as yf

        router_instance = get_data_router()
        financials, error = router_instance.fetch_financials(
            ticker, period="annual", limit=5
        )

        if error:
            logger.warning(f"Failed to fetch financials for {ticker}: {error}")
            return {
                "is_available": False,
                "ticker": ticker,
                "company_name": classification.company_name or ticker,
                "error": error,
                "income_statements": [],
                "balance_sheets": [],
                "cash_flows": [],
                "ratios": [],
                "highlights": [],
                "summary": "",
            }

        # Get current price, shares outstanding, and supplementary ratios from yfinance
        current_price = None
        shares_outstanding = None
        yf_ratios = {}
        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            shares_outstanding = info.get("sharesOutstanding")

            # Get pre-computed ratios from yfinance as fallback
            yf_ratios = {
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "peg_ratio": info.get("pegRatio"),
                "ev_to_ebitda": info.get("enterpriseToEbitda"),
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "profit_margin": info.get("profitMargins"),
                "operating_margin": info.get("operatingMargins"),
                "gross_margin": info.get("grossMargins"),
                "current_ratio": info.get("currentRatio"),
                "quick_ratio": info.get("quickRatio"),
                "debt_to_equity": info.get("debtToEquity"),
                "book_value": info.get("bookValue"),
                "total_cash": info.get("totalCash"),
                "total_debt": info.get("totalDebt"),
            }
        except Exception as e:
            logger.warning(f"Could not fetch price data for {ticker}: {e}")

        company_name = classification.company_name or ticker
        result = analyze_financial_statements(
            ticker,
            company_name,
            financials,
            current_price=current_price,
            shares_outstanding=shares_outstanding,
            yf_ratios=yf_ratios,
        )

        # Cache in session metadata
        with session_manager.session_context(session_id) as sess:
            if sess:
                sess.metadata["financial_statements"] = result.to_dict()

        return result.to_dict()

    except Exception as e:
        logger.error(f"Error fetching financial statements for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/company-info")
async def get_company_info(
    session: AnalysisSession = Depends(get_user_session),
):
    """Get company classification and data availability info. User must own the session."""
    classification = classify_company(session.ticker)
    return classification.to_dict()


@router.get("/queue/stats")
async def get_queue_stats():
    """Get statistics for both job queues."""
    stats = await job_queue.get_queue_stats()
    return stats


@router.post("/{session_id}/run")
async def run_analysis_stream(
    session: AnalysisSession = Depends(get_user_session),
):
    """
    Run analysis with SSE progress streaming (legacy endpoint for frontend compatibility).

    User must own the session. This endpoint:
    1. Checks if a job exists for this session (from /start)
    2. If not, creates one
    3. Streams progress updates until complete
    4. Returns cost breakdown when done
    """
    session_id = session.session_id
    ticker = session.ticker

    # Check if job already exists
    job = await job_queue.get_job_by_session(session_id)

    if not job:
        # Create job if doesn't exist (for legacy /start -> /run flow)
        classification = classify_company(ticker)
        queue_type = QueueType.US if classification.is_us else QueueType.NON_US

        job = await job_queue.enqueue(
            session_id=session_id,
            ticker=ticker,
            queue_type=queue_type,
        )

    async def generate():
        """Stream progress updates via SSE."""
        last_progress = -1
        total_steps = US_TOTAL_STEPS if job.queue_type == QueueType.US else NON_US_TOTAL_STEPS

        while True:
            current_job = await job_queue.get_job_by_session(session_id)

            if not current_job:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Job not found'})}\n\n"
                yield "data: [DONE]\n\n"
                break

            # Send progress update if changed
            if current_job.progress != last_progress:
                last_progress = current_job.progress
                yield f"data: {json.dumps({'status': 'running', 'message': current_job.progress_message, 'step': current_job.current_step, 'total': total_steps})}\n\n"

            if current_job.status == JobStatus.COMPLETE:
                # Get cost breakdown from session metadata
                with session_manager.session_context(session_id) as sess:
                    cost_usd = sess.metadata.get("total_cost_usd", 0.0) if sess else 0.0
                    cost_breakdown = (
                        sess.metadata.get("cost_breakdown", {}) if sess else {}
                    )
                    section_count = (
                        len(sess.report_state.sections)
                        if sess and sess.report_state
                        else 0
                    )

                yield f"data: {json.dumps({'status': 'complete', 'message': 'Analysis complete!', 'step': total_steps, 'total': total_steps, 'sections': section_count, 'cost_usd': round(cost_usd, 4), 'cost_breakdown': cost_breakdown})}\n\n"
                yield "data: [DONE]\n\n"
                break

            elif current_job.status == JobStatus.FAILED:
                yield f"data: {json.dumps({'status': 'error', 'message': current_job.error or 'Analysis failed'})}\n\n"
                yield "data: [DONE]\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream")
