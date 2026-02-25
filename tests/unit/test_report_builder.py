"""Tests for report_builder: SectionType, Source, Section, ReportState."""

import pytest
from datetime import datetime

from backend.core.report_builder import (
    SectionType,
    Source,
    AnalystSource,
    Section,
    ReportState,
)


class TestSectionType:
    """SectionType enum completeness and correctness."""

    EXPECTED_TYPES = [
        "executive_summary", "fundamentals", "technicals",
        "bull_case", "bear_case", "moat_analysis", "strategy",
        "financial_statements", "sentiment", "risks", "recommendation",
        "dcf_valuation", "comp_table", "earnings_model", "sensitivity",
        "conviction", "scenario_analysis", "precedent_transactions",
        "football_field", "external_forces", "sources", "custom",
    ]

    def test_all_expected_types_exist(self):
        for value in self.EXPECTED_TYPES:
            assert SectionType(value) is not None, f"Missing SectionType: {value}"

    def test_no_swot_type(self):
        """swot was replaced by strategy — ensure it stays removed."""
        with pytest.raises(ValueError):
            SectionType("swot")

    def test_enum_values_are_lowercase_snake_case(self):
        for member in SectionType:
            assert member.value == member.value.lower(), f"{member.name} value is not lowercase"
            assert " " not in member.value, f"{member.name} value contains spaces"

    def test_enum_count(self):
        assert len(SectionType) == len(self.EXPECTED_TYPES)


class TestSource:
    def test_creation(self):
        s = Source(id=1, title="Test", url="https://example.com", source_type="news", date="2025-01-01")
        assert s.id == 1
        assert s.snippet is None

    def test_to_dict(self):
        s = Source(id=1, title="Test", url="https://example.com", source_type="news", date="2025-01-01", snippet="excerpt")
        d = s.to_dict()
        assert d["id"] == 1
        assert d["snippet"] == "excerpt"
        assert set(d.keys()) == {"id", "title", "url", "source_type", "date", "snippet"}


class TestAnalystSource:
    def test_creation(self):
        a = AnalystSource(id="A1", belief_content="Revenue is growing", insight_type="confirmed_fact", section="fundamentals")
        assert a.id == "A1"
        assert isinstance(a.timestamp, datetime)

    def test_round_trip(self):
        a = AnalystSource(id="A1", belief_content="Test belief", insight_type="risk_identified", section="risks")
        d = a.to_dict()
        restored = AnalystSource.from_dict(d)
        assert restored.id == a.id
        assert restored.belief_content == a.belief_content
        assert restored.insight_type == a.insight_type
        assert restored.section == a.section

    def test_citation_text_strips_prefix(self):
        a = AnalystSource(id="A1", belief_content="The analyst believes that revenue will grow", insight_type="confirmed_fact", section="fundamentals")
        citation = a.to_citation_text()
        assert citation.startswith("It is our belief that")
        assert "The analyst believes" not in citation


class TestSection:
    def test_creation(self):
        s = Section(title="Test", content="Some content", section_type=SectionType.FUNDAMENTALS)
        assert s.version == 1
        assert s.confidence == 0.7

    def test_update_increments_version(self):
        s = Section(title="Test", content="v1", section_type=SectionType.FUNDAMENTALS)
        s.update("v2")
        assert s.content == "v2"
        assert s.version == 2

    def test_update_deduplicates_sources(self):
        s = Section(title="Test", content="v1", section_type=SectionType.FUNDAMENTALS)
        src1 = Source(id=1, title="A", url="https://a.com", source_type="news", date="2025-01-01")
        s.update("v2", [src1])
        s.update("v3", [src1])  # same source again
        assert len(s.sources) == 1

    def test_to_markdown(self):
        s = Section(title="Bull Case", content="Strong growth", section_type=SectionType.BULL_CASE)
        md = s.to_markdown()
        assert "## Bull Case" in md
        assert "Strong growth" in md

    def test_to_dict_serializes_section_type(self):
        s = Section(title="Test", content="content", section_type=SectionType.TECHNICALS)
        d = s.to_dict()
        assert d["section_type"] == "technicals"
        assert "last_updated" in d


class TestReportState:
    def test_creation(self):
        r = ReportState(ticker="AAPL")
        assert r.ticker == "AAPL"
        assert len(r.sections) == 0
        assert r.version == 1

    def test_add_section(self):
        r = ReportState(ticker="AAPL")
        section = r.add_section("fundamentals", "Fundamentals", "PE is 25", SectionType.FUNDAMENTALS)
        assert "fundamentals" in r.sections
        assert section.title == "Fundamentals"
        assert r.version == 2

    def test_update_existing_section(self):
        r = ReportState(ticker="AAPL")
        r.add_section("fundamentals", "Fundamentals", "PE is 25", SectionType.FUNDAMENTALS)
        r.update_section("fundamentals", "PE is 30")
        assert r.sections["fundamentals"].content == "PE is 30"
        assert r.sections["fundamentals"].version == 2

    def test_update_creates_section_if_missing(self):
        r = ReportState(ticker="AAPL")
        r.update_section("recommendation", "Buy with target $200")
        assert "recommendation" in r.sections
        assert r.sections["recommendation"].section_type == SectionType.RECOMMENDATION

    def test_get_section(self):
        r = ReportState(ticker="AAPL")
        r.add_section("test", "Test", "content", SectionType.CUSTOM)
        assert r.get_section("test") is not None
        assert r.get_section("nonexistent") is None

    def test_remove_section(self):
        r = ReportState(ticker="AAPL")
        r.add_section("test", "Test", "content", SectionType.CUSTOM)
        r.remove_section("test")
        assert "test" not in r.sections

    def test_add_source(self):
        r = ReportState(ticker="AAPL")
        r.add_source("Yahoo Finance", "https://yahoo.com", "api", "2025-01-01")
        assert "sources" in r.sections
        assert len(r.sections["sources"].sources) == 1

    def test_to_markdown(self):
        r = ReportState(ticker="AAPL")
        r.add_section("fundamentals", "Fundamentals", "PE is 25", SectionType.FUNDAMENTALS)
        md = r.to_markdown()
        assert "AAPL" in md
        assert "Fundamentals" in md

    def test_to_dict_round_trip(self):
        r = ReportState(ticker="AAPL")
        r.add_section("fundamentals", "Fundamentals", "PE is 25", SectionType.FUNDAMENTALS)
        d = r.to_dict()
        assert d["ticker"] == "AAPL"
        assert "fundamentals" in d["sections"]
        assert d["sections"]["fundamentals"]["section_type"] == "fundamentals"

    def test_get_stats(self):
        r = ReportState(ticker="AAPL")
        r.add_section("fundamentals", "Fundamentals", "PE is 25", SectionType.FUNDAMENTALS)
        stats = r.get_stats()
        assert stats["ticker"] == "AAPL"
        assert stats["section_count"] == 1
        assert stats["total_characters"] > 0

    def test_summarize(self):
        r = ReportState(ticker="AAPL")
        r.add_section("fundamentals", "Fundamentals", "PE is 25", SectionType.FUNDAMENTALS)
        summary = r.summarize()
        assert "AAPL" in summary
        assert "1 sections" in summary

    def test_excluded_source_ids(self):
        r = ReportState(ticker="AAPL")
        r.excluded_source_ids = [1, 3, 5]
        d = r.to_dict()
        assert d["excluded_source_ids"] == [1, 3, 5]
