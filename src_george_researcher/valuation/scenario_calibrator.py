"""
Volatility-based scenario calibration.

Replaces hardcoded BULL_*/BEAR_* constants with shifts derived from company
characteristics. A stable utility with 2% revenue growth stdev gets narrow
±10% fair value scenarios; a volatile tech stock with 15% stdev gets wide ±35%.

Pure math — no LLM calls.
"""

import statistics
from dataclasses import dataclass
from typing import List, Optional

from src_george_researcher.valuation.dcf_engine import DCFAssumptions
from src_george_researcher.valuation.constants import (
    MAX_GROWTH_RATE,
    MAX_WACC,
    MIN_FCF_MARGIN,
    MAX_FCF_MARGIN,
    MIN_TERMINAL_GROWTH,
    MIN_WACC,
)


@dataclass(frozen=True)
class CompanyVolatility:
    """Historical volatility metrics used to calibrate scenario spreads.

    Computed from EnrichedFinancials or provided directly.
    """
    revenue_growth_rates: List[float]          # Historical annual growth rates
    operating_margins: Optional[List[float]] = None  # Historical operating margins
    beta: Optional[float] = None
    market_cap: Optional[float] = None

    @property
    def growth_stdev(self) -> float:
        """Standard deviation of historical revenue growth rates."""
        if len(self.revenue_growth_rates) < 2:
            return 0.05  # Default: moderate volatility
        return statistics.stdev(self.revenue_growth_rates)

    @property
    def margin_stdev(self) -> float:
        """Standard deviation of historical operating margins."""
        if not self.operating_margins or len(self.operating_margins) < 2:
            return 0.02  # Default: modest margin volatility
        return statistics.stdev(self.operating_margins)


def calibrate_scenarios(
    base: DCFAssumptions,
    volatility: CompanyVolatility,
) -> tuple[DCFAssumptions, DCFAssumptions]:
    """Generate bull/bear assumptions calibrated to company volatility.

    Principles:
    - Growth shift proportional to historical revenue growth stdev
    - Margin shift proportional to historical margin stdev
    - WACC shift proportional to beta (higher beta = wider WACC swing)
    - Terminal growth shift is modest (bounded by economic reality)
    - Minimum spread enforced: bull and bear at least 15% apart in growth impact

    Returns:
        (bull_assumptions, bear_assumptions)
    """
    gs = volatility.growth_stdev
    ms = volatility.margin_stdev
    beta = volatility.beta or 1.0

    # Growth shifts: 1 stdev of historical growth rates, floored at 2pp
    growth_shift = max(0.02, gs)

    # Margin shifts: 1 stdev of historical margins, floored at 1pp
    margin_shift = max(0.01, ms)

    # WACC shift: 50-150bps scaled by beta
    wacc_shift = 0.005 * beta  # 50bps per unit of beta

    # Terminal growth shift: modest, 25-50bps
    tgr_shift = 0.005 if beta >= 1.0 else 0.0025

    bull = _build_bull(base, growth_shift, margin_shift, wacc_shift, tgr_shift)
    bear = _build_bear(base, growth_shift, margin_shift, wacc_shift, tgr_shift)
    return bull, bear


def _build_bull(
    base: DCFAssumptions,
    growth_shift: float,
    margin_shift: float,
    wacc_shift: float,
    tgr_shift: float,
) -> DCFAssumptions:
    """Build bull case by shifting base assumptions optimistically."""
    # Revenue growth: add growth_shift to each year
    bull_growth = [
        min(MAX_GROWTH_RATE, g + growth_shift)
        for g in base.revenue_growth_rates
    ]

    # Margins: expand gross, shrink opex
    bull_gross = (
        [min(0.95, m + margin_shift) for m in base.gross_margins]
        if base.gross_margins else None
    )
    bull_opex = (
        [max(0.05, o - margin_shift * 0.5) for o in base.opex_as_pct_revenue]
        if base.opex_as_pct_revenue else None
    )
    bull_capex = (
        [max(0.01, c - margin_shift * 0.25) for c in base.capex_as_pct_revenue]
        if base.capex_as_pct_revenue else None
    )

    bull_wacc = max(MIN_WACC, base.wacc - wacc_shift)
    bull_tgr = min(bull_wacc - 0.02, base.terminal_growth_rate + tgr_shift)
    bull_tgr = max(MIN_TERMINAL_GROWTH, bull_tgr)

    bull_fcf = min(MAX_FCF_MARGIN, base.fcf_margin + margin_shift + growth_shift * 0.5)

    return DCFAssumptions(
        revenue_growth_rates=bull_growth,
        wacc=bull_wacc,
        terminal_growth_rate=bull_tgr,
        projection_years=base.projection_years,
        fcf_margin=bull_fcf,
        gross_margins=bull_gross,
        opex_as_pct_revenue=bull_opex,
        da_as_pct_revenue=base.da_as_pct_revenue,
        sbc_as_pct_revenue=base.sbc_as_pct_revenue,
        capex_as_pct_revenue=bull_capex,
        nwc_change_pct=base.nwc_change_pct,
        tax_rate=base.tax_rate,
        revenue_growth_rationale=f"Bull: +{growth_shift*100:.1f}pp growth (1σ historical vol)",
        margin_rationale=f"Bull: +{margin_shift*100:.1f}pp margin expansion",
        wacc_rationale=f"Bull: WACC reduced by {wacc_shift*100:.0f}bps (lower risk)",
        terminal_growth_rationale=f"Bull: TGR +{tgr_shift*100:.0f}bps",
        fcf_margin_rationale=f"Bull: FCF margin expanded",
    )


def _build_bear(
    base: DCFAssumptions,
    growth_shift: float,
    margin_shift: float,
    wacc_shift: float,
    tgr_shift: float,
) -> DCFAssumptions:
    """Build bear case by shifting base assumptions pessimistically.

    Bear case uses asymmetric shifts: downside is 1.5x the upside shift
    because losses tend to be steeper than gains.
    """
    bear_growth_shift = growth_shift * 1.5

    bear_growth = [
        max(-MAX_GROWTH_RATE, g - bear_growth_shift)
        for g in base.revenue_growth_rates
    ]

    bear_margin_shift = margin_shift * 1.5

    bear_gross = (
        [max(0.0, m - bear_margin_shift) for m in base.gross_margins]
        if base.gross_margins else None
    )
    bear_opex = (
        [min(0.80, o + bear_margin_shift * 0.5) for o in base.opex_as_pct_revenue]
        if base.opex_as_pct_revenue else None
    )
    bear_capex = (
        [min(0.25, c + bear_margin_shift * 0.25) for c in base.capex_as_pct_revenue]
        if base.capex_as_pct_revenue else None
    )

    bear_wacc = min(MAX_WACC, base.wacc + wacc_shift * 1.5)
    bear_tgr = max(MIN_TERMINAL_GROWTH, base.terminal_growth_rate - tgr_shift)
    # Ensure TGR stays below WACC
    bear_tgr = min(bear_tgr, bear_wacc - 0.01)

    bear_fcf = max(MIN_FCF_MARGIN, base.fcf_margin - bear_margin_shift - bear_growth_shift * 0.5)

    return DCFAssumptions(
        revenue_growth_rates=bear_growth,
        wacc=bear_wacc,
        terminal_growth_rate=bear_tgr,
        projection_years=base.projection_years,
        fcf_margin=bear_fcf,
        gross_margins=bear_gross,
        opex_as_pct_revenue=bear_opex,
        da_as_pct_revenue=base.da_as_pct_revenue,
        sbc_as_pct_revenue=base.sbc_as_pct_revenue,
        capex_as_pct_revenue=bear_capex,
        nwc_change_pct=base.nwc_change_pct,
        tax_rate=base.tax_rate,
        revenue_growth_rationale=f"Bear: -{bear_growth_shift*100:.1f}pp growth (1.5σ downside)",
        margin_rationale=f"Bear: -{bear_margin_shift*100:.1f}pp margin compression",
        wacc_rationale=f"Bear: WACC increased by {wacc_shift*1.5*100:.0f}bps (elevated risk)",
        terminal_growth_rationale=f"Bear: TGR -{tgr_shift*100:.0f}bps",
        fcf_margin_rationale=f"Bear: FCF margin compressed",
    )
