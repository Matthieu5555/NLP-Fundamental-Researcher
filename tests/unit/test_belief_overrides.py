"""Tests for analyst belief override parser.

Covers:
- _compute_dirty_stages: cascade rules, conviction always added
- _validate_dcf_overrides: bounds checking for WACC, TGR, FCF margin, growth
- _format_qualitative_directives: output shape and content
- AnalysisOverrides: dataclass defaults
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: pre-register the valuation.constants module to avoid the
# circular import chain that _validate_dcf_overrides triggers when it
# does `from src_george_researcher.valuation.constants import ...`.
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


# Pre-register constants so the lazy import inside _validate_dcf_overrides
# resolves without triggering the full valuation __init__.py chain.
_load(_ROOT / "valuation" / "constants.py", "src_george_researcher.valuation.constants")

from backend.core.belief_overrides import (
    _compute_dirty_stages,
    _validate_dcf_overrides,
    _format_qualitative_directives,
    AnalysisOverrides,
    INSIGHT_TYPE_TO_DIRTY_STAGES,
    SECTION_TO_STAGE,
    STAGE_CASCADE,
)

# Restore sys.modules so stubs don't leak into other test files.
for _key in set(sys.modules) - set(_SNAPSHOT):
    del sys.modules[_key]
from backend.core.report_builder import AnalystSource


def _make_source(
    insight_type: str = "confirmed_fact",
    section: str = "recommendation",
    belief: str = "test belief",
) -> AnalystSource:
    """Create a minimal AnalystSource for testing."""
    return AnalystSource(
        id="A1",
        belief_content=belief,
        insight_type=insight_type,
        section=section,
    )


# =============================================================================
# _compute_dirty_stages
# =============================================================================

class TestComputeDirtyStages:
    """Dirty stage determination and cascade logic."""

    def test_empty_sources_returns_empty(self):
        assert _compute_dirty_stages([]) == set()

    def test_conviction_always_added(self):
        src = _make_source(insight_type="confirmed_fact", section="recommendation")
        dirty = _compute_dirty_stages([src])
        assert "conviction" in dirty

    def test_valuation_view_dirties_dcf_family(self):
        src = _make_source(insight_type="valuation_view")
        dirty = _compute_dirty_stages([src])
        assert {"dcf", "sensitivity", "scenarios", "football_field"}.issubset(dirty)

    def test_risk_identified_dirties_bull_bear_and_recommendation(self):
        src = _make_source(insight_type="risk_identified")
        dirty = _compute_dirty_stages([src])
        assert "bull_bear" in dirty
        assert "recommendation" in dirty

    def test_competitive_dirties_moat_and_cascades(self):
        src = _make_source(insight_type="competitive")
        dirty = _compute_dirty_stages([src])
        assert "moat" in dirty
        assert "strategic_assessment" in dirty
        # Moat cascades to bull_bear and recommendation
        assert "bull_bear" in dirty
        assert "recommendation" in dirty

    def test_section_targeting_adds_stage(self):
        src = _make_source(insight_type="new_insight", section="strategy")
        dirty = _compute_dirty_stages([src])
        assert "strategy" in dirty
        # Strategy cascades to bull_bear and recommendation
        assert "bull_bear" in dirty
        assert "recommendation" in dirty

    def test_dcf_cascades_to_sensitivity_scenarios_football(self):
        """DCF being dirty should cascade."""
        src = _make_source(insight_type="valuation_view")
        dirty = _compute_dirty_stages([src])
        assert "sensitivity" in dirty
        assert "scenarios" in dirty
        assert "football_field" in dirty

    def test_strategic_assessment_section_full_cascade(self):
        src = _make_source(insight_type="new_insight", section="industry")
        dirty = _compute_dirty_stages([src])
        assert "strategic_assessment" in dirty
        # strategic_assessment cascades to dcf, sensitivity, scenarios, football_field, bull_bear, recommendation
        for stage in ["dcf", "sensitivity", "scenarios", "football_field", "bull_bear", "recommendation"]:
            assert stage in dirty, f"Expected '{stage}' in dirty stages"

    def test_multiple_sources_combine(self):
        src1 = _make_source(insight_type="risk_identified")
        src2 = _make_source(insight_type="valuation_view")
        dirty = _compute_dirty_stages([src1, src2])
        assert "bull_bear" in dirty
        assert "dcf" in dirty


# =============================================================================
# _validate_dcf_overrides
# =============================================================================

class TestValidateDCFOverrides:
    """Bounds checking for analyst DCF overrides."""

    def test_empty_overrides_no_warnings(self):
        assert _validate_dcf_overrides({}) == []

    def test_wacc_below_min_warns(self):
        warnings = _validate_dcf_overrides({"wacc": 0.03})
        assert len(warnings) == 1
        assert "WACC" in warnings[0]

    def test_wacc_above_max_warns(self):
        warnings = _validate_dcf_overrides({"wacc": 0.25})
        assert len(warnings) == 1
        assert "WACC" in warnings[0]

    def test_wacc_within_bounds_no_warning(self):
        warnings = _validate_dcf_overrides({"wacc": 0.10})
        assert len(warnings) == 0

    def test_terminal_growth_below_floor_warns(self):
        warnings = _validate_dcf_overrides({"terminal_growth_rate": 0.001})
        assert len(warnings) == 1
        assert "Terminal growth" in warnings[0]

    def test_terminal_growth_at_floor_no_warning(self):
        warnings = _validate_dcf_overrides({"terminal_growth_rate": 0.005})
        assert len(warnings) == 0

    def test_fcf_margin_below_min_warns(self):
        warnings = _validate_dcf_overrides({"fcf_margin": -0.60})
        assert len(warnings) == 1
        assert "FCF margin" in warnings[0]

    def test_fcf_margin_above_max_warns(self):
        warnings = _validate_dcf_overrides({"fcf_margin": 0.90})
        assert len(warnings) == 1
        assert "FCF margin" in warnings[0]

    def test_fcf_margin_within_bounds_no_warning(self):
        warnings = _validate_dcf_overrides({"fcf_margin": 0.20})
        assert len(warnings) == 0

    def test_revenue_growth_exceeding_max(self):
        warnings = _validate_dcf_overrides({
            "revenue_growth_rates": [0.60, 0.10, 0.10, 0.10, 0.10]
        })
        assert len(warnings) == 1
        assert "year 1" in warnings[0]

    def test_revenue_growth_negative_exceeding_max(self):
        warnings = _validate_dcf_overrides({
            "revenue_growth_rates": [0.10, 0.10, -0.55, 0.10, 0.10]
        })
        assert len(warnings) == 1
        assert "year 3" in warnings[0]

    def test_multiple_violations(self):
        warnings = _validate_dcf_overrides({
            "wacc": 0.03,
            "terminal_growth_rate": 0.001,
            "fcf_margin": 0.90,
        })
        assert len(warnings) == 3


# =============================================================================
# _format_qualitative_directives
# =============================================================================

class TestFormatQualitativeDirectives:
    """Qualitative directive formatting."""

    def test_empty_returns_empty(self):
        assert _format_qualitative_directives([]) == ""

    def test_single_source(self):
        src = _make_source(insight_type="risk_identified", belief="Debt is too high")
        result = _format_qualitative_directives([src])
        assert "ANALYST DIRECTIVES" in result
        assert "Debt is too high" in result
        assert "RISK IDENTIFIED" in result

    def test_multiple_sources(self):
        sources = [
            _make_source(insight_type="confirmed_fact", belief="Revenue is growing"),
            _make_source(insight_type="opportunity", belief="Expansion into Asia"),
        ]
        result = _format_qualitative_directives(sources)
        assert "Revenue is growing" in result
        assert "Expansion into Asia" in result
        assert "CONFIRMED FACT" in result
        assert "OPPORTUNITY" in result

    def test_header_present(self):
        src = _make_source()
        result = _format_qualitative_directives([src])
        assert "non-negotiable" in result.lower()


# =============================================================================
# AnalysisOverrides dataclass
# =============================================================================

class TestAnalysisOverrides:
    """AnalysisOverrides default state."""

    def test_defaults(self):
        ao = AnalysisOverrides()
        assert ao.dcf_overrides == {}
        assert ao.qualitative_directives == ""
        assert ao.dirty_stages == set()
        assert ao.warnings == []
