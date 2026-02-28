"""Tests for CFA L2 valuation enhancements.

Covers:
- Override data model (overrides.py)
- Override applicator (override_applicator.py)
- EVBridge and enhanced WACC (dcf_engine.py)
- Scenario calibrator (scenario_calibrator.py)
- DDM (ddm.py)
- Earnings quality (earnings_quality.py)
- Precedent transaction control premium adjustment
- Football field DDM + minority-adjusted bars
- ROIC fix with DuPont 5-factor
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: stub problematic third-party deps and pre-register key packages
# so that direct-file-loading of individual modules works without triggering
# the full __init__.py chain (which has a circular import through yfinance).
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent.parent / "src_george_researcher"

if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = types.ModuleType("yfinance")


def _load(file_path: Path, module_name: str):
    """Load a single .py file as a named module, bypassing __init__.py chains."""
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load modules in dependency order — each module's internal `from X import Y`
# will resolve against sys.modules entries we register here.
_load(_ROOT / "valuation" / "constants.py", "src_george_researcher.valuation.constants")
_load(_ROOT / "valuation" / "overrides.py", "src_george_researcher.valuation.overrides")
_load(_ROOT / "valuation" / "dcf_engine.py", "src_george_researcher.valuation.dcf_engine")
_load(_ROOT / "valuation" / "override_applicator.py", "src_george_researcher.valuation.override_applicator")
_load(_ROOT / "valuation" / "scenario_calibrator.py", "src_george_researcher.valuation.scenario_calibrator")
_load(_ROOT / "valuation" / "ddm.py", "src_george_researcher.valuation.ddm")
_load(_ROOT / "valuation" / "football_field.py", "src_george_researcher.valuation.football_field")
_load(_ROOT / "analysis" / "us" / "earnings_quality.py", "src_george_researcher.analysis.us.earnings_quality")
_load(_ROOT / "analysis" / "us" / "financial_analysis.py", "src_george_researcher.analysis.us.financial_analysis")

# Now import normally from the modules we just registered
from src_george_researcher.valuation.overrides import (
    OverrideTarget, OverrideMode, AssumptionOverride, OverrideSet,
)
from src_george_researcher.valuation.constants import MAX_WACC
from src_george_researcher.valuation.dcf_engine import (
    DCFAssumptions, EVBridge, compute_wacc,
)
from src_george_researcher.valuation.override_applicator import apply_overrides
from src_george_researcher.valuation.scenario_calibrator import (
    CompanyVolatility, calibrate_scenarios,
)
from src_george_researcher.valuation.ddm import run_ddm
from src_george_researcher.valuation.football_field import build_football_field
from src_george_researcher.analysis.us.earnings_quality import (
    assess_earnings_quality, AccrualQuality,
)
from src_george_researcher.analysis.us.financial_analysis import FinancialRatios


# =============================================================================
# Override Data Model
# =============================================================================

class TestOverrideDataModel:
    def test_override_target_values(self):
        assert OverrideTarget.REVENUE_GROWTH.value == "revenue_growth"
        assert OverrideTarget.WACC.value == "wacc"
        assert OverrideTarget.NET_DEBT.value == "net_debt"

    def test_override_mode_values(self):
        assert OverrideMode.ABSOLUTE.value == "absolute"
        assert OverrideMode.DELTA.value == "delta"
        assert OverrideMode.MULTIPLIER.value == "multiplier"

    def test_assumption_override_frozen(self):
        override = AssumptionOverride(
            target=OverrideTarget.WACC,
            mode=OverrideMode.ABSOLUTE,
            value=0.12,
            rationale="Analyst override",
            belief_id="b1",
            confidence=0.9,
        )
        assert override.target == OverrideTarget.WACC
        assert override.value == 0.12
        with pytest.raises(AttributeError):
            override.value = 0.15

    def test_override_set_operations(self):
        OT = OverrideTarget
        OM = OverrideMode
        o1 = AssumptionOverride(
            target=OT.WACC, mode=OM.ABSOLUTE,
            value=0.12, rationale="test", belief_id="b1", confidence=0.9,
        )
        o2 = AssumptionOverride(
            target=OT.GROSS_MARGIN, mode=OM.DELTA,
            value=-0.05, rationale="test", belief_id="b2", confidence=0.8,
        )
        oset = OverrideSet(overrides=(o1, o2))
        assert len(oset.overrides) == 2
        assert OT.WACC in oset.targets_affected()
        assert OT.GROSS_MARGIN in oset.targets_affected()

        o3 = AssumptionOverride(
            target=OT.TERMINAL_GROWTH, mode=OM.ABSOLUTE,
            value=0.03, rationale="test", belief_id="b3", confidence=0.85,
        )
        new_set = oset.with_override(o3)
        assert len(new_set.overrides) == 3

        filtered = new_set.without_belief("b2")
        assert len(filtered.overrides) == 2

    def test_override_set_serialization(self):
        o = AssumptionOverride(
            target=OverrideTarget.WACC, mode=OverrideMode.ABSOLUTE,
            value=0.12, rationale="test", belief_id="b1", confidence=0.9,
        )
        oset = OverrideSet(overrides=(o,))
        d = oset.to_dict()
        restored = OverrideSet.from_dict(d)
        assert len(restored.overrides) == 1
        assert restored.overrides[0].target == OverrideTarget.WACC


# =============================================================================
# Override Applicator
# =============================================================================

class TestOverrideApplicator:
    def _make_base(self):
        return DCFAssumptions(
            revenue_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.04],
            wacc=0.10,
            terminal_growth_rate=0.025,
            fcf_margin=0.15,
            gross_margins=[0.60, 0.60, 0.60, 0.60, 0.60],
            opex_as_pct_revenue=[0.30, 0.29, 0.28, 0.27, 0.26],
        )

    def test_absolute_wacc_override(self):
        base = self._make_base()
        override = AssumptionOverride(
            target=OverrideTarget.WACC, mode=OverrideMode.ABSOLUTE,
            value=0.12, rationale="test", belief_id="b1", confidence=0.9,
        )
        result = apply_overrides(
            base, OverrideSet(overrides=(override,))
        )
        assert result.wacc == 0.12

    def test_delta_margin_override(self):
        base = self._make_base()
        override = AssumptionOverride(
            target=OverrideTarget.GROSS_MARGIN, mode=OverrideMode.DELTA,
            value=-0.05, rationale="compress", belief_id="b1", confidence=0.9,
        )
        result = apply_overrides(
            base, OverrideSet(overrides=(override,))
        )
        assert result.gross_margins is not None
        for m in result.gross_margins:
            assert abs(m - 0.55) < 0.001

    def test_zero_overrides_returns_identical(self):
        base = self._make_base()
        result = apply_overrides(base, OverrideSet())
        assert result.wacc == base.wacc
        assert result.revenue_growth_rates == base.revenue_growth_rates

    def test_bounds_respected(self):
        base = self._make_base()
        override = AssumptionOverride(
            target=OverrideTarget.WACC, mode=OverrideMode.ABSOLUTE,
            value=0.99, rationale="test", belief_id="b1", confidence=0.9,
        )
        result = apply_overrides(
            base, OverrideSet(overrides=(override,))
        )
        assert result.wacc <= MAX_WACC


# =============================================================================
# EVBridge
# =============================================================================

class TestEVBridge:
    def test_from_net_debt(self):
        bridge = EVBridge.from_net_debt(50e9)
        assert bridge.net_debt == 50e9
        assert bridge.minority_interest == 0
        assert bridge.total_deductions == 50e9

    def test_equity_value(self):
        bridge = EVBridge(
            net_debt=50e9,
            minority_interest=2e9,
            preferred_stock=1e9,
            pension_deficit=0.5e9,
            equity_investments=3e9,
        )
        ev = 200e9
        equity = bridge.equity_value(ev)
        expected = ev - 50e9 - 2e9 - 1e9 - 0.5e9 + 3e9
        assert abs(equity - expected) < 1.0

    def test_to_dict(self):
        bridge = EVBridge(net_debt=50e9, minority_interest=2e9)
        d = bridge.to_dict()
        assert d["net_debt"] == 50e9
        assert d["minority_interest"] == 2e9


# =============================================================================
# Enhanced WACC (Size Premium)
# =============================================================================

class TestEnhancedWACC:
    def test_size_premium_mega_cap(self):
        wacc, rationale = compute_wacc(beta=1.0, market_cap=500e9)
        # Mega-cap has 0% size premium, so SP= is omitted from rationale
        assert "SP=" not in rationale

    def test_size_premium_small_cap(self):
        wacc, rationale = compute_wacc(beta=1.0, market_cap=1.5e9)
        assert "SP=1.5%" in rationale
        wacc_mega, _ = compute_wacc(beta=1.0, market_cap=500e9)
        assert wacc > wacc_mega

    def test_size_premium_micro_cap(self):
        wacc, rationale = compute_wacc(beta=1.0, market_cap=200e6)
        assert "SP=3.0%" in rationale


# =============================================================================
# Scenario Calibrator
# =============================================================================

class TestScenarioCalibrator:
    def test_stable_company_narrow_spread(self):
        base = DCFAssumptions(
            revenue_growth_rates=[0.03, 0.03, 0.03, 0.03, 0.03],
            wacc=0.08, terminal_growth_rate=0.025, fcf_margin=0.15,
        )
        vol = CompanyVolatility(
            revenue_growth_rates=[0.02, 0.03, 0.025, 0.035, 0.028],
            beta=0.7,
        )
        bull, bear = calibrate_scenarios(base, vol)
        assert bull.revenue_growth_rates[0] > base.revenue_growth_rates[0]
        assert bear.revenue_growth_rates[0] < base.revenue_growth_rates[0]

    def test_volatile_company_wide_spread(self):
        base = DCFAssumptions(
            revenue_growth_rates=[0.15, 0.12, 0.10, 0.08, 0.06],
            wacc=0.12, terminal_growth_rate=0.025, fcf_margin=0.20,
        )
        vol = CompanyVolatility(
            revenue_growth_rates=[0.30, 0.05, -0.10, 0.25, 0.15],
            beta=1.5,
        )
        bull, bear = calibrate_scenarios(base, vol)
        growth_spread = bull.revenue_growth_rates[0] - bear.revenue_growth_rates[0]
        assert growth_spread > 0.10

    def test_bear_asymmetric(self):
        base = DCFAssumptions(
            revenue_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.04],
            wacc=0.10, terminal_growth_rate=0.025, fcf_margin=0.15,
        )
        vol = CompanyVolatility(
            revenue_growth_rates=[0.12, 0.08, 0.10, 0.06, 0.14],
            beta=1.0,
        )
        bull, bear = calibrate_scenarios(base, vol)
        bull_shift = bull.revenue_growth_rates[0] - base.revenue_growth_rates[0]
        bear_shift = base.revenue_growth_rates[0] - bear.revenue_growth_rates[0]
        assert bear_shift > bull_shift


# =============================================================================
# DDM
# =============================================================================

class TestDDM:
    def test_gordon_growth_basic(self):
        r = run_ddm(100.0, 3.0, 0.10, 0.03, 0.60)
        assert r.is_applicable
        assert r.gordon_growth_value is not None
        assert abs(r.gordon_growth_value - 44.14) < 0.5

    def test_h_model_higher_than_gordon(self):
        r = run_ddm(100.0, 3.0, 0.10, 0.03, 0.60, 0.08)
        assert r.is_applicable
        assert r.h_model_value is not None
        assert r.h_model_value > r.gordon_growth_value

    def test_not_applicable_low_yield(self):
        r = run_ddm(500.0, 0.5, 0.10, 0.03, 0.10)
        assert not r.is_applicable
        assert r.gordon_growth_value is None

    def test_not_applicable_low_payout(self):
        r = run_ddm(100.0, 2.0, 0.10, 0.03, 0.10)
        assert not r.is_applicable

    def test_growth_capped_below_ke(self):
        r = run_ddm(100.0, 3.0, 0.10, 0.15, 0.60)
        assert r.long_term_growth < r.cost_of_equity


# =============================================================================
# Earnings Quality
# =============================================================================

class TestEarningsQuality:
    def _clean(self):
        return [
            {"net_income": 10e9, "operating_cash_flow": 12e9, "free_cash_flow": 8e9,
             "total_assets": 100e9, "total_liabilities": 50e9, "total_equity": 50e9,
             "cash_and_equivalents": 20e9, "total_debt": 10e9},
            {"net_income": 9e9, "operating_cash_flow": 11e9, "free_cash_flow": 7e9,
             "total_assets": 95e9, "total_liabilities": 48e9, "total_equity": 47e9,
             "cash_and_equivalents": 18e9, "total_debt": 9e9},
        ]

    def _aggressive(self):
        return [
            {"net_income": 10e9, "operating_cash_flow": 3e9, "free_cash_flow": -2e9,
             "total_assets": 80e9, "total_liabilities": 55e9, "total_equity": 25e9,
             "cash_and_equivalents": 5e9, "total_debt": 30e9},
            {"net_income": 8e9, "operating_cash_flow": 4e9, "free_cash_flow": -1e9,
             "total_assets": 70e9, "total_liabilities": 48e9, "total_equity": 22e9,
             "cash_and_equivalents": 4e9, "total_debt": 25e9},
        ]

    def test_clean_company_scores_high(self):
        r = assess_earnings_quality(self._clean())
        assert r is not None
        assert r.accrual_quality == AccrualQuality.CLEAN
        assert r.quality_score >= 80
        assert len(r.red_flags) == 0

    def test_aggressive_company_flags(self):
        r = assess_earnings_quality(self._aggressive())
        assert r is not None
        assert r.quality_score < 60
        assert len(r.red_flags) > 0

    def test_insufficient_data_returns_none(self):
        r = assess_earnings_quality([{"net_income": 10e9}])
        assert r is None

    def test_cash_conversion_ratio(self):
        r = assess_earnings_quality(self._clean())
        assert r.cash_conversion_ratio is not None
        assert r.cash_conversion_ratio > 1.0

    def test_serialization(self):
        r = assess_earnings_quality(self._clean())
        d = r.to_dict()
        assert "quality_score" in d
        assert "red_flags" in d
        assert "accrual_quality" in d


# =============================================================================
# Football Field with DDM + Minority-Adjusted
# =============================================================================

class TestFootballFieldEnhancements:
    def test_ddm_bar_included(self):
        r = build_football_field(
            current_price=100.0,
            dcf_bear=80, dcf_base=110, dcf_bull=140,
            ddm_value=95.0,
        )
        methods = [rng.method for rng in r.ranges]
        assert "DDM" in methods
        ddm_range = [rng for rng in r.ranges if rng.method == "DDM"][0]
        assert ddm_range.mid == 95.0

    def test_minority_adjusted_bars(self):
        r = build_football_field(
            current_price=100.0,
            precedent_ev_revenue=120.0,
            precedent_minority_ev_revenue=96.0,
        )
        methods = [rng.method for rng in r.ranges]
        assert "M&A - EV/Revenue" in methods
        assert "M&A - EV/Rev (minority)" in methods

    def test_no_ddm_when_none(self):
        r = build_football_field(current_price=100.0, dcf_base=110)
        methods = [rng.method for rng in r.ranges]
        assert "DDM" not in methods


# =============================================================================
# ROIC Fix (NOPAT-based) + DuPont
# =============================================================================

class TestROICFix:
    def test_dupont_fields_exist(self):
        r = FinancialRatios(period="2024", fiscal_year=2024)
        assert hasattr(r, "dupont_tax_burden")
        assert hasattr(r, "dupont_interest_burden")
        assert hasattr(r, "dupont_operating_margin")
        assert hasattr(r, "dupont_asset_turnover")
        assert hasattr(r, "dupont_equity_multiplier")

    def test_dupont_in_to_dict(self):
        r = FinancialRatios(
            period="2024", fiscal_year=2024,
            dupont_tax_burden=0.75,
            dupont_interest_burden=0.90,
            dupont_operating_margin=0.20,
            dupont_asset_turnover=0.80,
            dupont_equity_multiplier=2.0,
        )
        d = r.to_dict()
        assert "dupont" in d
        assert d["dupont"]["tax_burden"] == 0.75
        assert d["dupont"]["equity_multiplier"] == 2.0

    def test_interest_coverage_field(self):
        r = FinancialRatios(
            period="2024", fiscal_year=2024, interest_coverage=8.5,
        )
        assert r.interest_coverage == 8.5
