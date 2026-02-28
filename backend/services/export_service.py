"""Report export orchestration.

Unifies the shared branding/stock-info fetching, generation call, and
markdown fallback logic that was duplicated across the PDF, slides, and
Excel export endpoints.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

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

        if fmt == ExportFormat.EXCEL:
            return self._generate_excel(session, filename, media_type)

        if fmt == ExportFormat.DOCX:
            return self._generate_docx(session, firm_id, analyst_id, filename, media_type)

        if fmt == ExportFormat.PPTX:
            return self._generate_pptx(session, firm_id, analyst_id, filename, media_type)

        return self._generate_pdf_or_slides(
            session, fmt, firm_id, analyst_id, filename, media_type
        )

    # --- PDF / Slides (shared pipeline) ---

    def _generate_pdf_or_slides(
        self,
        session: AnalysisSession,
        fmt: ExportFormat,
        firm_id: str,
        analyst_id: str,
        filename: str,
        media_type: str,
    ) -> ExportResult:
        try:
            from backend.core.branding_config import load_branding_config
            from src_george_researcher.data_fetchers.stock_data import fetch_stock_info

            branding = load_branding_config(firm_id, analyst_id)
            logger.info(
                "%s using branding: %s / %s",
                fmt.value.title(),
                branding.firm.name,
                branding.analyst.full_name,
            )

            stock_info, stock_error = fetch_stock_info(session.ticker)
            if stock_error:
                logger.warning("Could not fetch stock info: %s", stock_error)
                stock_info = None

            financial_statements = session.metadata.get("financial_statements")

            if fmt == ExportFormat.PDF:
                from backend.core.pdf_generator_v2 import generate_pdf

                content = generate_pdf(
                    session.report_state,
                    session.ticker,
                    stock_info=stock_info,
                    branding=branding,
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
                    stock_info=stock_info,
                    branding=branding,
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
        filename: str,
        media_type: str,
    ) -> ExportResult:
        from backend.core.excel_generator import generate_excel
        from backend.core.pdf_formatting import extract_recommendation

        try:
            rating = extract_recommendation(session.report_state)
        except Exception:
            rating = "N/A"

        current_price = self._resolve_current_price(session)

        company_name = session.ticker
        try:
            from src_george_researcher.data_fetchers.stock_data import fetch_stock_info

            stock_info, _ = fetch_stock_info(session.ticker)
            if stock_info:
                company_name = getattr(stock_info, "name", session.ticker) or session.ticker
        except Exception:
            pass

        content = generate_excel(
            session_metadata=session.metadata,
            ticker=session.ticker,
            company_name=company_name,
            rating=rating,
            current_price=current_price,
        )

        logger.info("Excel generated: %d bytes", len(content))
        return ExportResult(content=content, media_type=media_type, filename=filename)

    # --- DOCX ---

    def _generate_docx(
        self,
        session: AnalysisSession,
        firm_id: str,
        analyst_id: str,
        filename: str,
        media_type: str,
    ) -> ExportResult:
        from backend.core.branding_config import load_branding_config
        from backend.core.docx_generator import generate_docx
        from src_george_researcher.data_fetchers.stock_data import fetch_stock_info

        branding = load_branding_config(firm_id, analyst_id)

        stock_info = None
        try:
            stock_info, stock_error = fetch_stock_info(session.ticker)
            if stock_error:
                logger.warning("Could not fetch stock info for DOCX: %s", stock_error)
                stock_info = None
        except Exception:
            pass

        content = generate_docx(
            report_state=session.report_state,
            ticker=session.ticker,
            stock_info=stock_info,
            branding=branding,
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
        firm_id: str,
        analyst_id: str,
        filename: str,
        media_type: str,
    ) -> ExportResult:
        try:
            from backend.core.branding_config import load_branding_config
            from backend.core.pptx_renderer import generate_pptx
            from backend.core.slides_generator import build_slides_context
            from src_george_researcher.data_fetchers.stock_data import fetch_stock_info

            branding = load_branding_config(firm_id, analyst_id)
            logger.info(
                "PPTX using branding: %s / %s",
                branding.firm.name,
                branding.analyst.full_name,
            )

            stock_info = None
            try:
                stock_info, stock_error = fetch_stock_info(session.ticker)
                if stock_error:
                    logger.warning("Could not fetch stock info for PPTX: %s", stock_error)
                    stock_info = None
            except Exception:
                pass

            context = build_slides_context(
                report_state=session.report_state,
                ticker=session.ticker,
                session_metadata=session.metadata,
                stock_info=stock_info,
                branding=branding,
                analyst_sources=session.analyst_sources,
            )

            content = generate_pptx(context)

            logger.info("PPTX generated: %d bytes", len(content))
            return ExportResult(content=content, media_type=media_type, filename=filename)

        except (ImportError, OSError) as e:
            return self._markdown_fallback(session, filename, "pptx", str(e))

    # --- Helpers ---

    @staticmethod
    def _resolve_current_price(session: AnalysisSession) -> Any:
        football = session.metadata.get("football_field")
        if football:
            price = football.get("current_price")
            if price is not None:
                return price

        try:
            from src_george_researcher.data_fetchers.stock_data import fetch_stock_info

            stock_info, _ = fetch_stock_info(session.ticker)
            if stock_info:
                return getattr(stock_info, "current_price", None)
        except Exception:
            pass
        return None

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
