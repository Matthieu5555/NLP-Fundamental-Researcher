"""Tests for PDF formatting utilities and color system.

Covers:
- format_number: all format types (market_cap, price, percent, ratio, shares, default)
- extract_highlights: bullet extraction and sentence fallback
- md_to_html: markdown to HTML conversion
- get_exchange_name: exchange code mapping
- parse_strategy_grid: strategy content parsing
- Color palette: singleton loading, hex_to_rgb, rating colors, insight badges
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("markdown", reason="markdown not installed (optional backend dep)")

from backend.core.pdf_formatting import (
    format_number,
    extract_highlights,
    md_to_html,
    get_exchange_name,
    parse_strategy_grid,
    remove_key_questions_section,
)
from backend.core.colors import (
    PALETTE,
    get_rating_color,
    get_insight_badge,
    hex_to_rgb,
    hex_to_rgb_normalized,
    _hex_to_rgb,
)


# =============================================================================
# format_number
# =============================================================================

class TestFormatNumber:
    """Number formatting for display across all format types."""

    def test_none_returns_na(self):
        assert format_number(None) == "N/A"
        assert format_number(None, "market_cap") == "N/A"
        assert format_number(None, "price") == "N/A"
        assert format_number(None, "percent") == "N/A"

    # Market cap
    def test_market_cap_trillions(self):
        assert format_number(2.8e12, "market_cap") == "$2.80T"

    def test_market_cap_billions(self):
        assert format_number(500e9, "market_cap") == "$500.00B"

    def test_market_cap_millions(self):
        assert format_number(5e6, "market_cap") == "$5.00M"

    def test_market_cap_below_million(self):
        result = format_number(999_999, "market_cap")
        assert result.startswith("$")
        assert "M" not in result and "B" not in result

    # Price
    def test_price_format(self):
        assert format_number(185.50, "price") == "$185.50"

    def test_price_format_large(self):
        assert format_number(3_421.99, "price") == "$3,421.99"

    # Percent
    def test_percent_positive(self):
        assert format_number(8.3, "percent") == "+8.3%"

    def test_percent_negative(self):
        assert format_number(-5.0, "percent") == "-5.0%"

    def test_percent_zero(self):
        assert format_number(0.0, "percent") == "+0.0%"

    # Percent raw (decimal input)
    def test_percent_raw_positive(self):
        assert format_number(0.0214, "percent_raw") == "+2.1%"

    def test_percent_raw_negative(self):
        assert format_number(-0.05, "percent_raw") == "-5.0%"

    def test_percent_raw_zero(self):
        assert format_number(0.0, "percent_raw") == "+0.0%"

    def test_percent_raw_none(self):
        assert format_number(None, "percent_raw") == "N/A"

    # Ratio
    def test_ratio_format(self):
        assert format_number(28.5, "ratio") == "28.50x"

    # Shares
    def test_shares_billions(self):
        assert format_number(2.5e9, "shares") == "2.50B"

    def test_shares_millions(self):
        assert format_number(750e6, "shares") == "750.00M"

    def test_shares_below_million(self):
        result = format_number(500_000, "shares")
        assert "M" not in result and "B" not in result

    # Default
    def test_default_format(self):
        assert format_number(42.0) == "42.00"

    def test_default_format_with_unknown_type(self):
        assert format_number(42.0, "unknown") == "42.00"


# =============================================================================
# extract_highlights
# =============================================================================

class TestExtractHighlights:
    """Bullet extraction and sentence fallback."""

    def test_extracts_bullet_points(self):
        content = "- First point\n- Second point\n- Third point\n- Fourth point\n- Fifth point"
        result = extract_highlights(content, max_items=4)
        assert len(result) == 4
        assert result[0] == "First point"

    def test_respects_max_items(self):
        content = "- A\n- B\n- C\n- D\n- E"
        assert len(extract_highlights(content, max_items=2)) == 2

    def test_asterisk_bullets(self):
        content = "* Bullet one\n* Bullet two"
        result = extract_highlights(content)
        assert len(result) == 2
        assert result[0] == "Bullet one"

    def test_sentence_fallback_when_no_bullets(self):
        content = "This is a longer sentence about something important. Another meaningful sentence here. Short. Yet another sentence that is long enough to pass the filter."
        result = extract_highlights(content, max_items=4)
        assert len(result) >= 1
        # Short sentences (under 20 chars) like "Short." should be skipped
        for h in result:
            assert len(h) > 20

    def test_empty_string_returns_empty(self):
        assert extract_highlights("") == []

    def test_no_qualifying_content(self):
        # Only very short fragments
        assert extract_highlights("Hi. Ok.") == []


# =============================================================================
# md_to_html
# =============================================================================

class TestMdToHtml:
    """Markdown to HTML conversion."""

    def test_empty_string(self):
        assert md_to_html("") == ""

    def test_none_returns_empty(self):
        assert md_to_html(None) == ""

    def test_bold_renders_strong(self):
        result = md_to_html("**bold text**")
        assert "<strong>" in result
        assert "bold text" in result

    def test_table_renders(self):
        table = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = md_to_html(table)
        assert "<table>" in result


# =============================================================================
# get_exchange_name
# =============================================================================

class TestGetExchangeName:
    """Exchange code to human-readable name mapping."""

    def test_known_codes(self):
        assert get_exchange_name("NMS") == "NASDAQ"
        assert get_exchange_name("NYQ") == "NYSE"
        assert get_exchange_name("LSE") == "London"
        assert get_exchange_name("TYO") == "Tokyo"

    def test_case_insensitive(self):
        assert get_exchange_name("nms") == "NASDAQ"
        assert get_exchange_name("nyq") == "NYSE"

    def test_unknown_code_passthrough(self):
        assert get_exchange_name("XYZ") == "XYZ"

    def test_empty_string(self):
        assert get_exchange_name("") == ""


# =============================================================================
# parse_strategy_grid
# =============================================================================

class TestParseStrategyGrid:
    """Strategy grid parsing from markdown content."""

    def test_none_returns_none(self):
        assert parse_strategy_grid(None) is None

    def test_empty_returns_none(self):
        assert parse_strategy_grid("") is None

    def test_no_matching_headers_returns_none(self):
        assert parse_strategy_grid("Just some text without any headers.") is None

    def test_parses_advantages_section(self):
        content = "## Advantages\n- Strong brand\n- Market leader\n## Vulnerabilities\n- High debt"
        result = parse_strategy_grid(content)
        assert result is not None
        assert result["advantages"] != ""
        assert result["vulnerabilities"] != ""

    def test_legacy_labels_map_correctly(self):
        content = "## Strengths\n- Good\n## Weaknesses\n- Bad\n## Opportunities\n- Maybe\n## Threats\n- Uh oh"
        result = parse_strategy_grid(content)
        assert result is not None
        assert result["advantages"] != ""
        assert result["vulnerabilities"] != ""
        assert result["tailwinds"] != ""
        assert result["headwinds"] != ""

    def test_bold_headers_parsed(self):
        content = "**Advantages**\n- Item\n**Vulnerabilities**\n- Item"
        result = parse_strategy_grid(content)
        assert result is not None

    def test_numbered_list_headers(self):
        content = "1. **Advantages**\n- Strong brand\n2. **Vulnerabilities**\n- High debt"
        result = parse_strategy_grid(content)
        assert result is not None
        assert result["advantages"] != ""
        assert result["vulnerabilities"] != ""

    def test_bullet_overflow_capped(self):
        # More than 5 bullets should be truncated per quadrant
        lines = "\n".join(f"- Point {i}" for i in range(10))
        content = f"## Advantages\n{lines}\n## Vulnerabilities\n- One"
        result = parse_strategy_grid(content)
        assert result is not None
        # Count <li> tags in advantages: should be <= 5
        li_count = result["advantages"].count("<li>")
        assert li_count <= 5


# =============================================================================
# remove_key_questions_section
# =============================================================================

class TestRemoveKeyQuestions:
    """Removal of 'Key Questions for the Analyst' section from HTML."""

    def test_none_returns_none(self):
        assert remove_key_questions_section(None) is None

    def test_empty_returns_empty(self):
        assert remove_key_questions_section("") == ""

    def test_removes_key_questions_section(self):
        # The section between Key Questions and the next h2 is removed
        html = "<p>Preamble.</p><h2>Key Questions for the Analyst</h2><p>Remove me.</p><h2>Conclusion</h2><p>Final.</p>"
        result = remove_key_questions_section(html)
        assert "Key Questions" not in result
        assert "Remove me" not in result
        assert "Final" in result

    def test_preserves_content_without_section(self):
        html = "<h2>Analysis</h2><p>Keep this.</p>"
        assert remove_key_questions_section(html) == html


# =============================================================================
# Color System
# =============================================================================

class TestColorPalette:
    """Palette singleton loading and consistency with shared/colors.json."""

    def test_palette_loaded(self):
        assert PALETTE is not None

    def test_palette_matches_json(self):
        json_path = Path(__file__).parent.parent.parent / "shared" / "colors.json"
        with open(json_path) as f:
            data = json.load(f)
        assert PALETTE.brand.primary == data["brand"]["primary"]

    def test_palette_is_frozen(self):
        with pytest.raises(AttributeError):
            PALETTE.brand.primary = "#000000"

    def test_pdf_to_template_dict_keys(self):
        d = PALETTE.pdf.to_template_dict()
        assert isinstance(d, dict)
        assert "body_text" in d
        assert "bull_case_bg" in d
        assert "bear_case_border" in d
        assert "margin_highlight_bg" in d
        # All values should be strings (hex colors)
        for v in d.values():
            assert isinstance(v, str)


class TestHexToRgb:
    """Hex color conversion."""

    def test_known_conversion(self):
        # #C87A23 = (200, 122, 35)
        assert hex_to_rgb("#C87A23") == (200, 122, 35)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_invalid_returns_black(self):
        assert _hex_to_rgb("invalid") == (0, 0, 0)
        assert _hex_to_rgb("#GGG") == (0, 0, 0)

    def test_normalized_range(self):
        r, g, b = hex_to_rgb_normalized("#FF0080")
        assert abs(r - 1.0) < 0.001
        assert abs(g - 0.0) < 0.001
        assert 0.0 <= b <= 1.0


class TestRatingColors:
    """Rating color lookups."""

    def test_buy_returns_hex(self):
        color = get_rating_color("BUY")
        assert color.startswith("#")

    def test_sell_returns_different_from_buy(self):
        assert get_rating_color("BUY") != get_rating_color("SELL")

    def test_unknown_falls_back_to_na(self):
        assert get_rating_color("UNKNOWN") == get_rating_color("N/A")

    def test_case_insensitive(self):
        assert get_rating_color("buy") == get_rating_color("BUY")

    def test_all_known_ratings_return_hex(self):
        for rating in ["BUY", "SELL", "HOLD", "STRONG BUY", "STRONG SELL", "NEUTRAL", "N/A"]:
            color = get_rating_color(rating)
            assert color.startswith("#"), f"Rating '{rating}' returned '{color}'"


class TestInsightBadges:
    """Insight badge lookup."""

    def test_known_badge_keys(self):
        badge = get_insight_badge("confirmed")
        assert "label" in badge
        assert "color" in badge
        assert "bg" in badge

    def test_unknown_returns_default(self):
        badge = get_insight_badge("nonexistent_type")
        default = get_insight_badge("default")
        assert badge == default

    def test_badge_values_are_strings(self):
        badge = get_insight_badge("confirmed")
        assert isinstance(badge["label"], str)
        assert isinstance(badge["color"], str)
        assert isinstance(badge["bg"], str)


# =============================================================================
# Slides generator pure functions
# =============================================================================

_has_weasyprint = True
try:
    import weasyprint  # noqa: F401
except (ImportError, OSError):
    _has_weasyprint = False

_skip_no_weasyprint = pytest.mark.skipif(
    not _has_weasyprint, reason="weasyprint not available"
)


@_skip_no_weasyprint
class TestEarningsTakeaway:
    """Earnings takeaway computation from model rows."""

    def test_accelerating_growth(self):
        from backend.core.slides_generator import _compute_earnings_takeaway
        rows = [
            {"revenue_growth": 0.05, "ebitda_margin": 0.20},
            {"revenue_growth": 0.08, "ebitda_margin": 0.22},
            {"revenue_growth": 0.12, "ebitda_margin": 0.25},
        ]
        result = _compute_earnings_takeaway(rows)
        assert "accelerating" in result
        assert "expanding" in result

    def test_decelerating_compressing(self):
        from backend.core.slides_generator import _compute_earnings_takeaway
        rows = [
            {"revenue_growth": 0.12, "ebitda_margin": 0.25},
            {"revenue_growth": 0.08, "ebitda_margin": 0.20},
        ]
        result = _compute_earnings_takeaway(rows)
        assert "decelerating" in result
        assert "compressing" in result

    def test_empty_rows(self):
        from backend.core.slides_generator import _compute_earnings_takeaway
        assert _compute_earnings_takeaway([]) == ""

    def test_single_row(self):
        from backend.core.slides_generator import _compute_earnings_takeaway
        assert _compute_earnings_takeaway([{"revenue_growth": 0.10}]) == ""


@_skip_no_weasyprint
class TestPrecedentTakeaway:
    """Precedent transaction takeaway computation."""

    def test_with_premium_and_upside(self):
        from backend.core.slides_generator import _compute_precedent_takeaway
        summary = {"medians": {"premium": 30.0, "ev_ebitda": 12.0}}
        result = _compute_precedent_takeaway(summary, 25.0)
        assert "premium" in result.lower()
        assert "below" in result

    def test_empty_summary(self):
        from backend.core.slides_generator import _compute_precedent_takeaway
        assert _compute_precedent_takeaway({}, None) == ""

    def test_none_summary(self):
        from backend.core.slides_generator import _compute_precedent_takeaway
        assert _compute_precedent_takeaway(None, None) == ""
