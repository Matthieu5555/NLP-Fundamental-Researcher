"""
Detect contradictions and important items for further research.

Analyzes bull/bear cases and other sections to find claims that can't both be true
and are critical for valuation.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def detect_contradictions_and_research_items(full_analysis) -> str:
    """
    Analyze the full analysis to find contradictions and items needing further research.

    Args:
        full_analysis: FullAnalysis dataclass from orchestrator

    Returns:
        str: Markdown content for Further Research section
    """

    research_items = []

    # Check if we have bull and bear cases
    has_bull = full_analysis.bull_thesis and full_analysis.bull_thesis.success
    has_bear = full_analysis.bear_thesis and full_analysis.bear_thesis.success

    if has_bull and has_bear:
        bull_content = full_analysis.bull_thesis.content.lower()
        bear_content = full_analysis.bear_thesis.content.lower()

        # Detect valuation contradictions
        if ('undervalued' in bull_content or 'cheap' in bull_content) and \
           ('overvalued' in bear_content or 'expensive' in bear_content or 'priced for perfection' in bear_content):
            research_items.append({
                'title': 'Valuation Disagreement',
                'description': 'The bull case suggests the stock is undervalued while the bear case argues it is overvalued. This is a critical area requiring deeper analysis of comparable company multiples and growth assumptions.',
                'priority': 'HIGH'
            })

        # Detect growth contradictions
        if ('growth' in bull_content and 'strong' in bull_content) and \
           ('growth' in bear_content and ('slowing' in bear_content or 'declining' in bear_content)):
            research_items.append({
                'title': 'Growth Trajectory Uncertainty',
                'description': 'There is disagreement about the company\'s growth prospects. Examine recent revenue trends, management guidance, and industry growth rates.',
                'priority': 'HIGH'
            })

        # Detect competitive position contradictions
        if ('competitive advantage' in bull_content or 'moat' in bull_content) and \
           ('competitive threat' in bear_content or 'competition' in bear_content):
            research_items.append({
                'title': 'Competitive Position Assessment',
                'description': 'The strength of the company\'s competitive moat is disputed. Research market share trends, customer switching costs, and competitive dynamics.',
                'priority': 'MEDIUM'
            })

        # Detect margin/profitability contradictions
        if 'margin' in bull_content and 'margin' in bear_content:
            research_items.append({
                'title': 'Margin Sustainability',
                'description': 'There are conflicting views on the company\'s ability to maintain or expand margins. Analyze cost structure, pricing power, and competitive pressures.',
                'priority': 'MEDIUM'
            })

    # Check fundamentals for high debt
    if full_analysis.stock_info:
        debt_ratio = getattr(full_analysis.stock_info, 'debt_to_equity', None)
        if debt_ratio and debt_ratio > 1.0:
            research_items.append({
                'title': 'Balance Sheet Risk',
                'description': f'Debt-to-equity ratio of {debt_ratio:.2f} indicates significant leverage. Investigate debt maturity schedule, interest coverage, and refinancing risk.',
                'priority': 'HIGH'
            })

    # Check for high valuation multiples
    if full_analysis.stock_info:
        pe_ratio = getattr(full_analysis.stock_info, 'pe_ratio', None)
        if pe_ratio and pe_ratio > 30:
            research_items.append({
                'title': 'Valuation Multiple Risk',
                'description': f'P/E ratio of {pe_ratio:.1f} is elevated. Research if growth justifies the premium and what catalysts could drive multiple compression.',
                'priority': 'MEDIUM'
            })

    # Format as markdown
    if not research_items:
        return "No critical contradictions or research items identified at this time. The analysis presents a relatively consistent view."

    markdown = "The following items represent contradictions or critical uncertainties that require deeper investigation:\n\n"

    for item in research_items:
        priority_badge = f"**[{item['priority']} PRIORITY]**"
        markdown += f"### {item['title']} {priority_badge}\n\n"
        markdown += f"{item['description']}\n\n"
        markdown += "---\n\n"

    markdown += "\n**Recommendation**: Address these items before making investment decisions. "
    markdown += "Use the chat below to ask specific questions about each area."

    return markdown
