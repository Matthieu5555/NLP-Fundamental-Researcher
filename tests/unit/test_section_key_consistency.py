"""
Test that section keys are consistent across the pipeline.

The orchestrator stores sections under specific dict keys (e.g. "moat"),
and the SectionType enum now uses the same canonical values. The PDF and
slides context builders must read from the dict keys. This test catches
mismatches between the orchestrator keys and consumer code.

These tests inspect source code rather than importing modules that require
weasyprint (a system-level dependency not always present in CI).
"""

import re
from pathlib import Path

import pytest

from backend.core.report_builder import ReportState

# Root paths
BACKEND_CORE = Path(__file__).resolve().parents[2] / "backend" / "core"
ORCHESTRATOR_WRAPPER = Path(__file__).resolve().parents[2] / "backend" / "agents" / "orchestrator_wrapper.py"
FRONTEND_TAB_REGISTRY = Path(__file__).resolve().parents[2] / "frontend_v2" / "src" / "components" / "analysis" / "tabRegistry.jsx"

# Section keys written by _populate_report_us in orchestrator_wrapper.py.
# If a new section is added there, add it here too.
ORCHESTRATOR_SECTION_KEYS = [
    "recommendation",
    "fundamentals",
    "insider_activity",
    "technicals",
    "bull_case",
    "bear_case",
    "moat",
    "strategy",
    "dcf",
    "comps",
    "earnings_model",
    "sensitivity",
    "conviction",
    "scenarios",
    "precedents",
    "football_field",
    "industry",
    "further_research",
]


def _build_populated_report() -> ReportState:
    """Create a ReportState with all sections the orchestrator would write."""
    report = ReportState(ticker="TEST")
    for key in ORCHESTRATOR_SECTION_KEYS:
        report.update_section(key, f"Content for {key}")
    return report


def _extract_section_reads(filepath: Path) -> set[str]:
    """Extract all report_state.sections[...] key accesses from a Python file."""
    text = filepath.read_text()
    # Match patterns like: report_state.sections['key'], sections['key'],
    # 'key' in report_state.sections, sections.get('key')
    patterns = [
        r"""(?:report_state\.sections|sections)\[['"](\w+)['"]\]""",
        r"""['"](\w+)['"](?:\s+in\s+(?:report_state\.)?sections)""",
        r"""(?:report_state\.)?sections\.get\(['"](\w+)['"]\)""",
        r"""_get_section_content\(\s*\w+,\s*['"](\w+)['"]\)""",
    ]
    keys = set()
    for pattern in patterns:
        keys.update(re.findall(pattern, text))
    return keys


class TestPDFReadsOrchestatorKeys:
    """Verify pdf_generator_v2.py reads section keys that the orchestrator writes."""

    PDF_FILE = BACKEND_CORE / "pdf_generator_v2.py"

    # Sections the PDF should read (subset of orchestrator keys that have
    # prose content rendered in the PDF template).
    EXPECTED_PDF_READS = {
        "fundamentals",
        "technicals",
        "moat",
        "dcf",
        "comps",
        "earnings_model",
        "sensitivity",
        "conviction",
        "scenarios",
        "precedents",
        "football_field",
        "industry",
        "investment_thesis",
        "recommendation",
        "bull_case",
        "bear_case",
        "strategy",
    }

    def test_pdf_reads_correct_section_keys(self):
        """PDF context builder must not use old non-canonical keys."""
        actual_reads = _extract_section_reads(self.PDF_FILE)

        # These old keys should NOT appear as section key reads
        forbidden_keys = {
            "moat_analysis", "full_report", "dcf_valuation", "comp_table",
            "scenario_analysis", "precedent_transactions", "external_forces",
        }
        bad_reads = actual_reads & forbidden_keys
        assert not bad_reads, (
            f"PDF reads sections by old non-canonical key: {bad_reads}."
        )

    def test_pdf_reads_all_expected_prose_sections(self):
        """PDF should access all prose sections it needs to render."""
        actual_reads = _extract_section_reads(self.PDF_FILE)
        missing = self.EXPECTED_PDF_READS - actual_reads
        assert not missing, f"PDF does not read these expected sections: {missing}"


class TestSlidesReadsOrchestratorKeys:
    """Verify slides_generator.py reads correct section keys."""

    SLIDES_FILE = BACKEND_CORE / "slides_generator.py"

    def test_slides_reads_no_old_keys(self):
        """Slides must use canonical keys, not old non-canonical ones."""
        actual_reads = _extract_section_reads(self.SLIDES_FILE)
        forbidden_keys = {
            "moat_analysis", "full_report", "dcf_valuation", "comp_table",
            "scenario_analysis", "precedent_transactions", "external_forces",
        }
        bad_reads = actual_reads & forbidden_keys
        assert not bad_reads, (
            f"Slides reads old non-canonical keys: {bad_reads}"
        )

    def test_slides_reads_expected_prose_sections(self):
        """Slides should access the sections it summarizes into bullets."""
        actual_reads = _extract_section_reads(self.SLIDES_FILE)
        expected = {"investment_thesis", "bull_case", "bear_case", "moat", "industry", "conviction"}
        missing = expected - actual_reads
        assert not missing, f"Slides does not read these expected sections: {missing}"


class TestOrchestratorKeysMatchReportState:
    """Verify ReportState.update_section handles all orchestrator keys."""

    def test_all_orchestrator_keys_accepted(self):
        """ReportState.update_section should store every key the orchestrator uses."""
        report = ReportState(ticker="TEST")
        for key in ORCHESTRATOR_SECTION_KEYS:
            report.update_section(key, f"Content for {key}")
            assert key in report.sections, f"update_section failed to store key '{key}'"
            assert report.sections[key].content == f"Content for {key}"

    def test_orchestrator_keys_match_source(self):
        """The ORCHESTRATOR_SECTION_KEYS list in this test must match the actual
        update_section calls in orchestrator_wrapper.py."""
        text = ORCHESTRATOR_WRAPPER.read_text()
        # Extract all update_section("key", ...) calls
        actual_keys = set(re.findall(r'update_section\("(\w+)"', text))
        expected_keys = set(ORCHESTRATOR_SECTION_KEYS)
        assert actual_keys == expected_keys, (
            f"Test's ORCHESTRATOR_SECTION_KEYS is out of sync.\n"
            f"In source but not test: {actual_keys - expected_keys}\n"
            f"In test but not source: {expected_keys - actual_keys}"
        )


class TestInvestmentThesisTabFallback:
    """Verify the Investment Thesis tab does not dump all sections."""

    def test_no_render_generic_sections_fallback(self):
        """The 'all' tab (Investment Thesis) should NOT call renderGenericSections
        as a fallback, which would dump every section into the thesis view."""
        text = FRONTEND_TAB_REGISTRY.read_text()

        # Find the render function for the 'thesis' tab (was 'all')
        # It should reference 'recommendation', not 'renderGenericSections'
        all_tab_match = re.search(
            r"id:\s*['\"]thesis['\"].*?render:\s*\(ctx\)\s*=>\s*\{(.*?)\n\s*\},",
            text,
            re.DOTALL,
        )
        assert all_tab_match, "Could not find the 'thesis' tab render function in tabRegistry.jsx"

        render_body = all_tab_match.group(1)
        assert "renderGenericSections" not in render_body, (
            "Investment Thesis tab still falls back to renderGenericSections, "
            "which dumps ALL sections. It should show only 'recommendation'."
        )
        assert "recommendation" in render_body, (
            "Investment Thesis tab fallback should reference 'recommendation' section"
        )
