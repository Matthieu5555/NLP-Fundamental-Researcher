"""
Report editing via natural language commands.

Handles analyst requests to modify report sections through chat:
- Rewrite sections
- Expand/shorten content
- Emphasize specific points
- Add new content
- Change tone (bullish/bearish/neutral)

Uses LLM to intelligently apply edits while preserving analysis quality.
"""

import logging
from typing import Callable, Any
from dataclasses import dataclass

from .intent_classifier import ClassifiedIntent, ReportEditAction, UserIntent
from .report_builder import ReportState, SectionType
from .session import AnalysisSession

logger = logging.getLogger(__name__)


@dataclass
class EditResult:
    """Result of a report edit operation."""
    success: bool
    section_id: str
    old_content: str
    new_content: str
    action: ReportEditAction
    message: str  # Human-readable description of what was done
    tokens_used: int = 0


# Prompts for different edit actions
EDIT_PROMPTS = {
    ReportEditAction.REWRITE: """Rewrite this financial analysis section based on the analyst's instruction.

SECTION: {section_title}
CURRENT CONTENT:
{current_content}

ANALYST INSTRUCTION: {instruction}

Requirements:
- Completely rewrite the section following the instruction
- Maintain professional financial analysis tone
- Keep key facts and data points unless instructed otherwise
- Similar length to original (within 20%)
- Use **bold** for emphasis, no # headers

Rewritten section:""",

    ReportEditAction.EXPAND: """Expand this financial analysis section with more detail.

SECTION: {section_title}
CURRENT CONTENT:
{current_content}

ANALYST INSTRUCTION: {instruction}

Requirements:
- Add more depth, examples, and analysis
- Expand to roughly 1.5-2x the original length
- Add supporting data points where relevant
- Maintain professional financial analysis tone
- Use **bold** for emphasis, no # headers

Expanded section:""",

    ReportEditAction.SHORTEN: """Condense this financial analysis section to be more concise.

SECTION: {section_title}
CURRENT CONTENT:
{current_content}

ANALYST INSTRUCTION: {instruction}

Requirements:
- Reduce to roughly 50-70% of original length
- Keep the most important points
- Remove redundancy and fluff
- Maintain professional financial analysis tone
- Use **bold** for emphasis, no # headers

Condensed section:""",

    ReportEditAction.EMPHASIZE: """Rewrite this section to emphasize specific points.

SECTION: {section_title}
CURRENT CONTENT:
{current_content}

ANALYST INSTRUCTION: {instruction}
POINTS TO EMPHASIZE: {points}

Requirements:
- Prominently feature the specified points
- Move emphasized content toward the beginning
- May de-emphasize other points to create contrast
- Similar length to original
- Use **bold** for emphasis, no # headers

Rewritten section:""",

    ReportEditAction.ADD_POINT: """Add new content to this financial analysis section.

SECTION: {section_title}
CURRENT CONTENT:
{current_content}

ANALYST INSTRUCTION: {instruction}
NEW POINTS TO ADD: {points}

Requirements:
- Integrate new points naturally into existing content
- Place new content where it fits logically
- Maintain consistent tone and style
- Slightly longer than original is expected
- Use **bold** for emphasis, no # headers

Updated section:""",

    ReportEditAction.CHANGE_TONE: """Adjust the tone of this financial analysis section.

SECTION: {section_title}
CURRENT CONTENT:
{current_content}

ANALYST INSTRUCTION: {instruction}

Requirements:
- Adjust language to match requested tone (more bullish/bearish/neutral)
- Keep all factual content intact
- Only change framing and emphasis, not facts
- Similar length to original
- Use **bold** for emphasis, no # headers

Rewritten section:""",

    ReportEditAction.RESTRUCTURE: """Restructure the format of this section.

SECTION: {section_title}
CURRENT CONTENT:
{current_content}

ANALYST INSTRUCTION: {instruction}

Requirements:
- Change format (e.g., paragraphs to bullets, or vice versa)
- Keep all content and meaning intact
- Improve readability based on instruction
- Similar length to original
- Use **bold** for emphasis, no # headers

Restructured section:""",
}


def get_section_title(section_id: str, report_state: ReportState) -> str:
    """Get human-readable section title."""
    if section_id == 'investment_thesis':
        return 'Investment Thesis'

    section = report_state.get_section(section_id)
    if section:
        return section.title

    # Fallback mapping
    title_map = {
        'executive_summary': 'Executive Summary',
        'fundamentals': 'Fundamental Analysis',
        'technicals': 'Technical Analysis',
        'bull_case': 'Bull Case',
        'bear_case': 'Bear Case',
        'moat_analysis': 'Moat Analysis',
        'strategy': 'Strategy Analysis',
        'recommendation': 'Recommendation',
    }
    return title_map.get(section_id, section_id.replace('_', ' ').title())


def edit_section(
    session: AnalysisSession,
    intent: ClassifiedIntent,
    llm_func: Callable[..., Any],
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6"
) -> EditResult:
    """
    Apply an edit to a report section based on classified intent.

    Args:
        session: Current analysis session
        intent: Classified intent with edit details
        llm_func: The call_llm function
        api_key: API key for LLM
        model: Model to use (Sonnet for quality edits)

    Returns:
        EditResult with success status and edited content
    """
    if intent.intent != UserIntent.REPORT_EDIT:
        return EditResult(
            success=False,
            section_id="",
            old_content="",
            new_content="",
            action=ReportEditAction.REWRITE,
            message="Not a report edit intent"
        )

    if not session.report_state:
        return EditResult(
            success=False,
            section_id=intent.target_section or "",
            old_content="",
            new_content="",
            action=intent.edit_action or ReportEditAction.REWRITE,
            message="No report available to edit"
        )

    section_id = intent.target_section
    action = intent.edit_action or ReportEditAction.REWRITE

    # Handle full report edits
    if section_id == 'investment_thesis':
        return edit_full_report(session, intent, llm_func, api_key, model)

    # Get the section to edit
    section = session.report_state.get_section(section_id)
    if not section:
        return EditResult(
            success=False,
            section_id=section_id,
            old_content="",
            new_content="",
            action=action,
            message=f"Section '{section_id}' not found in report"
        )

    # Build the prompt
    prompt_template = EDIT_PROMPTS.get(action, EDIT_PROMPTS[ReportEditAction.REWRITE])
    prompt = prompt_template.format(
        section_title=section.title,
        current_content=section.content[:4000],  # Limit for context
        instruction=intent.edit_instruction or "Improve this section",
        points=", ".join(intent.specific_points) if intent.specific_points else "N/A"
    )

    try:
        response = llm_func(
            api_key=api_key,
            model=model,
            system_prompt="You are a senior financial analyst editing research reports. Produce clean, professional output.",
            user_prompt=prompt,
            temperature=0.3,  # Low temperature for precise, faithful edits
            max_tokens=3000
        )

        if not response.success:
            return EditResult(
                success=False,
                section_id=section_id,
                old_content=section.content,
                new_content="",
                action=action,
                message=f"LLM edit failed: {response.error}"
            )

        new_content = response.content.strip()
        old_content = section.content

        # Update the section
        session.report_state.update_section(section_id, new_content)
        logger.info(f"Edited section '{section_id}' with action '{action.value}'")

        # Build human-readable message
        action_messages = {
            ReportEditAction.REWRITE: f"Rewrote the {section.title}",
            ReportEditAction.EXPAND: f"Expanded the {section.title} with more detail",
            ReportEditAction.SHORTEN: f"Condensed the {section.title}",
            ReportEditAction.EMPHASIZE: f"Updated the {section.title} to emphasize key points",
            ReportEditAction.ADD_POINT: f"Added new content to the {section.title}",
            ReportEditAction.CHANGE_TONE: f"Adjusted the tone of the {section.title}",
            ReportEditAction.RESTRUCTURE: f"Restructured the {section.title}",
        }

        return EditResult(
            success=True,
            section_id=section_id,
            old_content=old_content,
            new_content=new_content,
            action=action,
            message=action_messages.get(action, f"Updated the {section.title}"),
            tokens_used=len(new_content.split()) * 2  # Rough estimate
        )

    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Section edit error: {e}")
        return EditResult(
            success=False,
            section_id=section_id,
            old_content=section.content if section else "",
            new_content="",
            action=action,
            message=f"Edit failed: {str(e)}"
        )


def edit_full_report(
    session: AnalysisSession,
    intent: ClassifiedIntent,
    llm_func: Callable[..., Any],
    api_key: str,
    model: str
) -> EditResult:
    """
    Apply an edit to all sections of the report.

    For full report edits, we apply the same transformation to each section.
    """
    if not session.report_state:
        return EditResult(
            success=False,
            section_id="investment_thesis",
            old_content="",
            new_content="",
            action=intent.edit_action or ReportEditAction.REWRITE,
            message="No report available"
        )

    edited_sections = []
    failed_sections = []

    # Edit each section (except sources)
    for section_id, section in session.report_state.sections.items():
        if section.section_type == SectionType.SOURCES:
            continue  # Skip sources section

        section_intent = ClassifiedIntent(
            intent=UserIntent.REPORT_EDIT,
            confidence=intent.confidence,
            edit_action=intent.edit_action,
            target_section=section_id,
            edit_instruction=intent.edit_instruction,
            specific_points=intent.specific_points
        )

        result = edit_section(session, section_intent, llm_func, api_key, model)
        if result.success:
            edited_sections.append(section_id)
        else:
            failed_sections.append(section_id)

    if edited_sections:
        action_name = intent.edit_action.value if intent.edit_action else "updated"
        return EditResult(
            success=True,
            section_id="investment_thesis",
            old_content="",
            new_content="",
            action=intent.edit_action or ReportEditAction.REWRITE,
            message=f"Successfully {action_name} {len(edited_sections)} sections"
        )
    else:
        return EditResult(
            success=False,
            section_id="investment_thesis",
            old_content="",
            new_content="",
            action=intent.edit_action or ReportEditAction.REWRITE,
            message="Failed to edit any sections"
        )


def generate_edit_confirmation(intent: ClassifiedIntent, result: EditResult) -> str:
    """
    Generate a natural language confirmation message for the user.

    This is what the assistant says after performing an edit.
    """
    if not result.success:
        return f"I wasn't able to make that edit: {result.message}"

    # Get a human-readable section name
    if result.section_id == "investment_thesis":
        section_name = "the full report"
    else:
        # Simple title from section_id
        section_name = result.section_id.replace('_', ' ').title()

    confirmations = {
        ReportEditAction.REWRITE: f"Done! I've rewritten the {section_name} based on your instructions. Take a look and let me know if you'd like any adjustments.",
        ReportEditAction.EXPAND: f"I've expanded the {section_name} with more detail. The section is now more comprehensive.",
        ReportEditAction.SHORTEN: f"Done - I've condensed the {section_name} to be more concise while keeping the key points.",
        ReportEditAction.EMPHASIZE: f"I've updated the {section_name} to emphasize those points more prominently.",
        ReportEditAction.ADD_POINT: f"Added that to the {section_name}. The new content has been integrated naturally.",
        ReportEditAction.CHANGE_TONE: f"I've adjusted the tone of the {section_name} as requested.",
        ReportEditAction.RESTRUCTURE: f"Done - I've restructured the {section_name} as you asked.",
    }

    return confirmations.get(result.action, result.message)
