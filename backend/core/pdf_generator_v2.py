"""
PDF Report Generator v2 - HTML/CSS to PDF using WeasyPrint.

This replaces the fpdf2-based generator with a modern HTML/CSS approach
that produces professional "Goldman Sachs" style equity research reports.

Features:
- Magazine-style two-column layouts
- Professional sidebar with key metrics
- Color-coded rating badges
- SWOT grids with color coding
- Bull/Bear case sections
- Proper Unicode support
- Easy template customization
"""

import base64
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING

import markdown
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from .report_builder import ReportState, Source, AnalystSource
from .branding_config import ReportBrandingConfig, get_default_config

if TYPE_CHECKING:
    from src_george_researcher.data_fetchers.stock_data import StockInfo
    from .pdf_data_collector import FirstPageData

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "pdf_templates"

# Rating colors
RATING_COLORS = {
    'BUY': '#16a34a',       # Green
    'STRONG BUY': '#16a34a',
    'SELL': '#dc2626',      # Red
    'STRONG SELL': '#dc2626',
    'HOLD': '#d97706',      # Amber
    'NEUTRAL': '#d97706',
    'N/A': '#6b7280',       # Gray
}

# Exchange code to readable name mapping
EXCHANGE_NAMES = {
    'NMS': 'NASDAQ',
    'NGM': 'NASDAQ',
    'NCM': 'NASDAQ',
    'NYQ': 'NYSE',
    'NYSE': 'NYSE',
    'NASDAQ': 'NASDAQ',
    'ASE': 'NYSE American',
    'PCX': 'NYSE Arca',
    'BTS': 'BATS',
    'LSE': 'London',
    'PAR': 'Euronext Paris',
    'EPA': 'Euronext Paris',
    'FRA': 'Frankfurt',
    'TYO': 'Tokyo',
    'HKG': 'Hong Kong',
}


def get_exchange_name(exchange_code: str) -> str:
    """Convert exchange code to readable name."""
    if not exchange_code:
        return ''
    return EXCHANGE_NAMES.get(exchange_code.upper(), exchange_code)


def md_to_html(text: str) -> str:
    """Convert markdown text to HTML."""
    if not text:
        return ""

    # Use markdown library with common extensions
    html = markdown.markdown(
        text,
        extensions=['tables', 'nl2br', 'sane_lists']
    )
    return html


def extract_highlights(content: str, max_items: int = 4) -> List[str]:
    """Extract key highlights from content (first few bullet points or sentences)."""
    highlights = []

    # Look for bullet points first
    bullet_pattern = r'^[-*]\s+(.+)$'
    for match in re.finditer(bullet_pattern, content, re.MULTILINE):
        highlights.append(match.group(1).strip())
        if len(highlights) >= max_items:
            break

    # If no bullets found, extract first sentences
    if not highlights:
        sentences = re.split(r'(?<=[.!?])\s+', content)
        for sentence in sentences[:max_items]:
            sentence = sentence.strip()
            if len(sentence) > 20:  # Skip very short fragments
                highlights.append(sentence)

    return highlights[:max_items]


def extract_recommendation(report_state: ReportState) -> str:
    """Parse recommendation section to extract BUY/SELL/HOLD verdict."""
    rec_section = report_state.sections.get('recommendation')
    if not rec_section:
        return 'N/A'

    content = rec_section.content.upper() if hasattr(rec_section, 'content') else ''

    if 'STRONG BUY' in content or 'STRONGLY BUY' in content:
        return 'BUY'
    elif 'STRONG SELL' in content or 'STRONGLY SELL' in content:
        return 'SELL'
    elif 'BUY' in content and 'SELL' not in content:
        return 'BUY'
    elif 'SELL' in content and 'BUY' not in content:
        return 'SELL'
    elif 'HOLD' in content or 'NEUTRAL' in content:
        return 'HOLD'

    return 'N/A'


def parse_swot(content: str) -> Optional[Dict[str, str]]:
    """Parse SWOT content into structured sections."""
    if not content:
        return None

    swot = {
        'strengths': '',
        'weaknesses': '',
        'opportunities': '',
        'threats': ''
    }

    # Try to find sections by headers
    sections_map = {
        'strength': 'strengths',
        'weakness': 'weaknesses',
        'opportunit': 'opportunities',
        'threat': 'threats'
    }

    current_section = None
    current_content = []

    for line in content.split('\n'):
        line_lower = line.lower().strip()

        # Check if this is a section header
        new_section = None
        for key, section_name in sections_map.items():
            if key in line_lower and (line.startswith('#') or line.startswith('**')):
                new_section = section_name
                break

        if new_section:
            # Save previous section
            if current_section and current_content:
                swot[current_section] = md_to_html('\n'.join(current_content))
            current_section = new_section
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section and current_content:
        swot[current_section] = md_to_html('\n'.join(current_content))

    # If parsing failed, return None
    if not any(swot.values()):
        return None

    return swot


def format_number(value: Optional[float], format_type: str = 'number') -> str:
    """Format numbers for display."""
    if value is None:
        return 'N/A'

    if format_type == 'market_cap':
        if value >= 1e12:
            return f'${value/1e12:.2f}T'
        elif value >= 1e9:
            return f'${value/1e9:.2f}B'
        elif value >= 1e6:
            return f'${value/1e6:.2f}M'
        return f'${value:,.0f}'

    elif format_type == 'price':
        return f'${value:,.2f}'

    elif format_type == 'percent':
        sign = '+' if value >= 0 else ''
        return f'{sign}{value:.1f}%'

    elif format_type == 'ratio':
        return f'{value:.2f}x'

    elif format_type == 'shares':
        if value >= 1e9:
            return f'{value/1e9:.2f}B'
        elif value >= 1e6:
            return f'{value/1e6:.2f}M'
        return f'{value:,.0f}'

    return f'{value:,.2f}'


def generate_report_headline(
    company_name: str,
    rating: str,
    thesis_content: str,
    highlights: List[str]
) -> str:
    """Generate a catchy headline for the report using LLM."""
    try:
        # Import LLM wrapper
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
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
            temperature=0.8
        )

        # Clean up response
        headline = headline.strip().strip('"\'')

        # Fallback if LLM fails or returns error
        if headline.startswith("Error:") or len(headline) > 100 or len(headline) < 10:
            return f"{company_name}: Investment Analysis and Outlook"

        return headline

    except Exception as e:
        logger.warning(f"Failed to generate headline via LLM: {e}")
        return f"{company_name}: Investment Analysis and Outlook"


def remove_key_questions_section(html_content: str) -> str:
    """Remove the 'Key Questions for the Analyst' section from HTML content."""
    if not html_content:
        return html_content

    # Common patterns for this section
    patterns = [
        r'<h[23][^>]*>.*?Key Questions.*?</h[23]>.*?(?=<h[23]|$)',
        r'<h[23][^>]*>.*?Questions for.*?Analyst.*?</h[23]>.*?(?=<h[23]|$)',
        r'<strong>Key Questions.*?</strong>.*?(?=<h|<strong>|$)',
    ]

    result = html_content
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE | re.DOTALL)

    return result


def build_template_context(
    report_state: ReportState,
    ticker: str,
    stock_info: Optional['StockInfo'] = None,
    branding: Optional[ReportBrandingConfig] = None,
    analyst_sources: Optional[List[AnalystSource]] = None,
    first_page_data: Optional['FirstPageData'] = None,
    technical_chart_bytes: Optional[bytes] = None,
    sidebar_chart_bytes: Optional[bytes] = None,
    financial_statements: Optional[Dict[str, Any]] = None
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
            {'label': 'ROE', 'value': format_number(first_page_data.roe * 100 if first_page_data.roe else None, 'percent')},
            {'label': 'Div Yield', 'value': format_number(first_page_data.dividend_yield * 100 if first_page_data.dividend_yield else None, 'percent')},
            {'label': 'Beta', 'value': f'{first_page_data.beta:.2f}' if first_page_data.beta else 'N/A'},
        ]

    # Investment thesis - use full_report for the main content, not recommendation
    # The full_report contains the Executive Summary, Business Context, etc.
    thesis_content = ''
    highlights = []
    full_analysis = ''

    if 'full_report' in report_state.sections:
        full = report_state.sections['full_report']
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

    # Fallback to recommendation if no full_report
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

    # Strategy Analysis (SWOT + Future Outlook)
    swot = None
    if 'strategy' in report_state.sections:
        strategy_section = report_state.sections['strategy']
        if hasattr(strategy_section, 'content'):
            swot = parse_swot(strategy_section.content)  # Parse into SWOT grid format

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

    # Moat Analysis
    moat_analysis = ''
    if 'moat_analysis' in report_state.sections:
        moat = report_state.sections['moat_analysis']
        if hasattr(moat, 'content'):
            moat_analysis = md_to_html(moat.content)

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

    # Build context
    context = {
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
        'swot': swot,
        'fundamentals': fundamentals,
        'technicals': technicals,
        'moat_analysis': moat_analysis,

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
    }

    return context


def generate_pdf_v2(
    report_state: ReportState,
    ticker: str,
    stock_info: Optional['StockInfo'] = None,
    branding: Optional[ReportBrandingConfig] = None,
    analyst_sources: Optional[List[AnalystSource]] = None,
    first_page_data: Optional['FirstPageData'] = None,
    financial_statements: Optional[Dict[str, Any]] = None
) -> bytes:
    """
    Generate professional PDF report using HTML/CSS and WeasyPrint.

    This produces a "Goldman Sachs" style equity research report with:
    - Professional header with firm branding
    - Sidebar with rating, key metrics, and returns
    - Two-column investment thesis
    - Color-coded SWOT and Bull/Bear sections
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
        except Exception as e:
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
        except Exception as e:
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
    except Exception as e:
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
        financial_statements=financial_statements
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
    financial_statements: Optional[Dict[str, Any]] = None
) -> bytes:
    """Alias for generate_pdf_v2 for backwards compatibility."""
    return generate_pdf_v2(
        report_state=report_state,
        ticker=ticker,
        stock_info=stock_info,
        branding=branding,
        analyst_sources=analyst_sources,
        first_page_data=first_page_data,
        financial_statements=financial_statements
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
