"""
Valuation module for Constant equity research platform.

Provides quantitative valuation methods:
- DCF (Discounted Cash Flow) with LLM-reasoned assumptions
- Comparable Company Analysis
- Earnings Model Summary
- Sensitivity Analysis (WACC x Terminal Growth)
- Conviction Scoring (decomposed 0-100)
"""

from src_george_researcher.valuation.dcf_engine import (
    DCFAssumptions,
    DCFResult,
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
