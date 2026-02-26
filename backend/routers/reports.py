"""
Reports API router.

Handles report retrieval and export (markdown, PDF, slides).

Endpoints:
    GET  /{session_id}                  - Get full report
    POST /{session_id}/export/pdf       - Export as PDF
    POST /{session_id}/export/slides    - Export as slide deck (PDF)
    GET  /{session_id}/sections         - List all sections
    GET  /{session_id}/sections/{id}    - Get specific section
    PUT  /{session_id}/sections/{id}    - Update section content
    GET  /{session_id}/stats            - Get report statistics
    POST /{session_id}/sources/{id}/exclude - Exclude a source
    POST /{session_id}/sources/{id}/restore - Restore a source
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from backend.core.session import session_manager, AnalysisSession
from backend.dependencies import get_user_session_with_report

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateSectionRequest(BaseModel):
    """Request body for updating a section."""

    content: str
    sources: Optional[list] = None


class ExportPdfRequest(BaseModel):
    """Request body for PDF export."""

    firm_id: Optional[str] = "constance"
    analyst_id: Optional[str] = "default"


@router.get("/{session_id}")
async def get_report(
    format: str = Query(default="json"),
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """
    Get the current report for a session.

    User must own the session.

    Query parameters:
        format: 'json' (default) or 'markdown'
    """
    if format == "markdown":
        markdown = session.report_state.to_markdown()
        return Response(content=markdown, media_type="text/markdown")
    else:
        return session.report_state.to_dict()


@router.post("/{session_id}/export/pdf")
async def export_pdf(
    request: ExportPdfRequest = None,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """
    Export report as PDF with white-labeling support.

    User must own the session.

    Returns PDF file download with:
    - Header banner with firm branding and key metrics
    - 15-year price chart
    - Full investment analysis
    - Sources section
    - Modular appendix
    - Analyst attribution
    """
    import traceback

    request = request or ExportPdfRequest()

    try:
        from backend.core.pdf_generator_v2 import generate_pdf
        from backend.core.branding_config import load_branding_config

        # sys.path configured in backend/main.py
        from src_george_researcher.data_fetchers.stock_data import fetch_stock_info

        branding = load_branding_config(request.firm_id, request.analyst_id)
        logger.info(f"Using branding: {branding.firm.name} / {branding.analyst.full_name}")

        stock_info, stock_error = fetch_stock_info(session.ticker)
        if stock_error:
            logger.warning(f"Could not fetch stock info: {stock_error}")
            stock_info = None

        financial_statements = session.metadata.get("financial_statements", None)

        pdf_bytes = generate_pdf(
            session.report_state,
            session.ticker,
            stock_info=stock_info,
            branding=branding,
            analyst_sources=session.analyst_sources,
            financial_statements=financial_statements,
        )

        logger.info(f"PDF generated: {len(pdf_bytes)} bytes")

        filename = f"{session.ticker}_analysis_{datetime.now().strftime('%Y%m%d')}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except (ImportError, OSError) as e:
        # Fallback to markdown export if PDF libraries not available
        logger.warning(f"PDF dependency missing, falling back to markdown: {e}")
        markdown = session.report_state.to_markdown()
        filename = f"{session.ticker}_analysis_{datetime.now().strftime('%Y%m%d')}.md"
        return Response(
            content=markdown,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-PDF-Fallback": "true",
                "X-PDF-Error": str(e)[:100],
            },
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        logger.error(traceback.format_exc())
        error_msg = str(e)
        # Also fallback to markdown for other PDF errors
        if "libgobject" in error_msg or "cannot load library" in error_msg or "weasyprint" in error_msg.lower():
            logger.warning("PDF library error, falling back to markdown")
            markdown = session.report_state.to_markdown()
            filename = f"{session.ticker}_analysis_{datetime.now().strftime('%Y%m%d')}.md"
            return Response(
                content=markdown,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-PDF-Fallback": "true",
                    "X-PDF-Error": error_msg[:100],
                },
            )
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {error_msg}")


@router.post("/{session_id}/export/slides")
async def export_slides(
    request: ExportPdfRequest = None,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """
    Export report as a McKinsey-style slide deck (PDF, landscape 16:9).

    User must own the session. Uses the same data pipeline as PDF export
    but renders a slide-per-page layout.
    """
    import traceback

    request = request or ExportPdfRequest()

    try:
        from backend.core.slides_generator import generate_slides
        from backend.core.branding_config import load_branding_config
        from src_george_researcher.data_fetchers.stock_data import fetch_stock_info

        branding = load_branding_config(request.firm_id, request.analyst_id)
        logger.info(f"Slides using branding: {branding.firm.name} / {branding.analyst.full_name}")

        stock_info, stock_error = fetch_stock_info(session.ticker)
        if stock_error:
            logger.warning(f"Could not fetch stock info: {stock_error}")
            stock_info = None

        financial_statements = session.metadata.get("financial_statements", None)

        slides_bytes = generate_slides(
            session.report_state,
            session.ticker,
            stock_info=stock_info,
            branding=branding,
            analyst_sources=session.analyst_sources,
            financial_statements=financial_statements,
        )

        logger.info(f"Slides generated: {len(slides_bytes)} bytes")

        filename = f"{session.ticker}_slides_{datetime.now().strftime('%Y%m%d')}.pdf"

        return Response(
            content=slides_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except (ImportError, OSError) as e:
        logger.warning(f"Slides dependency missing, falling back to markdown: {e}")
        markdown = session.report_state.to_markdown()
        filename = f"{session.ticker}_slides_{datetime.now().strftime('%Y%m%d')}.md"
        return Response(
            content=markdown,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Slides-Fallback": "true",
                "X-Slides-Error": str(e)[:100],
            },
        )
    except Exception as e:
        logger.error(f"Slides generation failed: {e}")
        logger.error(traceback.format_exc())
        error_msg = str(e)
        if "libgobject" in error_msg or "cannot load library" in error_msg or "weasyprint" in error_msg.lower():
            logger.warning("Slides library error, falling back to markdown")
            markdown = session.report_state.to_markdown()
            filename = f"{session.ticker}_slides_{datetime.now().strftime('%Y%m%d')}.md"
            return Response(
                content=markdown,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-Slides-Fallback": "true",
                    "X-Slides-Error": error_msg[:100],
                },
            )
        raise HTTPException(status_code=500, detail=f"Slides generation failed: {error_msg}")


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
    """
    Get structured valuation data for interactive frontend components.

    Returns DCF model, sensitivity grid, conviction scores from session metadata.
    """
    return {
        "dcf_model": session.metadata.get("dcf_model"),
        "sensitivity_data": session.metadata.get("sensitivity_data"),
        "conviction_data": session.metadata.get("conviction_data"),
        "scenario_data": session.metadata.get("scenario_data"),
        "football_field_data": session.metadata.get("football_field_data"),
        "earnings_model_data": session.metadata.get("earnings_model_data"),
        "precedent_data": session.metadata.get("precedent_data"),
        "growth_margin_sensitivity_data": session.metadata.get("growth_margin_sensitivity_data"),
    }


@router.post("/{session_id}/sources/{source_id}/exclude")
async def exclude_source(
    source_id: int,
    session: AnalysisSession = Depends(get_user_session_with_report),
):
    """
    Exclude a news source from the analysis.

    User must own the session. Only sources with source_type 'news' or 'search' can be excluded.
    """
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
