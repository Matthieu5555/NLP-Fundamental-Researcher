"""
Analyst belief override parser.

Transforms beliefs from the belief graph into actionable overrides:
- Numeric DCF assumption overrides (hard values the analyst specified)
- Qualitative directives for agent prompts (non-negotiable constraints)
- Dirty-stage determination (which pipeline stages need re-running)

The governing principle: the analyst knows better than the LLM. Analyst
beliefs are hard overrides, not suggestions. Numeric values are injected
directly into models; qualitative views become authoritative constraints
that agents must build around.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any

from backend.core.belief_graph import Belief
from backend.core.report_builder import AnalystSource

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DCF assumption field names that can be overridden, with human-friendly
# aliases the LLM parser should map to.
# ---------------------------------------------------------------------------
OVERRIDABLE_DCF_FIELDS = {
    "revenue_growth_rates",
    "wacc",
    "terminal_growth_rate",
    "fcf_margin",
    "gross_margins",
    "opex_as_pct_revenue",
    "da_as_pct_revenue",
    "sbc_as_pct_revenue",
    "capex_as_pct_revenue",
    "nwc_change_pct",
    "tax_rate",
}

# Maps insight_type strings to the pipeline stages they dirty.
# Each belief dirties everything listed plus conviction (always).
INSIGHT_TYPE_TO_DIRTY_STAGES: Dict[str, Set[str]] = {
    "valuation_view": {"dcf", "sensitivity", "scenarios", "football_field"},
    "risk_identified": {"bull_bear", "recommendation"},
    "opportunity": {"bull_bear", "recommendation"},
    "competitive": {"moat", "strategic_assessment", "bull_bear", "recommendation"},
    "new_insight": set(),  # depends on target_section, handled separately
    "confirmed_fact": set(),  # depends on target_section
}

# If a belief targets one of these sections, it dirties the corresponding stage.
SECTION_TO_STAGE: Dict[str, str] = {
    "strategy": "strategy",
    "industry": "strategic_assessment",
    "moat": "moat",
    "fundamentals": "fundamentals",
    "bull_case": "bull_bear",
    "bear_case": "bull_bear",
    "recommendation": "recommendation",
}

# Stages that cascade: if stage X is dirty, stages Y are also dirty.
STAGE_CASCADE: Dict[str, Set[str]] = {
    "strategy": {"bull_bear", "recommendation"},
    "strategic_assessment": {"dcf", "sensitivity", "scenarios", "football_field", "bull_bear", "recommendation"},
    "moat": {"bull_bear", "recommendation"},
    "fundamentals": {"bull_bear", "recommendation"},
    "dcf": {"sensitivity", "scenarios", "football_field"},
    "bull_bear": {"recommendation"},
}


@dataclass
class AnalysisOverrides:
    """Parsed analyst overrides ready for injection into the pipeline."""
    dcf_overrides: Dict = field(default_factory=dict)
    qualitative_directives: str = ""
    dirty_stages: Set[str] = field(default_factory=set)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt for the LLM to parse numeric overrides from natural language
# ---------------------------------------------------------------------------
NUMERIC_PARSE_PROMPT = """You are a financial data parser. Extract specific numeric DCF model overrides from the analyst's beliefs.

ANALYST BELIEFS:
{beliefs_text}

MAP each belief to the EXACT DCF field it overrides. Only extract beliefs that specify a concrete number.

Available fields:
- revenue_growth_rates: list of annual growth rates as decimals (e.g., 0.15 for 15%). If analyst specifies a single rate, repeat it for 5 years with gentle decay.
- wacc: weighted average cost of capital as decimal (e.g., 0.10 for 10%)
- terminal_growth_rate: long-run growth rate as decimal (e.g., 0.025 for 2.5%)
- fcf_margin: free cash flow margin as decimal (e.g., 0.20 for 20%)
- gross_margins: list of annual gross margins as decimals. If single value, repeat for 5 years.
- opex_as_pct_revenue: list of annual opex ratios as decimals. If single value, repeat for 5 years.
- tax_rate: effective tax rate as decimal (e.g., 0.21 for 21%)

RULES:
- Only extract when the analyst states a specific number
- Convert percentages to decimals (15% -> 0.15)
- If "revenue growth should be 15%", output {{"revenue_growth_rates": [0.15, 0.13, 0.11, 0.09, 0.07]}} (decay from stated rate)
- If "WACC is 12%", output {{"wacc": 0.12}}
- If no numeric overrides found, output {{}}
- Do NOT invent numbers the analyst didn't state

Respond with ONLY valid JSON:"""


def _parse_numeric_overrides(
    valuation_beliefs: List[AnalystSource],
    llm_func: Callable[..., Any],
    api_key: str,
    model: str,
) -> Dict:
    """Use LLM to extract numeric DCF overrides from valuation_view beliefs.

    The LLM's role here is strictly parsing: mapping natural language to field
    names and values. The analyst's numbers are authoritative.
    """
    if not valuation_beliefs:
        return {}

    beliefs_text = "\n".join(
        f"- {src.belief_content}" for src in valuation_beliefs
    )

    prompt = NUMERIC_PARSE_PROMPT.format(beliefs_text=beliefs_text)

    try:
        response = llm_func(
            api_key=api_key,
            model=model,
            system_prompt="You are a precise data parser. Respond only with valid JSON.",
            user_prompt=prompt,
            temperature=0.0,
            max_tokens=500,
        )

        if not response.success:
            logger.warning(f"Numeric override parsing failed: {response.error}")
            return {}

        text = response.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        overrides = json.loads(text)

        # Filter to only known fields
        filtered = {
            k: v for k, v in overrides.items()
            if k in OVERRIDABLE_DCF_FIELDS
        }

        if filtered:
            logger.info(f"Parsed numeric overrides: {list(filtered.keys())}")

        return filtered

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to parse numeric overrides: {e}")
        return {}


def _format_qualitative_directives(
    sources: List[AnalystSource],
) -> str:
    """Format non-numeric analyst beliefs as hard directives for agent prompts.

    These are framed as non-negotiable: the agent must treat them as ground
    truth and rebuild its analysis around them.
    """
    if not sources:
        return ""

    lines = [
        "",
        "ANALYST DIRECTIVES (non-negotiable, override any prior LLM assessment):",
        "The analyst's views below are established facts. Your analysis MUST",
        "be consistent with them. Where they contradict your initial assessment,",
        "the analyst is correct and you must explain why.",
        "",
    ]
    for src in sources:
        type_label = src.insight_type.upper().replace("_", " ")
        lines.append(f'- [{type_label}] "{src.belief_content}"')

    return "\n".join(lines)


def _compute_dirty_stages(
    sources: List[AnalystSource],
) -> Set[str]:
    """Determine which pipeline stages need re-running based on beliefs.

    Applies cascading: if strategy is dirty, bull/bear and recommendation
    are also dirty. Conviction is always dirty when any belief exists.
    """
    dirty = set()

    for src in sources:
        # Add stages for this insight type
        type_stages = INSIGHT_TYPE_TO_DIRTY_STAGES.get(src.insight_type, set())
        dirty.update(type_stages)

        # Add stage for target section
        section_stage = SECTION_TO_STAGE.get(src.section)
        if section_stage:
            dirty.add(section_stage)

    # Apply cascades
    changed = True
    while changed:
        changed = False
        for stage in list(dirty):
            cascaded = STAGE_CASCADE.get(stage, set())
            new_stages = cascaded - dirty
            if new_stages:
                dirty.update(new_stages)
                changed = True

    # Conviction is always re-scored when there are any beliefs
    if sources:
        dirty.add("conviction")

    return dirty


def parse_analyst_overrides(
    beliefs: List[Belief],
    analyst_sources: List[AnalystSource],
    llm_func: Callable[..., Any],
    api_key: str,
    model: str,
) -> AnalysisOverrides:
    """Parse all analyst beliefs into actionable overrides for the pipeline.

    This is the main entry point. It produces:
    - dcf_overrides: dict of field_name -> value for hard DCF assumption injection
    - qualitative_directives: formatted string for agent prompt injection
    - dirty_stages: set of pipeline stage names that need re-running
    - warnings: list of issues (e.g., out-of-bounds values)

    Args:
        beliefs: All beliefs from the belief graph
        analyst_sources: All analyst sources (have insight_type)
        llm_func: LLM call function for numeric parsing
        api_key: API key
        model: Model to use for parsing

    Returns:
        AnalysisOverrides with all parsed data
    """
    if not analyst_sources:
        return AnalysisOverrides()

    # Separate valuation views (need numeric parsing) from qualitative beliefs
    valuation_sources = [
        s for s in analyst_sources if s.insight_type == "valuation_view"
    ]
    qualitative_sources = [
        s for s in analyst_sources if s.insight_type != "valuation_view"
    ]

    # Parse numeric overrides from valuation beliefs
    dcf_overrides = _parse_numeric_overrides(
        valuation_sources, llm_func, api_key, model
    )

    # Format qualitative directives (all non-valuation beliefs)
    # Also include valuation beliefs in qualitative context so agents
    # understand the full picture
    qualitative_directives = _format_qualitative_directives(analyst_sources)

    # Determine dirty stages
    dirty_stages = _compute_dirty_stages(analyst_sources)

    # Validate DCF overrides against bounds
    warnings = _validate_dcf_overrides(dcf_overrides)

    return AnalysisOverrides(
        dcf_overrides=dcf_overrides,
        qualitative_directives=qualitative_directives,
        dirty_stages=dirty_stages,
        warnings=warnings,
    )


def _validate_dcf_overrides(overrides: Dict) -> List[str]:
    """Validate DCF overrides against constants bounds. Warn but do not clamp.

    The analyst's number is authoritative. We warn if it's outside typical
    bounds so the analyst can reconsider, but we do not silently modify it.
    """
    from src_george_researcher.valuation.constants import (
        MAX_GROWTH_RATE, MIN_FCF_MARGIN, MAX_FCF_MARGIN,
        MIN_WACC, MAX_WACC, MIN_TERMINAL_GROWTH,
    )

    warnings = []

    if "wacc" in overrides:
        w = overrides["wacc"]
        if w < MIN_WACC or w > MAX_WACC:
            warnings.append(
                f"WACC override {w*100:.1f}% is outside typical bounds "
                f"({MIN_WACC*100:.0f}%-{MAX_WACC*100:.0f}%). Proceeding with analyst's value."
            )

    if "terminal_growth_rate" in overrides:
        tgr = overrides["terminal_growth_rate"]
        if tgr < MIN_TERMINAL_GROWTH:
            warnings.append(
                f"Terminal growth {tgr*100:.1f}% is below floor ({MIN_TERMINAL_GROWTH*100:.1f}%). "
                f"Proceeding with analyst's value."
            )

    if "revenue_growth_rates" in overrides:
        for i, rate in enumerate(overrides["revenue_growth_rates"]):
            if abs(rate) > MAX_GROWTH_RATE:
                warnings.append(
                    f"Revenue growth year {i+1} ({rate*100:.1f}%) exceeds "
                    f"+/-{MAX_GROWTH_RATE*100:.0f}% bound. Proceeding with analyst's value."
                )

    if "fcf_margin" in overrides:
        m = overrides["fcf_margin"]
        if m < MIN_FCF_MARGIN or m > MAX_FCF_MARGIN:
            warnings.append(
                f"FCF margin override {m*100:.1f}% is outside bounds "
                f"({MIN_FCF_MARGIN*100:.0f}%-{MAX_FCF_MARGIN*100:.0f}%). "
                f"Proceeding with analyst's value."
            )

    for w in warnings:
        logger.warning(w)

    return warnings
