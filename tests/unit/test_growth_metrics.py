"""Tests for financial growth metrics computation.

Covers:
- _compute_pct_change: percentage change with edge cases
- _compute_margin: margin ratio calculation
- _compute_cagr: compound annual growth rate
- GrowthMetric: properties (yoy_pct, yoy_color, etc.)
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent.parent / "src_george_researcher"

_SNAPSHOT = dict(sys.modules)

if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = types.ModuleType("yfinance")


def _load(file_path: Path, module_name: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Ensure parent packages exist in sys.modules
for pkg in [
    "src_george_researcher",
    "src_george_researcher.analysis",
    "src_george_researcher.analysis.shared",
]:
    sys.modules.setdefault(pkg, types.ModuleType(pkg))

# Force-load the real module even if a stub was registered by another test file.
# This can happen when test_valuation_math.py runs before this file in the same session.
_mod_name = "src_george_researcher.analysis.shared.growth_metrics"
if _mod_name in sys.modules:
    _existing = sys.modules[_mod_name]
    if not hasattr(_existing, "_compute_pct_change"):
        # It's a stub, replace it with the real module
        del sys.modules[_mod_name]

_load(
    _ROOT / "analysis" / "shared" / "growth_metrics.py",
    _mod_name,
)

from src_george_researcher.analysis.shared.growth_metrics import (
    _compute_pct_change,
    _compute_margin,
    _compute_cagr,
    GrowthMetric,
)

# Restore sys.modules so stubs don't leak into other test files.
for _key in set(sys.modules) - set(_SNAPSHOT):
    del sys.modules[_key]


class TestComputePctChange:
    """Percentage change calculation."""

    def test_positive_growth(self):
        # 100 -> 115 = +15%
        result = _compute_pct_change(115.0, 100.0)
        assert abs(result - 0.15) < 1e-10

    def test_negative_growth(self):
        # 100 -> 90 = -10%
        result = _compute_pct_change(90.0, 100.0)
        assert abs(result - (-0.10)) < 1e-10

    def test_zero_previous_returns_none(self):
        assert _compute_pct_change(100.0, 0.0) is None

    def test_none_current_returns_none(self):
        assert _compute_pct_change(None, 100.0) is None

    def test_none_previous_returns_none(self):
        assert _compute_pct_change(100.0, None) is None

    def test_both_none_returns_none(self):
        assert _compute_pct_change(None, None) is None

    def test_negative_previous(self):
        # -100 -> -50: change is (-50 - (-100)) / abs(-100) = 50/100 = +0.5
        result = _compute_pct_change(-50.0, -100.0)
        assert abs(result - 0.5) < 1e-10

    def test_no_change(self):
        result = _compute_pct_change(100.0, 100.0)
        assert abs(result) < 1e-10


class TestComputeMargin:
    """Margin ratio calculation."""

    def test_positive_margin(self):
        # 30 / 100 = 0.30
        result = _compute_margin(30.0, 100.0)
        assert abs(result - 0.30) < 1e-10

    def test_zero_denominator_returns_none(self):
        assert _compute_margin(30.0, 0.0) is None

    def test_none_numerator_returns_none(self):
        assert _compute_margin(None, 100.0) is None

    def test_none_denominator_returns_none(self):
        assert _compute_margin(30.0, None) is None

    def test_negative_margin(self):
        result = _compute_margin(-10.0, 100.0)
        assert abs(result - (-0.10)) < 1e-10


class TestComputeCAGR:
    """Compound Annual Growth Rate calculation."""

    def test_positive_cagr(self):
        # 100 -> 121 over 2 years: CAGR = (121/100)^(1/2) - 1 = 0.10
        result = _compute_cagr(100.0, 121.0, 2)
        assert abs(result - 0.10) < 0.001

    def test_negative_cagr(self):
        # 100 -> 81 over 2 years: CAGR = (81/100)^(1/2) - 1 = -0.10
        result = _compute_cagr(100.0, 81.0, 2)
        assert abs(result - (-0.10)) < 0.001

    def test_one_year(self):
        # 100 -> 115 over 1 year = 15%
        result = _compute_cagr(100.0, 115.0, 1)
        assert abs(result - 0.15) < 1e-10

    def test_zero_start_returns_none(self):
        assert _compute_cagr(0.0, 100.0, 3) is None

    def test_negative_start_returns_none(self):
        assert _compute_cagr(-100.0, 200.0, 3) is None

    def test_zero_years_returns_none(self):
        assert _compute_cagr(100.0, 200.0, 0) is None

    def test_none_values_return_none(self):
        assert _compute_cagr(None, 200.0, 3) is None
        assert _compute_cagr(100.0, None, 3) is None


class TestGrowthMetric:
    """GrowthMetric dataclass properties."""

    def test_yoy_pct_positive(self):
        m = GrowthMetric("Revenue", 100.0, yoy_change=0.152)
        assert m.yoy_pct == "+15.2%"

    def test_yoy_pct_negative(self):
        m = GrowthMetric("Revenue", 100.0, yoy_change=-0.031)
        assert m.yoy_pct == "-3.1%"

    def test_yoy_pct_none(self):
        m = GrowthMetric("Revenue", 100.0)
        assert m.yoy_pct is None

    def test_qoq_pct(self):
        m = GrowthMetric("Revenue", 100.0, qoq_change=0.05)
        assert m.qoq_pct == "+5.0%"

    def test_yoy_color_green(self):
        m = GrowthMetric("Revenue", 100.0, yoy_change=0.05)
        assert m.yoy_color == "green"

    def test_yoy_color_red(self):
        m = GrowthMetric("Revenue", 100.0, yoy_change=-0.05)
        assert m.yoy_color == "red"

    def test_yoy_color_neutral(self):
        m = GrowthMetric("Revenue", 100.0, yoy_change=0.005)
        assert m.yoy_color == "neutral"

    def test_yoy_color_none(self):
        m = GrowthMetric("Revenue", 100.0)
        assert m.yoy_color == "neutral"

    def test_to_dict(self):
        m = GrowthMetric("Revenue", 100e9, yoy_change=0.10)
        d = m.to_dict()
        assert d["name"] == "Revenue"
        assert d["value"] == 100e9
        assert d["yoy_change"] == 0.10
        assert d["yoy_pct"] == "+10.0%"
        assert d["yoy_color"] == "green"
