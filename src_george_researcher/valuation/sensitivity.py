"""
Sensitivity Analysis grids.

Two grids, pure math, no LLM calls:
1. WACC x Terminal Growth Rate — classic discount-rate sensitivity
2. Revenue Growth x Operating Margin — operating leverage sensitivity (WACC held constant)
"""

from dataclasses import dataclass
from typing import Dict, List

from src_george_researcher.analysis_agents import AnalysisResult
from src_george_researcher.valuation.dcf_engine import DCFAssumptions, DCFResult, calculate_dcf
from src_george_researcher.valuation.constants import (
    MIN_WACC, MIN_TERMINAL_GROWTH,
    SENSITIVITY_WACC_STEP, SENSITIVITY_TGR_STEP,
    SENSITIVITY_GROWTH_STEP, SENSITIVITY_MARGIN_STEP,
)

# Step sizes derived from constants — large = full step, small = half step
WACC_STEP_LARGE = SENSITIVITY_WACC_STEP * 2
WACC_STEP_SMALL = SENSITIVITY_WACC_STEP
TGR_STEP_LARGE = SENSITIVITY_TGR_STEP * 2
TGR_STEP_SMALL = SENSITIVITY_TGR_STEP
GROWTH_STEP_LARGE = SENSITIVITY_GROWTH_STEP
GROWTH_STEP_SMALL = SENSITIVITY_GROWTH_STEP / 2
MARGIN_STEP_LARGE = SENSITIVITY_MARGIN_STEP
MARGIN_STEP_SMALL = SENSITIVITY_MARGIN_STEP / 2


@dataclass(frozen=True)
class SensitivityResult:
    """5x5 sensitivity grid of fair values."""
    wacc_values: List[float]
    terminal_growth_values: List[float]
    fair_value_grid: List[List[float]]  # [wacc_idx][tgr_idx]
    base_wacc_idx: int
    base_tgr_idx: int
    current_price: float

    def to_dict(self) -> Dict:
        return {
            "wacc_values": self.wacc_values,
            "terminal_growth_values": self.terminal_growth_values,
            "fair_value_grid": self.fair_value_grid,
            "base_wacc_idx": self.base_wacc_idx,
            "base_tgr_idx": self.base_tgr_idx,
            "current_price": self.current_price,
        }


@dataclass(frozen=True)
class GrowthMarginSensitivityResult:
    """5x5 Revenue Growth x Operating Margin sensitivity grid."""
    growth_values: List[float]       # average revenue growth rates (rows)
    margin_values: List[float]       # operating margin / FCF margin (columns)
    fair_value_grid: List[List[float]]
    base_growth_idx: int
    base_margin_idx: int
    current_price: float

    def to_dict(self) -> Dict:
        return {
            "growth_values": self.growth_values,
            "margin_values": self.margin_values,
            "fair_value_grid": self.fair_value_grid,
            "base_growth_idx": self.base_growth_idx,
            "base_margin_idx": self.base_margin_idx,
            "current_price": self.current_price,
        }


def _clone_assumptions_wacc_tgr(base: DCFAssumptions, wacc: float, tgr: float) -> DCFAssumptions:
    """Clone assumptions with different WACC and terminal growth rate."""
    kwargs = {
        "revenue_growth_rates": list(base.revenue_growth_rates),
        "wacc": wacc,
        "terminal_growth_rate": tgr,
        "projection_years": base.projection_years,
    }
    if base.is_decomposed:
        kwargs.update({
            "gross_margins": list(base.gross_margins) if base.gross_margins else None,
            "opex_as_pct_revenue": list(base.opex_as_pct_revenue) if base.opex_as_pct_revenue else None,
            "da_as_pct_revenue": base.da_as_pct_revenue,
            "sbc_as_pct_revenue": base.sbc_as_pct_revenue,
            "capex_as_pct_revenue": list(base.capex_as_pct_revenue) if base.capex_as_pct_revenue else None,
            "nwc_change_pct": base.nwc_change_pct,
            "tax_rate": base.tax_rate,
        })
    else:
        kwargs["fcf_margin"] = base.fcf_margin
    return DCFAssumptions(**kwargs)


def run_sensitivity(dcf_result: DCFResult) -> SensitivityResult:
    """
    Generate WACC x Terminal Growth sensitivity grid.

    Varies WACC: base +/- 1%, +/- 2% (5 steps)
    Varies terminal growth: base +/- 0.5%, +/- 1% (5 steps)

    Returns 5x5 grid of fair values per share.
    """
    base_wacc = dcf_result.assumptions.wacc
    base_tgr = dcf_result.assumptions.terminal_growth_rate

    wacc_values = [
        max(MIN_WACC, base_wacc - WACC_STEP_LARGE),
        max(MIN_WACC, base_wacc - WACC_STEP_SMALL),
        base_wacc,
        base_wacc + WACC_STEP_SMALL,
        base_wacc + WACC_STEP_LARGE,
    ]

    tgr_values = [
        max(MIN_TERMINAL_GROWTH, base_tgr - TGR_STEP_LARGE),
        max(MIN_TERMINAL_GROWTH, base_tgr - TGR_STEP_SMALL),
        base_tgr,
        min(base_wacc - 0.015, base_tgr + TGR_STEP_SMALL),
        min(base_wacc - WACC_STEP_SMALL, base_tgr + TGR_STEP_LARGE),
    ]

    grid = []
    for wacc in wacc_values:
        row = []
        for tgr in tgr_values:
            if tgr >= wacc:
                row.append(0.0)
                continue

            assumptions = _clone_assumptions_wacc_tgr(dcf_result.assumptions, wacc, tgr)
            result = calculate_dcf(
                base_revenue=dcf_result.base_revenue,
                net_debt=dcf_result.net_debt,
                shares_outstanding=dcf_result.shares_outstanding,
                current_price=dcf_result.current_price,
                assumptions=assumptions,
            )
            row.append(result.fair_value_per_share)
        grid.append(row)

    return SensitivityResult(
        wacc_values=wacc_values,
        terminal_growth_values=tgr_values,
        fair_value_grid=grid,
        base_wacc_idx=2,
        base_tgr_idx=2,
        current_price=dcf_result.current_price,
    )


def run_growth_margin_sensitivity(dcf_result: DCFResult) -> GrowthMarginSensitivityResult:
    """
    Generate Revenue Growth x Operating Margin sensitivity grid.

    WACC and terminal growth held constant at base case values.
    Varies average revenue growth: base +/- 2%, +/- 4% (5 steps)
    Varies operating margin (or FCF margin for legacy): base +/- 2%, +/- 4% (5 steps)

    More useful for M&A analysis — shows operating leverage sensitivity.
    """
    base_assumptions = dcf_result.assumptions

    # Determine base growth (average of growth rate array)
    base_growth = sum(base_assumptions.revenue_growth_rates) / len(base_assumptions.revenue_growth_rates)

    # Determine base margin
    if base_assumptions.is_decomposed:
        # Operating margin ≈ gross_margin - opex_pct
        avg_gross = sum(base_assumptions.gross_margins) / len(base_assumptions.gross_margins)
        avg_opex = sum(base_assumptions.opex_as_pct_revenue) / len(base_assumptions.opex_as_pct_revenue) if base_assumptions.opex_as_pct_revenue else 0.20
        base_margin = avg_gross - avg_opex
    else:
        base_margin = base_assumptions.fcf_margin

    growth_values = [
        max(-0.20, base_growth - GROWTH_STEP_LARGE),
        max(-0.10, base_growth - GROWTH_STEP_SMALL),
        base_growth,
        min(0.50, base_growth + GROWTH_STEP_SMALL),
        min(0.60, base_growth + GROWTH_STEP_LARGE),
    ]

    margin_values = [
        max(-0.20, base_margin - MARGIN_STEP_LARGE),
        max(-0.10, base_margin - MARGIN_STEP_SMALL),
        base_margin,
        min(0.80, base_margin + MARGIN_STEP_SMALL),
        min(0.90, base_margin + MARGIN_STEP_LARGE),
    ]

    grid = []
    for growth in growth_values:
        row = []
        for margin in margin_values:
            # Build uniform growth rates at this level
            uniform_growth = [growth] * base_assumptions.projection_years

            if base_assumptions.is_decomposed:
                # Distribute margin change: adjust gross margin to hit target op margin
                margin_delta = margin - base_margin
                adjusted_gross = [
                    max(0.0, min(0.99, m + margin_delta))
                    for m in (base_assumptions.gross_margins or [0.50])
                ]
                assumptions = DCFAssumptions(
                    revenue_growth_rates=uniform_growth,
                    wacc=base_assumptions.wacc,
                    terminal_growth_rate=base_assumptions.terminal_growth_rate,
                    projection_years=base_assumptions.projection_years,
                    gross_margins=adjusted_gross,
                    opex_as_pct_revenue=list(base_assumptions.opex_as_pct_revenue) if base_assumptions.opex_as_pct_revenue else None,
                    da_as_pct_revenue=base_assumptions.da_as_pct_revenue,
                    sbc_as_pct_revenue=base_assumptions.sbc_as_pct_revenue,
                    capex_as_pct_revenue=list(base_assumptions.capex_as_pct_revenue) if base_assumptions.capex_as_pct_revenue else None,
                    nwc_change_pct=base_assumptions.nwc_change_pct,
                    tax_rate=base_assumptions.tax_rate,
                )
            else:
                assumptions = DCFAssumptions(
                    revenue_growth_rates=uniform_growth,
                    fcf_margin=margin,
                    wacc=base_assumptions.wacc,
                    terminal_growth_rate=base_assumptions.terminal_growth_rate,
                    projection_years=base_assumptions.projection_years,
                )

            result = calculate_dcf(
                base_revenue=dcf_result.base_revenue,
                net_debt=dcf_result.net_debt,
                shares_outstanding=dcf_result.shares_outstanding,
                current_price=dcf_result.current_price,
                assumptions=assumptions,
            )
            row.append(result.fair_value_per_share)
        grid.append(row)

    return GrowthMarginSensitivityResult(
        growth_values=growth_values,
        margin_values=margin_values,
        fair_value_grid=grid,
        base_growth_idx=2,
        base_margin_idx=2,
        current_price=dcf_result.current_price,
    )


def format_sensitivity_markdown(result: SensitivityResult) -> str:
    """Format WACC x TGR sensitivity grid as markdown table."""
    lines = [
        "**Sensitivity Analysis: Fair Value per Share**\n",
        "WACC (rows) vs Terminal Growth Rate (columns)\n",
    ]

    # Header row with terminal growth values
    header = "| WACC \\\\ TGR |"
    for tgr in result.terminal_growth_values:
        header += f" {tgr*100:.1f}% |"
    lines.append(header)

    separator = "|---|" + "|".join(["---"] * len(result.terminal_growth_values)) + "|"
    lines.append(separator)

    for i, wacc in enumerate(result.wacc_values):
        is_base = i == result.base_wacc_idx
        row = f"| {'**' if is_base else ''}{wacc*100:.1f}%{'**' if is_base else ''} |"
        for j, fv in enumerate(result.fair_value_grid[i]):
            is_base_cell = i == result.base_wacc_idx and j == result.base_tgr_idx
            if fv <= 0:
                row += " N/A |"
            elif is_base_cell:
                row += f" **${fv:.2f}** |"
            else:
                row += f" ${fv:.2f} |"
        lines.append(row)

    lines.append(f"\nCurrent Price: ${result.current_price:.2f} | Base case (bold): WACC={result.wacc_values[2]*100:.1f}%, TGR={result.terminal_growth_values[2]*100:.1f}%")

    return "\n".join(lines)


def format_growth_margin_sensitivity_markdown(result: GrowthMarginSensitivityResult) -> str:
    """Format Revenue Growth x Operating Margin sensitivity grid as markdown table."""
    lines = [
        "**Operating Leverage Sensitivity: Fair Value per Share**\n",
        "Revenue Growth (rows) vs Operating Margin (columns) — WACC held constant\n",
    ]

    header = "| Growth \\\\ Margin |"
    for margin in result.margin_values:
        header += f" {margin*100:.1f}% |"
    lines.append(header)

    separator = "|---|" + "|".join(["---"] * len(result.margin_values)) + "|"
    lines.append(separator)

    for i, growth in enumerate(result.growth_values):
        is_base = i == result.base_growth_idx
        row = f"| {'**' if is_base else ''}{growth*100:.1f}%{'**' if is_base else ''} |"
        for j, fv in enumerate(result.fair_value_grid[i]):
            is_base_cell = i == result.base_growth_idx and j == result.base_margin_idx
            if fv <= 0:
                row += " N/A |"
            elif is_base_cell:
                row += f" **${fv:.2f}** |"
            else:
                row += f" ${fv:.2f} |"
        lines.append(row)

    lines.append(f"\nCurrent Price: ${result.current_price:.2f} | Base case (bold): Growth={result.growth_values[2]*100:.1f}%, Margin={result.margin_values[2]*100:.1f}%")

    return "\n".join(lines)


def run_sensitivity_analysis(dcf_result: DCFResult) -> tuple:
    """Run both sensitivity grids and return as AnalysisResult.

    Returns:
        (wacc_tgr_result, growth_margin_result, analysis_result)
    """
    sens_result = run_sensitivity(dcf_result)
    gm_result = run_growth_margin_sensitivity(dcf_result)

    content = format_sensitivity_markdown(sens_result)
    content += "\n\n---\n\n"
    content += format_growth_margin_sensitivity_markdown(gm_result)

    analysis = AnalysisResult(
        section="Sensitivity Analysis",
        content=content,
        tokens_used=0,
        success=True,
        cost_usd=0.0,
    )

    return sens_result, gm_result, analysis
