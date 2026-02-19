"""
Report update decision logic based on conversation analysis.

Determines when chat messages contain analytical insights worth preserving
in the living document. Uses keyword-based heuristics for fast classification.

Note: This module uses a heuristic approach for MVP speed. For improved
accuracy, consider replacing with LLM-based classification similar to
the approach used in rag_engine.py.
"""

import logging
from typing import Optional, Dict
from .session import AnalysisSession

logger = logging.getLogger(__name__)


# Keywords indicating analytical content worth preserving in report
# Heuristic approach for MVP speed - see TODO in should_update_report()
ANALYTICAL_KEYWORDS = [
    'calculate', 'compute', 'ratio', 'margin', 'growth', 'risk',
    'concern', 'opportunity', 'strength', 'weakness', 'competitive',
    'valuation', 'earnings', 'revenue', 'debt', 'cash flow',
    'analyst', 'upgrade', 'downgrade', 'catalyst', 'threat'
]

# Map keyword categories to report sections for routing insights
# Keys are category names, values are (keywords, section_id) tuples
SECTION_ROUTING = {
    'fundamental': (['ratio', 'margin', 'earnings', 'revenue', 'profit', 'roe', 'roa'], 'fundamentals'),
    'technical': (['chart', 'price', 'support', 'resistance', 'trend', 'moving average'], 'technicals'),
    'risk': (['risk', 'concern', 'threat', 'weakness', 'debt', 'liability'], 'risks'),
    'moat': (['competitive', 'advantage', 'moat', 'barrier', 'competition'], 'moat_analysis'),
}


def should_update_report(user_message: str, ai_response: str, session: AnalysisSession) -> Optional[Dict]:
    """
    Determine if a chat message contains analytical insights worth preserving.

    Implementation: Keyword-based heuristic for MVP speed. A message is
    considered analytical if it contains phrases suggesting original analysis.

    TODO: Replace with LLM-based classification for better accuracy.
    Current heuristic has ~70% precision but misses nuanced insights.
    Consider using the same classification approach as rag_engine.py
    with a cheap model like Claude 3 Haiku.

    Args:
        user_message: User's question
        ai_response: AI's response
        session: Current analysis session

    Returns:
        Dict with update info, or None if no update needed:
        {
            'should_update': bool,
            'section_id': str,
            'insight': str,
            'confidence': float,
            'user_question': str
        }
    """

    # Check if user asked an analytical question using module-level keywords
    message_lower = user_message.lower()
    is_analytical = any(keyword in message_lower for keyword in ANALYTICAL_KEYWORDS)

    if not is_analytical:
        return None

    # Check if response has substantial content (> 100 chars)
    if len(ai_response) < 100:
        return None

    # Route to appropriate section based on keyword categories
    target_section = 'recommendation'  # Default fallback
    for category, (keywords, section_id) in SECTION_ROUTING.items():
        if any(kw in message_lower for kw in keywords):
            target_section = section_id
            break

    return {
        'should_update': True,
        'section_id': target_section,
        'insight': ai_response,
        'confidence': 0.7,
        'user_question': user_message
    }


def extract_key_insight(ai_response: str, user_question: str) -> str:
    """
    Extract the key insight from AI response to add to report.

    For MVP, returns formatted version. In production, would use LLM to summarize.

    Args:
        ai_response: Full AI response
        user_question: User's question

    Returns:
        Formatted insight for report
    """

    # Format as Q&A entry
    insight = f"**User Question**: {user_question}\n\n"
    insight += f"**Analysis**: {ai_response}\n\n"

    return insight


def update_report_from_conversation(
    user_message: str,
    ai_response: str,
    session: AnalysisSession
) -> bool:
    """
    Track conversation insights in belief graph (no longer appends to report).

    Insights from chat are tracked in the belief graph and analyst_sources,
    which appear in the Sources section of the PDF. We no longer append
    "Additional Insight" sections to the report content.

    Args:
        user_message: User's question
        ai_response: AI's response
        session: Current session

    Returns:
        bool: True if belief was tracked
    """

    update_info = should_update_report(user_message, ai_response, session)

    if not update_info or not update_info['should_update']:
        return False

    logger.info(f"Tracking belief from conversation about: {update_info['section_id']}")

    # Add belief to graph (tracked in analyst_sources for PDF sources section)
    belief_content = f"User explored: {user_message}"
    session.belief_graph.add_belief(
        belief_content,
        confidence=update_info['confidence'],
        source='conversation'
    )

    return True
