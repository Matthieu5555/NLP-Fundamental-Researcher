"""
Earnings Normalization.

Identifies one-time items in financial statements and produces normalized
EBITDA and NOPAT figures that feed into the DCF base case.

Uses a focused LLM call to flag non-recurring items from the financial data,
then applies pure-math adjustments.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src_george_researcher.llm import call_llm

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EarningsAdjustment:
    """A single adjustment to normalize earnings."""
    description: str
    category: str       # restructuring, impairment, litigation, gain_on_sale, tax_one_time, sbc, other
    amount: float       # Positive = add back (expense), Negative = subtract (one-time gain)
    confidence: float   # 0-1, how confident we are this is non-recurring
    year: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "category": self.category,
            "amount": self.amount,
            "confidence": self.confidence,
            "year": self.year,
        }


@dataclass(frozen=True)
class NormalizedEarnings:
    """Normalized earnings with adjustments list."""
    reported_net_income: float
    reported_ebitda: float
    reported_operating_income: float
    adjustments: List[EarningsAdjustment]
    normalized_ebitda: float
    normalized_operating_income: float
    normalized_nopat: float          # For ROIC calculation
    effective_tax_rate: float
    total_adjustment: float
    rationale: str = ""

    def to_dict(self) -> Dict:
        return {
            "reported_net_income": self.reported_net_income,
            "reported_ebitda": self.reported_ebitda,
            "reported_operating_income": self.reported_operating_income,
            "adjustments": [a.to_dict() for a in self.adjustments],
            "normalized_ebitda": self.normalized_ebitda,
            "normalized_operating_income": self.normalized_operating_income,
            "normalized_nopat": self.normalized_nopat,
            "effective_tax_rate": self.effective_tax_rate,
            "total_adjustment": self.total_adjustment,
            "rationale": self.rationale,
        }


NORMALIZATION_SYSTEM = """You are a senior equity research analyst normalizing earnings.

Given financial statement data, identify non-recurring or one-time items that should be
adjusted to arrive at normalized/sustainable earnings.

Categories of adjustments:
- restructuring: Restructuring charges, severance, facility closures
- impairment: Goodwill/asset impairment charges
- litigation: Legal settlements, regulatory fines
- gain_on_sale: Gains/losses on asset sales, divestitures
- tax_one_time: One-time tax benefits/charges (e.g., tax reform, deferred tax valuation)
- sbc: Excessive stock-based compensation beyond industry norms (optional, flag only if extreme)
- other: Any other clearly non-recurring item

Rules:
- Only flag items you can identify from the data with reasonable confidence
- Use positive amounts for expenses to add back (they inflated costs)
- Use negative amounts for one-time gains to subtract (they inflated income)
- Confidence should be 0.5-1.0: lower for items that might be recurring
- If the financial data looks clean with no obvious one-time items, return an empty array
- Do NOT adjust for normal business operations, seasonal effects, or cyclicality

Respond with ONLY a JSON array of adjustments:
[{"description": "...", "category": "...", "amount": ..., "confidence": ...}]

Return [] if no adjustments are needed."""


def normalize_earnings(
    operating_income: float,
    net_income: float,
    depreciation_amortization: float,
    interest_expense: float,
    tax_rate: float,
    financial_summary: str,
    api_key: str,
    model: str,
    revenue: Optional[float] = None,
) -> NormalizedEarnings:
    """
    Normalize earnings by identifying and adjusting for one-time items.

    Args:
        operating_income: Reported EBIT.
        net_income: Reported net income.
        depreciation_amortization: D&A for EBITDA calculation.
        interest_expense: Interest expense.
        tax_rate: Effective tax rate (decimal).
        financial_summary: Text summary of financials for LLM context.
        api_key: LLM API key.
        model: LLM model ID.
        revenue: Revenue for context.

    Returns:
        NormalizedEarnings with adjustments applied.
    """
    reported_ebitda = operating_income + depreciation_amortization

    user_prompt = f"""Analyze these financial results for non-recurring items:

Revenue: ${revenue/1e6:,.0f}M
Operating Income (EBIT): ${operating_income/1e6:,.0f}M
EBITDA: ${reported_ebitda/1e6:,.0f}M
Net Income: ${net_income/1e6:,.0f}M
D&A: ${depreciation_amortization/1e6:,.0f}M
Interest Expense: ${interest_expense/1e6:,.0f}M
Effective Tax Rate: {tax_rate*100:.0f}%

Financial context:
{financial_summary[:3000]}

Identify any non-recurring items that should be adjusted.""" if revenue else f"""Analyze these financial results for non-recurring items:

Operating Income (EBIT): ${operating_income/1e6:,.0f}M
EBITDA: ${reported_ebitda/1e6:,.0f}M
Net Income: ${net_income/1e6:,.0f}M

Financial context:
{financial_summary[:3000]}

Identify any non-recurring items that should be adjusted."""

    response = call_llm(
        api_key=api_key,
        model=model,
        system_prompt=NORMALIZATION_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.0,
        max_tokens=1024,
    )

    adjustments = []
    if response.success:
        adjustments = _parse_adjustments(response.content)

    return _build_normalized_result(
        operating_income=operating_income,
        net_income=net_income,
        reported_ebitda=reported_ebitda,
        adjustments=adjustments,
        tax_rate=tax_rate,
    )


def normalize_earnings_from_statements(
    statements: List[Dict],
    financial_summary: str,
    api_key: str,
    model: str,
) -> Optional[NormalizedEarnings]:
    """
    Convenience wrapper that accepts raw statement data.

    Args:
        statements: List of financial statement dicts (most recent first).
        financial_summary: Text summary for LLM context.
        api_key: LLM API key.
        model: LLM model ID.

    Returns:
        NormalizedEarnings for the most recent period, or None if insufficient data.
    """
    if not statements:
        return None

    stmt = statements[0]
    operating_income = stmt.get("operating_income")
    net_income = stmt.get("net_income")
    da = stmt.get("depreciation_and_amortization", 0) or 0
    interest = stmt.get("interest_expense", 0) or 0

    if operating_income is None or net_income is None:
        return None

    # Compute effective tax rate
    pretax = operating_income - interest
    if pretax > 0 and net_income is not None:
        tax_rate = 1.0 - (net_income / pretax)
        tax_rate = max(0.0, min(0.50, tax_rate))
    else:
        tax_rate = 0.21

    return normalize_earnings(
        operating_income=operating_income,
        net_income=net_income,
        depreciation_amortization=da,
        interest_expense=interest,
        tax_rate=tax_rate,
        financial_summary=financial_summary,
        api_key=api_key,
        model=model,
        revenue=stmt.get("revenue"),
    )


def _parse_adjustments(content: str) -> List[EarningsAdjustment]:
    """Parse LLM JSON response into EarningsAdjustment list."""
    text = content.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return []

        adjustments = []
        valid_categories = {"restructuring", "impairment", "litigation", "gain_on_sale", "tax_one_time", "sbc", "other"}

        for item in data:
            category = item.get("category", "other")
            if category not in valid_categories:
                category = "other"

            amount = item.get("amount")
            if amount is None or not isinstance(amount, (int, float)):
                continue

            confidence = item.get("confidence", 0.7)
            confidence = max(0.0, min(1.0, float(confidence)))

            adjustments.append(EarningsAdjustment(
                description=str(item.get("description", "")),
                category=category,
                amount=float(amount),
                confidence=confidence,
            ))

        return adjustments

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning("Failed to parse normalization response: %s", e)
        return []


def _build_normalized_result(
    operating_income: float,
    net_income: float,
    reported_ebitda: float,
    adjustments: List[EarningsAdjustment],
    tax_rate: float,
) -> NormalizedEarnings:
    """Build NormalizedEarnings from reported figures and adjustments."""
    # Weight adjustments by confidence
    total_adj = sum(a.amount * a.confidence for a in adjustments)

    normalized_ebitda = reported_ebitda + total_adj
    normalized_oi = operating_income + total_adj
    normalized_nopat = normalized_oi * (1 - tax_rate)

    if adjustments:
        adj_descriptions = [f"{a.description} ({a.category}: ${a.amount/1e6:+,.0f}M)" for a in adjustments]
        rationale = f"Normalized with {len(adjustments)} adjustment(s): {'; '.join(adj_descriptions)}"
    else:
        rationale = "No material one-time items identified"

    return NormalizedEarnings(
        reported_net_income=net_income,
        reported_ebitda=reported_ebitda,
        reported_operating_income=operating_income,
        adjustments=adjustments,
        normalized_ebitda=normalized_ebitda,
        normalized_operating_income=normalized_oi,
        normalized_nopat=normalized_nopat,
        effective_tax_rate=tax_rate,
        total_adjustment=total_adj,
        rationale=rationale,
    )
