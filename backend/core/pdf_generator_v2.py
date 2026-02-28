"""
PDF Report Generator v2 - HTML/CSS to PDF using WeasyPrint.

Produces professional "Goldman Sachs" style equity research reports.
Formatting utilities live in pdf_formatting.py; this module handles
template context building, LLM headline generation, and PDF rendering.
"""

import base64
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from .report_builder import ReportState, Source, AnalystSource
from .branding_config import ReportBrandingConfig, get_default_config
from .colors import PALETTE
from .pdf_formatting import (
    RATING_COLORS,
    get_exchange_name,
    md_to_html,
    extract_highlights,
    extract_recommendation,
    parse_strategy_grid,
    format_number,
    remove_key_questions_section,
)

if TYPE_CHECKING:
    from src_george_researcher.data_fetchers.stock_data import StockInfo
    from .pdf_data_collector import FirstPageData

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "pdf_templates"


def generate_report_headline(
    company_name: str,
    rating: str,
    thesis_content: str,
    highlights: List[str]
) -> str:
    """Generate a catchy headline for the report using LLM."""
    try:
        # sys.path configured in backend/main.py
        from backend.agents.llm_wrapper import get_llm_response

        # Build context for LLM
        highlights_text = "\n".join(f"- {h}" for h in highlights[:4]) if highlights else ""

        # Strip HTML from thesis for cleaner context
        thesis_plain = re.sub(r'<[^>]+>', '', thesis_content or '')[:500]

        prompt = f"""Generate a single catchy, professional headline for an equity research report.

Company: {company_name}
Rating: {rating}

Key Points:
{highlights_text}

Context: {thesis_plain}

Requirements:
- One line only, no quotes
- Professional but engaging tone (think Financial Times or Bloomberg style)
- Should hint at the investment thesis
- 8-15 words maximum
- Do NOT start with "Headline:" or similar

Example styles:
- "Apple: The Services Flywheel Accelerates"
- "Tesla at a Crossroads: Growth vs. Profitability"
- "Microsoft's AI Bet: Early Innings of a Secular Shift"

Your headline:"""

        system_prompt = "You are a financial journalist writing headlines for equity research reports. Be concise and impactful."

        headline = get_llm_response(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.8  # High temperature for creative, punchy headlines
        )

        # Clean up response
        headline = headline.strip().strip('"\'')

        # Fallback if LLM fails or returns error
        if headline.startswith("Error:") or len(headline) > 100 or len(headline) < 10:
            return f"{company_name}: Investment Analysis and Outlook"

        return headline

    except Exception as e:  # Broad catch: optional feature, any failure is non-fatal
        logger.warning(f"Failed to generate headline via LLM: {e}")
        return f"{company_name}: Investment Analysis and Outlook"


def build_template_context(
    report_state: ReportState,
    ticker: str,
    stock_info: Optional['StockInfo'] = None,
    branding: Optional[ReportBrandingConfig] = None,
    analyst_sources: Optional[List[AnalystSource]] = None,
    first_page_data: Optional['FirstPageData'] = None,
    technical_chart_bytes: Optional[bytes] = None,
    sidebar_chart_bytes: Optional[bytes] = None,
    financial_statements: Optional[Dict[str, Any]] = None,
    session_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the context dictionary for Jinja2 template rendering."""

    branding = branding or get_default_config()
    rating = extract_recommendation(report_state)

    # Company info
    company_name = 'Company'
    exchange = ''
    sector = ''
    country = ''
    industry = ''

    if stock_info:
        company_name = getattr(stock_info, 'name', ticker) or ticker
        exchange = getattr(stock_info, 'exchange', '') or ''
        sector = getattr(stock_info, 'sector', '') or ''
        country = getattr(stock_info, 'country', '') or ''
        industry = getattr(stock_info, 'industry', '') or ''
    elif first_page_data:
        company_name = first_page_data.company_name or ticker
        exchange = first_page_data.exchange or ''
        sector = first_page_data.sector or ''
        country = first_page_data.country or ''
        industry = first_page_data.industry or ''

    # Key data
    key_data = []
    if first_page_data:
        key_data = [
            {'label': 'Price', 'value': format_number(first_page_data.current_price, 'price')},
            {'label': 'Market Cap', 'value': format_number(first_page_data.market_cap, 'market_cap')},
            {'label': 'EPS', 'value': f'{first_page_data.eps:.2f}' if first_page_data.eps else 'N/A'},
            {'label': '52W High', 'value': format_number(first_page_data.week_52_high, 'price')},
            {'label': '52W Low', 'value': format_number(first_page_data.week_52_low, 'price')},
        ]
    elif stock_info:
        key_data = [
            {'label': 'Price', 'value': format_number(getattr(stock_info, 'current_price', None), 'price')},
            {'label': 'Market Cap', 'value': format_number(getattr(stock_info, 'market_cap', None), 'market_cap')},
        ]

    # Period returns
    returns = []
    if first_page_data and first_page_data.returns:
        r = first_page_data.returns
        returns = [
            {'period': '1M', 'value': r.return_1m, 'display': format_number(r.return_1m, 'percent') if r.return_1m else 'N/A'},
            {'period': 'YTD', 'value': r.return_ytd, 'display': format_number(r.return_ytd, 'percent') if r.return_ytd else 'N/A'},
            {'period': '1Y', 'value': r.return_1y, 'display': format_number(r.return_1y, 'percent') if r.return_1y else 'N/A'},
            {'period': '5Y', 'value': r.return_5y, 'display': format_number(r.return_5y, 'percent') if r.return_5y else 'N/A'},
            {'period': '10Y', 'value': r.return_10y, 'display': format_number(r.return_10y, 'percent') if r.return_10y else 'N/A'},
        ]

    # Valuation statistics
    statistics = []
    if first_page_data:
        statistics = [
            {'label': 'P/E (TTM)', 'value': format_number(first_page_data.pe_ratio, 'ratio')},
            {'label': 'P/B', 'value': format_number(first_page_data.price_to_book, 'ratio')},
            {'label': 'EV/EBITDA', 'value': format_number(first_page_data.ev_to_ebitda, 'ratio')},
            {'label': 'ROE', 'value': format_number(first_page_data.roe, 'percent_raw')},
            {'label': 'Div Yield', 'value': format_number(first_page_data.dividend_yield, 'percent_raw')},
            {'label': 'Beta', 'value': f'{first_page_data.beta:.2f}' if first_page_data.beta else 'N/A'},
        ]

    # Investment thesis - use investment_thesis for the main content, not recommendation
    # The investment_thesis contains the Executive Summary, Business Context, etc.
    thesis_content = ''
    highlights = []
    full_analysis = ''

    if 'investment_thesis' in report_state.sections:
        full = report_state.sections['investment_thesis']
        if hasattr(full, 'content') and full.content:
            full_content = full.content

            # Extract highlights from the full report
            raw_highlights = extract_highlights(full_content)
            highlights = [md_to_html(h) for h in raw_highlights]

            # Split the content: first ~1500 chars for thesis_content (cover page)
            # and the rest for full_analysis (page 2+)
            # Try to split at a paragraph boundary
            split_point = 1500
            if len(full_content) > split_point:
                # Find a good split point (end of paragraph)
                potential_split = full_content.find('\n\n', split_point - 300, split_point + 500)
                if potential_split > 0:
                    split_point = potential_split

                thesis_content = md_to_html(full_content[:split_point])
                full_analysis = md_to_html(full_content[split_point:].strip())
            else:
                thesis_content = md_to_html(full_content)
                full_analysis = ''

    # Fallback to recommendation if no investment_thesis
    if not thesis_content and 'recommendation' in report_state.sections:
        rec = report_state.sections['recommendation']
        if hasattr(rec, 'content') and rec.content:
            thesis_content = md_to_html(rec.content)
            raw_highlights = extract_highlights(rec.content)
            highlights = [md_to_html(h) for h in raw_highlights]

    # Bull/Bear cases
    bull_case = ''
    bear_case = ''
    if 'bull_case' in report_state.sections:
        bull = report_state.sections['bull_case']
        if hasattr(bull, 'content'):
            bull_case = md_to_html(bull.content)
    if 'bear_case' in report_state.sections:
        bear = report_state.sections['bear_case']
        if hasattr(bear, 'content'):
            bear_case = md_to_html(bear.content)

    # Strategy Analysis (Strategic Position + Future Outlook)
    strategy_grid = None
    strategy_content = ''
    if 'strategy' in report_state.sections:
        strategy_section = report_state.sections['strategy']
        if hasattr(strategy_section, 'content') and strategy_section.content:
            strategy_grid = parse_strategy_grid(strategy_section.content)
            if not strategy_grid:
                strategy_content = md_to_html(strategy_section.content)

    # Fundamentals
    fundamentals = ''
    if 'fundamentals' in report_state.sections:
        fund = report_state.sections['fundamentals']
        if hasattr(fund, 'content'):
            fundamentals = md_to_html(fund.content)

    # Technicals
    technicals = ''
    if 'technicals' in report_state.sections:
        tech = report_state.sections['technicals']
        if hasattr(tech, 'content'):
            technicals = md_to_html(tech.content)

    # Moat Analysis (stored as "moat" by the orchestrator)
    moat_analysis = ''
    if 'moat' in report_state.sections:
        moat = report_state.sections['moat']
        if hasattr(moat, 'content'):
            moat_analysis = md_to_html(moat.content)

    # Valuation sections
    dcf_valuation = ''
    if 'dcf' in report_state.sections:
        dcf_sec = report_state.sections['dcf']
        if hasattr(dcf_sec, 'content'):
            dcf_valuation = md_to_html(dcf_sec.content)

    comp_table = ''
    if 'comps' in report_state.sections:
        comp_sec = report_state.sections['comps']
        if hasattr(comp_sec, 'content'):
            comp_table = md_to_html(comp_sec.content)

    earnings_model = ''
    if 'earnings_model' in report_state.sections:
        earn_sec = report_state.sections['earnings_model']
        if hasattr(earn_sec, 'content'):
            earnings_model = md_to_html(earn_sec.content)

    sensitivity = ''
    if 'sensitivity' in report_state.sections:
        sens_sec = report_state.sections['sensitivity']
        if hasattr(sens_sec, 'content'):
            sensitivity = md_to_html(sens_sec.content)

    conviction = ''
    if 'conviction' in report_state.sections:
        conv_sec = report_state.sections['conviction']
        if hasattr(conv_sec, 'content'):
            conviction = md_to_html(conv_sec.content)

    scenario_analysis = ''
    if 'scenarios' in report_state.sections:
        scen_sec = report_state.sections['scenarios']
        if hasattr(scen_sec, 'content'):
            scenario_analysis = md_to_html(scen_sec.content)

    precedent_transactions = ''
    if 'precedents' in report_state.sections:
        prec_sec = report_state.sections['precedents']
        if hasattr(prec_sec, 'content'):
            precedent_transactions = md_to_html(prec_sec.content)

    football_field = ''
    if 'football_field' in report_state.sections:
        ff_sec = report_state.sections['football_field']
        if hasattr(ff_sec, 'content'):
            football_field = md_to_html(ff_sec.content)

    strategic_assessment = ''
    if 'industry' in report_state.sections:
        sa_sec = report_state.sections['industry']
        if hasattr(sa_sec, 'content'):
            strategic_assessment = md_to_html(sa_sec.content)

    # Sources
    research_sources = []
    sources_section = report_state.sections.get('sources')
    if sources_section and hasattr(sources_section, 'sources'):
        for source in sources_section.sources:
            if isinstance(source, Source):
                research_sources.append({
                    'id': source.id,
                    'title': source.title,
                    'url': source.url,
                    'date': source.date if source.date != 'N/A' else None
                })
            elif isinstance(source, dict):
                research_sources.append(source)

    analyst_notes = []
    if analyst_sources:
        for src in analyst_sources:
            analyst_notes.append({
                'id': src.id,
                'content': src.to_citation_text() if hasattr(src, 'to_citation_text') else str(src)
            })

    # Technical chart (base64 encoded)
    technical_chart = None
    if technical_chart_bytes:
        technical_chart = base64.b64encode(technical_chart_bytes).decode('utf-8')

    # Sidebar chart (base64 encoded)
    sidebar_chart = None
    if sidebar_chart_bytes:
        sidebar_chart = base64.b64encode(sidebar_chart_bytes).decode('utf-8')

    # Use pre-generated headline from metadata if available, otherwise generate on the fly
    report_headline = report_state.metadata.get('headline')
    if not report_headline:
        report_headline = generate_report_headline(company_name, rating, thesis_content, highlights)

    # Clean up full_analysis - remove "Key Questions for the Analyst" section
    if full_analysis:
        full_analysis = remove_key_questions_section(full_analysis)

    # Log section availability for debugging missing sections
    available = [k for k, s in report_state.sections.items() if hasattr(s, 'content') and s.content]
    logger.info("PDF context: available sections = %s", available)

    # Build context
    context = {
        # Colors from unified palette (replaces all hardcoded hex in templates)
        'c': PALETTE.pdf.to_template_dict(),

        # Firm branding
        'firm_name': branding.firm.name,
        'tool_branding': branding.firm.tool_branding,
        'primary_color': branding.firm.primary_color,

        # Analyst info
        'analyst_name': branding.analyst.full_name,
        'analyst_email': branding.analyst.email,
        'analyst_sector': branding.analyst.sector,

        # Company info
        'ticker': ticker,
        'company_name': company_name,
        'exchange': get_exchange_name(exchange),
        'sector': sector or industry or 'Equity',
        'country': country,

        # Rating
        'rating': rating,
        'rating_color': RATING_COLORS.get(rating, RATING_COLORS['N/A']),

        # Report metadata
        'report_date': datetime.now().strftime("%d %B %Y"),
        'generation_time': datetime.now().strftime("%Y-%m-%d %H:%M"),

        # Data sections
        'key_data': key_data,
        'returns': returns,
        'statistics': statistics,

        # Content sections
        'thesis_content': thesis_content,
        'highlights': highlights,
        'full_analysis': full_analysis,
        'bull_case': bull_case,
        'bear_case': bear_case,
        'strategy_grid': strategy_grid,
        'strategy_content': strategy_content,
        'fundamentals': fundamentals,
        'technicals': technicals,
        'moat_analysis': moat_analysis,
        'dcf_valuation': dcf_valuation,
        'comp_table': comp_table,
        'earnings_model': earnings_model,
        'sensitivity': sensitivity,
        'conviction': conviction,
        'scenario_analysis': scenario_analysis,
        'precedent_transactions': precedent_transactions,
        'football_field': football_field,
        'strategic_assessment': strategic_assessment,

        # Sources
        'research_sources': research_sources,
        'analyst_sources': analyst_notes,

        # Charts
        'technical_chart': technical_chart,
        'sidebar_chart': sidebar_chart,

        # Report headline
        'report_headline': report_headline,

        # Financial statements (US companies only)
        'financial_statements': financial_statements,

        # Model audit (LLM-powered quality review)
        'model_audit': session_metadata.get("model_audit", {}) if session_metadata else {},
    }

    # Merge structured valuation display data when session_metadata is available
    if session_metadata:
        from .valuation_display import build_valuation_display

        cp = first_page_data.current_price if first_page_data else None
        val_display = build_valuation_display(session_metadata, current_price=cp)
        context.update(val_display.to_template_context())

        # Derive price target: prefer weighted fair value from scenarios, fall back to DCF
        scenario_sum = val_display.scenario_summary
        dcf_sum = val_display.dcf_summary
        price_target = scenario_sum.get("weighted_fair_value") or dcf_sum.get("fair_value")
        target_upside_pct = None
        if price_target and cp and cp > 0:
            target_upside_pct = round(((price_target - cp) / cp) * 100, 1)
        context["price_target"] = price_target
        context["target_upside_pct"] = target_upside_pct

    # Build table of contents from sections that actually rendered.
    # Order matches template section order so the TOC reads top-to-bottom.
    toc_section_map = [
        ('full_analysis', 'Investment Analysis'),
        ('conviction', 'Conviction & Rating'),
        ('football_field', 'Valuation Summary'),
        ('dcf_valuation', 'DCF Valuation'),
        ('ddm_summary', 'Dividend Discount Model'),
        ('scenario_analysis', 'Scenario Analysis'),
        ('comp_table', 'Comparable Company Analysis'),
        ('precedent_transactions', 'Precedent Transactions'),
        ('earnings_model', 'Earnings Model'),
        ('sensitivity', 'Sensitivity Analysis'),
        ('fundamentals', 'Fundamental Analysis'),
        ('financial_statements', 'Financial Statements'),
        ('strategy_grid', 'Strategic Assessment'),
        ('strategy_content', 'Strategic Assessment'),
        ('strategic_assessment', 'Industry Dynamics'),
        ('moat_analysis', 'Competitive Moat'),
        ('bull_case', 'Bull Case'),
        ('bear_case', 'Bear Case'),
        ('technicals', 'Technical Analysis'),
        ('research_sources', 'Sources & References'),
    ]
    toc_entries = []
    seen_titles: set[str] = set()
    for key, title in toc_section_map:
        if title in seen_titles:
            continue
        val = context.get(key)
        if key == 'financial_statements':
            if val and getattr(val, 'is_available', False):
                toc_entries.append({'title': title})
                seen_titles.add(title)
        elif key == 'bull_case':
            if context.get('bull_case') or context.get('bear_case'):
                toc_entries.append({'title': title})
                seen_titles.add(title)
        elif val:
            toc_entries.append({'title': title})
            seen_titles.add(title)
    context['toc_entries'] = toc_entries

    return context


def generate_pdf_v2(
    report_state: ReportState,
    ticker: str,
    stock_info: Optional['StockInfo'] = None,
    branding: Optional[ReportBrandingConfig] = None,
    analyst_sources: Optional[List[AnalystSource]] = None,
    first_page_data: Optional['FirstPageData'] = None,
    financial_statements: Optional[Dict[str, Any]] = None,
    session_metadata: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Generate professional PDF report using HTML/CSS and WeasyPrint.

    This produces a "Goldman Sachs" style equity research report with:
    - Professional header with firm branding
    - Sidebar with rating, key metrics, and returns
    - Two-column investment thesis
    - Color-coded strategy grid and Bull/Bear sections
    - Full Unicode support

    Args:
        report_state: The report data
        ticker: Stock ticker symbol
        stock_info: Stock information (price, market cap, etc.)
        branding: Branding configuration (firm, analyst)
        analyst_sources: List of analyst belief sources
        first_page_data: Pre-collected data for first page

    Returns:
        PDF as bytes
    """
    branding = branding or get_default_config()

    # Collect first page data if not provided
    if first_page_data is None:
        try:
            from .pdf_data_collector import collect_first_page_data
            first_page_data = collect_first_page_data(ticker, stock_info)
        except Exception as e:  # Broad catch: optional feature, any failure is non-fatal
            logger.warning(f"Could not collect first page data: {e}")
            first_page_data = None

    # Generate technical chart
    technical_chart_bytes = None
    if 'technicals' in report_state.sections:
        try:
            from .chart_generator import generate_technical_chart
            technical_chart_bytes = generate_technical_chart(
                ticker,
                branding.firm.primary_color,
                period='1y'
            )
        except Exception as e:  # Broad catch: optional feature, any failure is non-fatal
            logger.warning(f"Could not generate technical chart: {e}")

    # Generate sidebar chart (5-year price history)
    sidebar_chart_bytes = None
    try:
        from .chart_generator import generate_sidebar_chart
        sidebar_chart_bytes = generate_sidebar_chart(
            ticker,
            branding.firm.primary_color,
            period='5y'
        )
    except Exception as e:  # Broad catch: optional feature, any failure is non-fatal
        logger.warning(f"Could not generate sidebar chart: {e}")

    # Build template context
    context = build_template_context(
        report_state=report_state,
        ticker=ticker,
        stock_info=stock_info,
        branding=branding,
        analyst_sources=analyst_sources,
        first_page_data=first_page_data,
        technical_chart_bytes=technical_chart_bytes,
        sidebar_chart_bytes=sidebar_chart_bytes,
        financial_statements=financial_statements,
        session_metadata=session_metadata,
    )

    # Load and render template
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template('equity_report.html')
    html_content = template.render(**context)

    # Convert to PDF
    html = HTML(string=html_content, base_url=str(TEMPLATE_DIR))
    pdf_bytes = html.write_pdf()

    return pdf_bytes


# Backwards compatibility alias
def generate_pdf(
    report_state: ReportState,
    ticker: str,
    stock_info: Optional['StockInfo'] = None,
    branding: Optional[ReportBrandingConfig] = None,
    analyst_sources: Optional[List[AnalystSource]] = None,
    first_page_data: Optional['FirstPageData'] = None,
    financial_statements: Optional[Dict[str, Any]] = None,
    session_metadata: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Alias for generate_pdf_v2 for backwards compatibility."""
    return generate_pdf_v2(
        report_state=report_state,
        ticker=ticker,
        stock_info=stock_info,
        branding=branding,
        analyst_sources=analyst_sources,
        first_page_data=first_page_data,
        financial_statements=financial_statements,
        session_metadata=session_metadata,
    )


class PDFGenerator:
    """Wrapper class for backwards compatibility."""

    def generate_report(
        self,
        report_state: ReportState,
        ticker: str,
        analyst_sources: Optional[List[AnalystSource]] = None
    ) -> bytes:
        return generate_pdf_v2(report_state, ticker, analyst_sources=analyst_sources)
