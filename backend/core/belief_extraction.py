"""
Belief extraction and report updating logic.

Analyzes conversation to detect insights worth adding to the report.
"""

import logging
from typing import Optional, Dict
from .session import AnalysisSession
from .report_builder import SectionType

logger = logging.getLogger(__name__)


def should_update_report(user_message: str, ai_response: str, session: AnalysisSession) -> Optional[Dict]:
    """
    Determine if the conversation revealed insights worth adding to the report.

    Uses simple heuristics for MVP. In production, would use LLM to classify.

    Args:
        user_message: User's question
        ai_response: AI's response
        session: Current analysis session

    Returns:
        Dict with update info, or None if no update needed
        {
            'should_update': bool,
            'section_id': str,
            'insight': str,
            'confidence': float
        }
    """

    # Keywords that indicate analytical insights
    insight_keywords = [
        'calculate', 'compute', 'ratio', 'margin', 'growth', 'risk',
        'concern', 'opportunity', 'strength', 'weakness', 'competitive',
        'valuation', 'earnings', 'revenue', 'debt', 'cash flow',
        'analyst', 'upgrade', 'downgrade', 'catalyst', 'threat'
    ]

    # Check if user asked an analytical question
    message_lower = user_message.lower()
    is_analytical = any(keyword in message_lower for keyword in insight_keywords)

    if not is_analytical:
        return None

    # Check if response has substantial content (> 100 chars)
    if len(ai_response) < 100:
        return None

    # Route to appropriate section based on keywords
    section_routing = {
        'fundamental': (['ratio', 'margin', 'earnings', 'revenue', 'profit', 'roe', 'roa'], 'fundamentals'),
        'technical': (['chart', 'price', 'support', 'resistance', 'trend', 'moving average'], 'technicals'),
        'risk': (['risk', 'concern', 'threat', 'weakness', 'debt', 'liability'], 'risks'),
        'moat': (['competitive', 'advantage', 'moat', 'barrier', 'competition'], 'moat_analysis'),
    }

    target_section = 'recommendation'  # Default
    for category, (keywords, section_id) in section_routing.items():
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
    Update the report based on conversation insights.

    Args:
        user_message: User's question
        ai_response: AI's response
        session: Current session

    Returns:
        bool: True if report was updated
    """

    update_info = should_update_report(user_message, ai_response, session)

    if not update_info or not update_info['should_update']:
        return False

    logger.info(f"Updating report section: {update_info['section_id']}")

    # Check if section exists
    section = session.report_state.get_section(update_info['section_id'])

    if section:
        # Append to existing section
        insight = extract_key_insight(ai_response, user_message)
        new_content = section.content + "\n\n---\n\n### Additional Insight\n\n" + insight

        session.report_state.update_section(
            update_info['section_id'],
            new_content
        )
        logger.info(f"Updated existing section: {update_info['section_id']}")
    else:
        # Create new section for insights
        insight = extract_key_insight(ai_response, user_message)

        session.report_state.add_section(
            'additional_insights',
            'Additional Insights from Conversation',
            insight,
            SectionType.CUSTOM
        )
        logger.info("Created new section: additional_insights")

    # Add belief to graph
    belief_content = f"User explored: {user_message}"
    session.belief_graph.add_belief(
        belief_content,
        confidence=update_info['confidence'],
        source='conversation'
    )

    return True
