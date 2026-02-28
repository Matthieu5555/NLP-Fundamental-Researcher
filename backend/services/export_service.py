"""Report export orchestration.

Unifies the shared branding/stock-info fetching, generation call, and
markdown fallback logic that was duplicated across the PDF, slides, and
Excel export endpoints.

All format methods receive an ExportContext so stock info and branding are
fetched exactly once per export, regardless of format.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from backend.core.session import AnalysisSession

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    PDF = "pdf"
    SLIDES = "slides"
    EXCEL = "excel"
    DOCX = "docx"
    PPTX = "pptx"


@dataclass(frozen=True)
class ExportResult:
    """Completed export ready for HTTP response."""

    content: bytes
    media_type: str
    filename: str
    is_fallback: bool = False
    fallback_reason: str | None = None
    consistency_warnings: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ExportContext:
    """Shared context resolved once and passed to every format generator."""

    stock_info: Any  # Optional[StockInfo]
    branding: Any  # Optional[ReportBrandingConfig]
    first_page_data: Any  # Optional[FirstPageData]
    current_price: Optional[float]
    company_name: str
    rating: str


# Maps format to (media_type, filename_template)
_FORMAT_META = {
    ExportFormat.PDF: ("application/pdf", "{ticker}_analysis_{date}.pdf"),
    ExportFormat.SLIDES: ("application/pdf", "{ticker}_slides_{date}.pdf"),
    ExportFormat.EXCEL: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "{ticker}_financial_model_{date}.xlsx",
    ),
    ExportFormat.DOCX: (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "{ticker}_equity_report_{date}.docx",
    ),
    ExportFormat.PPTX: (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "{ticker}_slides_{date}.pptx",
    ),
}


class ExportService:
    """Generates report exports in PDF, slides, or Excel format."""

    def export(
        self,
        session: AnalysisSession,
        fmt: ExportFormat,
        firm_id: str = "george",
        analyst_id: str = "default",
    ) -> ExportResult:
        date_str = datetime.now().strftime("%Y%m%d")
        media_type, filename_tmpl = _FORMAT_META[fmt]
        filename = filename_tmpl.format(ticker=session.ticker, date=date_str)

        ctx = self._resolve_export_context(session, firm_id, analyst_id)
        consistency_warnings = self._check_export_consistency(session)

        if fmt == ExportFormat.EXCEL:
            result = self._generate_excel(session, ctx, filename, media_type)
        elif fmt == ExportFormat.DOCX:
            result = self._generate_docx(session, ctx, filename, media_type)
        elif fmt == ExportFormat.PPTX:
            result = self._generate_pptx(session, ctx, filename, media_type)
        else:
            result = self._generate_pdf_or_slides(session, fmt, ctx, filename, media_type)

        if consistency_warnings and not result.is_fallback:
            # Attach warnings to the result (frozen dataclass, so reconstruct)
            result = ExportResult(
                content=result.content,
                media_type=result.media_type,
                filename=result.filename,
                is_fallback=result.is_fallback,
                fallback_reason=result.fallback_reason,
                consistency_warnings=consistency_warnings,
            )

        return result

    # --- Shared context resolution ---

    @staticmethod
    def _resolve_export_context(
        session: AnalysisSession,
        firm_id: str,
        analyst_id: str,
    ) -> ExportContext:
        """Fetch stock info, branding, and first-page data once for all formats."""
        stock_info = None
        branding = None
        first_page_data = None

        try:
            from backend.core.branding_config import load_branding_config
            branding = load_branding_config(firm_id, analyst_id)
            logger.info(
                "Export using branding: %s / %s",
                branding.firm.name,
                branding.analyst.full_name,
            )
        except Exception as e:
            logger.warning("Could not load branding config: %s", e)

        try:
            from src_george_researcher.data_fetchers.stock_data import fetch_stock_info
            stock_info, stock_error = fetch_stock_info(session.ticker)
            if stock_error:
                logger.warning("Could not fetch stock info: %s", stock_error)
                stock_info = None
        except Exception:
            pass

        try:
            from backend.core.pdf_data_collector import collect_first_page_data
            first_page_data = collect_first_page_data(session.ticker, stock_info=stock_info)
        except Exception as e:
            logger.warning("Could not collect first page data: %s", e)

        # Resolve current price: prefer football field, then stock info
        current_price = None
        football = session.metadata.get("football_field")
        if football:
            current_price = football.get("current_price")
        if current_price is None and first_page_data:
            current_price = getattr(first_page_data, "current_price", None)
        if current_price is None and stock_info:
            current_price = getattr(stock_info, "current_price", None)

        # Company name
        company_name = session.ticker
        if stock_info:
            company_name = getattr(stock_info, "name", session.ticker) or session.ticker

        # Rating
        rating = "N/A"
        try:
            from backend.core.pdf_formatting import extract_recommendation
            rating = extract_recommendation(session.report_state)
        except Exception:
            pass

        return ExportContext(
            stock_info=stock_info,
            branding=branding,
            first_page_data=first_page_data,
            current_price=current_price,
            company_name=company_name,
            rating=rating,
        )

    # --- PDF / Slides (shared pipeline) ---

    def _generate_pdf_or_slides(
        self,
        session: AnalysisSession,
        fmt: ExportFormat,
        ctx: ExportContext,
        filename: str,
        media_type: str,
    ) -> ExportResult:
        try:
            financial_statements = session.metadata.get("financial_statements")

            if fmt == ExportFormat.PDF:
                from backend.core.pdf_generator_v2 import generate_pdf

                content = generate_pdf(
                    session.report_state,
                    session.ticker,
                    stock_info=ctx.stock_info,
                    branding=ctx.branding,
                    analyst_sources=session.analyst_sources,
                    financial_statements=financial_statements,
                    session_metadata=session.metadata,
                )
            else:
                from backend.core.slides_generator import generate_slides

                content = generate_slides(
                    session.report_state,
                    session.ticker,
                    session_metadata=session.metadata,
                    stock_info=ctx.stock_info,
                    branding=ctx.branding,
                    analyst_sources=session.analyst_sources,
                    financial_statements=financial_statements,
                )

            logger.info("%s generated: %d bytes", fmt.value.title(), len(content))
            return ExportResult(content=content, media_type=media_type, filename=filename)

        except (ImportError, OSError) as e:
            return self._markdown_fallback(session, filename, fmt.value, str(e))

        except Exception as e:
            error_msg = str(e)
            if any(
                kw in error_msg.lower()
                for kw in ("libgobject", "cannot load library", "weasyprint")
            ):
                return self._markdown_fallback(session, filename, fmt.value, error_msg)
            raise

    # --- Excel ---

    def _generate_excel(
        self,
        session: AnalysisSession,
        ctx: ExportContext,
        filename: str,
        media_type: str,
    ) -> ExportResult:
        from backend.core.excel_generator import generate_excel

        content = generate_excel(
            session_metadata=session.metadata,
            ticker=session.ticker,
            company_name=ctx.company_name,
            rating=ctx.rating,
            current_price=ctx.current_price,
        )

        logger.info("Excel generated: %d bytes", len(content))
        return ExportResult(content=content, media_type=media_type, filename=filename)

    # --- DOCX ---

    def _generate_docx(
        self,
        session: AnalysisSession,
        ctx: ExportContext,
        filename: str,
        media_type: str,
    ) -> ExportResult:
        from backend.core.docx_generator import generate_docx

        content = generate_docx(
            report_state=session.report_state,
            ticker=session.ticker,
            stock_info=ctx.stock_info,
            branding=ctx.branding,
            analyst_sources=session.analyst_sources,
            financial_statements=session.metadata.get("financial_statements"),
            session_metadata=session.metadata,
        )

        logger.info("DOCX generated: %d bytes", len(content))
        return ExportResult(content=content, media_type=media_type, filename=filename)

    # --- PPTX ---

    def _generate_pptx(
        self,
        session: AnalysisSession,
        ctx: ExportContext,
        filename: str,
        media_type: str,
    ) -> ExportResult:
        try:
            from backend.core.pptx_renderer import generate_pptx
            from backend.core.slides_generator import build_slides_context

            context = build_slides_context(
                report_state=session.report_state,
                ticker=session.ticker,
                session_metadata=session.metadata,
                stock_info=ctx.stock_info,
                branding=ctx.branding,
                analyst_sources=session.analyst_sources,
                first_page_data=ctx.first_page_data,
            )

            content = generate_pptx(context)

            logger.info("PPTX generated: %d bytes", len(content))
            return ExportResult(content=content, media_type=media_type, filename=filename)

        except (ImportError, OSError) as e:
            return self._markdown_fallback(session, filename, "pptx", str(e))

    # --- Consistency check ---

    @staticmethod
    def _check_export_consistency(session: AnalysisSession) -> list[dict]:
        """Compare prose dollar amounts and ratings against structured data.

        Non-blocking: returns a list of warning dicts. Divergences above 20%
        between prose fair value and DCF fair_value_per_share, or mismatched
        rating strings, are flagged for the frontend to surface.
        """
        warnings: list[dict] = []

        dcf = session.metadata.get("dcf", {})
        dcf_fair_value = dcf.get("fair_value_per_share")

        # Check prose fair value vs DCF
        if dcf_fair_value:
            thesis_section = session.report_state.sections.get("investment_thesis")
            if thesis_section and thesis_section.content:
                prose_values = re.findall(
                    r'\$\s*([\d,]+(?:\.\d+)?)', thesis_section.content
                )
                for raw in prose_values:
                    try:
                        prose_val = float(raw.replace(",", ""))
                        if prose_val < 1 or prose_val > 100_000:
                            continue
                        divergence = abs(prose_val - dcf_fair_value) / dcf_fair_value
                        if divergence > 0.20:
                            warnings.append({
                                "type": "fair_value_divergence",
                                "prose_value": prose_val,
                                "dcf_value": round(dcf_fair_value, 2),
                                "divergence_pct": round(divergence * 100, 1),
                                "message": (
                                    f"Prose mentions ${prose_val:.0f} but DCF fair value is "
                                    f"${dcf_fair_value:.2f} ({divergence*100:.0f}% divergence)"
                                ),
                            })
                            break
                    except ValueError:
                        continue

        # Check recommendation rating consistency
        conviction = session.metadata.get("conviction", {})
        conviction_rec = conviction.get("recommendation", "")
        if conviction_rec:
            rec_section = session.report_state.sections.get("recommendation")
            if rec_section and rec_section.content:
                prose_upper = rec_section.content.upper()
                if conviction_rec.upper() not in prose_upper:
                    warnings.append({
                        "type": "rating_mismatch",
                        "conviction_rating": conviction_rec,
                        "message": (
                            f"Conviction rating '{conviction_rec}' not found in "
                            f"recommendation section prose"
                        ),
                    })

        if warnings:
            logger.warning("Export consistency warnings: %s", warnings)

        return warnings

    # --- Helpers ---

    @staticmethod
    def _markdown_fallback(
        session: AnalysisSession,
        original_filename: str,
        format_label: str,
        error_msg: str,
    ) -> ExportResult:
        logger.warning(
            "%s dependency issue, falling back to markdown: %s",
            format_label.title(),
            error_msg,
        )
        markdown = session.report_state.to_markdown()
        fallback_filename = original_filename.rsplit(".", 1)[0] + ".md"
        return ExportResult(
            content=markdown.encode() if isinstance(markdown, str) else markdown,
            media_type="text/markdown",
            filename=fallback_filename,
            is_fallback=True,
            fallback_reason=error_msg[:100],
        )
