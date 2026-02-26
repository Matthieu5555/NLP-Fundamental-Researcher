"""
LLM-powered belief extraction from analyst conversations.

Identifies when analysts confirm, validate, or discover insights during chat
and routes them to appropriate report sections. Extracted beliefs are
categorized by type and routed to the appropriate report section for
integration into the living document.

Key Components:
- InsightType: Enum of belief categories for UI badge display
- ExtractedBelief: Dataclass holding extracted belief data
- extract_beliefs_from_conversation(): LLM-powered extraction
- rewrite_section_with_beliefs(): LLM-powered section integration
"""

import logging
import json
from typing import Optional, List, Callable, Any
from dataclasses import dataclass
from enum import Enum

from .colors import PALETTE, get_insight_badge

logger = logging.getLogger(__name__)


class InsightType(Enum):
    """
    Types of insights extracted from analyst conversation.

    Used to categorize beliefs for UI badge display and section routing.
    Each type maps to a semantic color in INSIGHT_BADGES for visual distinction.
    """
    CONFIRMED_FACT = "confirmed_fact"      # Verified information from data sources
    NEW_INSIGHT = "new_insight"            # Original analytical observation
    RISK_IDENTIFIED = "risk_identified"    # Potential concern or downside risk
    OPPORTUNITY = "opportunity"            # Bullish signal or upside potential
    VALUATION_VIEW = "valuation_view"      # Opinion on fair value vs current price
    COMPETITIVE_INSIGHT = "competitive"    # Moat durability or competition analysis


# UI badge styling for insight types — sourced from shared/colors.json via colors.py
# Maps InsightType enum values to their keys in the shared palette
_INSIGHT_TYPE_TO_KEY = {
    InsightType.CONFIRMED_FACT: "confirmed",
    InsightType.NEW_INSIGHT: "insight",
    InsightType.RISK_IDENTIFIED: "risk",
    InsightType.OPPORTUNITY: "opportunity",
    InsightType.VALUATION_VIEW: "valuation",
    InsightType.COMPETITIVE_INSIGHT: "competitive",
}

INSIGHT_BADGES = {
    itype: get_insight_badge(key)
    for itype, key in _INSIGHT_TYPE_TO_KEY.items()
}


def get_badge_for_belief(insight_type: InsightType) -> dict:
    """Get badge configuration for an insight type."""
    return INSIGHT_BADGES.get(insight_type, get_insight_badge("default"))


@dataclass
class ExtractedBelief:
    """A belief/insight extracted from conversation."""
    content: str
    insight_type: InsightType
    target_section: str
    confidence: float
    supporting_quote: str
    rationale: Optional[str] = None  # WHY the analyst believes this
    has_rationale: bool = False  # Whether rationale was provided


# Prompt for LLM to extract beliefs from conversation
BELIEF_EXTRACTION_PROMPT = """You are analyzing a conversation between a financial analyst (USER) and an AI assistant (CONSTANT) about {ticker}.

Your task: Detect ONLY when the analyst EXPLICITLY states their own opinion, conclusion, or judgment.
ALSO detect whether they provided REASONING (rationale) for their belief.

EXTRACT beliefs when the analyst says things like:
- "I think the valuation is too high"
- "I believe management is underperforming"
- "My view is that the moat is weakening"
- "I'm skeptical of the growth projections"
- "I agree with the bear case because..."
- "This confirms my suspicion that..."

RATIONALE DETECTION:
A belief HAS rationale when the analyst explains WHY they hold that belief:
- WITH rationale: "I think AAPL is overvalued because the P/E is 35x vs industry 20x"
- WITH rationale: "Management seems weak - they've missed guidance 3 quarters in a row"
- WITHOUT rationale: "I think AAPL is overvalued" (no because/reasoning)
- WITHOUT rationale: "I'm bearish on this stock" (opinion without support)

Look for reasoning signals: "because", "since", "given that", "due to", specific data points, comparisons, or causal explanations.

DO NOT extract beliefs from:
- Questions (even leading ones like "Isn't the P/E too high?")
- Requests for information ("Tell me about China exposure")
- Information the AI provided (that's research, not analyst opinion)
- Acknowledgments ("Thanks", "Got it", "Interesting")
- Hypotheticals ("What if China slows down?")
- The AI's analysis or conclusions

CRITICAL: If the analyst only asks questions, there is NO belief to extract.

Conversation:
Analyst: {user_message}
Constant: {ai_response}

Respond in JSON:
{{
    "has_belief": true/false,
    "beliefs": [
        {{
            "content": "The analyst believes [specific opinion in third person]",
            "type": "confirmed_fact|new_insight|risk_identified|opportunity|valuation_view|competitive",
            "section": "fundamentals|technicals|bull_case|bear_case|moat_analysis|strategy|recommendation",
            "confidence": 0.0-1.0,
            "quote": "Exact words from the analyst (NOT from Constant's response)",
            "has_rationale": true/false,
            "rationale": "The reasoning provided (or null if none)"
        }}
    ]
}}

Rules:
- Be VERY conservative - when in doubt, return no beliefs
- The quote MUST come from the analyst's message, never from Constant's response
- Questions = NO belief, even if the AI's answer contains useful information
- Maximum 1 belief per exchange (only the clearest, most explicit one)
- has_rationale should be true ONLY if the analyst explicitly explained their reasoning"""


def extract_beliefs_from_conversation(
    user_message: str,
    ai_response: str,
    ticker: str,
    llm_func: Callable[..., Any],
    api_key: str,
    model: str
) -> List[ExtractedBelief]:
    """
    Use LLM to extract confirmed beliefs/insights from a conversation turn.

    Args:
        user_message: What the analyst asked
        ai_response: What the AI responded
        ticker: Stock ticker being analyzed
        llm_func: The call_llm function
        api_key: API key for LLM
        model: Model to use

    Returns:
        List of extracted beliefs
    """
    # Skip very short exchanges
    if len(ai_response) < 50:
        return []

    prompt = BELIEF_EXTRACTION_PROMPT.format(
        ticker=ticker,
        user_message=user_message,
        ai_response=ai_response[:1500]  # Limit response length
    )

    try:
        response = llm_func(
            api_key=api_key,
            model=model,
            system_prompt="You are a belief extraction system. Respond only with valid JSON.",
            user_prompt=prompt,
            temperature=0.0,
            max_tokens=500
        )

        if not response.success:
            logger.warning(f"Belief extraction LLM call failed: {response.error}")
            return []

        # Parse JSON response
        result = json.loads(response.content)

        if not result.get("has_belief", False):
            return []

        beliefs = []
        for insight in result.get("beliefs", []):
            try:
                belief = ExtractedBelief(
                    content=insight["content"],
                    insight_type=InsightType(insight["type"]),
                    target_section=insight["section"],
                    confidence=float(insight.get("confidence", 0.7)),
                    supporting_quote=insight.get("quote", ""),
                    rationale=insight.get("rationale"),
                    has_rationale=insight.get("has_rationale", False)
                )
                beliefs.append(belief)
                rationale_status = "with rationale" if belief.has_rationale else "NO rationale"
                logger.info(f"Extracted belief ({rationale_status}): {belief.content[:50]}... -> {belief.target_section}")
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse insight: {e}")
                continue

        return beliefs

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse belief extraction response: {e}")
        return []
    except Exception as e:
        logger.error(f"Belief extraction error: {e}")
        return []


def format_belief_for_section(belief: ExtractedBelief) -> str:
    """Format a belief for inclusion in a report section."""
    type_labels = {
        InsightType.CONFIRMED_FACT: "Confirmed",
        InsightType.NEW_INSIGHT: "Insight",
        InsightType.RISK_IDENTIFIED: "Risk",
        InsightType.OPPORTUNITY: "Opportunity",
        InsightType.VALUATION_VIEW: "Valuation",
        InsightType.COMPETITIVE_INSIGHT: "Competitive",
    }

    label = type_labels.get(belief.insight_type, "Note")
    return f"**[{label}]** {belief.content}"


# Section rewriting prompt for finalization
SECTION_REWRITE_PROMPT = """You are rewriting a financial analysis section to incorporate new insights from analyst conversation.

ORIGINAL {section_title}:
{original_content}

NEW INSIGHTS TO INCORPORATE:
{beliefs_text}

Instructions:
1. Preserve the original analysis structure and key points
2. Naturally integrate the new insights where relevant
3. If insights contradict original analysis, present both views
4. Maintain professional financial analysis tone
5. Keep similar length to original (within 20%)
6. Use **bold** for headers, no # markdown

Rewrite the section:"""


def rewrite_section_with_beliefs(
    section_id: str,
    section_title: str,
    original_content: str,
    beliefs: List[ExtractedBelief],
    llm_func: Callable[..., Any],
    api_key: str,
    model: str
) -> Optional[str]:
    """
    Rewrite a report section incorporating extracted beliefs.

    Args:
        section_id: ID of the section
        section_title: Title of the section
        original_content: Original section content
        beliefs: List of beliefs to incorporate
        llm_func: The call_llm function
        api_key: API key
        model: Model to use

    Returns:
        Rewritten content or None if failed
    """
    if not beliefs:
        return None

    # Format beliefs for prompt
    beliefs_text = "\n".join([
        f"- {format_belief_for_section(b)}"
        for b in beliefs
    ])

    prompt = SECTION_REWRITE_PROMPT.format(
        section_title=section_title,
        original_content=original_content[:3000],
        beliefs_text=beliefs_text
    )

    try:
        response = llm_func(
            api_key=api_key,
            model=model,
            system_prompt="You are a senior financial analyst rewriting research reports.",
            user_prompt=prompt,
            temperature=0.3,
            max_tokens=2000
        )

        if response.success:
            logger.info(f"Rewrote section {section_id} with {len(beliefs)} beliefs")
            return response.content
        else:
            logger.error(f"Section rewrite failed: {response.error}")
            return None

    except Exception as e:
        logger.error(f"Section rewrite error: {e}")
        return None
