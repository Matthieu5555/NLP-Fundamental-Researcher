"""Session-level valuation repropagation.

Orchestrates the chain: DCF override -> sensitivity -> scenarios ->
football field, given a set of analyst overrides (DCF assumption diffs).
Extracted from the inline logic in sessions.py so that both the selective-
update endpoint and the chat flow can trigger repropagation without code
duplication.

Single entry point: run_valuation_repropagation() -> Optional[RepropagationOutcome]
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Fields accepted by DCFAssumptions constructor
_DCF_CONSTRUCTOR_FIELDS = frozenset({
    "revenue_growth_rates", "wacc", "terminal_growth_rate",
    "projection_years", "fcf_margin", "gross_margins",
    "opex_as_pct_revenue", "da_as_pct_revenue", "sbc_as_pct_revenue",
    "capex_as_pct_revenue", "nwc_change_pct", "tax_rate",
    "revenue_growth_rationale", "fcf_margin_rationale",
    "margin_rationale", "wacc_rationale", "terminal_growth_rationale",
})


@dataclass(frozen=True)
class RepropagationOutcome:
    """Result of a valuation repropagation pass."""

    dcf_updated: bool
    fair_value_per_share: Optional[float]
    metadata_updates: Dict[str, Any]
    assumption_changes: List[Dict[str, Any]] = field(default_factory=list)
    conviction_updated: bool = False
    cost_usd: float = 0.0
    warnings: List[str] = field(default_factory=list)


def _diff_assumptions(
    old: Dict[str, Any], new: Dict[str, Any], rationale: str = "",
) -> List[Dict[str, Any]]:
    """Compare two assumption dicts and return a changelog of changed fields."""
    changes: List[Dict[str, Any]] = []
    for key in set(old) | set(new):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes.append({
                "field": key,
                "old_value": old_val,
                "new_value": new_val,
                "rationale": rationale,
                "timestamp": datetime.now().isoformat(),
            })
    return changes


def run_valuation_repropagation(
    session_metadata: Dict[str, Any],
    dcf_overrides: Dict[str, Any],
    existing_scenarios: Optional[Dict[str, Any]] = None,
    existing_football_field: Optional[Dict[str, Any]] = None,
    skip_conviction: bool = True,
    conviction_kwargs: Optional[Dict[str, Any]] = None,
) -> Optional[RepropagationOutcome]:
    """Run the DCF -> sensitivity -> scenarios -> football field chain.

    All computation here is pure math (no LLM calls) except for the optional
    conviction re-scoring step. Returns None if no DCF data exists or no
    overrides are applicable.

    Args:
        session_metadata: the session.metadata dict containing "dcf" etc.
        dcf_overrides: dict of assumption field -> new value from analyst beliefs.
        existing_scenarios: fallback scenario data if scenarios are not re-run.
        existing_football_field: fallback football field data for comp/precedent ranges.
        skip_conviction: if True, do not re-score conviction (default for chat flow).
        conviction_kwargs: if skip_conviction is False, dict with keys needed by
            score_conviction (api_key, model, stock_info, fundamentals, etc.).

    Returns:
        RepropagationOutcome with updated metadata, or None if nothing to do.
    """
    existing_dcf = session_metadata.get("dcf")
    if not existing_dcf or "assumptions" not in existing_dcf:
        return None
    if not dcf_overrides:
        return None

    from src_george_researcher.valuation.dcf_engine import DCFAssumptions, calculate_dcf

    # Reconstruct base assumptions and snapshot for changelog
    base_assumptions_dict = existing_dcf["assumptions"]
    base_kwargs = {
        k: v for k, v in base_assumptions_dict.items()
        if k in _DCF_CONSTRUCTOR_FIELDS and v is not None
    }
    base_assumptions = DCFAssumptions(**base_kwargs)

    # Snapshot before overrides for changelog (Item 6)
    old_snapshot = {k: getattr(base_assumptions, k, None) for k in dcf_overrides}

    overridden = base_assumptions.with_overrides(dcf_overrides)

    # Changelog: diff changed fields
    new_snapshot = {k: getattr(overridden, k, None) for k in dcf_overrides}
    assumption_changes = _diff_assumptions(old_snapshot, new_snapshot, rationale="analyst override")

    # Re-run DCF (pure math)
    dcf_result = calculate_dcf(
        base_revenue=existing_dcf["base_revenue"],
        net_debt=existing_dcf["net_debt"],
        shares_outstanding=existing_dcf["shares_outstanding"],
        current_price=existing_dcf["current_price"],
        assumptions=overridden,
    )

    metadata_updates: Dict[str, Any] = {"dcf": dcf_result.to_dict()}
    warnings: List[str] = []
    cost_usd = 0.0

    # Sensitivity
    from src_george_researcher.valuation.sensitivity import run_sensitivity_analysis
    sensitivity_result, growth_margin_sensitivity, _ = run_sensitivity_analysis(dcf_result)
    metadata_updates["sensitivity"] = sensitivity_result.to_dict()
    metadata_updates["sensitivity_operating"] = growth_margin_sensitivity.to_dict()

    # Scenarios
    from src_george_researcher.valuation.scenarios import run_scenarios
    scenario_result = run_scenarios(
        base_revenue=dcf_result.base_revenue,
        net_debt=dcf_result.net_debt,
        shares_outstanding=dcf_result.shares_outstanding,
        current_price=dcf_result.current_price,
        base_assumptions=dcf_result.assumptions,
    )
    metadata_updates["scenarios"] = scenario_result.to_dict()

    # Football field
    from src_george_researcher.valuation.football_field import build_football_field
    ff_kwargs: Dict[str, Any] = {
        "current_price": dcf_result.current_price,
        "dcf_bear": scenario_result.bear_case.fair_value,
        "dcf_base": scenario_result.base_case.fair_value,
        "dcf_bull": scenario_result.bull_case.fair_value,
        "weighted_fair_value": scenario_result.weighted_fair_value,
    }

    # Carry forward comp/precedent data from existing football field
    existing_ff = existing_football_field or session_metadata.get("football_field", {})
    for key in ("comp_pe_implied", "comp_fwd_pe_implied", "comp_ev_revenue_implied",
                "comp_ev_ebitda_implied", "precedent_ev_revenue", "precedent_ev_ebitda",
                "consensus_target"):
        if key in existing_ff:
            ff_kwargs[key] = existing_ff[key]

    football_field_result = build_football_field(**ff_kwargs)
    metadata_updates["football_field"] = football_field_result.to_dict()

    # Optional conviction re-scoring
    conviction_updated = False
    if not skip_conviction and conviction_kwargs:
        try:
            from src_george_researcher.valuation.conviction import score_conviction
            conviction_result, conviction_analysis = score_conviction(
                dcf_result=dcf_result,
                **conviction_kwargs,
            )
            if conviction_analysis.success and conviction_result:
                metadata_updates["conviction"] = conviction_result.to_dict()
                conviction_updated = True
                cost_usd += conviction_analysis.cost_usd
        except Exception as e:
            warnings.append(f"Conviction re-scoring failed: {e}")

    return RepropagationOutcome(
        dcf_updated=True,
        fair_value_per_share=dcf_result.fair_value_per_share,
        metadata_updates=metadata_updates,
        assumption_changes=assumption_changes,
        conviction_updated=conviction_updated,
        cost_usd=cost_usd,
        warnings=warnings,
    )
