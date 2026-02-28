"""
Valuation re-propagation pipeline.

When an analyst provides overrides via chat (e.g., "margins will compress 5pp"),
this module re-runs the valuation chain without re-fetching data or re-running
fundamentals/strategic assessment.

Chain: apply_overrides -> calculate_dcf -> run_scenarios -> run_sensitivity
       -> build_football_field -> score_conviction

Cost: DCF/scenarios/sensitivity/football field are pure math (zero LLM cost).
Only conviction scoring requires an LLM call (~$0.005).
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src_george_researcher.data_fetchers.stock_data import StockInfo
from src_george_researcher.valuation.comp_table import CompTableResult
from src_george_researcher.valuation.conviction import ConvictionResult, score_conviction
from src_george_researcher.valuation.dcf_engine import (
    DCFAssumptions,
    DCFResult,
    EVBridge,
    calculate_dcf,
)
from src_george_researcher.valuation.football_field import (
    FootballFieldResult,
    build_football_field,
)
from src_george_researcher.valuation.override_applicator import apply_overrides
from src_george_researcher.valuation.overrides import OverrideSet
from src_george_researcher.valuation.scenarios import ScenarioResult, run_scenarios
from src_george_researcher.valuation.sensitivity import (
    GrowthMarginSensitivityResult,
    SensitivityResult,
    run_growth_margin_sensitivity,
    run_sensitivity,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepropagationInput:
    """Everything needed to re-run the valuation chain with analyst overrides."""

    # DCF inputs
    base_revenue: float
    net_debt: float
    shares_outstanding: float
    current_price: float
    ev_bridge: Optional[EVBridge] = None

    # Original LLM-generated assumptions (never mutated)
    base_assumptions: Optional[DCFAssumptions] = None

    # Analyst overrides to apply on top of base
    overrides: Optional[OverrideSet] = None

    # Context for conviction re-scoring
    stock_info: Optional[StockInfo] = None
    fundamentals_content: str = ""
    technicals_content: str = ""
    bull_thesis: str = ""
    bear_thesis: str = ""
    sentiment_report: str = ""

    # Existing comp/precedent results (not re-computed, just passed through)
    comp_result: Optional[CompTableResult] = None
    consensus_target: Optional[float] = None

    # LLM config for conviction scoring
    api_key: str = ""
    model: str = ""


@dataclass(frozen=True)
class RepropagationResult:
    """Complete output from re-running the valuation chain."""

    adjusted_assumptions: DCFAssumptions
    dcf_result: DCFResult
    scenario_result: ScenarioResult
    sensitivity_result: SensitivityResult
    growth_margin_sensitivity: GrowthMarginSensitivityResult
    football_field_result: FootballFieldResult
    conviction_result: Optional[ConvictionResult] = None
    overrides_applied: Optional[OverrideSet] = None


def repropagate(inp: RepropagationInput) -> RepropagationResult:
    """Re-run the valuation chain with analyst overrides.

    Steps:
    1. Apply overrides to base assumptions
    2. Run DCF with adjusted assumptions
    3. Run bull/base/bear scenarios
    4. Run sensitivity grids (WACC x TGR, Growth x Margin)
    5. Build football field (aggregates all methods)
    6. Re-score conviction (only LLM call in the chain)

    Returns:
        RepropagationResult with all updated valuation outputs.
    """
    if inp.base_assumptions is None:
        raise ValueError("base_assumptions is required for re-propagation")

    # 1. Apply analyst overrides
    overrides = inp.overrides or OverrideSet()
    adjusted = apply_overrides(inp.base_assumptions, overrides)
    logger.info(
        "Re-propagating with %d override(s) affecting %s",
        len(overrides.overrides),
        [t.value for t in overrides.targets_affected()],
    )

    # 2. Run DCF
    bridge = inp.ev_bridge or EVBridge.from_net_debt(inp.net_debt)
    dcf_result = calculate_dcf(
        base_revenue=inp.base_revenue,
        net_debt=inp.net_debt,
        shares_outstanding=inp.shares_outstanding,
        current_price=inp.current_price,
        assumptions=adjusted,
        ev_bridge=bridge,
    )

    # 3. Run scenarios (bull/bear auto-generated from adjusted base)
    scenario_result = run_scenarios(
        base_revenue=inp.base_revenue,
        net_debt=inp.net_debt,
        shares_outstanding=inp.shares_outstanding,
        current_price=inp.current_price,
        base_assumptions=adjusted,
    )

    # 4. Run sensitivity grids
    sensitivity_result = run_sensitivity(dcf_result)
    growth_margin_sensitivity = run_growth_margin_sensitivity(dcf_result)

    # 5. Build football field
    football_field_result = _build_football_field_from_results(
        inp, dcf_result, scenario_result,
    )

    # 6. Re-score conviction (requires LLM)
    conviction_result = None
    if inp.api_key and inp.model and inp.stock_info:
        try:
            conviction_result, _ = score_conviction(
                api_key=inp.api_key,
                model=inp.model,
                stock_info=inp.stock_info,
                fundamentals=inp.fundamentals_content,
                technicals=inp.technicals_content,
                bull_thesis=inp.bull_thesis,
                bear_thesis=inp.bear_thesis,
                dcf_result=dcf_result,
                comp_result=inp.comp_result,
                sentiment_report=inp.sentiment_report,
            )
        except Exception:
            logger.warning("Conviction re-scoring failed during re-propagation", exc_info=True)

    return RepropagationResult(
        adjusted_assumptions=adjusted,
        dcf_result=dcf_result,
        scenario_result=scenario_result,
        sensitivity_result=sensitivity_result,
        growth_margin_sensitivity=growth_margin_sensitivity,
        football_field_result=football_field_result,
        conviction_result=conviction_result,
        overrides_applied=overrides,
    )


def _build_football_field_from_results(
    inp: RepropagationInput,
    dcf_result: DCFResult,
    scenario_result: ScenarioResult,
) -> FootballFieldResult:
    """Build football field from re-propagation results and existing comp/precedent data."""
    kwargs = {
        "current_price": inp.current_price,
        "dcf_bear": scenario_result.bear.result.fair_value_per_share,
        "dcf_base": scenario_result.base.result.fair_value_per_share,
        "dcf_bull": scenario_result.bull.result.fair_value_per_share,
        "weighted_fair_value": scenario_result.weighted_fair_value,
    }

    # Pass through existing comp implied values if available
    if inp.comp_result:
        cr = inp.comp_result
        if hasattr(cr, "pe_implied"):
            kwargs["comp_pe_implied"] = cr.pe_implied
        if hasattr(cr, "fwd_pe_implied"):
            kwargs["comp_fwd_pe_implied"] = cr.fwd_pe_implied
        if hasattr(cr, "ev_revenue_implied"):
            kwargs["comp_ev_revenue_implied"] = cr.ev_revenue_implied
        if hasattr(cr, "ev_ebitda_implied"):
            kwargs["comp_ev_ebitda_implied"] = cr.ev_ebitda_implied

    if inp.consensus_target:
        kwargs["consensus_target"] = inp.consensus_target

    return build_football_field(**kwargs)
