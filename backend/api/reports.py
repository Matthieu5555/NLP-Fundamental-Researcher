"""
Reports API endpoints.

Handles report retrieval and export (markdown, PDF).
"""

from flask import Blueprint, request, jsonify, send_file
from core.session import session_manager
import io

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/<session_id>', methods=['GET'])
def get_report(session_id: str):
    """
    Get the current report for a session.

    Query parameters:
        format: 'json' (default) or 'markdown'

    Returns:
        Report in requested format
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    if not session.report_state:
        return jsonify({'error': 'No report generated yet'}), 404

    format_type = request.args.get('format', 'json')

    if format_type == 'markdown':
        markdown = session.report_state.to_markdown()
        return markdown, 200, {'Content-Type': 'text/markdown'}
    else:
        return jsonify(session.report_state.to_dict())


@reports_bp.route('/<session_id>/export/pdf', methods=['POST'])
def export_pdf(session_id: str):
    """
    Export report as PDF.

    Returns:
        PDF file download
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    if not session.report_state:
        return jsonify({'error': 'No report generated yet'}), 404

    # TODO: Integrate PDF generation
    # from report_generator import generate_pdf
    # pdf_bytes = generate_pdf(session.report_state)

    # For now, return markdown as text
    markdown = session.report_state.to_markdown()

    # Create a file-like object
    pdf_io = io.BytesIO(markdown.encode('utf-8'))
    pdf_io.seek(0)

    return send_file(
        pdf_io,
        mimetype='text/plain',  # TODO: Change to 'application/pdf' when PDF gen is implemented
        as_attachment=True,
        download_name=f'{session.ticker}_analysis.txt'
    )


@reports_bp.route('/<session_id>/sections', methods=['GET'])
def get_sections(session_id: str):
    """
    Get all report sections.

    Returns:
        {
            "session_id": "uuid",
            "ticker": "AAPL",
            "sections": {...}
        }
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    if not session.report_state:
        return jsonify({'error': 'No report generated yet'}), 404

    return jsonify({
        'session_id': session_id,
        'ticker': session.report_state.ticker,
        'sections': {
            section_id: section.to_dict()
            for section_id, section in session.report_state.sections.items()
        },
        'stats': session.report_state.get_stats()
    })


@reports_bp.route('/<session_id>/sections/<section_id>', methods=['GET'])
def get_section(session_id: str, section_id: str):
    """
    Get a specific report section.

    Returns:
        Section data
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    if not session.report_state:
        return jsonify({'error': 'No report generated yet'}), 404

    section = session.report_state.get_section(section_id)

    if not section:
        return jsonify({'error': 'Section not found'}), 404

    return jsonify(section.to_dict())


@reports_bp.route('/<session_id>/sections/<section_id>', methods=['PUT'])
def update_section(session_id: str, section_id: str):
    """
    Update a report section.

    Request body:
        {
            "content": "Updated markdown content",
            "sources": ["https://example.com"]
        }

    Returns:
        Updated section data
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    if not session.report_state:
        return jsonify({'error': 'No report generated yet'}), 404

    data = request.get_json()

    if not data or 'content' not in data:
        return jsonify({'error': 'content required'}), 400

    try:
        session.report_state.update_section(
            section_id,
            data['content'],
            data.get('sources')
        )

        section = session.report_state.get_section(section_id)
        return jsonify(section.to_dict())

    except KeyError as e:
        return jsonify({'error': str(e)}), 404


@reports_bp.route('/<session_id>/stats', methods=['GET'])
def get_stats(session_id: str):
    """
    Get report statistics.

    Returns:
        {
            "ticker": "AAPL",
            "section_count": 8,
            "total_characters": 5000,
            ...
        }
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    if not session.report_state:
        return jsonify({'error': 'No report generated yet'}), 404

    return jsonify(session.report_state.get_stats())
