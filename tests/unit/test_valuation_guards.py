"""Tests for valuation subsection guard consistency.

The frontend ValuationTab.jsx uses `has*` boolean guards to decide whether to
render each subsection heading. Each child component has its own null-return
guard. If the parent shows a heading but the child returns null, the user sees
an orphaned heading above empty space.

These tests verify two things:
1. The backend valuation_display module handles empty/partial data gracefully.
2. The guard logic in ValuationTab.jsx (replicated here in Python) never admits
   data that the child component would reject, for every edge-case shape the
   backend can produce.
"""

import pytest
import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap valuation_display without full backend import chain
# ---------------------------------------------------------------------------
_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"

sys.path.insert(0, str(_BACKEND.parent))
from backend.core.valuation_display import (
    build_valuation_display,
    _build_football_field,
    _build_dcf_summary,
    _build_scenario_summary,
    _build_sensitivity_grid,
    _build_earnings_table,
    _build_precedent_summary,
)


# =============================================================================
# Python replicas of the JS guard logic from ValuationTab.jsx
# =============================================================================

def js_has_football_field(football_field_data, sections_football_field):
    """Mirrors: (footballFieldData?.ranges?.length > 0) || sections.football_field"""
    data_ok = (
        football_field_data is not None
        and isinstance(football_field_data.get("ranges"), list)
        and len(football_field_data["ranges"]) > 0
    )
    return data_ok or bool(sections_football_field)


def js_has_earnings(earnings_model_data, sections_earnings_model):
    """Mirrors: (earningsModelData?.rows?.length > 0) || sections.earnings_model"""
    data_ok = (
        earnings_model_data is not None
        and isinstance(earnings_model_data.get("rows"), list)
        and len(earnings_model_data["rows"]) > 0
    )
    return data_ok or bool(sections_earnings_model)


def js_has_sensitivity(sensitivity_data, sections_sensitivity):
    """Mirrors: (sensitivityData?.fair_value_grid && (wacc_values || growth_values) && (terminal_growth_values || margin_values)) || sections.sensitivity"""
    if sensitivity_data is not None:
        has_grid = bool(sensitivity_data.get("fair_value_grid"))
        has_rows = bool(sensitivity_data.get("wacc_values") or sensitivity_data.get("growth_values"))
        has_cols = bool(sensitivity_data.get("terminal_growth_values") or sensitivity_data.get("margin_values"))
        if has_grid and has_rows and has_cols:
            return True
    return bool(sections_sensitivity)


def js_has_growth_margin(data):
    """Mirrors: data?.fair_value_grid && (wacc_values || growth_values) && (terminal_growth_values || margin_values)"""
    if data is None:
        return False
    has_grid = bool(data.get("fair_value_grid"))
    has_rows = bool(data.get("wacc_values") or data.get("growth_values"))
    has_cols = bool(data.get("terminal_growth_values") or data.get("margin_values"))
    return has_grid and has_rows and has_cols


def child_football_field_renders(data):
    """Mirrors FootballField.jsx guards: !footballFieldData -> null, then !ranges || ranges.length === 0 -> null"""
    if not data:
        return False
    ranges = data.get("ranges")
    return isinstance(ranges, list) and len(ranges) > 0


def child_earnings_renders(data):
    """Mirrors EarningsModelTable.jsx: if (!earningsModelData?.rows?.length) return null"""
    if not data:
        return False
    rows = data.get("rows")
    return isinstance(rows, list) and len(rows) > 0


def child_sensitivity_renders(data):
    """Mirrors SensitivityGrid.jsx: !sensitivityData -> null, then !rowValues || !colValues || !grid -> null"""
    if not data:
        return False
    row_values = data.get("wacc_values") or data.get("growth_values")
    col_values = data.get("terminal_growth_values") or data.get("margin_values")
    grid = data.get("fair_value_grid")
    return bool(row_values) and bool(col_values) and bool(grid)


def child_precedent_renders(data):
    """Mirrors PrecedentTransactionTable.jsx: if (!precedentData?.deals?.length) return null"""
    if not data:
        return False
    deals = data.get("deals")
    return isinstance(deals, list) and len(deals) > 0


# =============================================================================
# Guard Parity Tests: parent guard never shows heading when child returns null
# =============================================================================

class TestFootballFieldGuardParity:
    """If js_has_football_field passes on data (not fallback), child must also render."""

    @pytest.mark.parametrize("data", [
        None,
        {},
        {"ranges": None},
        {"ranges": []},
        {"ranges": [], "current_price": 100},
    ])
    def test_empty_data_rejected_by_both(self, data):
        parent = js_has_football_field(data, None)
        child = child_football_field_renders(data)
        assert not parent, f"Parent admitted {data!r} but child would return null"
        assert not child

    def test_valid_data_accepted_by_both(self):
        data = {"ranges": [{"method": "DCF", "low": 80, "mid": 100, "high": 120}]}
        assert js_has_football_field(data, None)
        assert child_football_field_renders(data)

    def test_fallback_to_markdown_when_no_data(self):
        assert js_has_football_field(None, {"content": "some markdown"})
        assert js_has_football_field({"ranges": []}, {"content": "some markdown"})


class TestEarningsGuardParity:
    """If js_has_earnings passes on data (not fallback), child must also render."""

    @pytest.mark.parametrize("data", [
        None,
        {},
        {"rows": None},
        {"rows": []},
    ])
    def test_empty_data_rejected_by_both(self, data):
        parent = js_has_earnings(data, None)
        child = child_earnings_renders(data)
        assert not parent, f"Parent admitted {data!r} but child would return null"
        assert not child

    def test_valid_data_accepted_by_both(self):
        data = {"rows": [{"fiscal_year": 2024, "revenue": 1e9}]}
        assert js_has_earnings(data, None)
        assert child_earnings_renders(data)


class TestSensitivityGuardParity:
    """If js_has_sensitivity passes on data (not fallback), child must also render."""

    @pytest.mark.parametrize("data", [
        None,
        {},
        {"fair_value_grid": [[100]]},
        {"fair_value_grid": [[100]], "wacc_values": [0.08]},
        {"fair_value_grid": [[100]], "terminal_growth_values": [0.02]},
        {"wacc_values": [0.08], "terminal_growth_values": [0.02]},
        {"fair_value_grid": None, "wacc_values": [0.08], "terminal_growth_values": [0.02]},
        {"fair_value_grid": [], "wacc_values": [0.08], "terminal_growth_values": [0.02]},
    ])
    def test_incomplete_data_rejected_by_both(self, data):
        parent = js_has_sensitivity(data, None)
        child = child_sensitivity_renders(data)
        # If parent passes, child must also pass (no orphaned heading)
        if parent and not child:
            pytest.fail(f"MISMATCH: parent admitted {data!r} but child returns null")

    def test_complete_wacc_tgr_data_accepted(self):
        data = {
            "fair_value_grid": [[100, 110], [90, 100]],
            "wacc_values": [0.08, 0.10],
            "terminal_growth_values": [0.02, 0.03],
        }
        assert js_has_sensitivity(data, None)
        assert child_sensitivity_renders(data)

    def test_complete_growth_margin_data_accepted(self):
        data = {
            "fair_value_grid": [[100, 110], [90, 100]],
            "growth_values": [0.05, 0.10],
            "margin_values": [0.15, 0.20],
        }
        assert js_has_sensitivity(data, None)
        assert child_sensitivity_renders(data)

    def test_mixed_keys_missing_cols_rejected(self):
        """wacc_values present but neither terminal_growth_values nor margin_values."""
        data = {
            "fair_value_grid": [[100]],
            "wacc_values": [0.10],
        }
        assert not js_has_sensitivity(data, None)

    def test_null_wacc_with_grid_rejected(self):
        """fair_value_grid present but wacc_values is null."""
        data = {
            "fair_value_grid": [[100]],
            "wacc_values": None,
            "terminal_growth_values": [0.02],
        }
        assert not js_has_sensitivity(data, None)


class TestGrowthMarginGuardParity:
    """Growth/margin sensitivity has no markdown fallback, so guard must be tight."""

    @pytest.mark.parametrize("data", [
        None,
        {},
        {"fair_value_grid": [[100]]},
        {"fair_value_grid": [[100]], "growth_values": [0.05]},
        {"growth_values": [0.05], "margin_values": [0.15]},
    ])
    def test_incomplete_data_rejected(self, data):
        parent = js_has_growth_margin(data)
        child = child_sensitivity_renders(data)
        if parent and not child:
            pytest.fail(f"MISMATCH: parent admitted {data!r} but child returns null")

    def test_complete_data_accepted(self):
        data = {
            "fair_value_grid": [[100, 110], [90, 100]],
            "growth_values": [0.05, 0.10],
            "margin_values": [0.15, 0.20],
        }
        assert js_has_growth_margin(data)
        assert child_sensitivity_renders(data)


class TestPrecedentGuardParity:
    """Precedent already had a deep check; verify it still holds."""

    @pytest.mark.parametrize("data", [
        None,
        {},
        {"deals": None},
        {"deals": []},
    ])
    def test_empty_data_rejected(self, data):
        child = child_precedent_renders(data)
        assert not child

    def test_valid_deals_accepted(self):
        data = {"deals": [{"acquirer": "A", "target": "B"}]}
        assert child_precedent_renders(data)


# =============================================================================
# Backend valuation_display edge cases
# =============================================================================

class TestValuationDisplayEdgeCases:
    """Verify valuation_display module handles empty/partial data without crashing."""

    def test_empty_metadata(self):
        result = build_valuation_display({})
        assert result.dcf_summary == {}
        assert result.scenario_summary == {}
        assert result.football_ranges == []
        assert result.sensitivity_grid == {}
        assert result.earnings_table == {}
        assert result.precedent_summary == {}

    def test_football_field_empty_ranges(self):
        ranges, pct, price = _build_football_field({"ranges": []}, 100.0)
        assert ranges == []
        # pct is still computed from current_price alone (it's the only data point)
        assert price == 100.0

    def test_football_field_none_ranges(self):
        """Backend could theoretically store ranges: None instead of []."""
        ranges, pct, price = _build_football_field({"ranges": None}, 100.0)
        assert ranges == []

    def test_football_field_valid(self):
        data = {
            "ranges": [{"method": "DCF", "low": 80, "mid": 100, "high": 120}],
            "current_price": 95,
        }
        ranges, pct, price = _build_football_field(data, 95.0)
        assert len(ranges) == 1
        assert ranges[0]["method"] == "DCF"
        assert pct is not None

    def test_earnings_empty_rows(self):
        result = _build_earnings_table({"rows": []})
        assert result == {}

    def test_earnings_none(self):
        result = _build_earnings_table(None)
        assert result == {}

    def test_earnings_valid(self):
        result = _build_earnings_table({"rows": [{"fiscal_year": 2024, "revenue": 1e9}]})
        assert len(result["rows"]) == 1

    def test_sensitivity_empty_grid(self):
        result = _build_sensitivity_grid({"fair_value_grid": []}, 100.0)
        assert result.get("grid") == []

    def test_sensitivity_missing_keys(self):
        # Empty dict is falsy in Python, so the function short-circuits
        result = _build_sensitivity_grid({}, 100.0)
        assert result == {}

    def test_sensitivity_none(self):
        result = _build_sensitivity_grid(None, 100.0)
        assert result == {}

    def test_sensitivity_valid(self):
        data = {
            "wacc_values": [0.08, 0.10],
            "terminal_growth_values": [0.02, 0.03],
            "fair_value_grid": [[120, 130], [100, 110]],
        }
        result = _build_sensitivity_grid(data, 100.0)
        assert len(result["grid"]) == 2
        assert len(result["cell_classes"]) == 2

    def test_dcf_summary_empty(self):
        result = _build_dcf_summary({}, 100.0)
        assert result == {}

    def test_dcf_summary_none(self):
        result = _build_dcf_summary(None, 100.0)
        assert result == {}

    def test_scenario_summary_empty(self):
        result = _build_scenario_summary({}, 100.0)
        # Empty dict is falsy, so this should return minimal structure
        assert result == {}

    def test_precedent_empty_deals(self):
        result = _build_precedent_summary({"deals": []})
        assert result == {}

    def test_precedent_none(self):
        result = _build_precedent_summary(None)
        assert result == {}

    def test_precedent_with_deals(self):
        data = {
            "deals": [{"acquirer": "A", "target": "B"}],
            "median_ev_to_revenue": 2.5,
        }
        result = _build_precedent_summary(data)
        assert len(result["deals"]) == 1


class TestBuildValuationDisplayIntegration:
    """End-to-end test with realistic metadata shapes."""

    def test_full_metadata(self):
        metadata = {
            "dcf": {
                "fair_value_per_share": 150,
                "assumptions": {"wacc": 0.10, "terminal_growth_rate": 0.025},
            },
            "scenarios": {
                "bull": {"fair_value": 200, "probability": 0.25},
                "base": {"fair_value": 150, "probability": 0.50},
                "bear": {"fair_value": 100, "probability": 0.25},
                "weighted_fair_value": 150,
            },
            "football_field": {
                "ranges": [{"method": "DCF", "low": 120, "mid": 150, "high": 180}],
                "current_price": 130,
            },
            "sensitivity": {
                "wacc_values": [0.08, 0.10, 0.12],
                "terminal_growth_values": [0.02, 0.025, 0.03],
                "fair_value_grid": [[180, 160, 140], [160, 150, 130], [140, 130, 120]],
            },
            "earnings_model": {
                "rows": [
                    {"fiscal_year": 2023, "is_estimate": False, "revenue": 50e9},
                    {"fiscal_year": 2024, "is_estimate": True, "revenue": 55e9},
                ],
            },
            "precedents": {
                "deals": [{"acquirer": "BigCo", "target": "SmallCo"}],
                "median_ev_to_revenue": 3.0,
            },
        }
        result = build_valuation_display(metadata, current_price=130.0)
        assert result.dcf_summary["fair_value"] == 150
        assert len(result.football_ranges) == 1
        assert result.sensitivity_grid["grid"] is not None
        assert len(result.earnings_table["rows"]) == 2
        assert len(result.precedent_summary["deals"]) == 1

    def test_partial_metadata_no_crash(self):
        """Only DCF succeeded, everything else missing."""
        metadata = {
            "dcf": {
                "fair_value_per_share": 100,
                "assumptions": {"wacc": 0.10},
            },
        }
        result = build_valuation_display(metadata, current_price=90.0)
        assert result.dcf_summary["fair_value"] == 100
        assert result.football_ranges == []
        assert result.sensitivity_grid == {}
        assert result.earnings_table == {}
        assert result.precedent_summary == {}
