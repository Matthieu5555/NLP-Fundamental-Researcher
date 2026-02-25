"""
Detect contradictions and important items for further research.

Analyzes bull/bear cases to find claims where analysts interpret the SAME facts
differently. Returns structured data for card-based UI display.

Detection Approach:
Uses LLM-based semantic analysis for nuanced contradiction detection,
with keyword-based heuristics as a fallback. The LLM approach catches
contradictions expressed with different vocabulary (e.g., "declining revenue"
vs "slowing growth") that simple keyword matching would miss.

Contradiction Categories:
1. Valuation: Disagreements on fair value vs current price
2. Growth: Differing views on revenue/earnings trajectory
3. Competition: Moat durability vs competitive erosion
4. Margins: Expansion expectations vs compression concerns
5. Management: Leadership quality and shareholder alignment
6. Capital Allocation: Uses of cash, M&A strategy, buybacks
7. Macro/Industry: Market cycle, regulatory, external factors
"""

import logging
import json
from typing import List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, asdict

if TYPE_CHECKING:
    from src_george_researcher.orchestrator import FullAnalysis

# sys.path configured in backend/main.py
from backend.agents.llm_wrapper import get_llm_response

logger = logging.getLogger(__name__)


@dataclass
class Contradiction:
    """Structured representation of a bull/bear contradiction."""
    disputed_fact: str           # The underlying fact being disputed
    bull_interpretation: str     # How bulls view this fact
    bear_interpretation: str     # How bears view this fact
    judgment_question: str       # What the analyst needs to determine
    priority: str                # HIGH, MEDIUM, LOW
    category: str                # valuation, growth, competition, etc.

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ResearchGap:
    """An area needing further investigation."""
    title: str
    description: str
    priority: str
    data_source: str  # Where to find more info


# LLM prompt for semantic contradiction detection
CONTRADICTION_DETECTION_PROMPT = """You are analyzing bull and bear investment theses for the same company.

Your task: Identify where bulls and bears interpret the SAME underlying facts DIFFERENTLY.
A contradiction is NOT just disagreement - it's when both sides acknowledge the same data point
but reach opposite conclusions about what it means.

BULL CASE:
{bull_case}

BEAR CASE:
{bear_case}

Find 2-5 semantic contradictions. For each, identify:
1. The disputed fact (the underlying data point both sides reference)
2. The bull interpretation (how bulls view this fact as positive)
3. The bear interpretation (how bears view this fact as concerning)
4. A judgment question (what the analyst must determine)
5. Priority (HIGH if central to thesis, MEDIUM if supporting, LOW if peripheral)
6. Category (valuation, growth, competition, margins, management, capital_allocation, macro)

Examples of REAL contradictions:
- Bulls say "P/E of 25 is reasonable for this growth" vs Bears say "P/E of 25 is expensive given slowing growth"
- Bulls say "market share gains show moat strength" vs Bears say "share gains required heavy discounting"
- Bulls say "management has delivered consistently" vs Bears say "management is too promotional"

NOT contradictions:
- Bulls mention revenue growth, Bears mention debt (different topics, not contradiction)
- Bulls are optimistic, Bears are pessimistic (general sentiment, not specific disagreement)

Respond in JSON:
{{
    "contradictions": [
        {{
            "disputed_fact": "What underlying fact/metric both sides reference",
            "bull_interpretation": "How bulls interpret this as positive (1-2 sentences)",
            "bear_interpretation": "How bears interpret this as concerning (1-2 sentences)",
            "judgment_question": "What must the analyst determine to resolve this?",
            "priority": "HIGH|MEDIUM|LOW",
            "category": "valuation|growth|competition|margins|management|capital_allocation|macro"
        }}
    ]
}}

If you find NO genuine contradictions (rare), return {{"contradictions": []}}"""


def find_contradictions_llm(full_analysis: Any) -> List[Contradiction]:
    """
    Use LLM to detect semantic contradictions between bull and bear cases.

    This approach catches nuanced disagreements that keyword matching misses,
    such as when the same concern is expressed with different vocabulary.

    Args:
        full_analysis: FullAnalysis dataclass with bull_thesis and bear_thesis

    Returns:
        List of detected Contradiction objects
    """
    has_bull = full_analysis.bull_thesis and full_analysis.bull_thesis.success
    has_bear = full_analysis.bear_thesis and full_analysis.bear_thesis.success

    if not (has_bull and has_bear):
        logger.info("Missing bull or bear thesis, skipping LLM contradiction detection")
        return []

    bull_content = full_analysis.bull_thesis.content
    bear_content = full_analysis.bear_thesis.content

    # Truncate if too long
    bull_content = bull_content[:3000] if len(bull_content) > 3000 else bull_content
    bear_content = bear_content[:3000] if len(bear_content) > 3000 else bear_content

    prompt = CONTRADICTION_DETECTION_PROMPT.format(
        bull_case=bull_content,
        bear_case=bear_content
    )

    try:
        response = get_llm_response(
            prompt=prompt,
            system_prompt="You are a financial analyst identifying contradictions. Return only valid JSON.",
            temperature=0.2  # Low temperature for consistency
        )

        if response.startswith("Error:"):
            logger.warning(f"LLM contradiction detection failed: {response}")
            return []

        # Parse JSON response
        result = json.loads(response)
        contradictions = []

        for item in result.get("contradictions", []):
            try:
                contradiction = Contradiction(
                    disputed_fact=item["disputed_fact"],
                    bull_interpretation=item["bull_interpretation"],
                    bear_interpretation=item["bear_interpretation"],
                    judgment_question=item["judgment_question"],
                    priority=item.get("priority", "MEDIUM").upper(),
                    category=item.get("category", "general")
                )
                contradictions.append(contradiction)
            except KeyError as e:
                logger.warning(f"Missing field in contradiction: {e}")
                continue

        logger.info(f"LLM detected {len(contradictions)} contradictions")
        return contradictions

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM contradiction response: {e}")
        return []
    except Exception as e:
        logger.error(f"LLM contradiction detection error: {e}")
        return []


def detect_contradictions_and_research_items(full_analysis) -> str:
    """
    Analyze the full analysis to find contradictions and items needing further research.

    Uses LLM-based semantic analysis first for better accuracy, falls back to
    keyword-based heuristics if LLM fails.

    Args:
        full_analysis: FullAnalysis dataclass from orchestrator

    Returns:
        str: Markdown content for Further Research section
    """
    contradictions = []
    research_gaps = []

    # Try LLM-based detection first (more accurate)
    try:
        contradictions = find_contradictions_llm(full_analysis)
    except Exception as e:
        logger.warning(f"LLM contradiction detection failed: {e}")

    # Fall back to heuristic if LLM returns nothing or fails
    if not contradictions:
        logger.info("LLM returned no contradictions, falling back to heuristic")
        try:
            contradictions = find_contradictions_heuristic(full_analysis)
        except Exception as e:
            logger.warning(f"Heuristic contradiction detection failed: {e}")

    # Try to find research gaps (separate try/except so contradictions aren't lost)
    try:
        research_gaps = find_research_gaps(full_analysis)
    except Exception as e:
        logger.warning(f"Research gap detection failed: {e}")

    # Format as markdown for backwards compatibility
    return format_contradictions_markdown(contradictions, research_gaps)


def find_contradictions_heuristic(full_analysis: 'FullAnalysis') -> List[Contradiction]:
    """
    Fallback: Detect contradictions using keyword matching.

    Used when LLM-based detection fails or returns empty results.
    Faster but less accurate than semantic analysis.

    Patterns detected:
    1. Valuation: "undervalued/cheap" vs "overvalued/expensive"
    2. Growth: "strong growth" vs "slowing/declining"
    3. Competition: "moat/market leader" vs "losing share"
    4. Margins: "margin expansion" vs "margin pressure"
    5. Management: positive vs negative management sentiment

    Args:
        full_analysis: FullAnalysis dataclass with bull_thesis and bear_thesis

    Returns:
        List of detected Contradiction objects
    """
    contradictions = []

    has_bull = full_analysis.bull_thesis and full_analysis.bull_thesis.success
    has_bear = full_analysis.bear_thesis and full_analysis.bear_thesis.success

    if not (has_bull and has_bear):
        return contradictions

    bull_content = full_analysis.bull_thesis.content.lower()
    bear_content = full_analysis.bear_thesis.content.lower()

    # Pattern 1: Valuation contradiction
    # Detects when bulls see value while bears see overpricing
    bull_undervalued = 'undervalued' in bull_content or 'cheap' in bull_content or 'attractive valuation' in bull_content
    bear_overvalued = 'overvalued' in bear_content or 'expensive' in bear_content or 'priced for perfection' in bear_content

    if bull_undervalued and bear_overvalued:
        contradictions.append(Contradiction(
            disputed_fact="Current valuation relative to fair value",
            bull_interpretation="The stock trades below intrinsic value based on growth prospects and fundamentals.",
            bear_interpretation="The stock is overpriced given risks and current multiples compared to peers.",
            judgment_question="What is the appropriate multiple for this company's risk/reward profile?",
            priority="HIGH",
            category="valuation"
        ))

    # Pattern 2: Growth trajectory contradiction
    # Detects when bulls see momentum while bears see deceleration
    bull_growth = 'strong growth' in bull_content or 'growth potential' in bull_content or 'revenue growth' in bull_content
    bear_slowdown = 'slowing growth' in bear_content or 'declining' in bear_content or 'growth concerns' in bear_content

    if bull_growth and bear_slowdown:
        contradictions.append(Contradiction(
            disputed_fact="Future revenue growth trajectory",
            bull_interpretation="Strong momentum will continue as the company captures market share.",
            bear_interpretation="Growth is decelerating and may disappoint expectations.",
            judgment_question="Is recent growth sustainable, or are we seeing peak performance?",
            priority="HIGH",
            category="growth"
        ))

    # Pattern 3: Competitive moat contradiction
    # Detects when bulls see defensible position while bears see erosion
    bull_moat = 'competitive advantage' in bull_content or 'moat' in bull_content or 'market leader' in bull_content
    bear_competition = 'competitive threat' in bear_content or 'losing share' in bear_content or 'competition intensifying' in bear_content

    if bull_moat and bear_competition:
        contradictions.append(Contradiction(
            disputed_fact="Durability of competitive position",
            bull_interpretation="Strong moat protects margins and market position long-term.",
            bear_interpretation="Competitors are eroding the company's advantages.",
            judgment_question="Can the company defend its market position over the next 3-5 years?",
            priority="MEDIUM",
            category="competition"
        ))

    # Pattern 4: Margin sustainability contradiction
    # Detects when bulls see expansion while bears see compression
    bull_margin = 'margin expansion' in bull_content or 'operating leverage' in bull_content or 'improving margins' in bull_content
    bear_margin = 'margin pressure' in bear_content or 'margin compression' in bear_content or 'cost pressures' in bear_content

    if bull_margin and bear_margin:
        contradictions.append(Contradiction(
            disputed_fact="Margin trajectory over next 1-2 years",
            bull_interpretation="Operating leverage and scale will drive margin expansion.",
            bear_interpretation="Competitive and cost pressures will compress margins.",
            judgment_question="Does the company have pricing power and cost control to protect margins?",
            priority="MEDIUM",
            category="profitability"
        ))

    # Pattern 5: Management credibility contradiction
    # Detects when bulls praise leadership while bears question execution/alignment
    bull_mgmt = 'management' in bull_content and ('strong' in bull_content or 'proven' in bull_content or 'track record' in bull_content)
    bear_mgmt = 'management' in bear_content and ('concern' in bear_content or 'question' in bear_content or 'aggressive' in bear_content)

    if bull_mgmt and bear_mgmt:
        contradictions.append(Contradiction(
            disputed_fact="Management execution and credibility",
            bull_interpretation="Proven leadership team with strong execution track record.",
            bear_interpretation="Management incentives or past actions raise concerns.",
            judgment_question="Does management have shareholders' long-term interests aligned?",
            priority="MEDIUM",
            category="governance"
        ))

    return contradictions


def find_research_gaps(full_analysis: Any) -> List[ResearchGap]:
    """
    Find areas that need more investigation based on the analysis.

    Uses stock_info metrics (non-US) or enriched_financials (US) to identify potential concerns:
    - High leverage (debt_to_equity > 1.0)
    - Premium valuation (P/E > 35)
    - Unprofitable company (P/E < 0)

    Args:
        full_analysis: FullAnalysis (non-US) or USFullAnalysis (US) dataclass

    Returns:
        List of ResearchGap objects for areas needing investigation
    """
    gaps = []

    # Try to get metrics from stock_info (non-US) or build from US data
    debt_ratio = None
    pe_ratio = None

    # Non-US analysis with stock_info
    if hasattr(full_analysis, 'stock_info') and full_analysis.stock_info:
        debt_ratio = getattr(full_analysis.stock_info, 'debt_to_equity', None)
        pe_ratio = getattr(full_analysis.stock_info, 'pe_ratio', None)

    # US analysis with enriched_financials
    elif hasattr(full_analysis, 'enriched_financials') and full_analysis.enriched_financials:
        ef = full_analysis.enriched_financials
        if ef.periods:
            latest = ef.periods[0]
            if hasattr(latest, 'debt_to_equity') and latest.debt_to_equity:
                debt_ratio = latest.debt_to_equity.current_value

        # For US, calculate P/E from technicals and financials
        if hasattr(full_analysis, 'technicals') and full_analysis.technicals:
            current_price = full_analysis.technicals.current_price
            if ef.periods and current_price:
                latest = ef.periods[0]
                if hasattr(latest, 'eps') and latest.eps and latest.eps.current_value:
                    eps = latest.eps.current_value
                    if eps > 0:
                        pe_ratio = current_price / eps
                    elif eps < 0:
                        pe_ratio = -1  # Mark as negative earnings

    # High leverage
    if debt_ratio is not None:
        # Normalize: values > 10 are likely percentages (e.g., 33.15% = 0.3315 ratio)
        normalized_ratio = debt_ratio / 100 if debt_ratio > 10 else debt_ratio
        if normalized_ratio > 1.0:
            gaps.append(ResearchGap(
                title="Balance Sheet Leverage",
                description=f"Debt-to-equity of {normalized_ratio:.2f}x indicates significant leverage. Investigate debt maturity schedule and interest coverage.",
                priority="HIGH",
                data_source="10-K filings, investor presentations"
            ))

    # Premium valuation
    if pe_ratio and pe_ratio > 35:
        gaps.append(ResearchGap(
            title="Premium Valuation",
            description=f"P/E of {pe_ratio:.1f} is well above market average. Verify growth assumptions justify the premium.",
            priority="MEDIUM",
            data_source="Analyst estimates, earnings transcripts"
        ))

    # Negative earnings
    if pe_ratio and pe_ratio < 0:
        gaps.append(ResearchGap(
            title="Path to Profitability",
            description="Company is currently unprofitable. Research cash burn rate and timeline to break-even.",
            priority="HIGH",
            data_source="Earnings calls, cash flow statements"
        ))

    return gaps


def format_contradictions_markdown(contradictions: List[Contradiction], gaps: List[ResearchGap]) -> str:
    """Format contradictions and gaps as markdown for backwards compatibility."""

    if not contradictions and not gaps:
        return "No critical contradictions or research items identified. The analysis presents a relatively consistent view."

    markdown = ""

    if contradictions:
        markdown += "## Key Disagreements\n\n"
        markdown += "These are areas where bulls and bears interpret the same facts differently. Your judgment is needed.\n\n"

        for c in contradictions:
            markdown += f"### {c.disputed_fact}\n\n"
            markdown += f"**Bulls argue:** {c.bull_interpretation}\n\n"
            markdown += f"**Bears argue:** {c.bear_interpretation}\n\n"
            markdown += f"**Your call:** {c.judgment_question}\n\n"
            markdown += f"*Priority: {c.priority} | Category: {c.category}*\n\n---\n\n"

    if gaps:
        markdown += "## Research Gaps\n\n"
        markdown += "Additional areas requiring investigation:\n\n"

        for g in gaps:
            markdown += f"### {g.title}\n\n"
            markdown += f"{g.description}\n\n"
            markdown += f"*Data source: {g.data_source}*\n\n---\n\n"

    markdown += "\n**Recommendation**: Address these items in chat before making investment decisions."

    return markdown


def get_structured_contradictions(full_analysis) -> Dict:
    """
    Get structured contradiction data for frontend card UI.

    Uses LLM-based detection with heuristic fallback.

    Returns:
        Dict with 'contradictions' and 'research_gaps' as lists of dicts
    """
    contradictions = []
    gaps = []

    # Try LLM-based detection first
    try:
        contradictions = find_contradictions_llm(full_analysis)
    except Exception as e:
        logger.warning(f"LLM contradiction detection failed: {e}")

    # Fall back to heuristic if LLM returns nothing or fails
    if not contradictions:
        try:
            contradictions = find_contradictions_heuristic(full_analysis)
        except Exception as e:
            logger.warning(f"Heuristic contradiction detection failed: {e}")

    # Try to find research gaps
    try:
        gaps = find_research_gaps(full_analysis)
    except Exception as e:
        logger.warning(f"Research gap detection failed: {e}")

    return {
        'contradictions': [c.to_dict() for c in contradictions],
        'research_gaps': [asdict(g) for g in gaps]
    }
