"""
PDF formatting utilities for equity research reports.

Pure functions for text transformation, number formatting, and content extraction.
No LLM calls, no I/O, no side effects — just data in, formatted data out.

Used by pdf_generator_v2.py for template context building.
"""

import re
from typing import Any, Dict, List, Optional

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


def parse_strategy_grid(content: str) -> Optional[Dict[str, str]]:
    """Parse strategy content into a four-quadrant grid (advantages/vulnerabilities/tailwinds/headwinds)."""
    if not content:
        return None

    grid = {
        'advantages': '',
        'vulnerabilities': '',
        'tailwinds': '',
        'headwinds': ''
    }

    # Map header keywords to grid quadrants. Matches both the new labels
    # and legacy labels (strengths -> advantages, etc.) for backward compatibility.
    sections_map = {
        'advantage': 'advantages',
        'strength': 'advantages',
        'capabilit': 'advantages',
        'strategic position': 'advantages',
        'internal capabilities': 'advantages',
        'competitive position': 'advantages',
        'core competenc': 'advantages',
        'vulnerabilit': 'vulnerabilities',
        'weakness': 'vulnerabilities',
        'risk': 'vulnerabilities',
        'challenge': 'vulnerabilities',
        'concern': 'vulnerabilities',
        'tailwind': 'tailwinds',
        'opportunit': 'tailwinds',
        'future outlook': 'tailwinds',
        'growth driver': 'tailwinds',
        'catalyst': 'tailwinds',
        'headwind': 'headwinds',
        'threat': 'headwinds',
        'industry': 'headwinds',
        'competitive environment': 'headwinds',
        'competitive landscape': 'headwinds',
    }

    # Maximum bullet points per quadrant to prevent slide overflow
    MAX_BULLETS_PER_QUADRANT = 5

    current_section = None
    current_content: List[str] = []

    for line in content.split('\n'):
        stripped = line.strip()
        line_lower = stripped.lower()

        # Check if this is a section header: markdown heading, bold marker, or numbered prefix
        new_section = None
        is_header = (
            stripped.startswith('#')
            or stripped.startswith('**')
            or re.match(r'^\d+[.)]\s+\**', stripped)
        )
        if is_header:
            for key, section_name in sections_map.items():
                if key in line_lower:
                    new_section = section_name
                    break

        if new_section:
            # Save previous section
            if current_section and current_content:
                grid[current_section] = md_to_html(
                    '\n'.join(current_content[:MAX_BULLETS_PER_QUADRANT])
                )
            current_section = new_section
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section and current_content:
        grid[current_section] = md_to_html(
            '\n'.join(current_content[:MAX_BULLETS_PER_QUADRANT])
        )

    # If parsing failed, return None
    if not any(grid.values()):
        return None

    return grid


# Backward-compatible alias
parse_swot = parse_strategy_grid


def deduplicate_fiscal_years(rows: List[Dict]) -> List[Dict]:
    """Keep last occurrence when multiple entries share the same fiscal_year."""
    seen: Dict[Any, int] = {}
    for i, row in enumerate(rows):
        fy = row.get("fiscal_year")
        seen[fy] = i
    if len(seen) == len(rows):
        return rows
    keep = set(seen.values())
    return [row for i, row in enumerate(rows) if i in keep]


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

    elif format_type == 'percent_raw':
        # Accepts decimal input (e.g. 0.0214) and converts to display percent (+2.1%)
        pct = value * 100
        sign = '+' if pct >= 0 else ''
        return f'{sign}{pct:.1f}%'

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
