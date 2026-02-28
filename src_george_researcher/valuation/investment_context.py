"""
Structured investment context extraction.

Runs a single LLM call to produce structured, actionable components for IC
presentation decks: thesis pillars, catalyst timeline, quantified risks,
monitoring KPIs, and market-missing narrative.

Single entry point: extract_investment_context() -> InvestmentContext
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src_george_researcher.llm import call_llm
from src_george_researcher.prompts import STRUCTURED_THESIS_SYSTEM

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(frozen=True)
class ThesisPillar:
    number: int
    statement: str
    falsifiable_by: str
    evidence: str


@dataclass(frozen=True)
class Catalyst:
    event: str
    expected_date: str
    expected_impact: str
    pillar_number: Optional[int] = None


@dataclass(frozen=True)
class QuantifiedRisk:
    risk: str
    metric: str
    sensitivity: str
    current_value: str
    bear_scenario: str


@dataclass(frozen=True)
class MonitoringKPI:
    kpi: str
    current_value: str
    bull_threshold: str
    bear_threshold: str
    frequency: str = "Quarterly"


@dataclass(frozen=True)
class InvestmentContext:
    """Structured investment context for IC decks and professional reports."""
    thesis_pillars: tuple[ThesisPillar, ...] = ()
    market_missing: str = ""
    catalysts: tuple[Catalyst, ...] = ()
    quantified_risks: tuple[QuantifiedRisk, ...] = ()
    monitoring_kpis: tuple[MonitoringKPI, ...] = ()
    risk_reward_ratio: str = ""
    risk_reward_explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thesis_pillars": [
                {"number": p.number, "statement": p.statement,
                 "falsifiable_by": p.falsifiable_by, "evidence": p.evidence}
                for p in self.thesis_pillars
            ],
            "market_missing": self.market_missing,
            "catalysts": [
                {"event": c.event, "expected_date": c.expected_date,
                 "expected_impact": c.expected_impact, "pillar_number": c.pillar_number}
                for c in self.catalysts
            ],
            "quantified_risks": [
                {"risk": r.risk, "metric": r.metric, "sensitivity": r.sensitivity,
                 "current_value": r.current_value, "bear_scenario": r.bear_scenario}
                for r in self.quantified_risks
            ],
            "monitoring_kpis": [
                {"kpi": k.kpi, "current_value": k.current_value,
                 "bull_threshold": k.bull_threshold, "bear_threshold": k.bear_threshold,
                 "frequency": k.frequency}
                for k in self.monitoring_kpis
            ],
            "risk_reward_ratio": self.risk_reward_ratio,
            "risk_reward_explanation": self.risk_reward_explanation,
        }


# =============================================================================
# Parsing
# =============================================================================

def _parse_investment_context(raw: Dict[str, Any]) -> InvestmentContext:
    """Parse raw JSON dict into frozen InvestmentContext dataclass."""
    pillars = tuple(
        ThesisPillar(
            number=p.get("number", i + 1),
            statement=p.get("statement", ""),
            falsifiable_by=p.get("falsifiable_by", ""),
            evidence=p.get("evidence", ""),
        )
        for i, p in enumerate(raw.get("thesis_pillars", []))
        if p.get("statement")
    )

    catalysts = tuple(
        Catalyst(
            event=c.get("event", ""),
            expected_date=c.get("expected_date", ""),
            expected_impact=c.get("expected_impact", ""),
            pillar_number=c.get("pillar_number"),
        )
        for c in raw.get("catalysts", [])
        if c.get("event")
    )

    risks = tuple(
        QuantifiedRisk(
            risk=r.get("risk", ""),
            metric=r.get("metric", ""),
            sensitivity=r.get("sensitivity", ""),
            current_value=r.get("current_value", ""),
            bear_scenario=r.get("bear_scenario", ""),
        )
        for r in raw.get("quantified_risks", [])
        if r.get("risk")
    )

    kpis = tuple(
        MonitoringKPI(
            kpi=k.get("kpi", ""),
            current_value=k.get("current_value", ""),
            bull_threshold=k.get("bull_threshold", ""),
            bear_threshold=k.get("bear_threshold", ""),
            frequency=k.get("frequency", "Quarterly"),
        )
        for k in raw.get("monitoring_kpis", [])
        if k.get("kpi")
    )

    return InvestmentContext(
        thesis_pillars=pillars,
        market_missing=raw.get("market_missing", ""),
        catalysts=catalysts,
        quantified_risks=risks,
        monitoring_kpis=kpis,
        risk_reward_ratio=raw.get("risk_reward_ratio", ""),
        risk_reward_explanation=raw.get("risk_reward_explanation", ""),
    )


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` wrapper
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])
    return json.loads(text)


# =============================================================================
# Entry Point
# =============================================================================

def extract_investment_context(
    api_key: str,
    model: str,
    ticker: str,
    fundamentals: str,
    bull_thesis: str,
    bear_thesis: str,
    dcf_summary: str,
    scenario_summary: str,
    conviction_summary: str,
    strategy: str = "",
    moat: str = "",
) -> InvestmentContext:
    """
    Extract structured investment context via a single LLM call.

    Designed to run in parallel with recommendation synthesis since it
    consumes the same inputs but produces structured JSON rather than prose.

    Args:
        api_key: OpenRouter API key.
        model: LLM model identifier.
        ticker: Stock ticker symbol.
        fundamentals: Fundamentals analysis prose.
        bull_thesis: Bull case prose.
        bear_thesis: Bear case prose.
        dcf_summary: DCF analysis prose or summary.
        scenario_summary: Scenario analysis prose.
        conviction_summary: Conviction score summary string.
        strategy: Strategy analysis prose.
        moat: Moat analysis prose.

    Returns:
        InvestmentContext with all structured components populated.
        Returns empty InvestmentContext on failure (never raises).
    """
    # Truncate inputs to stay within context budget
    max_section = 1500

    user_prompt = f"""Analyze {ticker} and produce structured investment context.

## Conviction Score
{conviction_summary}

## Fundamentals
{fundamentals[:max_section]}

## Bull Case
{bull_thesis[:max_section]}

## Bear Case
{bear_thesis[:max_section]}

## DCF Valuation
{dcf_summary[:max_section]}

## Scenario Analysis (Bull/Base/Bear)
{scenario_summary[:max_section]}

## Strategy
{strategy[:max_section]}

## Competitive Moat
{moat[:max_section]}

Produce the structured JSON for {ticker}."""

    try:
        response = call_llm(
            api_key=api_key,
            model=model,
            system_prompt=STRUCTURED_THESIS_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.15,
        )

        if not response.success:
            logger.warning("Investment context LLM call failed: %s", response.error)
            return InvestmentContext()

        raw = _extract_json(response.content)
        return _parse_investment_context(raw)

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to parse investment context JSON: %s", e)
        return InvestmentContext()
    except Exception as e:
        logger.warning("Investment context extraction failed: %s", e)
        return InvestmentContext()
