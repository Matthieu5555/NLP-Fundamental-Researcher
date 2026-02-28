"""
Intent classification for analyst chat messages.

Classifies user messages into three categories:
1. RESEARCH - Questions and requests for information
2. BELIEF - Analyst stating their opinion or conviction
3. REPORT_EDIT - Commands to modify the report content

This enables the chat to route messages appropriately:
- Research: RAG search + LLM response (existing behavior)
- Belief: Extract and store belief (existing behavior)
- Report Edit: Parse command and modify report section
"""

import logging
import json
from enum import Enum
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


class UserIntent(Enum):
    """Primary intent categories for chat messages."""
    RESEARCH = "research"           # Asking questions, requesting info
    BELIEF = "belief"               # Stating analyst opinion/conviction
    REPORT_EDIT = "report_edit"     # Command to modify report
    CONVERSATIONAL = "conversational"  # Thanks, acknowledgments, etc.


class ReportEditAction(Enum):
    """Specific actions for report modification."""
    REWRITE = "rewrite"             # Rewrite section entirely
    EXPAND = "expand"               # Make section longer/more detailed
    SHORTEN = "shorten"             # Make section more concise
    EMPHASIZE = "emphasize"         # Highlight specific points
    ADD_POINT = "add_point"         # Add specific content to section
    CHANGE_TONE = "change_tone"     # Make more bullish/bearish/neutral
    RESTRUCTURE = "restructure"     # Change format (bullets, paragraphs, etc.)


# Map section keywords to section IDs
SECTION_KEYWORDS = {
    'investment_thesis': ['report', 'full report', 'entire report', 'whole report', 'everything', 'all sections', 'thesis'],
    'fundamentals': ['fundamentals', 'fundamental', 'valuation', 'metrics', 'financials', 'pe', 'p/e', 'earnings', 'revenue'],
    'technicals': ['technical', 'technicals', 'chart', 'price', 'trading', 'momentum', 'rsi', 'macd'],
    'bull_case': ['bull', 'bullish', 'upside', 'positive', 'optimistic', 'bull case'],
    'bear_case': ['bear', 'bearish', 'downside', 'negative', 'pessimistic', 'bear case', 'risks'],
    'moat': ['moat', 'competitive', 'advantage', 'competition', 'defensibility'],
    'strategy': ['strategy', 'strengths', 'weaknesses', 'opportunities', 'threats', 'future outlook'],
    'recommendation': ['recommendation', 'verdict', 'conclusion', 'final', 'rating'],
    'industry': ['industry', 'macro', 'regulatory', 'market sizing', 'tam', 'competitive forces'],
}

# Keywords indicating report edit intent
EDIT_KEYWORDS = {
    'rewrite': ['rewrite', 're-write', 'redo', 'reword', 'rephrase', 'reframe'],
    'expand': ['expand', 'longer', 'more detail', 'elaborate', 'flesh out', 'add more', 'deeper', 'in-depth'],
    'shorten': ['shorten', 'shorter', 'concise', 'brief', 'condense', 'summarize', 'trim', 'cut down'],
    'emphasize': ['emphasize', 'highlight', 'focus on', 'stress', 'underscore', 'call out', 'prioritize'],
    'add_point': ['add', 'include', 'mention', 'insert', 'incorporate', 'put in'],
    'change_tone': ['more bullish', 'more bearish', 'more neutral', 'less optimistic', 'less pessimistic', 'balanced'],
    'restructure': ['restructure', 'reorganize', 'bullet points', 'paragraphs', 'format', 'structure'],
}


@dataclass
class ClassifiedIntent:
    """Result of intent classification."""
    intent: UserIntent
    confidence: float

    # For REPORT_EDIT intent
    edit_action: Optional[ReportEditAction] = None
    target_section: Optional[str] = None  # Section ID or 'investment_thesis'
    edit_instruction: Optional[str] = None  # Natural language instruction
    specific_points: Optional[List[str]] = None  # Points to emphasize/add

    def to_dict(self) -> Dict:
        return {
            'intent': self.intent.value,
            'confidence': self.confidence,
            'edit_action': self.edit_action.value if self.edit_action else None,
            'target_section': self.target_section,
            'edit_instruction': self.edit_instruction,
            'specific_points': self.specific_points
        }


def classify_intent_heuristic(message: str) -> ClassifiedIntent:
    """
    Fast heuristic-based intent classification.

    Checks for edit keywords and patterns before falling back to research intent.
    This is used for quick classification without LLM call.

    Args:
        message: User's chat message

    Returns:
        ClassifiedIntent with detected intent and metadata
    """
    msg_lower = message.lower().strip()

    # Check for conversational/acknowledgment
    ack_phrases = ['thanks', 'thank you', 'got it', 'ok', 'okay', 'understood', 'i see', 'cool', 'great', 'perfect']
    for phrase in ack_phrases:
        # Check exact match or phrase followed by punctuation
        if msg_lower == phrase or msg_lower.rstrip('!.?') == phrase:
            return ClassifiedIntent(intent=UserIntent.CONVERSATIONAL, confidence=0.95)
        if msg_lower.startswith(phrase + ' ') and len(msg_lower) < 30:  # Short follow-up
            return ClassifiedIntent(intent=UserIntent.CONVERSATIONAL, confidence=0.85)

    # Check for report edit intent
    detected_action = None
    action_confidence = 0.0

    for action_key, keywords in EDIT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in msg_lower:
                detected_action = ReportEditAction(action_key)
                action_confidence = 0.8
                break
        if detected_action:
            break

    # If edit keyword found, look for target section
    if detected_action:
        target_section = None
        for section_id, section_keywords in SECTION_KEYWORDS.items():
            for keyword in section_keywords:
                if keyword in msg_lower:
                    target_section = section_id
                    break
            if target_section:
                break

        # Default to full report if no specific section mentioned but edit intent detected
        if not target_section and detected_action:
            # Check if they're clearly referring to "the report"
            if any(word in msg_lower for word in ['report', 'analysis', 'document']):
                target_section = 'investment_thesis'

        if target_section:
            return ClassifiedIntent(
                intent=UserIntent.REPORT_EDIT,
                confidence=action_confidence,
                edit_action=detected_action,
                target_section=target_section,
                edit_instruction=message
            )

    # Check for belief indicators
    belief_phrases = [
        'i think', 'i believe', 'my view', 'i agree', 'indeed', 'exactly',
        'that confirms', 'i suspect', 'my takeaway', 'in my opinion',
        "i'm starting to think", 'this confirms', "i'm convinced",
        'my conclusion', 'it seems to me', 'i feel that', 'my sense is'
    ]
    if any(phrase in msg_lower for phrase in belief_phrases):
        # Could be belief + question
        if '?' in message:
            return ClassifiedIntent(intent=UserIntent.RESEARCH, confidence=0.6)  # Treat as research, belief extraction happens separately
        return ClassifiedIntent(intent=UserIntent.BELIEF, confidence=0.75)

    # Default to research (questions, requests for info)
    return ClassifiedIntent(intent=UserIntent.RESEARCH, confidence=0.7)


# LLM prompt for more accurate intent classification
INTENT_CLASSIFICATION_PROMPT = """You are classifying analyst messages in a financial research tool.

The analyst is reviewing a stock report and chatting with an AI assistant. Classify their message intent.

Message: "{message}"

INTENT TYPES:
1. RESEARCH - Asking questions or requesting information about the stock
   Examples: "What is the P/E ratio?", "Tell me about revenue growth", "What are the risks?"

2. BELIEF - Stating their own opinion or conviction (NOT asking a question)
   Examples: "I think the valuation is too high", "I'm convinced the moat is strong"

3. REPORT_EDIT - Asking to modify/change the report content
   Examples: "Make the bull case shorter", "Emphasize the debt concerns", "Rewrite the summary"
   Key signals: words like "rewrite", "shorten", "expand", "emphasize", "change", "make it", "add to the report"

4. CONVERSATIONAL - Simple acknowledgments
   Examples: "Thanks", "Got it", "Okay"

Respond in JSON:
{{
    "intent": "research|belief|report_edit|conversational",
    "confidence": 0.0-1.0,
    "edit_action": "rewrite|expand|shorten|emphasize|add_point|change_tone|restructure" (only if report_edit),
    "target_section": "investment_thesis|fundamentals|technicals|bull_case|bear_case|moat|strategy|industry|recommendation" (only if report_edit),
    "edit_instruction": "natural language description of the edit" (only if report_edit),
    "specific_points": ["point1", "point2"] (only if emphasize or add_point)
}}"""


def classify_intent_llm(
    message: str,
    llm_func: Callable[..., Any],
    api_key: str,
    model: str = "google/gemini-3-flash-preview"
) -> ClassifiedIntent:
    """
    LLM-powered intent classification for higher accuracy.

    Use this when heuristic classification is uncertain (confidence < 0.7)
    or when the message is complex.

    Args:
        message: User's chat message
        llm_func: The call_llm function
        api_key: API key for LLM
        model: Model to use (default: Haiku for speed)

    Returns:
        ClassifiedIntent with detected intent and metadata
    """
    prompt = INTENT_CLASSIFICATION_PROMPT.format(message=message)

    try:
        response = llm_func(
            api_key=api_key,
            model=model,
            system_prompt="You are an intent classification system. Respond only with valid JSON.",
            user_prompt=prompt,
            temperature=0.0,
            max_tokens=300
        )

        if not response.success:
            logger.warning(f"Intent classification LLM call failed: {response.error}")
            return classify_intent_heuristic(message)

        result = json.loads(response.content)

        intent = UserIntent(result['intent'])
        confidence = float(result.get('confidence', 0.8))

        if intent == UserIntent.REPORT_EDIT:
            return ClassifiedIntent(
                intent=intent,
                confidence=confidence,
                edit_action=ReportEditAction(result['edit_action']) if result.get('edit_action') else None,
                target_section=result.get('target_section'),
                edit_instruction=result.get('edit_instruction', message),
                specific_points=result.get('specific_points')
            )

        return ClassifiedIntent(intent=intent, confidence=confidence)

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Failed to parse intent classification response: {e}")
        return classify_intent_heuristic(message)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Intent classification error: {e}")
        return classify_intent_heuristic(message)


def classify_intent(
    message: str,
    use_llm: bool = False,
    llm_func: Callable[..., Any] = None,
    api_key: str = None,
    model: str = "google/gemini-3-flash-preview"
) -> ClassifiedIntent:
    """
    Main entry point for intent classification.

    Uses heuristics first, falls back to LLM if uncertain and LLM is enabled.

    Args:
        message: User's chat message
        use_llm: Whether to use LLM for uncertain classifications
        llm_func: The call_llm function (required if use_llm=True)
        api_key: API key for LLM
        model: Model to use for LLM classification

    Returns:
        ClassifiedIntent with detected intent and metadata
    """
    # First try heuristic classification
    result = classify_intent_heuristic(message)

    # If confident enough or LLM not enabled, return heuristic result
    if result.confidence >= 0.75 or not use_llm:
        return result

    # Use LLM for uncertain cases
    if llm_func and api_key:
        return classify_intent_llm(message, llm_func, api_key, model)

    return result
