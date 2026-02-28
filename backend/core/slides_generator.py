"""
Slide Deck Generator -- condensed bullet-point slides as landscape PDF.

Two-phase pipeline:
1. build_slides_context() extracts structured data and uses the LLM to
   summarize prose sections into presentation-ready bullet points.
2. generate_slides() renders the equity_slides.html template via WeasyPrint.

Single entry point: generate_slides() -> bytes (PDF)
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from .report_builder import ReportState, AnalystSource
from .branding_config import ReportBrandingConfig, get_default_config
from .colors import PALETTE
from .pdf_formatting import (
    RATING_COLORS,
    extract_highlights,
    extract_recommendation,
    format_number,
    get_exchange_name,
    parse_strategy_grid,
)

if TYPE_CHECKING:
    from src_george_researcher.data_fetchers.stock_data import StockInfo
    from .pdf_data_collector import FirstPageData

logger = logging.getLogger(__name__)

# Maximum characters for source titles on the sources slide.
# Longer titles are truncated with "..." to prevent overflow.
SOURCE_TITLE_MAX_CHARS = 80

TEMPLATE_DIR = Path(__file__).parent / "pdf_templates"

# =============================================================================
# LLM SUMMARIZATION
# =============================================================================
# Impact of changing: controls how verbose each bullet-point slide is.
BULLET_PROMPT_TEMPLATE = (
    "Summarize the following into exactly {count} concise bullet points "
    "suitable for a presentation slide. Each bullet must be under 15 words. "
    "Return only the bullets, one per line, prefixed with a dash (-).\n\n"
    "{content}"
)
BULLET_SYSTEM_PROMPT = (
    "You are a financial analyst preparing presentation slides. "
    "Be concise and data-driven. No filler."
)


def _summarize_to_bullets(content: str, count: int = 5) -> List[str]:
    """
    Use the LLM to condense a prose section into bullet points.

    Falls back to mechanical extraction (first N bullet points or sentences)
    if the LLM call fails for any reason.
    """
    if not content or not content.strip():
        return []

    try:
        from backend.agents.llm_wrapper import get_llm_response

        prompt = BULLET_PROMPT_TEMPLATE.format(count=count, content=content[:2000])
        response = get_llm_response(
            prompt=prompt,
            system_prompt=BULLET_SYSTEM_PROMPT,
            temperature=0.3,
        )

        if response.startswith("Error:"):
            raise ValueError(response)

        bullets = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("-"):
                line = line[1:].strip()
            if line:
                bullets.append(line)
        if bullets:
            return bullets[:count]

    except Exception as e:
        logger.warning(f"LLM bullet summarization failed, using fallback: {e}")

    return extract_highlights(content, max_items=count)


def _summarize_sections_parallel(sections: Dict[str, str], count: int = 5) -> Dict[str, List[str]]:
    """
    Summarize multiple prose sections into bullets in parallel.

    Each section is a short text (~500 chars), so payloads are small and
    parallelism gives a meaningful speedup on the network-bound LLM calls.
    """
    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_summarize_to_bullets, content, count): key
            for key, content in sections.items()
            if content
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                logger.warning(f"Parallel summarization failed for {key}: {e}")
                results[key] = extract_highlights(sections[key], max_items=count)

    return results


def _compute_earnings_takeaway(rows: List[Dict]) -> str:
    """Derive a one-sentence takeaway from earnings model rows.

    Compares first and last revenue growth (accelerating vs decelerating)
    and margin direction (expanding vs compressing). No LLM needed.
    """
    if not rows or len(rows) < 2:
        return ""
    growths = [r.get("revenue_growth") for r in rows if r.get("revenue_growth") is not None]
    margins = [r.get("ebitda_margin") for r in rows if r.get("ebitda_margin") is not None]
    parts = []
    if len(growths) >= 2:
        direction = "accelerating" if growths[-1] > growths[0] else "decelerating"
        parts.append(f"Revenue growth {direction} from {growths[0]*100:.1f}% to {growths[-1]*100:.1f}%")
    if len(margins) >= 2:
        direction = "expanding" if margins[-1] > margins[0] else "compressing"
        parts.append(f"margins {direction}")
    if not parts:
        return ""
    return "; ".join(parts) + "."


def _compute_precedent_takeaway(
    precedent_summary: Dict, current_upside_pct: Optional[float]
) -> str:
    """Derive a one-sentence takeaway from precedent transaction data.

    Compares median premium to current upside. No LLM needed.
    """
    if not precedent_summary:
        return ""
    medians = precedent_summary.get("medians", {})
    median_premium = medians.get("premium")
    median_ev_ebitda = medians.get("ev_ebitda")
    parts = []
    if median_premium is not None:
        parts.append(f"Median deal premium: {median_premium:.0f}%")
        if current_upside_pct is not None:
            comparison = "above" if current_upside_pct > median_premium else "below"
            parts.append(f"current upside ({current_upside_pct:.1f}%) is {comparison} the precedent median")
    elif median_ev_ebitda is not None:
        parts.append(f"Median EV/EBITDA: {median_ev_ebitda:.1f}x")
    if not parts:
        return ""
    return "; ".join(parts) + "."


def _build_forward_snapshot(
    earnings_table: Dict,
    current_price: Optional[float],
    scenario_summary: Dict,
) -> List[Dict]:
    """Build a forward financial snapshot table from earnings model data.

    Extracts forward EPS and computes implied forward P/E for estimated years.
    Also includes the bull/base/bear fair value range as a compact summary row.
    Returns a list of dicts suitable for rendering as a small table on the cover.
    """
    rows = []
    if not earnings_table:
        return rows

    earnings_rows = earnings_table.get("rows", [])
    for row in earnings_rows:
        if not row.get("is_estimate"):
            continue
        year = row.get("year") or row.get("period", "")
        eps = row.get("eps")
        revenue = row.get("revenue")
        ebitda_margin = row.get("ebitda_margin")
        fwd_pe = None
        if eps and current_price and eps > 0:
            fwd_pe = round(current_price / eps, 1)

        rows.append({
            "year": year,
            "eps": eps,
            "forward_pe": fwd_pe,
            "revenue": revenue,
            "ebitda_margin": ebitda_margin,
        })

        if len(rows) >= 3:
            break

    return rows


def _get_section_content(report_state: ReportState, section_id: str) -> str:
    """Safely extract raw text content from a report section."""
    section = report_state.sections.get(section_id)
    if section and hasattr(section, "content") and section.content:
        return section.content
    return ""


# =============================================================================
# CONTEXT BUILDER
# =============================================================================

def build_slides_context(
    report_state: ReportState,
    ticker: str,
    session_metadata: Dict[str, Any],
    stock_info: Optional['StockInfo'] = None,
    branding: Optional[ReportBrandingConfig] = None,
    analyst_sources: Optional[List[AnalystSource]] = None,
    first_page_data: Optional['FirstPageData'] = None,
) -> Dict[str, Any]:
    """
    Build the template context for bullet-point slides.

    Reuses structured data that is already slide-friendly (company info, key
    metrics, strategy grid) and calls the LLM to condense prose sections into
    4-5 bullet points each.

    Args:
        report_state: The report with all prose sections.
        ticker: Stock ticker symbol.
        session_metadata: session.metadata dict with valuation model outputs.
        stock_info: Optional stock info for company details.
        branding: White-label branding config.
        analyst_sources: Analyst belief sources.
        first_page_data: Pre-collected first-page metrics.
    """
    from datetime import datetime
    from .pdf_formatting import md_to_html

    branding = branding or get_default_config()
    rating = extract_recommendation(report_state)

    # --- Company info (same logic as pdf_generator_v2) ---
    company_name = ticker
    exchange = ""
    sector = ""

    if stock_info:
        company_name = getattr(stock_info, "name", ticker) or ticker
        exchange = getattr(stock_info, "exchange", "") or ""
        sector = getattr(stock_info, "sector", "") or getattr(stock_info, "industry", "") or ""
    elif first_page_data:
        company_name = first_page_data.company_name or ticker
        exchange = first_page_data.exchange or ""
        sector = first_page_data.sector or ""

    # --- Structured data from first_page_data (already slide-friendly) ---
    key_data = []
    statistics = []
    returns = []

    if first_page_data:
        key_data = [
            {"label": "Price", "value": format_number(first_page_data.current_price, "price")},
            {"label": "Market Cap", "value": format_number(first_page_data.market_cap, "market_cap")},
            {"label": "EPS", "value": f"{first_page_data.eps:.2f}" if first_page_data.eps is not None else "N/A"},
            {"label": "52W High", "value": format_number(first_page_data.week_52_high, "price")},
            {"label": "52W Low", "value": format_number(first_page_data.week_52_low, "price")},
        ]
        statistics = [
            {"label": "P/E (TTM)", "value": format_number(first_page_data.pe_ratio, "ratio")},
            {"label": "P/B", "value": format_number(first_page_data.price_to_book, "ratio")},
            {"label": "EV/EBITDA", "value": format_number(first_page_data.ev_to_ebitda, "ratio")},
            {"label": "Div Yield", "value": format_number(first_page_data.dividend_yield, "percent_raw")},
        ]
        if first_page_data.returns:
            r = first_page_data.returns
            returns = [
                {"period": "1M", "value": r.return_1m, "display": format_number(r.return_1m, "percent") if r.return_1m is not None else "N/A"},
                {"period": "YTD", "value": r.return_ytd, "display": format_number(r.return_ytd, "percent") if r.return_ytd is not None else "N/A"},
                {"period": "1Y", "value": r.return_1y, "display": format_number(r.return_1y, "percent") if r.return_1y is not None else "N/A"},
                {"period": "5Y", "value": r.return_5y, "display": format_number(r.return_5y, "percent") if r.return_5y is not None else "N/A"},
            ]
    elif stock_info:
        key_data = [
            {"label": "Price", "value": format_number(getattr(stock_info, "current_price", None), "price")},
            {"label": "Market Cap", "value": format_number(getattr(stock_info, "market_cap", None), "market_cap")},
        ]

    # --- Headline and highlights (already concise, reuse directly) ---
    report_headline = report_state.metadata.get("headline", "")
    raw_highlights = []
    if "investment_thesis" in report_state.sections:
        full = report_state.sections["investment_thesis"]
        if hasattr(full, "content") and full.content:
            raw_highlights = extract_highlights(full.content, max_items=4)
    highlights = [md_to_html(h) for h in raw_highlights]

    # --- Strategy grid (already structured, reuse directly) ---
    strategy_grid = None
    strategy_content = _get_section_content(report_state, "strategy")
    if strategy_content:
        strategy_grid = parse_strategy_grid(strategy_content)

    # --- LLM-summarized bullet sections (parallel) ---
    prose_sections: Dict[str, str] = {
        "thesis": _get_section_content(report_state, "investment_thesis"),
        "bull": _get_section_content(report_state, "bull_case"),
        "bear": _get_section_content(report_state, "bear_case"),
        "moat": _get_section_content(report_state, "moat"),
        "external": _get_section_content(report_state, "industry"),
    }
    # If strategy grid parsing failed, fall through to LLM summarization
    if not strategy_grid and strategy_content:
        prose_sections["strategy"] = strategy_content
    bullet_results = _summarize_sections_parallel(prose_sections, count=5)

    thesis_bullets = bullet_results.get("thesis", [])
    bull_bullets = bullet_results.get("bull", [])
    bear_bullets = bullet_results.get("bear", [])
    moat_bullets = bullet_results.get("moat", [])
    external_bullets = bullet_results.get("external", [])
    strategy_bullets = bullet_results.get("strategy", [])

    # Conviction summary (short paragraph, not bullets)
    conviction_content = _get_section_content(report_state, "conviction")
    conviction_summary = ""
    if conviction_content:
        # Take first 2 sentences as summary
        sentences = re.split(r'(?<=[.!?])\s+', conviction_content.strip())
        conviction_summary = " ".join(sentences[:2])

    # --- Structured valuation data from session metadata ---
    from .valuation_display import build_valuation_display

    val = build_valuation_display(
        session_metadata,
        current_price=first_page_data.current_price if first_page_data else None,
    )
    dcf_summary = val.dcf_summary
    scenario_summary = val.scenario_summary
    football_ranges = val.football_ranges
    football_current_pct = val.football_current_pct
    conviction_data = val.conviction_structured
    conviction_categories = val.conviction_categories

    # --- Executive summary (defensive assembly from multiple sources) ---
    current_price = first_page_data.current_price if first_page_data else None
    target_price = (
        scenario_summary.get("weighted_fair_value")
        or dcf_summary.get("fair_value")
    )
    exec_upside_pct = None
    if target_price is not None and current_price and current_price > 0:
        exec_upside_pct = round(((target_price - current_price) / current_price) * 100, 1)
    exec_summary = {
        "rating": rating,
        "target_price": target_price,
        "current_price": current_price,
        "upside_pct": exec_upside_pct,
        "catalysts": thesis_bullets[:3] or bull_bullets[:3],
        "key_risk": bear_bullets[0] if bear_bullets else None,
        "weighted_fv": scenario_summary.get("weighted_fair_value"),
    }

    # --- Investment context (structured thesis data) ---
    investment_context = val.investment_context

    # --- Forward snapshot table (cover page) ---
    # Built from earnings model rows: extract forward EPS, P/E, EV/EBITDA for 2-3 years
    forward_snapshot = _build_forward_snapshot(
        val.earnings_table,
        current_price,
        scenario_summary,
    )

    # --- Analytical takeaways for data tables ---
    earnings_takeaway = _compute_earnings_takeaway(
        val.earnings_table.get("rows", []) if val.earnings_table else []
    )
    precedent_takeaway = _compute_precedent_takeaway(
        val.precedent_summary,
        exec_upside_pct,
    )

    # --- Sources ---
    from .report_builder import Source
    research_sources = []
    sources_section = report_state.sections.get("sources")
    if sources_section and hasattr(sources_section, "sources"):
        for source in sources_section.sources:
            if isinstance(source, Source):
                title = source.title or ""
                if len(title) > SOURCE_TITLE_MAX_CHARS:
                    title = title[:SOURCE_TITLE_MAX_CHARS] + "..."
                research_sources.append({
                    "id": source.id,
                    "title": title,
                    "url": source.url,
                    "date": source.date if source.date != "N/A" else None,
                })
            elif isinstance(source, dict):
                src_copy = dict(source)
                t = src_copy.get("title", "")
                if len(t) > SOURCE_TITLE_MAX_CHARS:
                    src_copy["title"] = t[:SOURCE_TITLE_MAX_CHARS] + "..."
                research_sources.append(src_copy)

    analyst_notes = []
    if analyst_sources:
        for src in analyst_sources:
            analyst_notes.append({
                "id": src.id,
                "content": src.to_citation_text() if hasattr(src, "to_citation_text") else str(src),
            })

    context = {
        # Colors from unified palette (replaces all hardcoded hex in templates)
        "c": PALETTE.pdf.to_template_dict(),

        # Branding
        "firm_name": branding.firm.name,
        "tool_branding": branding.firm.tool_branding,
        "primary_color": branding.firm.primary_color,
        "analyst_name": branding.analyst.full_name,
        "analyst_email": branding.analyst.email,
        "analyst_sector": branding.analyst.sector,

        # Company
        "ticker": ticker,
        "company_name": company_name,
        "exchange": get_exchange_name(exchange),
        "sector": sector or "Equity",
        "rating": rating,
        "rating_color": RATING_COLORS.get(rating, RATING_COLORS["N/A"]),
        "report_date": datetime.now().strftime("%d %B %Y"),
        "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M"),

        # Structured data (reused from report)
        "key_data": key_data,
        "statistics": statistics,
        "returns": returns,
        "report_headline": report_headline,
        "highlights": highlights,
        "strategy_grid": strategy_grid,
        "strategy_bullets": strategy_bullets,
        "exec_summary": exec_summary,

        # LLM-summarized bullets
        "thesis_bullets": thesis_bullets,
        "bull_bullets": bull_bullets,
        "bear_bullets": bear_bullets,
        "moat_bullets": moat_bullets,
        "external_bullets": external_bullets,
        "conviction_summary": conviction_summary,

        # Structured valuation data
        "dcf_summary": dcf_summary,
        "scenario_summary": scenario_summary,
        "football_ranges": football_ranges,
        "football_current_pct": football_current_pct,
        "football_current_price": val.football_current_price,
        "sensitivity_grid": val.sensitivity_grid,
        "growth_margin_grid": val.growth_margin_grid,
        "conviction_structured": conviction_data,
        "conviction_categories": conviction_categories,
        "earnings_table": val.earnings_table,
        "precedent_summary": val.precedent_summary,
        "comp_summary": val.comp_summary,
        "earnings_takeaway": earnings_takeaway,
        "precedent_takeaway": precedent_takeaway,

        # Investment context (structured thesis data)
        "investment_context": investment_context,
        "forward_snapshot": forward_snapshot,

        # Sources
        "research_sources": research_sources,
        "analyst_sources": analyst_notes,

        # Model audit (LLM-powered quality review)
        "model_audit": session_metadata.get("model_audit", {}),
    }

    # Build table of contents from slides that will actually render.
    # Order matches template slide order.
    toc_slide_sections = [
        ("thesis_bullets", "Investment Thesis"),
        ("conviction_categories", "Conviction & Rating"),
        ("key_data", "Financial Overview"),
        ("football_ranges", "Valuation Football Field"),
        ("dcf_summary", "DCF Valuation"),
        ("scenario_summary", "Scenario Analysis"),
        ("comp_summary", "Comparable Companies"),
        ("strategy_grid|strategy_bullets", "Strategic Assessment"),
        ("external_bullets", "Industry Dynamics"),
        ("moat_bullets", "Competitive Moat"),
        ("bull_bullets", "Investment Cases"),
        ("investment_context", "Catalysts & Risks"),
        ("research_sources", "Sources & References"),
    ]
    toc_entries = []
    seen_titles: set[str] = set()
    for key, title in toc_slide_sections:
        if title in seen_titles:
            continue
        if key == "bull_bullets":
            if context.get("bull_bullets") or context.get("bear_bullets"):
                toc_entries.append({"title": title})
                seen_titles.add(title)
        elif "|" in key:
            # OR logic: show if any of the pipe-separated keys have data
            if any(context.get(k) for k in key.split("|")):
                toc_entries.append({"title": title})
                seen_titles.add(title)
        elif context.get(key):
            toc_entries.append({"title": title})
            seen_titles.add(title)
    context["toc_entries"] = toc_entries

    return context


# =============================================================================
# PDF GENERATION
# =============================================================================

def generate_slides(
    report_state: ReportState,
    ticker: str,
    session_metadata: Optional[Dict[str, Any]] = None,
    stock_info: Optional['StockInfo'] = None,
    branding: Optional[ReportBrandingConfig] = None,
    analyst_sources: Optional[List[AnalystSource]] = None,
    first_page_data: Optional['FirstPageData'] = None,
    financial_statements: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Generate a condensed slide deck as a landscape PDF.

    When session_metadata is provided, uses build_slides_context() which
    produces LLM-summarized bullet points and structured valuation cards.
    Falls back to the old prose-based context when metadata is absent.

    Returns:
        PDF bytes of the slide deck.
    """
    branding = branding or get_default_config()

    if first_page_data is None:
        try:
            from .pdf_data_collector import collect_first_page_data
            first_page_data = collect_first_page_data(ticker, stock_info)
        except Exception as e:
            logger.warning(f"Could not collect first page data: {e}")

    if session_metadata is not None:
        context = build_slides_context(
            report_state=report_state,
            ticker=ticker,
            session_metadata=session_metadata,
            stock_info=stock_info,
            branding=branding,
            analyst_sources=analyst_sources,
            first_page_data=first_page_data,
        )
    else:
        # Fallback: old prose-based context for backwards compatibility
        from .pdf_generator_v2 import build_template_context
        context = build_template_context(
            report_state=report_state,
            ticker=ticker,
            stock_info=stock_info,
            branding=branding,
            analyst_sources=analyst_sources,
            first_page_data=first_page_data,
            financial_statements=financial_statements,
        )

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("equity_slides.html")
    html_content = template.render(**context)

    html = HTML(string=html_content, base_url=str(TEMPLATE_DIR))
    return html.write_pdf()
