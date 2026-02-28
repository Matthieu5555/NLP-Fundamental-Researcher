"""
Dividend Discount Model (DDM).

Implements Gordon Growth Model and H-Model for dividend-paying companies.
Triggered when dividend_yield > 1% and payout_ratio > 20%.

Pure math — no LLM calls.
"""

from dataclasses import dataclass
from typing import Optional


# Minimum thresholds to trigger DDM
MIN_DIVIDEND_YIELD = 0.01       # 1%
MIN_PAYOUT_RATIO = 0.20         # 20%
MAX_PAYOUT_RATIO = 1.50         # Cap at 150% (some companies temporarily over-distribute)
MAX_SUSTAINABLE_GROWTH = 0.15   # 15% — DDM unreliable above this


@dataclass(frozen=True)
class DDMResult:
    """Result of dividend discount model valuation."""
    gordon_growth_value: Optional[float]   # Simple perpetuity model
    h_model_value: Optional[float]         # Two-stage with linear fade
    blended_value: Optional[float]         # Weighted average
    cost_of_equity: float                  # Ke used
    current_dividend: float                # D0
    implied_dividend_next: float           # D1
    long_term_growth: float                # Terminal growth rate
    short_term_growth: Optional[float]     # Near-term growth (H-model)
    payout_ratio: float
    is_applicable: bool                    # Whether DDM is meaningful for this company
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "gordon_growth_value": self.gordon_growth_value,
            "h_model_value": self.h_model_value,
            "blended_value": self.blended_value,
            "cost_of_equity": self.cost_of_equity,
            "current_dividend": self.current_dividend,
            "implied_dividend_next": self.implied_dividend_next,
            "long_term_growth": self.long_term_growth,
            "short_term_growth": self.short_term_growth,
            "payout_ratio": self.payout_ratio,
            "is_applicable": self.is_applicable,
            "rationale": self.rationale,
        }


def run_ddm(
    current_price: float,
    dividend_per_share: float,
    cost_of_equity: float,
    long_term_growth: float,
    payout_ratio: float,
    earnings_growth_short_term: Optional[float] = None,
    h_model_half_life_years: int = 5,
) -> DDMResult:
    """
    Run dividend discount model valuation.

    Args:
        current_price: Current stock price.
        dividend_per_share: Current annual dividend per share (D0).
        cost_of_equity: Ke from CAPM (decimal, e.g. 0.10 for 10%).
        long_term_growth: Sustainable long-term dividend growth rate.
        payout_ratio: Dividends / Net Income.
        earnings_growth_short_term: Near-term earnings growth for H-model.
        h_model_half_life_years: Years for short-term growth to fade to long-term.

    Returns:
        DDMResult with valuations and applicability assessment.
    """
    # Check applicability
    dividend_yield = dividend_per_share / current_price if current_price > 0 else 0
    if dividend_per_share <= 0 or dividend_yield < MIN_DIVIDEND_YIELD:
        return DDMResult(
            gordon_growth_value=None,
            h_model_value=None,
            blended_value=None,
            cost_of_equity=cost_of_equity,
            current_dividend=dividend_per_share,
            implied_dividend_next=0,
            long_term_growth=long_term_growth,
            short_term_growth=earnings_growth_short_term,
            payout_ratio=payout_ratio,
            is_applicable=False,
            rationale=f"DDM not applicable: dividend yield {dividend_yield*100:.1f}% below {MIN_DIVIDEND_YIELD*100:.0f}% threshold",
        )

    if payout_ratio < MIN_PAYOUT_RATIO:
        return DDMResult(
            gordon_growth_value=None,
            h_model_value=None,
            blended_value=None,
            cost_of_equity=cost_of_equity,
            current_dividend=dividend_per_share,
            implied_dividend_next=0,
            long_term_growth=long_term_growth,
            short_term_growth=earnings_growth_short_term,
            payout_ratio=payout_ratio,
            is_applicable=False,
            rationale=f"DDM not applicable: payout ratio {payout_ratio*100:.0f}% below {MIN_PAYOUT_RATIO*100:.0f}% threshold",
        )

    # Constrain growth rates
    long_term_growth = min(long_term_growth, cost_of_equity - 0.01)
    long_term_growth = max(long_term_growth, 0.0)

    # Sustainable growth rate check: g = ROE * (1 - payout)
    # If payout is very high, long-term growth should be lower
    capped_payout = min(payout_ratio, MAX_PAYOUT_RATIO)
    sustainable_g = min(long_term_growth, MAX_SUSTAINABLE_GROWTH)

    # D1 = D0 * (1 + g)
    d1 = dividend_per_share * (1 + sustainable_g)

    # Gordon Growth Model: V = D1 / (Ke - g)
    gordon_denominator = cost_of_equity - sustainable_g
    gordon_value = None
    if gordon_denominator > 0.005:  # Require at least 50bps spread
        gordon_value = d1 / gordon_denominator

    # H-Model: accounts for near-term higher growth fading to long-term
    h_model_value = None
    short_term_g = earnings_growth_short_term
    if short_term_g is not None and short_term_g > sustainable_g and gordon_denominator > 0.005:
        short_term_g = min(short_term_g, MAX_SUSTAINABLE_GROWTH)
        h = h_model_half_life_years / 2.0
        # V = D0 * (1 + gL) / (Ke - gL) + D0 * H * (gS - gL) / (Ke - gL)
        base_value = dividend_per_share * (1 + sustainable_g) / gordon_denominator
        growth_premium = dividend_per_share * h * (short_term_g - sustainable_g) / gordon_denominator
        h_model_value = base_value + growth_premium

    # Blended value: prefer H-model when available, else Gordon
    blended = None
    if h_model_value is not None and gordon_value is not None:
        blended = 0.6 * h_model_value + 0.4 * gordon_value
    elif h_model_value is not None:
        blended = h_model_value
    elif gordon_value is not None:
        blended = gordon_value

    rationale_parts = [f"Ke={cost_of_equity*100:.1f}%", f"gL={sustainable_g*100:.1f}%"]
    if short_term_g is not None:
        rationale_parts.append(f"gS={short_term_g*100:.1f}%")
    rationale_parts.append(f"D0=${dividend_per_share:.2f}")
    rationale_parts.append(f"payout={capped_payout*100:.0f}%")

    return DDMResult(
        gordon_growth_value=gordon_value,
        h_model_value=h_model_value,
        blended_value=blended,
        cost_of_equity=cost_of_equity,
        current_dividend=dividend_per_share,
        implied_dividend_next=d1,
        long_term_growth=sustainable_g,
        short_term_growth=short_term_g,
        payout_ratio=capped_payout,
        is_applicable=True,
        rationale=f"DDM ({', '.join(rationale_parts)})",
    )


def format_ddm_markdown(result: DDMResult) -> str:
    """Format DDM results as markdown."""
    if not result.is_applicable:
        return f"**DDM**: {result.rationale}"

    lines = [
        "**Dividend Discount Model**\n",
        f"- Current Dividend (D0): ${result.current_dividend:.2f}",
        f"- Next Year Dividend (D1): ${result.implied_dividend_next:.2f}",
        f"- Cost of Equity (Ke): {result.cost_of_equity*100:.1f}%",
        f"- Long-term Growth: {result.long_term_growth*100:.1f}%",
        f"- Payout Ratio: {result.payout_ratio*100:.0f}%",
    ]

    if result.short_term_growth is not None:
        lines.append(f"- Short-term Growth: {result.short_term_growth*100:.1f}%")

    lines.append("")

    if result.gordon_growth_value is not None:
        lines.append(f"**Gordon Growth Model**: ${result.gordon_growth_value:.2f}")

    if result.h_model_value is not None:
        lines.append(f"**H-Model**: ${result.h_model_value:.2f}")

    if result.blended_value is not None:
        lines.append(f"**Blended DDM Value**: ${result.blended_value:.2f}")

    return "\n".join(lines)
