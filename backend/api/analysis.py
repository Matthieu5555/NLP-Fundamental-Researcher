"""
Analysis API endpoints.

Handles stock analysis initiation, status checking, and initial report generation.
"""

from flask import Blueprint, request, jsonify, Response
from core.session import session_manager
from core.report_builder import ReportState, SectionType
from core.contradiction_detector import detect_contradictions_and_research_items
import time
import sys
from pathlib import Path
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import via wrapper to handle relative imports
from agents.orchestrator_wrapper import run_analysis

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/start', methods=['POST'])
def start_analysis():
    """
    Start a new stock analysis session.

    Request body:
        {
            "ticker": "AAPL",
            "options": {
                "include_moat": true,
                "include_swot": true,
                "debate_rounds": 2
            }
        }

    Returns:
        {
            "session_id": "uuid",
            "ticker": "AAPL",
            "status": "initializing"
        }
    """
    data = request.get_json()

    if not data or 'ticker' not in data:
        return jsonify({'error': 'Ticker symbol required'}), 400

    ticker = data['ticker'].upper()
    options = data.get('options', {})

    # Create new session
    session = session_manager.create_session(
        ticker=ticker,
        metadata={'options': options}
    )

    # Initialize report state
    session.report_state = ReportState(ticker=ticker)

    return jsonify({
        'session_id': session.session_id,
        'ticker': session.ticker,
        'status': 'created',
        'message': f'Analysis session created for {ticker}'
    }), 201


@analysis_bp.route('/<session_id>/status', methods=['GET'])
def get_status(session_id: str):
    """
    Get the status of an analysis session.

    Returns:
        {
            "session_id": "uuid",
            "ticker": "AAPL",
            "status": "ready",
            "message_count": 5,
            "report_sections": 8,
            "beliefs_count": 3
        }
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    belief_stats = session.belief_graph.get_stats()
    report_stats = session.report_state.get_stats() if session.report_state else {}

    return jsonify({
        'session_id': session.session_id,
        'ticker': session.ticker,
        'status': 'ready',
        'message_count': len(session.conversation_history),
        'report_sections': report_stats.get('section_count', 0),
        'beliefs_count': belief_stats['belief_count'],
        'created_at': session.created_at.isoformat()
    })


@analysis_bp.route('/<session_id>/run', methods=['POST'])
def run_initial_analysis(session_id: str):
    """
    Run the initial multi-agent analysis.

    This endpoint streams the analysis progress as Server-Sent Events.

    Returns:
        SSE stream with progress updates
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    def generate():
        """Stream analysis progress."""
        try:
            logger.info(f"Starting analysis for {session.ticker}, session {session_id}")
            yield f"data: {json.dumps({'status': 'starting', 'message': 'Validating ticker...'})}\n\n"

            # Quick validation check with yfinance
            import yfinance as yf
            ticker_obj = yf.Ticker(session.ticker)
            try:
                # Try to get basic info to validate ticker exists
                info = ticker_obj.info
                if not info or 'symbol' not in info:
                    error_msg = f"Invalid ticker symbol: {session.ticker}. Please check the symbol and try again."
                    logger.error(error_msg)
                    yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
            except Exception as e:
                error_msg = f"Could not find data for ticker {session.ticker}. Please verify the symbol is correct."
                logger.error(f"Ticker validation failed: {str(e)}")
                yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            yield f"data: {json.dumps({'status': 'starting', 'message': 'Fetching stock data...'})}\n\n"

            # Get analysis options
            options = session.metadata.get('options', {})
            logger.info(f"Analysis options: {options}")

            # Run actual analysis
            yield f"data: {json.dumps({'status': 'running', 'message': 'Running multi-agent analysis...'})}\n\n"

            logger.info("Calling run_analysis...")
            results = run_analysis(
                symbol=session.ticker,
                include_moat=options.get('include_moat', True),
                include_swot=options.get('include_swot', True),
                include_debate=options.get('include_debate', True),
                debate_rounds=options.get('debate_rounds', 2)
            )

            logger.info(f"Analysis complete, success: {results.success}")

            # Process results from FullAnalysis dataclass
            analyses_to_process = [
                ('fundamentals_analysis', 'fundamentals', SectionType.FUNDAMENTALS, 'Fundamental Analysis'),
                ('technical_analysis', 'technicals', SectionType.TECHNICALS, 'Technical Analysis'),
                ('bull_thesis', 'bull_case', SectionType.BULL_CASE, 'Bull Case'),
                ('bear_thesis', 'bear_case', SectionType.BEAR_CASE, 'Bear Case'),
                ('moat_analysis', 'moat_analysis', SectionType.MOAT_ANALYSIS, 'Competitive Moat Analysis'),
                ('swot_analysis', 'swot', SectionType.SWOT, 'SWOT Analysis'),
                ('recommendation', 'recommendation', SectionType.RECOMMENDATION, 'Investment Recommendation'),
            ]

            for attr_name, section_id, section_type, default_title in analyses_to_process:
                result = getattr(results, attr_name, None)
                if result and result.success:
                    logger.info(f"Processing {attr_name}: {result.success}")

                    yield f"data: {json.dumps({'status': 'running', 'message': f'Processing {default_title}...'})}\n\n"

                    session.report_state.add_section(
                        section_id,
                        default_title,
                        result.content,
                        section_type,
                        sources=[]
                    )
                    logger.info(f"Added section: {section_id}")

            # Generate Further Research section
            logger.info("Generating Further Research section...")
            research_content = detect_contradictions_and_research_items(results)
            session.report_state.add_section(
                'further_research',
                'Further Research',
                research_content,
                SectionType.CUSTOM
            )
            logger.info("Added Further Research section")

            logger.info(f"Analysis complete, {len(session.report_state.sections)} sections created")
            yield f"data: {json.dumps({'status': 'complete', 'message': 'Initial analysis complete', 'sections': len(session.report_state.sections)})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            import traceback
            error_msg = f"Analysis error: {str(e)}"
            logger.error(f"ERROR in analysis: {traceback.format_exc()}")
            yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"
            yield "data: [DONE]\n\n"

    return Response(generate(), content_type='text/event-stream')


@analysis_bp.route('/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete an analysis session."""
    success = session_manager.delete_session(session_id)

    if success:
        return jsonify({'message': 'Session deleted'}), 200
    else:
        return jsonify({'error': 'Session not found'}), 404


@analysis_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """List all active analysis sessions."""
    sessions = session_manager.list_sessions()
    return jsonify({'sessions': sessions, 'count': len(sessions)})
