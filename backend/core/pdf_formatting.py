"""
PDF formatting utilities for equity research reports.

Pure functions for text transformation, number formatting, and content extraction.
No LLM calls, no I/O, no side effects — just data in, formatted data out.

Used by pdf_generator_v2.py for template context building.
"""

import re
from typing import List, Optional, Dict

import markdown

from .report_builder import ReportState
from .colors import PALETTE, get_rating_color


# Rating badge colors sourced from shared/colors.json via colors.py
RATING_COLORS = PALETTE.ratings

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
