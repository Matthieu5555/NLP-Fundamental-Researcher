"""Tests for conviction parsing, precedent transaction parsing, and earnings model.

Covers:
- _parse_conviction: score thresholds, clamping, code-fenced JSON, malformed input
- format_conviction_markdown: output structure
- PrecedentDeal / PrecedentTransactionResult: dataclass serialization
- EarningsModelRow: dataclass fields
"""

import importlib.util
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load target modules via importlib, then restore sys.modules so
# stubs don't leak into other test files (e.g. test_imports.py).
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent.parent / "src_george_researcher"

# Snapshot sys.modules before we add any stubs.
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


def _make_pkg(name: str, path: str):
    """Register a stub package with __path__ so sub-imports resolve."""
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = [path]
        sys.modules[name] = pkg


def _make_mod(name: str):
    """Register an empty stub leaf module."""
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


# Stub analysis_agents
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
sys.modules.setdefault("src_george_researcher.analysis_agents", _analysis_agents)

# Stub data_fetchers hierarchy
_make_pkg("src_george_researcher.data_fetchers", str(_ROOT / "data_fetchers"))
_make_pkg("src_george_researcher.data_fetchers.us", str(_ROOT / "data_fetchers" / "us"))
_make_mod("src_george_researcher.data_fetchers.stock_data")
_make_mod("src_george_researcher.data_fetchers.us.financial_datasets_client")

# StockInfo stub for conviction.py
_stock_data = sys.modules["src_george_researcher.data_fetchers.stock_data"]


@dataclass
class _StubStockInfo:
    symbol: str = "AAPL"
    name: str = "Apple"
    sector: str = "Technology"
    current_price: float = 185.0
    market_cap: float = 3e12


_stock_data.StockInfo = _StubStockInfo
_stock_data.fetch_stock_info = lambda *a, **kw: None

# Stub for AnalystEstimate used by earnings_model.py
_fds = sys.modules["src_george_researcher.data_fetchers.us.financial_datasets_client"]


@dataclass
class _StubAnalystEstimate:
    fiscal_year: int = 2025
    fiscal_quarter: Optional[int] = None
    revenue_estimate: Optional[float] = None
    eps_estimate: Optional[float] = None
    ebitda_estimate: Optional[float] = None


_fds.AnalystEstimate = _StubAnalystEstimate

# Stub LLM and prompts for conviction.py
_make_mod("src_george_researcher.llm")
_make_mod("src_george_researcher.prompts")
sys.modules["src_george_researcher.prompts"].CONVICTION_SYSTEM = "stub"

# Load shared parsing (conviction.py imports it for code-fence stripping)
_make_pkg("src_george_researcher.analysis", str(_ROOT / "analysis"))
_make_pkg("src_george_researcher.analysis.shared", str(_ROOT / "analysis" / "shared"))
_load(_ROOT / "analysis" / "shared" / "parsing.py", "src_george_researcher.analysis.shared.parsing")

# Load valuation modules
_load(_ROOT / "valuation" / "constants.py", "src_george_researcher.valuation.constants")
_load(_ROOT / "valuation" / "overrides.py", "src_george_researcher.valuation.overrides")
_load(_ROOT / "valuation" / "dcf_engine.py", "src_george_researcher.valuation.dcf_engine")
_load(_ROOT / "valuation" / "exceptions.py", "src_george_researcher.valuation.exceptions")
_load(_ROOT / "valuation" / "comp_table.py", "src_george_researcher.valuation.comp_table")
_load(_ROOT / "valuation" / "conviction.py", "src_george_researcher.valuation.conviction")
_load(_ROOT / "valuation" / "precedent_transactions.py", "src_george_researcher.valuation.precedent_transactions")

# Stub growth metrics for earnings model
_growth_metrics = types.ModuleType("src_george_researcher.analysis.shared.growth_metrics")


@dataclass
class _StubEnrichedFinancials:
    periods: list = None
    ticker: str = ""
    company_name: str = ""


_growth_metrics.EnrichedFinancials = _StubEnrichedFinancials
sys.modules.setdefault("src_george_researcher.analysis.shared.growth_metrics", _growth_metrics)

_load(_ROOT / "valuation" / "earnings_model.py", "src_george_researcher.valuation.earnings_model")

# Grab references to everything we need BEFORE restoring sys.modules.
from src_george_researcher.valuation.conviction import (
    _parse_conviction,
    format_conviction_markdown,
    ConvictionResult,
    ConvictionCategory,
)
from src_george_researcher.valuation.exceptions import AssumptionParseError
from src_george_researcher.valuation.dcf_engine import compute_wacc
from src_george_researcher.valuation.precedent_transactions import (
    PrecedentDeal,
    PrecedentTransactionResult,
    _normalize_premium,
    _normalize_multiple,
)
from src_george_researcher.valuation.earnings_model import EarningsModelRow

# ---------------------------------------------------------------------------
# Restore sys.modules: remove every key we added that wasn't in the snapshot.
# This prevents our stubs from breaking test_imports.py and other tests.
# ---------------------------------------------------------------------------
_added = set(sys.modules) - set(_SNAPSHOT)
for _key in _added:
    del sys.modules[_key]


# =============================================================================
# Conviction Parsing
# =============================================================================

class TestParseConviction:
    """Parse LLM JSON into ConvictionResult."""

    def _valid_json(self, overall_score=75, confidence=80):
        return json.dumps({
            "overall_score": overall_score,
            "confidence": confidence,
            "categories": [
                {"name": "Valuation", "score": 70, "evidence": "Fair DCF upside"},
                {"name": "Fundamentals", "score": 80, "evidence": "Strong margins"},
            ],
            "summary": "Attractive risk-reward.",
        })

    def test_valid_json_parses(self):
        result = _parse_conviction(self._valid_json())
        assert result.overall_score == 75
        assert result.confidence == 80
        assert result.recommendation == "BUY"
        assert len(result.categories) == 2

    def test_score_above_50_is_buy(self):
        result = _parse_conviction(self._valid_json(overall_score=51))
        assert result.recommendation == "BUY"

    def test_score_at_50_is_sell(self):
        result = _parse_conviction(self._valid_json(overall_score=50))
        assert result.recommendation == "SELL"

    def test_score_below_50_is_sell(self):
        result = _parse_conviction(self._valid_json(overall_score=30))
        assert result.recommendation == "SELL"
        assert result.overall_score == 30

    def test_score_clamped_to_100(self):
        result = _parse_conviction(self._valid_json(overall_score=150))
        assert result.overall_score == 100

    def test_score_clamped_to_0(self):
        result = _parse_conviction(self._valid_json(overall_score=-10))
        assert result.overall_score == 0

    def test_confidence_clamped(self):
        result = _parse_conviction(self._valid_json(confidence=200))
        assert result.confidence == 100

    def test_code_fenced_json(self):
        text = f"```json\n{self._valid_json()}\n```"
        result = _parse_conviction(text)
        assert result.overall_score == 75

    def test_triple_backtick_json(self):
        text = f"```\n{self._valid_json()}\n```"
        result = _parse_conviction(text)
        assert result.overall_score == 75

    def test_malformed_json_raises(self):
        with pytest.raises(AssumptionParseError):
            _parse_conviction("not json at all {{{")

    def test_empty_categories(self):
        data = json.dumps({"overall_score": 60, "confidence": 70, "categories": [], "summary": "OK"})
        result = _parse_conviction(data)
        assert result.categories == []

    def test_category_scores_clamped(self):
        data = json.dumps({
            "overall_score": 60,
            "confidence": 70,
            "categories": [{"name": "Test", "score": 150, "evidence": "high"}],
            "summary": "OK",
        })
        result = _parse_conviction(data)
        assert result.categories[0].score == 100

    def test_markdown_preamble_with_json(self):
        """LLM prefixes JSON with prose and code fence."""
        inner = self._valid_json()
        text = f"Here is my analysis:\n```json\n{inner}\n```"
        result = _parse_conviction(text)
        assert result.overall_score == 75

    def test_empty_string_raises(self):
        """Empty LLM response raises AssumptionParseError."""
        with pytest.raises(AssumptionParseError):
            _parse_conviction("")

    def test_error_prefix_raises(self):
        """Error response from LLM raises AssumptionParseError."""
        with pytest.raises(AssumptionParseError):
            _parse_conviction("Error: rate limit exceeded")


class TestFormatConvictionMarkdown:
    """Conviction markdown formatting."""

    def test_contains_table(self):
        result = ConvictionResult(
            overall_score=75,
            recommendation="BUY",
            confidence=80,
            categories=[ConvictionCategory("Valuation", 70, "Good")],
            summary="Strong.",
        )
        md = format_conviction_markdown(result)
        assert "|" in md
        assert "BUY" in md
        assert "75" in md

    def test_contains_summary(self):
        result = ConvictionResult(
            overall_score=50,
            recommendation="SELL",
            confidence=60,
            categories=[],
            summary="Weak outlook.",
        )
        md = format_conviction_markdown(result)
        assert "Weak outlook." in md


# =============================================================================
# Precedent Transaction dataclasses
# =============================================================================

class TestPrecedentDeal:
    """PrecedentDeal frozen dataclass."""

    def test_to_dict(self):
        deal = PrecedentDeal(
            acquirer="BigCo",
            target="SmallCo",
            date="2024-Q3",
            deal_value_usd=5e9,
            ev_to_revenue=4.5,
            ev_to_ebitda=18.0,
            premium_pct=0.30,
            description="Strategic acquisition.",
        )
        d = deal.to_dict()
        assert d["acquirer"] == "BigCo"
        assert d["ev_to_revenue"] == 4.5
        assert d["premium_pct"] == 0.30

    def test_frozen(self):
        deal = PrecedentDeal("A", "B", "2024", None, None, None, None)
        with pytest.raises(AttributeError):
            deal.acquirer = "C"


class TestPrecedentTransactionResult:
    """PrecedentTransactionResult dataclass."""

    def test_to_dict_keys(self):
        result = PrecedentTransactionResult(
            deals=[],
            median_ev_revenue=3.5,
            median_ev_ebitda=15.0,
            median_premium=0.25,
            implied_value_from_revenue=200.0,
            implied_value_from_ebitda=180.0,
        )
        d = result.to_dict()
        expected_keys = {
            "deals", "median_ev_revenue", "median_ev_ebitda", "median_premium",
            "implied_value_from_revenue", "implied_value_from_ebitda",
            "minority_adj_value_from_revenue", "minority_adj_value_from_ebitda",
            "control_premium_used", "narrative",
        }
        assert set(d.keys()) == expected_keys

    def test_default_control_premium(self):
        result = PrecedentTransactionResult(
            deals=[], median_ev_revenue=None, median_ev_ebitda=None,
            median_premium=None, implied_value_from_revenue=None,
            implied_value_from_ebitda=None,
        )
        assert result.control_premium_used == 0.25


# =============================================================================
# Earnings Model
# =============================================================================

class TestEarningsModelRow:
    """EarningsModelRow frozen dataclass."""

    def test_fields(self):
        row = EarningsModelRow(
            fiscal_year=2024,
            is_estimate=False,
            revenue=100e9,
            revenue_growth=0.08,
            ebitda=30e9,
            ebitda_margin=0.30,
            eps=6.50,
        )
        assert row.fiscal_year == 2024
        assert row.is_estimate is False
        assert row.revenue == 100e9

    def test_optional_fields_default_none(self):
        row = EarningsModelRow(fiscal_year=2025, is_estimate=True)
        assert row.revenue is None
        assert row.eps is None

    def test_frozen(self):
        row = EarningsModelRow(fiscal_year=2024, is_estimate=False)
        with pytest.raises(AttributeError):
            row.fiscal_year = 2025


# =============================================================================
# WACC Derivation
# =============================================================================

class TestComputeWACC:
    """WACC computation with market cap derivation fallbacks."""

    def test_derives_market_cap_from_price_and_shares(self):
        """When market_cap is None, derive from price * shares."""
        result = compute_wacc(
            market_cap=None,
            current_price=243.0,
            shares_outstanding=2.41e9,
            total_debt=50e9,
        )
        # 243 * 2.41e9 = ~585.6B; debt = 50B
        # equity weight ~= 585.6 / (585.6 + 50) ~= 0.921
        assert 0.85 < result.weight_equity < 0.97
        assert result.wacc > 0.05
        assert result.wacc < 0.20

    def test_defaults_to_85pct_equity_when_all_missing(self):
        """When market_cap, price, and shares are all missing, default to 85%."""
        result = compute_wacc(
            market_cap=None,
            current_price=None,
            shares_outstanding=None,
            total_debt=100e9,
        )
        assert result.weight_equity == pytest.approx(0.85)
        assert result.weight_debt == pytest.approx(0.15)

    def test_uses_market_cap_directly_when_available(self):
        """When market_cap is provided, use it directly (no derivation)."""
        result = compute_wacc(
            market_cap=500e9,
            current_price=100.0,
            shares_outstanding=2e9,
            total_debt=100e9,
        )
        # 500B / (500B + 100B) = 0.833
        assert result.weight_equity == pytest.approx(500e9 / 600e9, rel=1e-3)

    def test_zero_market_cap_falls_to_derivation(self):
        """market_cap=0 should be treated as missing, triggering derivation."""
        result = compute_wacc(
            market_cap=0,
            current_price=100.0,
            shares_outstanding=1e9,
            total_debt=50e9,
        )
        # Derived equity = 100 * 1e9 = 100B; total = 150B; weight ~= 0.667
        assert 0.60 < result.weight_equity < 0.75

    def test_negative_market_cap_falls_to_derivation(self):
        """Negative market_cap (bad data) should be treated as missing."""
        result = compute_wacc(
            market_cap=-500e9,
            current_price=200.0,
            shares_outstanding=2e9,
            total_debt=100e9,
        )
        # Derived equity = 200 * 2e9 = 400B; weight ~= 0.80
        assert 0.70 < result.weight_equity < 0.90

    def test_negative_derived_equity_ignored(self):
        """If price * shares is negative (nonsensical data), fall to 85% default."""
        result = compute_wacc(
            market_cap=None,
            current_price=-50.0,
            shares_outstanding=1e9,
            total_debt=100e9,
        )
        assert result.weight_equity == pytest.approx(0.85)

    def test_wacc_clamps_to_range(self):
        """WACC clamped between 5% and 20%."""
        # Very low beta and no debt => low WACC, should clamp to 5%
        result = compute_wacc(beta=0.01, market_cap=1e12, total_debt=0)
        assert result.wacc >= 0.05


# =============================================================================
# Premium Normalization
# =============================================================================

class TestPremiumNormalization:
    """Precedent transaction premium/multiple normalization."""

    def test_percentage_integer_converted_to_decimal(self):
        """LLM returns 30 meaning 30%; should become 0.30."""
        assert _normalize_premium(30) == pytest.approx(0.30, rel=1e-3)

    def test_decimal_left_unchanged(self):
        """Already-decimal values pass through."""
        assert _normalize_premium(0.50) == pytest.approx(0.50)

    def test_small_negative_left_unchanged(self):
        """Small negatives (distressed deals) pass through."""
        assert _normalize_premium(-0.05) == pytest.approx(-0.05)

    def test_value_2_5_preserved_as_multiple(self):
        """2.5 (250% premium, biotech M&A) should be preserved, not divided by 100."""
        assert _normalize_premium(2.5) == pytest.approx(2.5)

    def test_value_3_0_preserved_as_multiple(self):
        """3.0 in the ambiguous zone should be treated as real multiple."""
        assert _normalize_premium(3.0) == pytest.approx(3.0)

    def test_value_above_5_divided(self):
        """Values above 5.0 are percentage-as-integer: 30 -> 0.30."""
        assert _normalize_premium(30) == pytest.approx(0.30, rel=1e-3)

    def test_large_positive_clamped(self):
        """Values > 500% after normalization are clamped to 5.0."""
        assert _normalize_premium(600) == pytest.approx(5.0)

    def test_none_returns_none(self):
        assert _normalize_premium(None) is None

    def test_normalize_multiple_rejects_negative(self):
        assert _normalize_multiple(-5.0) is None

    def test_normalize_multiple_rejects_huge(self):
        assert _normalize_multiple(500.0) is None

    def test_normalize_multiple_passes_valid(self):
        assert _normalize_multiple(12.5) == pytest.approx(12.5)
