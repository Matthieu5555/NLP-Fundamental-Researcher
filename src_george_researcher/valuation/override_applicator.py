"""
Pure-function override applicator for DCF assumptions.

Takes a base DCFAssumptions (from LLM) and an OverrideSet (from analyst),
returns a new frozen DCFAssumptions with overrides applied. Never mutates
the base — always produces a fresh object.

All values are clamped to the bounds defined in constants.py to prevent
impossible assumptions (negative WACC, margins > 100%, etc.).
"""

from typing import List, Optional

from src_george_researcher.valuation.constants import (
    MAX_GROWTH_RATE,
    MAX_FCF_MARGIN,
    MAX_WACC,
    MIN_FCF_MARGIN,
    MIN_TERMINAL_GROWTH,
    MIN_WACC,
)
from src_george_researcher.valuation.dcf_engine import DCFAssumptions
from src_george_researcher.valuation.overrides import (
    AssumptionOverride,
    OverrideMode,
    OverrideSet,
    OverrideTarget,
)


def apply_overrides(base: DCFAssumptions, overrides: OverrideSet) -> DCFAssumptions:
    """Apply analyst overrides to base assumptions, returning new frozen DCFAssumptions.

    Overrides are applied in order. If no overrides exist, returns the base unchanged.
    All results are clamped to valuation bounds.
    """
    if not overrides.overrides:
        return base

    # Work with mutable copies of per-year lists
    growth_rates = list(base.revenue_growth_rates)
    gross_margins = list(base.gross_margins) if base.gross_margins else None
    opex_pcts = list(base.opex_as_pct_revenue) if base.opex_as_pct_revenue else None
    capex_pcts = list(base.capex_as_pct_revenue) if base.capex_as_pct_revenue else None

    # Scalar fields
    wacc = base.wacc
    terminal_growth = base.terminal_growth_rate
    tax_rate = base.tax_rate
    da_ratio = base.da_as_pct_revenue
    sbc_ratio = base.sbc_as_pct_revenue
    nwc_change = base.nwc_change_pct
    fcf_margin = base.fcf_margin

    # Collect rationale additions
    rationale_parts: list[str] = []

    for override in overrides.overrides:
        rationale_parts.append(f"[Analyst] {override.rationale}")

        match override.target:
            case OverrideTarget.REVENUE_GROWTH:
                growth_rates = _apply_to_list(
                    growth_rates, override, lo=-MAX_GROWTH_RATE, hi=MAX_GROWTH_RATE,
                )
            case OverrideTarget.GROSS_MARGIN:
                if gross_margins is not None:
                    gross_margins = _apply_to_list(
                        gross_margins, override, lo=0.0, hi=0.95,
                    )
            case OverrideTarget.OPEX_RATIO:
                if opex_pcts is not None:
                    opex_pcts = _apply_to_list(
                        opex_pcts, override, lo=0.05, hi=0.80,
                    )
            case OverrideTarget.CAPEX_RATIO:
                if capex_pcts is not None:
                    capex_pcts = _apply_to_list(
                        capex_pcts, override, lo=0.01, hi=0.25,
                    )
            case OverrideTarget.WACC:
                wacc = _apply_scalar(wacc, override, lo=MIN_WACC, hi=MAX_WACC)
            case OverrideTarget.TERMINAL_GROWTH:
                terminal_growth = _apply_scalar(
                    terminal_growth, override, lo=MIN_TERMINAL_GROWTH, hi=wacc - 0.01,
                )
            case OverrideTarget.TAX_RATE:
                tax_rate = _apply_scalar(tax_rate, override, lo=0.0, hi=0.50)
            case OverrideTarget.DA_RATIO:
                da_ratio = _apply_scalar(da_ratio, override, lo=0.0, hi=0.20)
            case OverrideTarget.SBC_RATIO:
                sbc_ratio = _apply_scalar(sbc_ratio, override, lo=0.0, hi=0.15)
            case OverrideTarget.NWC_CHANGE:
                nwc_change = _apply_scalar(nwc_change, override, lo=0.0, hi=0.15)
            case OverrideTarget.FCF_MARGIN:
                fcf_margin = _apply_scalar(
                    fcf_margin, override, lo=MIN_FCF_MARGIN, hi=MAX_FCF_MARGIN,
                )

    # Ensure terminal growth stays below WACC
    terminal_growth = min(terminal_growth, wacc - 0.01)
    terminal_growth = max(terminal_growth, MIN_TERMINAL_GROWTH)

    analyst_note = " | ".join(rationale_parts) if rationale_parts else ""

    return DCFAssumptions(
        revenue_growth_rates=growth_rates,
        wacc=wacc,
        terminal_growth_rate=terminal_growth,
        projection_years=base.projection_years,
        fcf_margin=fcf_margin,
        gross_margins=gross_margins,
        opex_as_pct_revenue=opex_pcts,
        da_as_pct_revenue=da_ratio,
        sbc_as_pct_revenue=sbc_ratio,
        capex_as_pct_revenue=capex_pcts,
        nwc_change_pct=nwc_change,
        tax_rate=tax_rate,
        revenue_growth_rationale=_append_rationale(
            base.revenue_growth_rationale, analyst_note,
        ) if _targets_field(overrides, OverrideTarget.REVENUE_GROWTH) else base.revenue_growth_rationale,
        fcf_margin_rationale=_append_rationale(
            base.fcf_margin_rationale, analyst_note,
        ) if _targets_field(overrides, OverrideTarget.FCF_MARGIN) else base.fcf_margin_rationale,
        margin_rationale=_append_rationale(
            base.margin_rationale, analyst_note,
        ) if _targets_margin(overrides) else base.margin_rationale,
        wacc_rationale=_append_rationale(
            base.wacc_rationale, analyst_note,
        ) if _targets_field(overrides, OverrideTarget.WACC) else base.wacc_rationale,
        terminal_growth_rationale=_append_rationale(
            base.terminal_growth_rationale, analyst_note,
        ) if _targets_field(overrides, OverrideTarget.TERMINAL_GROWTH) else base.terminal_growth_rationale,
    )


def _apply_scalar(base_val: float, override: AssumptionOverride, lo: float, hi: float) -> float:
    """Apply a single override to a scalar value, clamping to bounds."""
    match override.mode:
        case OverrideMode.ABSOLUTE:
            result = override.value
        case OverrideMode.DELTA:
            result = base_val + override.value
        case OverrideMode.MULTIPLIER:
            result = base_val * override.value
    return max(lo, min(hi, result))


def _apply_to_list(
    base_list: List[float],
    override: AssumptionOverride,
    lo: float,
    hi: float,
) -> List[float]:
    """Apply an override to a per-year list.

    If override.year_indices is set, only those years are affected.
    Otherwise, all years are modified.
    """
    result = list(base_list)
    indices = override.year_indices if override.year_indices is not None else range(len(result))

    for i in indices:
        if 0 <= i < len(result):
            match override.mode:
                case OverrideMode.ABSOLUTE:
                    result[i] = override.value
                case OverrideMode.DELTA:
                    result[i] = result[i] + override.value
                case OverrideMode.MULTIPLIER:
                    result[i] = result[i] * override.value
            result[i] = max(lo, min(hi, result[i]))

    return result


def _targets_field(overrides: OverrideSet, target: OverrideTarget) -> bool:
    """Check if any override in the set targets a specific field."""
    return target in overrides.targets_affected()


def _targets_margin(overrides: OverrideSet) -> bool:
    """Check if any override targets margin-related fields."""
    margin_targets = {
        OverrideTarget.GROSS_MARGIN,
        OverrideTarget.OPEX_RATIO,
        OverrideTarget.CAPEX_RATIO,
        OverrideTarget.DA_RATIO,
        OverrideTarget.SBC_RATIO,
    }
    return bool(overrides.targets_affected() & margin_targets)


def _append_rationale(base_rationale: str, analyst_note: str) -> str:
    """Append analyst note to existing rationale."""
    if not analyst_note:
        return base_rationale
    if base_rationale:
        return f"{base_rationale} | {analyst_note}"
    return analyst_note
