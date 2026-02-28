"""Tests for CFA-grade PDF quality fixes.

Covers:
- _parse_wacc_rationale: standard with/without size premium, garbage input, empty
- _build_dcf_summary: terminal_value, ev_bridge, projection_details, wacc_components
  (both direct dict and fallback parsing), tv_pct_of_ev
- _build_conviction: evidence field passthrough
- parse_strategy_grid: new keyword mappings
- deduplicate_fiscal_years: duplicate resolution
"""

import importlib

import pytest

from backend.core.valuation_display import (
    _parse_wacc_rationale,
    _build_dcf_summary,
    _build_conviction,
)

_has_markdown = importlib.util.find_spec("markdown") is not None
if _has_markdown:
    from backend.core.pdf_formatting import deduplicate_fiscal_years, parse_strategy_grid


# =============================================================================
# _parse_wacc_rationale
# =============================================================================

class TestParseWaccRationale:
    """Regex-based WACC rationale string parsing."""

    STANDARD_WITH_SP = (
        "WACC=9.5%: Ke=11.3% (Rf=4.3% + Beta=1.15 x ERP=5.5% + SP=0.5%), "
        "Kd=3.5% after-tax, E/(D+E)=80%"
    )
    STANDARD_NO_SP = (
        "WACC=8.8%: Ke=10.5% (Rf=4.3% + Beta=1.10 x ERP=5.5%), "
        "Kd=3.2% after-tax, E/(D+E)=85%"
    )

    def test_standard_rationale_with_size_premium(self):
        result = _parse_wacc_rationale(self.STANDARD_WITH_SP)
        assert result["wacc"] == pytest.approx(0.095, abs=1e-4)
        assert result["ke"] == pytest.approx(0.113, abs=1e-4)
        assert result["rf"] == pytest.approx(0.043, abs=1e-4)
        assert result["beta"] == pytest.approx(1.15, abs=1e-3)
        assert result["erp"] == pytest.approx(0.055, abs=1e-4)
        assert result["sp"] == pytest.approx(0.005, abs=1e-4)
        assert result["kd"] == pytest.approx(0.035, abs=1e-4)
        assert result["weight_equity"] == pytest.approx(0.80, abs=1e-3)
        assert result["weight_debt"] == pytest.approx(0.20, abs=1e-3)

    def test_standard_rationale_without_size_premium(self):
        result = _parse_wacc_rationale(self.STANDARD_NO_SP)
        assert result["wacc"] == pytest.approx(0.088, abs=1e-4)
        assert result["ke"] == pytest.approx(0.105, abs=1e-4)
        assert result["weight_equity"] == pytest.approx(0.85, abs=1e-3)
        assert "sp" not in result

    def test_garbage_input_returns_empty(self):
        assert _parse_wacc_rationale("not a rationale at all") == {}

    def test_empty_string_returns_empty(self):
        assert _parse_wacc_rationale("") == {}

    def test_none_returns_empty(self):
        assert _parse_wacc_rationale(None) == {}

    def test_partial_rationale_returns_empty(self):
        # Missing required components
        assert _parse_wacc_rationale("WACC=9.5%, Ke=11.3%") == {}


# =============================================================================
# _build_dcf_summary (expanded)
# =============================================================================

class TestBuildDcfSummaryExpanded:
    """Verify new fields extracted by _build_dcf_summary."""

    def _make_dcf_model(self, **overrides):
        base = {
            "fair_value_per_share": 338.0,
            "enterprise_value": 830e9,
            "terminal_value": 1200e9,
            "pv_terminal_value": 620e9,
            "equity_value": 815e9,
            "shares_outstanding": 2.41e9,
            "net_debt": 15e9,
            "ev_bridge": {
                "net_debt": 15e9,
                "minority_interest": 2e9,
                "preferred_stock": 0,
                "equity_investments": 3e9,
            },
            "projection_details": [
                {"year": 2025, "revenue": 400e9, "ebitda": 120e9,
                 "nopat": 80e9, "unlevered_fcf": 70e9, "discounted_fcf": 63e9},
            ],
            "assumptions": {
                "wacc": 0.095,
                "terminal_growth_rate": 0.03,
                "fcf_margin": 0.18,
                "revenue_growth_rates": [0.08],
                "wacc_rationale": (
                    "WACC=9.5%: Ke=11.3% (Rf=4.3% + Beta=1.15 x ERP=5.5% + SP=0.5%), "
                    "Kd=3.5% after-tax, E/(D+E)=80%"
                ),
                "terminal_growth_rationale": "In line with long-run GDP",
                "revenue_growth_rationale": "Cloud momentum",
            },
        }
        base.update(overrides)
        return base

    def test_terminal_value_passes_through(self):
        result = _build_dcf_summary(self._make_dcf_model(), 200.0)
        assert result["terminal_value"] == 1200e9

    def test_ev_bridge_passes_through(self):
        result = _build_dcf_summary(self._make_dcf_model(), 200.0)
        assert result["ev_bridge"]["net_debt"] == 15e9
        assert result["ev_bridge"]["minority_interest"] == 2e9

    def test_projection_details_passes_through(self):
        result = _build_dcf_summary(self._make_dcf_model(), 200.0)
        assert len(result["projection_details"]) == 1
        assert result["projection_details"][0]["year"] == 2025

    def test_tv_pct_of_ev_computed(self):
        result = _build_dcf_summary(self._make_dcf_model(), 200.0)
        expected = 620e9 / 830e9 * 100
        assert result["tv_pct_of_ev"] == pytest.approx(expected, abs=0.1)

    def test_tv_pct_of_ev_none_when_missing(self):
        model = self._make_dcf_model(pv_terminal_value=None)
        result = _build_dcf_summary(model, 200.0)
        assert result["tv_pct_of_ev"] is None

    def test_wacc_components_direct_dict(self):
        model = self._make_dcf_model(
            wacc_components={"wacc": 0.095, "ke": 0.113, "rf": 0.043,
                             "beta": 1.15, "erp": 0.055}
        )
        result = _build_dcf_summary(model, 200.0)
        assert result["wacc_components"]["wacc"] == 0.095

    def test_wacc_components_fallback_parsing(self):
        # No wacc_components key, should fall back to parsing rationale string
        model = self._make_dcf_model()
        assert "wacc_components" not in model  # not set at top level
        result = _build_dcf_summary(model, 200.0)
        assert result["wacc_components"]["wacc"] == pytest.approx(0.095, abs=1e-4)
        assert result["wacc_components"]["ke"] == pytest.approx(0.113, abs=1e-4)

    def test_empty_dcf_model_returns_empty(self):
        assert _build_dcf_summary({}, 200.0) == {}
        assert _build_dcf_summary(None, 200.0) == {}

    def test_rationale_fields_pass_through(self):
        result = _build_dcf_summary(self._make_dcf_model(), 200.0)
        assert result["terminal_growth_rationale"] == "In line with long-run GDP"
        assert result["revenue_growth_rationale"] == "Cloud momentum"


# =============================================================================
# _build_conviction with evidence
# =============================================================================

class TestBuildConvictionEvidence:
    """Verify evidence field passes through in conviction categories."""

    def test_evidence_included(self):
        data = {
            "overall_score": 75,
            "summary": "Strong conviction based on fundamentals.",
            "categories": [
                {"name": "Valuation", "score": 8, "evidence": "Trading below intrinsic value"},
                {"name": "Quality", "score": 7, "evidence": "Strong ROIC"},
            ],
        }
        _, categories = _build_conviction(data)
        assert len(categories) == 2
        assert categories[0]["evidence"] == "Trading below intrinsic value"
        assert categories[1]["evidence"] == "Strong ROIC"

    def test_missing_evidence_defaults_empty(self):
        data = {
            "categories": [
                {"name": "Valuation", "score": 8},
            ],
        }
        _, categories = _build_conviction(data)
        assert categories[0]["evidence"] == ""

    def test_empty_conviction_returns_empty(self):
        data, categories = _build_conviction({})
        assert data == {}
        assert categories == []


# =============================================================================
# parse_strategy_grid with new keywords
# =============================================================================

@pytest.mark.skipif(not _has_markdown, reason="markdown not installed")
class TestStrategyGridNewKeywords:
    """New keyword mappings for strategy grid parsing."""

    @pytest.fixture(autouse=True)
    def _import_parser(self):
        self.parse_strategy_grid = parse_strategy_grid

    def test_internal_capabilities_maps_to_advantages(self):
        content = "## Internal Capabilities\n- Strong R&D\n## Future Outlook\n- AI tailwind"
        result = self.parse_strategy_grid(content)
        assert result is not None
        assert result["advantages"] != ""
        assert result["tailwinds"] != ""

    def test_competitive_landscape_maps_to_headwinds(self):
        content = "## Competitive Landscape\n- Intense competition\n## Risks\n- Regulatory"
        result = self.parse_strategy_grid(content)
        assert result is not None
        assert result["headwinds"] != ""
        assert result["vulnerabilities"] != ""

    def test_growth_driver_maps_to_tailwinds(self):
        content = "## Growth Drivers\n- International expansion"
        result = self.parse_strategy_grid(content)
        assert result is not None
        assert result["tailwinds"] != ""

    def test_catalyst_maps_to_tailwinds(self):
        content = "## Catalysts\n- Product launch in Q3"
        result = self.parse_strategy_grid(content)
        assert result is not None
        assert result["tailwinds"] != ""

    def test_challenge_maps_to_vulnerabilities(self):
        content = "## Key Challenges\n- Supply chain disruption"
        result = self.parse_strategy_grid(content)
        assert result is not None
        assert result["vulnerabilities"] != ""

    def test_strategic_position_maps_to_advantages(self):
        content = "**Strategic Position**\n- Market leader\n**Concerns**\n- Margin pressure"
        result = self.parse_strategy_grid(content)
        assert result is not None
        assert result["advantages"] != ""
        assert result["vulnerabilities"] != ""


# =============================================================================
# deduplicate_fiscal_years
# =============================================================================

@pytest.mark.skipif(not _has_markdown, reason="markdown not installed")
class TestDeduplicateFiscalYears:
    """Fiscal year deduplication keeping last occurrence."""

    def test_duplicates_resolved(self):
        rows = [
            {"fiscal_year": 2023, "revenue": 100},
            {"fiscal_year": 2023, "revenue": 110},
            {"fiscal_year": 2024, "revenue": 120},
        ]
        result = deduplicate_fiscal_years(rows)
        assert len(result) == 2
        # Should keep the last 2023 entry (revenue=110)
        fy_2023 = [r for r in result if r["fiscal_year"] == 2023]
        assert fy_2023[0]["revenue"] == 110

    def test_no_duplicates_unchanged(self):
        rows = [
            {"fiscal_year": 2022, "revenue": 90},
            {"fiscal_year": 2023, "revenue": 100},
            {"fiscal_year": 2024, "revenue": 110},
        ]
        result = deduplicate_fiscal_years(rows)
        assert len(result) == 3
        assert result == rows

    def test_empty_list(self):
        assert deduplicate_fiscal_years([]) == []

    def test_missing_fiscal_year_key(self):
        rows = [{"revenue": 100}, {"revenue": 110}]
        # fiscal_year is None for all, so they're all "same" key
        result = deduplicate_fiscal_years(rows)
        assert len(result) == 1
        assert result[0]["revenue"] == 110
