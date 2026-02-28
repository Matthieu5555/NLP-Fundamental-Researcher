"""
Unified color module for all backend services.

Reads from shared/colors.json (the single source of truth) and provides
typed access to every color used across PDF generation, chart rendering,
and belief classification.

All backend modules should import colors from here instead of hardcoding
hex values. The frontend derives its CSS variables from the same JSON file
via scripts/generate-theme.js.

Usage:
    from core.colors import PALETTE, get_rating_color, get_insight_badge

    color = PALETTE.brand.primary          # "#C87A23"
    rgb = PALETTE.brand.primary_rgb        # (200, 122, 35)
    green = PALETTE.semantic.success       # "#22c55e"
    buy_color = get_rating_color("BUY")    # "#16a34a"
    badge = get_insight_badge("confirmed") # {"label": "CONFIRMED", "color": ..., "bg": ...}
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

COLORS_PATH = Path(__file__).parent.parent.parent / "shared" / "colors.json"


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string (#RRGGBB) to RGB tuple (0-255)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        logger.warning("Invalid hex color: %s, returning black", hex_color)
        return (0, 0, 0)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _hex_to_rgb_normalized(hex_color: str) -> Tuple[float, float, float]:
    """Convert hex color string to matplotlib-compatible RGB tuple (0.0-1.0)."""
    r, g, b = _hex_to_rgb(hex_color)
    return (r / 255.0, g / 255.0, b / 255.0)


@dataclass(frozen=True)
class BrandColors:
    """Primary brand colors used across the entire application."""
    primary: str
    primary_dark: str
    primary_light: str
    gradient_from: str
    gradient_to: str
    surface: str
    surface_dark: str
    border: str
    dark: str
    dark_light: str

    @property
    def primary_rgb(self) -> Tuple[int, int, int]:
        return _hex_to_rgb(self.primary)

    @property
    def primary_rgb_normalized(self) -> Tuple[float, float, float]:
        return _hex_to_rgb_normalized(self.primary)


@dataclass(frozen=True)
class SemanticColors:
    """Semantic colors for success/danger/warning/info states."""
    success: str
    success_light: str
    success_dark: str
    danger: str
    danger_light: str
    danger_dark: str
    warning: str
    warning_light: str
    warning_dark: str
    info: str
    info_light: str
    info_dark: str


@dataclass(frozen=True)
class ChartColors:
    """Colors used in matplotlib chart generation."""
    background: str
    grid: str
    text: str
    bullish: str
    bearish: str
    sma20: str
    sma50: str
    sma200: str
    bollinger_line: str
    rsi_line: str
    rsi_overbought: str
    rsi_oversold: str
    rsi_center: str
    macd_line: str
    macd_signal: str
    macd_positive: str
    macd_negative: str
    volume_positive: str
    volume_negative: str
    axis_label: str
    title: str
    spine: str
    spine_technical: str
    grid_line: str
    dimmed_text: str


@dataclass(frozen=True)
class InsightBadge:
    """Badge styling for a belief/insight type."""
    label: str
    color: str
    bg: str


@dataclass(frozen=True)
class CaseStyling:
    """Bull/bear case or strategy grid styling."""
    bg: str
    border: str
    text: str = ""


@dataclass(frozen=True)
class FinancialHighlight:
    """Financial table row highlight colors."""
    bg: str
    text: str


@dataclass(frozen=True)
class PdfColors:
    """Colors used in the equity report PDF template."""
    body_text: str
    dark_text: str
    content_text: str
    label_text: str
    secondary_text: str
    dimmed_text: str
    border_light: str
    border_dotted: str
    row_separator: str
    section_bg: str
    highlight_bg: str
    table_alt_row: str
    bull_case: CaseStyling
    bear_case: CaseStyling
    swot_strengths: CaseStyling
    swot_weaknesses: CaseStyling
    swot_opportunities: CaseStyling
    swot_threats: CaseStyling
    margin_highlight: FinancialHighlight
    debt_highlight: FinancialHighlight
    fcf_highlight: FinancialHighlight
    positive: str
    negative: str
    base_case_bg: str
    estimate_row_bg: str

    def to_template_dict(self) -> Dict[str, str]:
        """Flatten all PDF colors into a simple dict for Jinja2 templates.

        Templates reference these as {{ c.body_text }}, {{ c.bull_case_bg }}, etc.
        This is the bridge between the typed dataclass and the template engine.
        """
        return {
            "body_text": self.body_text,
            "dark_text": self.dark_text,
            "content_text": self.content_text,
            "label_text": self.label_text,
            "secondary_text": self.secondary_text,
            "dimmed_text": self.dimmed_text,
            "border_light": self.border_light,
            "border_dotted": self.border_dotted,
            "row_separator": self.row_separator,
            "section_bg": self.section_bg,
            "highlight_bg": self.highlight_bg,
            "table_alt_row": self.table_alt_row,
            "positive": self.positive,
            "negative": self.negative,
            "bull_case_bg": self.bull_case.bg,
            "bull_case_border": self.bull_case.border,
            "bull_case_text": self.bull_case.text,
            "bear_case_bg": self.bear_case.bg,
            "bear_case_border": self.bear_case.border,
            "bear_case_text": self.bear_case.text,
            "swot_strengths_bg": self.swot_strengths.bg,
            "swot_strengths_border": self.swot_strengths.border,
            "swot_weaknesses_bg": self.swot_weaknesses.bg,
            "swot_weaknesses_border": self.swot_weaknesses.border,
            "swot_opportunities_bg": self.swot_opportunities.bg,
            "swot_opportunities_border": self.swot_opportunities.border,
            "swot_threats_bg": self.swot_threats.bg,
            "swot_threats_border": self.swot_threats.border,
            "margin_highlight_bg": self.margin_highlight.bg,
            "margin_highlight_text": self.margin_highlight.text,
            "debt_highlight_bg": self.debt_highlight.bg,
            "debt_highlight_text": self.debt_highlight.text,
            "fcf_highlight_bg": self.fcf_highlight.bg,
            "fcf_highlight_text": self.fcf_highlight.text,
            "base_case_bg": self.base_case_bg,
            "estimate_row_bg": self.estimate_row_bg,
        }


@dataclass(frozen=True)
class BadgeColors:
    """Priority badge colors (high/medium/low)."""
    high_bg: str
    high_text: str
    medium_bg: str
    medium_text: str
    low_bg: str
    low_text: str


@dataclass(frozen=True)
class ColorPalette:
    """Complete color palette for the application.

    This is the single runtime representation of shared/colors.json.
    All backend code should reference PALETTE.* instead of hardcoding hex values.
    """
    brand: BrandColors
    semantic: SemanticColors
    chart: ChartColors
    ratings: Dict[str, str]
    insights: Dict[str, InsightBadge]
    pdf: PdfColors
    badges: BadgeColors


def _load_palette() -> ColorPalette:
    """Load the color palette from shared/colors.json."""
    try:
        with open(COLORS_PATH, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Failed to load colors from %s: %s", COLORS_PATH, e)
        raise RuntimeError(f"Cannot load color palette: {e}") from e

    brand_data = data["brand"]
    semantic_data = data["semantic"]
    chart_data = data["chart"]
    pdf_data = data["pdf"]
    badges_data = data["badges"]

    brand = BrandColors(
        primary=brand_data["primary"],
        primary_dark=brand_data["primaryDark"],
        primary_light=brand_data["primaryLight"],
        gradient_from=brand_data["gradientFrom"],
        gradient_to=brand_data["gradientTo"],
        surface=brand_data["surface"],
        surface_dark=brand_data["surfaceDark"],
        border=brand_data["border"],
        dark=brand_data["dark"],
        dark_light=brand_data["darkLight"],
    )

    semantic = SemanticColors(
        success=semantic_data["success"],
        success_light=semantic_data["successLight"],
        success_dark=semantic_data["successDark"],
        danger=semantic_data["danger"],
        danger_light=semantic_data["dangerLight"],
        danger_dark=semantic_data["dangerDark"],
        warning=semantic_data["warning"],
        warning_light=semantic_data["warningLight"],
        warning_dark=semantic_data["warningDark"],
        info=semantic_data["info"],
        info_light=semantic_data["infoLight"],
        info_dark=semantic_data["infoDark"],
    )

    chart = ChartColors(
        background=chart_data["background"],
        grid=chart_data["grid"],
        text=chart_data["text"],
        bullish=chart_data["bullish"],
        bearish=chart_data["bearish"],
        sma20=chart_data["sma20"],
        sma50=chart_data["sma50"],
        sma200=chart_data["sma200"],
        bollinger_line=chart_data["bollingerLine"],
        rsi_line=chart_data["rsiLine"],
        rsi_overbought=chart_data["rsiOverbought"],
        rsi_oversold=chart_data["rsiOversold"],
        rsi_center=chart_data["rsiCenter"],
        macd_line=chart_data["macdLine"],
        macd_signal=chart_data["macdSignal"],
        macd_positive=chart_data["macdPositive"],
        macd_negative=chart_data["macdNegative"],
        volume_positive=chart_data["volumePositive"],
        volume_negative=chart_data["volumeNegative"],
        axis_label=chart_data["axisLabel"],
        title=chart_data["title"],
        spine=chart_data["spine"],
        spine_technical=chart_data["spineTechnical"],
        grid_line=chart_data["gridLine"],
        dimmed_text=chart_data["dimmedText"],
    )

    # Build ratings lookup (case-insensitive keys)
    ratings_data = data["ratings"]
    ratings = {
        "BUY": ratings_data["buy"],
        "STRONG BUY": ratings_data["strongBuy"],
        "SELL": ratings_data["sell"],
        "STRONG SELL": ratings_data["strongSell"],
        "HOLD": ratings_data["hold"],
        "NEUTRAL": ratings_data["neutral"],
        "N/A": ratings_data["na"],
    }

    # Build insight badges
    insights_data = data["insights"]
    insights = {
        key: InsightBadge(
            label=val["label"],
            color=val["color"],
            bg=val["bg"],
        )
        for key, val in insights_data.items()
    }

    pdf = PdfColors(
        body_text=pdf_data["bodyText"],
        dark_text=pdf_data["darkText"],
        content_text=pdf_data["contentText"],
        label_text=pdf_data["labelText"],
        secondary_text=pdf_data["secondaryText"],
        dimmed_text=pdf_data["dimmedText"],
        border_light=pdf_data["borderLight"],
        border_dotted=pdf_data["borderDotted"],
        row_separator=pdf_data["rowSeparator"],
        section_bg=pdf_data["sectionBg"],
        highlight_bg=pdf_data["highlightBg"],
        table_alt_row=pdf_data["tableAltRow"],
        bull_case=CaseStyling(**pdf_data["bullCase"]),
        bear_case=CaseStyling(**pdf_data["bearCase"]),
        swot_strengths=CaseStyling(**pdf_data["swot"]["strengths"]),
        swot_weaknesses=CaseStyling(**pdf_data["swot"]["weaknesses"]),
        swot_opportunities=CaseStyling(**pdf_data["swot"]["opportunities"]),
        swot_threats=CaseStyling(**pdf_data["swot"]["threats"]),
        margin_highlight=FinancialHighlight(**pdf_data["financials"]["marginHighlight"]),
        debt_highlight=FinancialHighlight(**pdf_data["financials"]["debtHighlight"]),
        fcf_highlight=FinancialHighlight(**pdf_data["financials"]["fcfHighlight"]),
        positive=pdf_data["positive"],
        negative=pdf_data["negative"],
        base_case_bg=pdf_data["baseCaseBg"],
        estimate_row_bg=pdf_data["estimateRowBg"],
    )

    badges = BadgeColors(
        high_bg=badges_data["high"]["bg"],
        high_text=badges_data["high"]["text"],
        medium_bg=badges_data["medium"]["bg"],
        medium_text=badges_data["medium"]["text"],
        low_bg=badges_data["low"]["bg"],
        low_text=badges_data["low"]["text"],
    )

    return ColorPalette(
        brand=brand,
        semantic=semantic,
        chart=chart,
        ratings=ratings,
        insights=insights,
        pdf=pdf,
        badges=badges,
    )


# Module-level singleton — loaded once at import time
PALETTE = _load_palette()


def get_rating_color(rating: str) -> str:
    """Get the hex color for a stock rating badge.

    Args:
        rating: Rating string like "BUY", "SELL", "HOLD", "STRONG BUY", etc.

    Returns:
        Hex color string. Falls back to neutral gray for unknown ratings.
    """
    return PALETTE.ratings.get(rating.upper(), PALETTE.ratings["N/A"])


def get_insight_badge(insight_key: str) -> dict:
    """Get badge styling for an insight/belief type.

    Args:
        insight_key: Key like "confirmed", "risk", "opportunity", etc.

    Returns:
        Dict with "label", "color", "bg" keys.
    """
    badge = PALETTE.insights.get(insight_key, PALETTE.insights["default"])
    return {"label": badge.label, "color": badge.color, "bg": badge.bg}


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string (#RRGGBB) to RGB tuple (0-255).

    Public re-export of the internal helper for backwards compatibility
    with code that imported hex_to_rgb from branding_config.
    """
    return _hex_to_rgb(hex_color)


def hex_to_rgb_normalized(hex_color: str) -> Tuple[float, float, float]:
    """Convert hex color to matplotlib-compatible RGB tuple (0.0-1.0)."""
    return _hex_to_rgb_normalized(hex_color)
