"""
Conviction Scoring - Decomposed 0-100 scoring with LLM structured output.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from src_george_researcher.analysis.shared.parsing import extract_json_from_llm_response
from src_george_researcher.analysis_agents import AnalysisResult
from src_george_researcher.data_fetchers.stock_data import StockInfo
from src_george_researcher.llm import call_llm
from src_george_researcher.prompts import CONVICTION_SYSTEM
from src_george_researcher.valuation.dcf_engine import DCFResult
from src_george_researcher.valuation.comp_table import CompTableResult
from src_george_researcher.valuation.exceptions import AssumptionParseError

# Max characters sent to LLM for each context section.
# Higher values give more context but increase token cost.
MAX_FUNDAMENTALS_CHARS = 1500
MAX_SECTION_CHARS = 800
MAX_SENTIMENT_CHARS = 500

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConvictionCategory:
    """A single conviction category with score and evidence."""
    name: str
    score: int
    evidence: str

    def to_dict(self) -> Dict:
        return {"name": self.name, "score": self.score, "evidence": self.evidence}


@dataclass(frozen=True)
class ConvictionResult:
    """Complete conviction scoring result."""
    overall_score: int
    recommendation: str  # "BUY" or "SELL"
    confidence: int  # 0-100 confidence level
    categories: List[ConvictionCategory]
    summary: str

    def to_dict(self) -> Dict:
        return {
            "overall_score": self.overall_score,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "categories": [c.to_dict() for c in self.categories],
            "summary": self.summary,
        }


def _parse_conviction(response_text: str) -> Optional[ConvictionResult]:
    """Parse LLM JSON response into ConvictionResult."""
    try:
        data = extract_json_from_llm_response(response_text)

        overall = max(0, min(100, data.get("overall_score", 50)))
        # No HOLD — derive recommendation from score
        recommendation = "BUY" if overall > 50 else "SELL"
        # Confidence is a separate dimension: how reliable is our analysis
        confidence = max(0, min(100, data.get("confidence", 50)))

        categories = []
        for cat in data.get("categories", []):
            categories.append(ConvictionCategory(
                name=cat.get("name", "Unknown"),
                score=max(0, min(100, cat.get("score", 50))),
                evidence=cat.get("evidence", ""),
            ))

        return ConvictionResult(
            overall_score=overall,
            recommendation=recommendation,
            confidence=confidence,
            categories=categories,
            summary=data.get("summary", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise AssumptionParseError(f"Failed to parse conviction response: {e}") from e


def format_conviction_markdown(result: ConvictionResult) -> str:
    """Format conviction result as markdown."""
    lines = [
        f"**{result.recommendation} at {result.confidence}% confidence** (Score: {result.overall_score}/100)\n",
        f"{result.summary}\n",
        "**Category Scores**\n",
        "| Category | Score | Evidence |",
        "|---|---|---|",
    ]

    for cat in result.categories:
        lines.append(f"| {cat.name} | {cat.score}/100 | {cat.evidence} |")

    return "\n".join(lines)


def _build_conviction_context(
    stock_info: StockInfo,
    fundamentals: str,
    technicals: str,
    bull_thesis: str,
    bear_thesis: str,
    dcf_result: Optional[DCFResult],
    sentiment_report: str,
) -> str:
    """Build the LLM prompt with analysis context for conviction scoring."""
    context_parts = [
        f"**Company**: {stock_info.name} ({stock_info.symbol})",
        f"**Sector**: {stock_info.sector or 'Unknown'}",
        f"**Current Price**: ${stock_info.current_price:.2f}" if stock_info.current_price else "",
    ]

    if dcf_result:
        context_parts.append(
            f"\n**DCF Fair Value**: ${dcf_result.fair_value_per_share:.2f} "
            f"({'Upside' if dcf_result.upside_downside_pct > 0 else 'Downside'}: "
            f"{abs(dcf_result.upside_downside_pct):.1f}%)"
        )

    if fundamentals:
        context_parts.append(f"\n**Fundamentals Summary**:\n{fundamentals[:MAX_FUNDAMENTALS_CHARS]}")

    if technicals:
        context_parts.append(f"\n**Technicals Summary**:\n{technicals[:MAX_SECTION_CHARS]}")

    if bull_thesis:
        context_parts.append(f"\n**Bull Thesis**:\n{bull_thesis[:MAX_SECTION_CHARS]}")

    if bear_thesis:
        context_parts.append(f"\n**Bear Thesis**:\n{bear_thesis[:MAX_SECTION_CHARS]}")

    if sentiment_report:
        context_parts.append(f"\n**Sentiment**:\n{sentiment_report[:MAX_SENTIMENT_CHARS]}")

    return "\n".join(context_parts) + "\n\nScore the conviction for this investment."


def score_conviction(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    fundamentals: str = "",
    technicals: str = "",
    bull_thesis: str = "",
    bear_thesis: str = "",
    dcf_result: Optional[DCFResult] = None,
    comp_result: Optional[CompTableResult] = None,
    sentiment_report: str = "",
) -> tuple[Optional[ConvictionResult], AnalysisResult]:
    """
    Score investment conviction across multiple dimensions.

    Returns:
        (ConvictionResult or None, AnalysisResult with narrative)
    """
    user_prompt = _build_conviction_context(
        stock_info, fundamentals, technicals, bull_thesis,
        bear_thesis, dcf_result, sentiment_report,
    )

    response = call_llm(
        api_key=api_key,
        model=model,
        system_prompt=CONVICTION_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.1,
    )

    conviction_result = None
    if response.success:
        try:
            conviction_result = _parse_conviction(response.content)
        except AssumptionParseError as e:
            logger.warning(str(e))

    if conviction_result is None:
        # Default fallback
        conviction_result = ConvictionResult(
            overall_score=50,
            recommendation="SELL",
            confidence=50,
            categories=[
                ConvictionCategory("Valuation", 50, "Insufficient data for scoring."),
                ConvictionCategory("Fundamentals", 50, "Insufficient data for scoring."),
                ConvictionCategory("Technicals", 50, "Insufficient data for scoring."),
                ConvictionCategory("Sentiment", 50, "Insufficient data for scoring."),
            ],
            summary="Conviction scoring could not be fully determined. Defaulting to SELL at 50% confidence.",
        )

    content = format_conviction_markdown(conviction_result)

    analysis_result = AnalysisResult(
        section="Conviction Score",
        content=content,
        tokens_used=response.tokens_used,
        success=True,
        cost_usd=response.cost_usd,
    )

    return conviction_result, analysis_result
