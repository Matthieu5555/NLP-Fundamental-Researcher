"""Tests for belief classification and badge retrieval.

Covers:
- InsightType enum completeness
- get_badge_for_belief: all known types return valid badges
- ExtractedBelief: dataclass construction
- INSIGHT_BADGES: all enum values have entries
"""

import pytest

from backend.core.belief_classifier import (
    InsightType,
    get_badge_for_belief,
    ExtractedBelief,
    INSIGHT_BADGES,
)
from backend.core.colors import get_insight_badge


class TestInsightType:
    """InsightType enum coverage."""

    def test_all_values(self):
        expected = {
            "confirmed_fact", "new_insight", "risk_identified",
            "opportunity", "valuation_view", "competitive",
        }
        actual = {t.value for t in InsightType}
        assert actual == expected

    def test_enum_from_value(self):
        assert InsightType("confirmed_fact") == InsightType.CONFIRMED_FACT
        assert InsightType("risk_identified") == InsightType.RISK_IDENTIFIED


class TestGetBadgeForBelief:
    """Badge retrieval for all insight types."""

    def test_all_types_return_dict(self):
        for itype in InsightType:
            badge = get_badge_for_belief(itype)
            assert isinstance(badge, dict), f"Badge for {itype} is not a dict"

    def test_badge_has_required_keys(self):
        for itype in InsightType:
            badge = get_badge_for_belief(itype)
            assert "label" in badge, f"Missing 'label' for {itype}"
            assert "color" in badge, f"Missing 'color' for {itype}"
            assert "bg" in badge, f"Missing 'bg' for {itype}"

    def test_confirmed_fact_badge(self):
        badge = get_badge_for_belief(InsightType.CONFIRMED_FACT)
        assert badge["label"].upper() == "CONFIRMED"

    def test_risk_badge(self):
        badge = get_badge_for_belief(InsightType.RISK_IDENTIFIED)
        assert "RISK" in badge["label"].upper()

    def test_colors_are_hex(self):
        for itype in InsightType:
            badge = get_badge_for_belief(itype)
            assert badge["color"].startswith("#"), f"Color for {itype} not hex: {badge['color']}"
            assert badge["bg"].startswith("#"), f"Bg for {itype} not hex: {badge['bg']}"


class TestInsightBadgesDict:
    """INSIGHT_BADGES module-level dict completeness."""

    def test_all_insight_types_covered(self):
        for itype in InsightType:
            assert itype in INSIGHT_BADGES, f"Missing badge for {itype}"

    def test_no_extra_keys(self):
        for key in INSIGHT_BADGES:
            assert isinstance(key, InsightType), f"Unexpected key type: {type(key)}"


class TestExtractedBelief:
    """ExtractedBelief dataclass construction."""

    def test_construction(self):
        belief = ExtractedBelief(
            content="AAPL is overvalued",
            insight_type=InsightType.VALUATION_VIEW,
            target_section="recommendation",
            confidence=0.85,
            supporting_quote="I think the P/E is too high",
        )
        assert belief.content == "AAPL is overvalued"
        assert belief.insight_type == InsightType.VALUATION_VIEW
        assert belief.confidence == 0.85

    def test_defaults(self):
        belief = ExtractedBelief(
            content="Test",
            insight_type=InsightType.NEW_INSIGHT,
            target_section="moat",
            confidence=0.5,
            supporting_quote="quote",
        )
        assert belief.rationale is None
        assert belief.has_rationale is False

    def test_with_rationale(self):
        belief = ExtractedBelief(
            content="Moat is weakening",
            insight_type=InsightType.COMPETITIVE_INSIGHT,
            target_section="moat",
            confidence=0.70,
            supporting_quote="The moat is weakening because of competition",
            rationale="Increasing competition from Chinese EVs",
            has_rationale=True,
        )
        assert belief.has_rationale is True
        assert belief.rationale is not None
