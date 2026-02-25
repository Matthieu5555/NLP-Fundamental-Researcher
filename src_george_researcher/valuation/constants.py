"""
Valuation constants and bounds.

All magic numbers used in valuation calculations are centralized here.
Reference: Damodaran "Investment Valuation", McKinsey "Valuation" 7th Ed.

Changing any value here affects all valuation agents that import it.
"""

# =============================================================================
# DCF Model Bounds
# =============================================================================

# Maximum annual revenue growth rate the model accepts.
# +/-50% covers hypergrowth (early NVDA AI ramp ~40% YoY) while
# rejecting implausible LLM hallucinations.
MAX_GROWTH_RATE: float = 0.50

# Free cash flow margin bounds.
# -50% floor: allows deep-negative for pre-profit growth companies (e.g., early Uber).
# +80% ceiling: theoretical max for asset-light monopolies (e.g., Visa at ~65%).
MIN_FCF_MARGIN: float = -0.50
MAX_FCF_MARGIN: float = 0.80

# Weighted average cost of capital bounds.
# 5% floor: US risk-free rate (~4.5%) + minimal equity premium for mega-caps.
# 20% ceiling: appropriate for distressed small-cap or frontier market equities.
MIN_WACC: float = 0.05
MAX_WACC: float = 0.20

# Terminal growth rate floor.
# Must stay below long-term nominal GDP growth (2-3%).
# 0.5% floor: minimal inflation pass-through for a shrinking business.
MIN_TERMINAL_GROWTH: float = 0.005

# Max historical periods and analyst estimates sent to LLM for DCF reasoning.
# Higher values give more context but increase token cost (~$0.01 per period).
MAX_HISTORICAL_PERIODS: int = 5
MAX_ANALYST_ESTIMATES: int = 4

# Conservative fallback assumptions when LLM parsing fails.
# These produce a modestly growing, moderately profitable business —
# intentionally generic so the result is "safe" rather than misleading.
DEFAULT_REVENUE_GROWTH: list[float] = [0.05, 0.04, 0.03, 0.03, 0.02]
DEFAULT_FCF_MARGIN: float = 0.15
DEFAULT_WACC: float = 0.10
DEFAULT_TERMINAL_GROWTH: float = 0.025

# =============================================================================
# Scenario Analysis
# =============================================================================

# Probability weights for bull/base/bear scenarios. Must sum to 1.0.
# Standard institutional weighting: base case dominates.
SCENARIO_PROB_BULL: float = 0.25
SCENARIO_PROB_BASE: float = 0.50
SCENARIO_PROB_BEAR: float = 0.25
SCENARIO_WEIGHTS: tuple[float, float, float] = (
    SCENARIO_PROB_BULL,
    SCENARIO_PROB_BASE,
    SCENARIO_PROB_BEAR,
)

# =============================================================================
# Sensitivity Grid
# =============================================================================

# WACC and terminal growth rate step sizes for the 5x5 sensitivity grid.
SENSITIVITY_WACC_STEP: float = 0.01
SENSITIVITY_TGR_STEP: float = 0.005
SENSITIVITY_GROWTH_STEP: float = 0.04
SENSITIVITY_MARGIN_STEP: float = 0.04

# =============================================================================
# Comparable Companies
# =============================================================================

# Football field comp spread: +/- around peer median for valuation range.
COMP_SPREAD: float = 0.15

# =============================================================================
# Scenario Shift Constants — Bull Case
# =============================================================================
# These multipliers and additive shifts transform the base DCF assumptions
# into an optimistic scenario. All values chosen to produce ~20-40% upside
# vs base case for a typical mid-growth company.

# Revenue growth: base * MULTIPLIER + BOOST, capped at MAX_GROWTH_RATE.
BULL_GROWTH_MULTIPLIER: float = 1.3    # Boost base growth rates by 30% relative
BULL_GROWTH_BOOST: float = 0.02        # Add 2pp absolute growth boost

# Margins: expand gross, shrink opex/capex to model operating leverage.
BULL_MARGIN_BOOST: float = 0.02        # Expand gross margins by 2pp
BULL_OPEX_REDUCTION: float = 0.02      # Reduce opex ratio by 2pp
BULL_CAPEX_REDUCTION: float = 0.005    # Reduce capex ratio by 0.5pp

# Discount rate: lower WACC reflects reduced perceived risk.
BULL_WACC_REDUCTION: float = 0.005     # Lower WACC by 50bps

# Terminal value: slightly higher long-run growth.
BULL_TGR_BOOST: float = 0.005          # Increase terminal growth by 50bps
BULL_TGR_WACC_SPREAD: float = 0.02     # Terminal growth must stay ≥2pp below WACC

# Legacy FCF margin mode: boost margin directly.
BULL_FCF_MULTIPLIER: float = 1.15      # Boost FCF margin by 15% relative
BULL_FCF_BOOST: float = 0.02           # Add 2pp absolute FCF boost

# =============================================================================
# Scenario Shift Constants — Bear Case
# =============================================================================
# Pessimistic scenario shifts. Chosen to produce ~20-40% downside vs base.

# Revenue growth: base * MULTIPLIER - CUT, floored at -MAX_GROWTH_RATE.
BEAR_GROWTH_MULTIPLIER: float = 0.6    # Cut base growth to 60%
BEAR_GROWTH_CUT: float = 0.02          # Subtract 2pp absolute growth

# Margins: compress gross, inflate opex/capex to model cost pressure.
BEAR_GROSS_MARGIN_CUT: float = 0.03    # Cut gross margins by 3pp
BEAR_OPEX_INCREASE: float = 0.03       # Increase opex ratio by 3pp
BEAR_CAPEX_INCREASE: float = 0.01      # Increase capex ratio by 1pp

# Discount rate: higher WACC reflects elevated risk.
BEAR_WACC_INCREASE: float = 0.01       # Raise WACC by 100bps

# Terminal value: lower long-run growth.
BEAR_TGR_CUT: float = 0.005            # Decrease terminal growth by 50bps

# Legacy FCF margin mode: cut margin directly.
BEAR_FCF_MULTIPLIER: float = 0.75      # Cut FCF margin to 75% of base
BEAR_FCF_CUT: float = 0.02             # Subtract 2pp absolute FCF
