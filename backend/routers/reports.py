"""Reports API router.

Handles report retrieval and export (markdown, PDF, slides, Excel).

Endpoints:
    GET  /{session_id}                  - Get full report
    POST /{session_id}/export/pdf       - Export as PDF
    POST /{session_id}/export/slides    - Export as slide deck (PDF)
    POST /{session_id}/export/excel     - Export as Excel workbook
    POST /{session_id}/export/docx      - Export as editable Word document
    POST /{session_id}/export/pptx     - Export as editable PowerPoint deck
    GET  /{session_id}/sections         - List all sections
    GET  /{session_id}/sections/{id}    - Get specific section
    PUT  /{session_id}/sections/{id}    - Update section content
    GET  /{session_id}/stats            - Get report statistics
    POST /{session_id}/sources/{id}/exclude - Exclude a source
    POST /{session_id}/sources/{id}/restore - Restore a source
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from backend.core.session import session_manager, AnalysisSession
from backend.dependencies import get_user_session_with_report
from backend.services.export_service import ExportService, ExportFormat

logger = logging.getLogger(__name__)

router = APIRouter()

_export_service = ExportService()


class UpdateSectionRequest(BaseModel):
    """Request body for updating a section."""

    content: str
    sources: Optional[list] = None


class ExportPdfRequest(BaseModel):
    """Request body for PDF/slides/Excel export."""

    firm_id: Optional[str] = "george"
    analyst_id: Optional[str] = "default"


def _export_response(session: AnalysisSession, fmt: ExportFormat, request: ExportPdfRequest) -> Response:
    """Run an export and build the HTTP response with appropriate headers."""
    request = request or ExportPdfRequest()
    result = _export_service.export(session, fmt, request.firm_id, request.analyst_id)

    headers = {"Content-Disposition": f"attachment; filename={result.filename}"}
    if result.is_fallback:
        fallback_prefix = fmt.value.upper()
        headers[f"X-{fallback_prefix}-Fallback"] = "true"
        headers[f"X-{fallback_prefix}-Error"] = result.fallback_reason or ""

    return Response(content=result.content, media_type=result.media_type, headers=headers)


@router.get("/{session_id}")
async def get_report(
    format: str = Query(default="json"),
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Get the current report for a session. User must own the session."""
    if format == "markdown":
        markdown = session.report_state.to_markdown()
        return Response(content=markdown, media_type="text/markdown")
    return session.report_state.to_dict()


@router.post("/{session_id}/export/pdf")
async def export_pdf(
    request: ExportPdfRequest = None,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Export report as branded PDF. User must own the session."""
    try:
        return _export_response(session, ExportFormat.PDF, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")


@router.post("/{session_id}/export/slides")
async def export_slides(
    request: ExportPdfRequest = None,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Export report as McKinsey-style slide deck (PDF). User must own the session."""
    try:
        return _export_response(session, ExportFormat.SLIDES, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Slides generation failed: {e}")


@router.post("/{session_id}/export/excel")
async def export_excel(
    request: ExportPdfRequest = None,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Export structured valuation data as Excel. User must own the session."""
    try:
        return _export_response(session, ExportFormat.EXCEL, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {e}")


@router.post("/{session_id}/export/docx")
async def export_docx(
    request: ExportPdfRequest = None,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Export report as editable Word document. User must own the session."""
    try:
        return _export_response(session, ExportFormat.DOCX, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DOCX generation failed: {e}")


@router.post("/{session_id}/export/pptx")
async def export_pptx(
    request: ExportPdfRequest = None,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Export report as editable PowerPoint deck. User must own the session."""
    try:
        return _export_response(session, ExportFormat.PPTX, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PPTX generation failed: {e}")


@router.get("/{session_id}/sections")
async def get_sections(
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Get all report sections. User must own the session."""
    return {
        "session_id": session.session_id,
        "ticker": session.report_state.ticker,
        "sections": {
            section_id: section.to_dict()
            for section_id, section in session.report_state.sections.items()
        },
        "stats": session.report_state.get_stats(),
        "contradictions": session.metadata.get("contradictions", []),
        "research_gaps": session.metadata.get("research_gaps", []),
        "excluded_source_ids": session.report_state.excluded_source_ids,
    }


@router.get("/{session_id}/sections/{section_id}")
async def get_section(
    section_id: str,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Get a specific report section. User must own the session."""
    section = session.report_state.get_section(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section.to_dict()


@router.put("/{session_id}/sections/{section_id}")
async def update_section(
    section_id: str,
    request: UpdateSectionRequest,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Update a report section. User must own the session."""
    existing_section = session.report_state.get_section(section_id)
    if not existing_section:
        raise HTTPException(status_code=404, detail=f'Section "{section_id}" not found')

    if not request.content or not request.content.strip():
        raise HTTPException(status_code=400, detail="content must be a non-empty string")

    try:
        session.report_state.update_section(section_id, request.content, request.sources)
        session_manager.update_session(session.session_id)
        section = session.report_state.get_section(section_id)
        return section.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.get("/{session_id}/stats")
async def get_stats(
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Get report statistics. User must own the session."""
    return session.report_state.get_stats()


@router.get("/{session_id}/valuation-data")
async def get_valuation_data(
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Get structured valuation data for interactive frontend components."""
    return {
        "dcf": session.metadata.get("dcf"),
        "sensitivity": session.metadata.get("sensitivity"),
        "conviction": session.metadata.get("conviction"),
        "scenarios": session.metadata.get("scenarios"),
        "football_field": session.metadata.get("football_field"),
        "earnings_model": session.metadata.get("earnings_model"),
        "precedents": session.metadata.get("precedents"),
        "sensitivity_operating": session.metadata.get("sensitivity_operating"),
        "ddm": session.metadata.get("ddm"),
        "earnings_quality_data": session.metadata.get("earnings_quality_data"),
    }


@router.post("/{session_id}/sources/{source_id}/exclude")
async def exclude_source(
    source_id: int,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Exclude a news source from the analysis. User must own the session."""
    sources_section = session.report_state.get_section("sources")
    if not sources_section:
        raise HTTPException(status_code=404, detail="No sources section found")

    source_found = None
    for source in sources_section.sources:
        if hasattr(source, "id") and source.id == source_id:
            source_found = source
            break
        elif isinstance(source, dict) and source.get("id") == source_id:
            source_found = source
            break

    if not source_found:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    source_type = (
        source_found.source_type
        if hasattr(source_found, "source_type")
        else source_found.get("source_type", "")
    )
    if source_type not in ("news", "search"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot exclude source type: {source_type}. Only news and search sources can be excluded.",
        )

    if source_id in session.report_state.excluded_source_ids:
        raise HTTPException(status_code=400, detail=f"Source {source_id} is already excluded")

    session.report_state.excluded_source_ids.append(source_id)
    session_manager.update_session(session.session_id)

    return {"success": True, "excluded_source_ids": session.report_state.excluded_source_ids}


@router.post("/{session_id}/sources/{source_id}/restore")
async def restore_source(
    source_id: int,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """Restore a previously excluded source. User must own the session."""
    if source_id not in session.report_state.excluded_source_ids:
        raise HTTPException(status_code=400, detail=f"Source {source_id} is not excluded")

    session.report_state.excluded_source_ids.remove(source_id)
    session_manager.update_session(session.session_id)

    return {"success": True, "excluded_source_ids": session.report_state.excluded_source_ids}
