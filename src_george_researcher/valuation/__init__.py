"""
Valuation module for George equity research platform.

Provides quantitative valuation methods:
- DCF (Discounted Cash Flow) with LLM-reasoned assumptions
- Comparable Company Analysis
- Earnings Model Summary
- Sensitivity Analysis (WACC x Terminal Growth)
- Conviction Scoring (decomposed 0-100)
- Analyst Override System (structured belief → model re-propagation)
"""

from src_george_researcher.valuation.dcf_engine import (
    DCFAssumptions,
    DCFResult,
    EVBridge,
    calculate_dcf,
)
from src_george_researcher.valuation.sensitivity import (
    SensitivityResult,
    GrowthMarginSensitivityResult,
    run_sensitivity,
    run_growth_margin_sensitivity,
)
from src_george_researcher.valuation.scenarios import (
    ScenarioResult,
    ScenarioCase,
    run_scenarios,
)
from src_george_researcher.valuation.overrides import (
    AssumptionOverride,
    OverrideMode,
    OverrideSet,
    OverrideTarget,
)
from src_george_researcher.valuation.override_applicator import apply_overrides
from src_george_researcher.valuation.ddm import DDMResult, run_ddm
