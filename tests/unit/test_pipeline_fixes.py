"""
Tests for pipeline audit fixes: DCF format bug, peer selection dash normalization,
strategy grid parsing, openpyxl availability, and synthesis prompt structure.
"""

import importlib
import importlib.util
from dataclasses import dataclass, field
from typing import List, Optional

import pytest


# =============================================================================
# 1. DCF Format Specifier Bug
# =============================================================================

class TestDCFFormatSpecifier:
    """The f-string at dcf_agent.py:194 had a conditional inside the format spec
    which Python doesn't support. Verify the fix by testing the pattern directly."""

    def test_format_with_price(self):
        """The fixed f-string pattern should format a float price correctly."""
        current_price = 245.0
        result = f"Current Price: {f'${current_price:.2f}' if current_price else 'N/A'}"
        assert result == "Current Price: $245.00"

    def test_format_with_none_price(self):
        """The fixed f-string pattern should produce N/A for None."""
        current_price = None
        result = f"Current Price: {f'${current_price:.2f}' if current_price else 'N/A'}"
        assert result == "Current Price: N/A"

    def test_format_with_zero_price(self):
        """Edge case: 0.0 is falsy, should produce N/A."""
        current_price = 0.0
        result = f"Current Price: {f'${current_price:.2f}' if current_price else 'N/A'}"
        assert result == "Current Price: N/A"

    def test_original_bug_pattern_crashes(self):
        """Confirm the old pattern (conditional inside format spec) raises."""
        current_price = 245.0
        with pytest.raises(ValueError):
            f"${current_price:.2f if current_price else 'N/A'}"


# =============================================================================
# 2. Peer Selection Dash Normalization
# =============================================================================

def _get_select_peers():
    """Import select_peers bypassing valuation.__init__ (which triggers circular imports)."""
    import importlib.util, sys, pathlib
    mod_name = "src_george_researcher.valuation.comp_table"
    if mod_name in sys.modules:
        return sys.modules[mod_name].select_peers
    file_path = pathlib.Path(__file__).resolve().parents[2] / "src_george_researcher" / "valuation" / "comp_table.py"
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod.select_peers


class TestPeerSelectionDashNormalization:
    """Yahoo Finance returns industry names with regular dashes, but the peer
    mapping used em dashes. Verify normalization handles all variants."""

    def test_em_dash_matches(self):
        """Original em-dash key should still work."""
        select_peers = _get_select_peers()
        peers = select_peers(
            sector="Healthcare",
            industry="Drug Manufacturers\u2014General",
            market_cap=400e9,
            target_ticker="JNJ",
        )
        assert len(peers) > 0
        assert "JNJ" not in peers  # Target should be excluded

    def test_regular_dash_matches(self):
        """Yahoo-style regular dash should now match via normalization."""
        select_peers = _get_select_peers()
        peers = select_peers(
            sector="Healthcare",
            industry="Drug Manufacturers - General",
            market_cap=400e9,
            target_ticker="JNJ",
        )
        assert len(peers) > 0
        assert "PFE" in peers or "MRK" in peers or "LLY" in peers

    def test_en_dash_matches(self):
        """En dash should also normalize correctly."""
        select_peers = _get_select_peers()
        peers = select_peers(
            sector="Healthcare",
            industry="Drug Manufacturers\u2013General",  # en dash
            market_cap=400e9,
            target_ticker="JNJ",
        )
        assert len(peers) > 0

    def test_sector_fallback_when_industry_missing(self):
        """When industry is not in the map, should fall back to sector peers."""
        select_peers = _get_select_peers()
        peers = select_peers(
            sector="Healthcare",
            industry="Some Unknown Industry",
            market_cap=400e9,
            target_ticker="JNJ",
        )
        # Should find peers from SECTOR_PEERS["Healthcare"]
        assert len(peers) > 0

    def test_no_peers_for_unknown_everything(self):
        """When both industry and sector are unknown, should return empty list."""
        select_peers = _get_select_peers()
        peers = select_peers(
            sector="AlienTechnology",
            industry="SpaceWidgets",
            market_cap=1e9,
            target_ticker="FAKE",
        )
        assert peers == []


# =============================================================================
# 3. Strategy Grid Parsing (formerly parse_swot)
# =============================================================================

@pytest.mark.skipif(
    not importlib.util.find_spec("markdown"),
    reason="markdown not installed (pdf_formatting optional dep)",
)
class TestStrategyGridParsing:
    """parse_strategy_grid should extract four quadrants from LLM-generated
    strategy text using the new label scheme."""

    def test_new_labels(self):
        """Should parse advantages/vulnerabilities/tailwinds/headwinds headers."""
        from backend.core.pdf_formatting import parse_strategy_grid

        content = """**Advantages**
Strong brand and market leadership in pharma.

**Vulnerabilities**
High R&D spend with uncertain pipeline outcomes.

**Tailwinds**
Aging population drives healthcare demand globally.

**Headwinds**
Patent cliff approaching for key drug in 2026.
"""
        result = parse_strategy_grid(content)
        assert result is not None
        assert "brand" in result["advantages"].lower()
        assert "r&amp;d" in result["vulnerabilities"].lower() or "R&D" in result["vulnerabilities"]
        assert "aging" in result["tailwinds"].lower()
        assert "patent" in result["headwinds"].lower()

    def test_legacy_labels(self):
        """Should still parse legacy strengths/weaknesses/opportunities/threats."""
        from backend.core.pdf_formatting import parse_strategy_grid

        content = """**Strengths**
Dominant market position.

**Weaknesses**
Regulatory exposure.

**Opportunities**
Emerging markets expansion.

**Threats**
Generic competition.
"""
        result = parse_strategy_grid(content)
        assert result is not None
        assert result["advantages"]  # strengths maps to advantages
        assert result["vulnerabilities"]  # weaknesses maps to vulnerabilities
        assert result["tailwinds"]  # opportunities maps to tailwinds
        assert result["headwinds"]  # threats maps to headwinds

    def test_empty_content_returns_none(self):
        from backend.core.pdf_formatting import parse_strategy_grid
        assert parse_strategy_grid("") is None
        assert parse_strategy_grid(None) is None

    def test_no_matching_headers_returns_none(self):
        from backend.core.pdf_formatting import parse_strategy_grid
        result = parse_strategy_grid("Just some random text with no headers.")
        assert result is None

    def test_backward_compatible_alias(self):
        """parse_swot should still work as alias."""
        from backend.core.pdf_formatting import parse_swot, parse_strategy_grid
        assert parse_swot is parse_strategy_grid


# =============================================================================
# 4. openpyxl Importability
# =============================================================================

class TestOpenpyxlAvailability:
    """Excel export requires openpyxl. Verify it's importable."""

    def test_openpyxl_imports(self):
        import openpyxl
        assert openpyxl is not None

    def test_excel_generator_imports(self):
        """The backend Excel generator should import without error."""
        mod = importlib.import_module("backend.core.excel_generator")
        assert mod is not None


# =============================================================================
# 5. Framework Name Scrub Verification
# =============================================================================

class TestFrameworkNameScrub:
    """Verify that framework names are purged from prompts and user-facing text."""

    def test_no_swot_in_prompts(self):
        """SWOT should not appear in any prompt except the prohibition."""
        from src_george_researcher import prompts
        # Collect all prompt strings
        prompt_strings = [
            prompts.BULL_CASE_SYSTEM,
            prompts.BEAR_CASE_SYSTEM,
            prompts.STRATEGY_SYSTEM,
            prompts.MOAT_SYSTEM,
            prompts.SYNTHESIS_SYSTEM,
            prompts.DCF_ASSUMPTIONS_SYSTEM,
        ]
        for p in prompt_strings:
            # "SWOT" should not appear except in the FULL_REPORT prohibition
            assert "SWOT" not in p, f"Found 'SWOT' in prompt: {p[:80]}..."

    def test_no_porters_in_prompts(self):
        from src_george_researcher import prompts
        prompt_strings = [
            prompts.BULL_CASE_SYSTEM,
            prompts.BEAR_CASE_SYSTEM,
            prompts.STRATEGY_SYSTEM,
            prompts.MOAT_SYSTEM,
            prompts.SYNTHESIS_SYSTEM,
            prompts.DCF_ASSUMPTIONS_SYSTEM,
        ]
        for p in prompt_strings:
            assert "Porter" not in p, f"Found 'Porter' in prompt: {p[:80]}..."

    def test_swot_system_alias_removed(self):
        """SWOT_SYSTEM should no longer exist."""
        from src_george_researcher import prompts
        assert not hasattr(prompts, "SWOT_SYSTEM")

    def test_swot_removed_from_registry(self):
        """'swot' key should not be in the prompt registry."""
        from src_george_researcher.prompts import PROMPT_REGISTRY
        assert "swot" not in PROMPT_REGISTRY

    def test_full_report_prohibition_intact(self):
        """The FULL_REPORT_SYSTEM should still prohibit framework labels."""
        from src_george_researcher.prompts import FULL_REPORT_SYSTEM
        assert 'no "PESTEL"' in FULL_REPORT_SYSTEM
        assert 'no "SWOT"' in FULL_REPORT_SYSTEM or '"SWOT"' in FULL_REPORT_SYSTEM


# =============================================================================
# 6. Strategy Agent Receives Strategic Context
# =============================================================================

def _parse_analysis_agents_ast():
    """Parse analysis_agents.py via AST to inspect signatures without triggering imports."""
    import ast, pathlib
    file_path = pathlib.Path(__file__).resolve().parents[2] / "src_george_researcher" / "analysis_agents.py"
    tree = ast.parse(file_path.read_text())
    functions = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [arg.arg for arg in node.args.args]
            functions[node.name] = params
    return functions


class TestStrategyAgentWiring:
    """Verify that analyze_strategy accepts strategic_context parameter."""

    def test_analyze_strategy_signature(self):
        """analyze_strategy should accept strategic_context kwarg."""
        funcs = _parse_analysis_agents_ast()
        assert "analyze_strategy" in funcs
        assert "strategic_context" in funcs["analyze_strategy"]

    def test_analyze_moat_signature(self):
        """analyze_moat should accept fundamentals_analysis kwarg."""
        funcs = _parse_analysis_agents_ast()
        assert "analyze_moat" in funcs
        assert "fundamentals_analysis" in funcs["analyze_moat"]

    def test_analyze_swot_alias_removed(self):
        """analyze_swot should not be defined as a function."""
        funcs = _parse_analysis_agents_ast()
        assert "analyze_swot" not in funcs
