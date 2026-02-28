"""Tests for sensitivity analysis grids.

Covers:
- WACC x Terminal Growth Rate sensitivity grid: shape, center cell, monotonicity
- Revenue Growth x Operating Margin sensitivity grid: shape, monotonicity
- format_sensitivity_markdown: output structure
"""

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load modules individually to avoid the circular import chain
# through yfinance and analysis.__init__.py.
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent.parent / "src_george_researcher"

# Snapshot sys.modules before adding stubs; restored after loading.
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


# Stub analysis_agents to avoid heavy import chain
_analysis_agents = types.ModuleType("src_george_researcher.analysis_agents")


@dataclass(frozen=True)
class _StubAnalysisResult:
    section: str = ""
    content: str = ""
    tokens_used: int = 0
    success: bool = True
    error: Optional[str] = None
    cost_usd: float = 0.0


_analysis_agents.AnalysisResult = _StubAnalysisResult
sys.modules["src_george_researcher.analysis_agents"] = _analysis_agents

# Load in dependency order
_load(_ROOT / "valuation" / "constants.py", "src_george_researcher.valuation.constants")
_load(_ROOT / "valuation" / "overrides.py", "src_george_researcher.valuation.overrides")
_load(_ROOT / "valuation" / "dcf_engine.py", "src_george_researcher.valuation.dcf_engine")
_load(_ROOT / "valuation" / "sensitivity.py", "src_george_researcher.valuation.sensitivity")

from src_george_researcher.valuation.dcf_engine import DCFAssumptions, DCFResult, calculate_dcf
from src_george_researcher.valuation.sensitivity import (
    run_sensitivity,
    run_growth_margin_sensitivity,
    format_sensitivity_markdown,
    SensitivityResult,
)

# Restore sys.modules so stubs don't leak into other test files.
for _key in set(sys.modules) - set(_SNAPSHOT):
    del sys.modules[_key]


def _make_base_dcf() -> DCFResult:
    """Create a base DCF result for testing sensitivity grids."""
    assumptions = DCFAssumptions(
        revenue_growth_rates=[0.10, 0.09, 0.08, 0.07, 0.06],
        fcf_margin=0.15,
        wacc=0.10,
        terminal_growth_rate=0.025,
    )
    return calculate_dcf(
        base_revenue=10e9,
        net_debt=2e9,
        shares_outstanding=1e9,
        current_price=120.0,
        assumptions=assumptions,
    )


class TestWACCTGRSensitivity:
    """WACC x Terminal Growth Rate sensitivity grid."""

    def test_grid_is_5x5(self):
        result = run_sensitivity(_make_base_dcf())
        assert len(result.fair_value_grid) == 5
        for row in result.fair_value_grid:
            assert len(row) == 5

    def test_five_wacc_values(self):
        result = run_sensitivity(_make_base_dcf())
        assert len(result.wacc_values) == 5

    def test_five_tgr_values(self):
        result = run_sensitivity(_make_base_dcf())
        assert len(result.terminal_growth_values) == 5

    def test_base_indices_are_center(self):
        result = run_sensitivity(_make_base_dcf())
        assert result.base_wacc_idx == 2
        assert result.base_tgr_idx == 2

    def test_center_cell_equals_base_dcf(self):
        dcf = _make_base_dcf()
        result = run_sensitivity(dcf)
        center_value = result.fair_value_grid[2][2]
        assert abs(center_value - dcf.fair_value_per_share) < 0.01

    def test_higher_wacc_lowers_value(self):
        """Moving down rows (higher WACC) should decrease fair values."""
        result = run_sensitivity(_make_base_dcf())
        for j in range(5):
            for i in range(4):
                # Skip zero-value cells (where tgr >= wacc)
                if result.fair_value_grid[i][j] > 0 and result.fair_value_grid[i + 1][j] > 0:
                    assert result.fair_value_grid[i][j] >= result.fair_value_grid[i + 1][j], (
                        f"WACC monotonicity violated at row {i}, col {j}: "
                        f"{result.fair_value_grid[i][j]} < {result.fair_value_grid[i + 1][j]}"
                    )

    def test_higher_tgr_raises_value(self):
        """Moving right columns (higher TGR) should increase fair values."""
        result = run_sensitivity(_make_base_dcf())
        for i in range(5):
            for j in range(4):
                if result.fair_value_grid[i][j] > 0 and result.fair_value_grid[i][j + 1] > 0:
                    assert result.fair_value_grid[i][j] <= result.fair_value_grid[i][j + 1], (
                        f"TGR monotonicity violated at row {i}, col {j}: "
                        f"{result.fair_value_grid[i][j]} > {result.fair_value_grid[i][j + 1]}"
                    )

    def test_wacc_values_are_sorted_ascending(self):
        result = run_sensitivity(_make_base_dcf())
        for i in range(4):
            assert result.wacc_values[i] <= result.wacc_values[i + 1]

    def test_to_dict_keys(self):
        result = run_sensitivity(_make_base_dcf())
        d = result.to_dict()
        expected = {"wacc_values", "terminal_growth_values", "fair_value_grid",
                    "base_wacc_idx", "base_tgr_idx", "current_price"}
        assert set(d.keys()) == expected

    def test_current_price_preserved(self):
        result = run_sensitivity(_make_base_dcf())
        assert result.current_price == 120.0


class TestGrowthMarginSensitivity:
    """Revenue Growth x Operating Margin sensitivity grid."""

    def test_grid_is_5x5(self):
        result = run_growth_margin_sensitivity(_make_base_dcf())
        assert len(result.fair_value_grid) == 5
        for row in result.fair_value_grid:
            assert len(row) == 5

    def test_base_indices_are_center(self):
        result = run_growth_margin_sensitivity(_make_base_dcf())
        assert result.base_growth_idx == 2
        assert result.base_margin_idx == 2

    def test_higher_margin_raises_value(self):
        """Moving right (higher margin) should increase fair values."""
        result = run_growth_margin_sensitivity(_make_base_dcf())
        for i in range(5):
            for j in range(4):
                if result.fair_value_grid[i][j] > 0 and result.fair_value_grid[i][j + 1] > 0:
                    assert result.fair_value_grid[i][j] <= result.fair_value_grid[i][j + 1], (
                        f"Margin monotonicity violated at row {i}, col {j}"
                    )

    def test_higher_growth_raises_value(self):
        """Moving down (higher growth) should increase fair values."""
        result = run_growth_margin_sensitivity(_make_base_dcf())
        for j in range(5):
            for i in range(4):
                if result.fair_value_grid[i][j] > 0 and result.fair_value_grid[i + 1][j] > 0:
                    assert result.fair_value_grid[i][j] <= result.fair_value_grid[i + 1][j], (
                        f"Growth monotonicity violated at row {i}, col {j}"
                    )


class TestFormatSensitivityMarkdown:
    """Markdown formatting of sensitivity results."""

    def test_contains_table_markers(self):
        result = run_sensitivity(_make_base_dcf())
        md = format_sensitivity_markdown(result)
        assert "|" in md
        assert "WACC" in md

    def test_contains_current_price(self):
        result = run_sensitivity(_make_base_dcf())
        md = format_sensitivity_markdown(result)
        assert "$120.00" in md

    def test_base_case_is_bold(self):
        result = run_sensitivity(_make_base_dcf())
        md = format_sensitivity_markdown(result)
        assert "**$" in md
