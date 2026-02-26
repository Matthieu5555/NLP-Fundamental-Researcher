"""
Slide Deck Generator — McKinsey-style equity research slides as PDF.

Uses the same data pipeline as the report PDF (build_template_context),
but renders a landscape 16:9 slide-per-page HTML template via WeasyPrint.

Single entry point: generate_slides() → bytes (PDF)
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from .report_builder import ReportState, AnalystSource
from .branding_config import ReportBrandingConfig, get_default_config
from .pdf_generator_v2 import build_template_context

if TYPE_CHECKING:
    from src_george_researcher.data_fetchers.stock_data import StockInfo
    from .pdf_data_collector import FirstPageData

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "pdf_templates"


def generate_slides(
    report_state: ReportState,
    ticker: str,
    stock_info: Optional['StockInfo'] = None,
    branding: Optional[ReportBrandingConfig] = None,
    analyst_sources: Optional[List[AnalystSource]] = None,
    first_page_data: Optional['FirstPageData'] = None,
    financial_statements: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Generate a McKinsey-style slide deck as a PDF.

    Reuses build_template_context() for data extraction, then renders
    the equity_slides.html template (landscape 16:9, one slide per page)
    through WeasyPrint.

    Returns:
        PDF bytes of the slide deck.
    """
    branding = branding or get_default_config()

    # Collect first page data if not provided
    if first_page_data is None:
        try:
            from .pdf_data_collector import collect_first_page_data
            first_page_data = collect_first_page_data(ticker, stock_info)
        except Exception as e:
            logger.warning(f"Could not collect first page data: {e}")

    # Build the same context dict the report PDF uses
    context = build_template_context(
        report_state=report_state,
        ticker=ticker,
        stock_info=stock_info,
        branding=branding,
        analyst_sources=analyst_sources,
        first_page_data=first_page_data,
        financial_statements=financial_statements,
    )

    # Render slide template
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("equity_slides.html")
    html_content = template.render(**context)

    # Convert to PDF
    html = HTML(string=html_content, base_url=str(TEMPLATE_DIR))
    return html.write_pdf()
