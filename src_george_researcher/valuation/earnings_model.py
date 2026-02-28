"""
Earnings Model Summary - Pure data formatting, no LLM.

Combines historical financials with analyst estimates into a unified table.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Number of historical and forecast years in the earnings model table.
# 5 historical + 5 forward matches sell-side convention and aligns
# with the DCF's 5-year projection horizon.
MAX_ACTUAL_YEARS = 5
MAX_ESTIMATE_YEARS = 5

from src_george_researcher.analysis.shared.growth_metrics import EnrichedFinancials
from src_george_researcher.data_fetchers.us.financial_datasets_client import AnalystEstimate
from src_george_researcher.analysis_agents import AnalysisResult


@dataclass(frozen=True)
class EarningsModelRow:
    """A single row in the earnings model table."""
    fiscal_year: int
    is_estimate: bool
    revenue: Optional[float] = None
    revenue_growth: Optional[float] = None
    ebitda: Optional[float] = None
    ebitda_margin: Optional[float] = None
    eps: Optional[float] = None


def build_earnings_model(
    enriched_financials: Optional[EnrichedFinancials],
    analyst_estimates: Optional[List[AnalystEstimate]],
) -> List[EarningsModelRow]:
    """
    Build earnings model rows from historical data + analyst estimates.

    Returns last 3 years of actuals + next 2 years of estimates.
    """
    rows = []

    # Historical rows from enriched financials (most recent first)
    if enriched_financials and enriched_financials.periods:
        for period in enriched_financials.periods[:MAX_ACTUAL_YEARS]:
            revenue = period.revenue.current_value if period.revenue else None
            revenue_growth = period.revenue.yoy_change if period.revenue else None
            # Use actual EBITDA (OI + D&A) when available, fall back to operating income
            ebitda_val = period.ebitda.current_value if period.ebitda and period.ebitda.current_value else None
            if ebitda_val is None:
                ebitda_val = period.operating_income.current_value if period.operating_income else None
            ebitda_margin_val = period.ebitda_margin.current_value if period.ebitda_margin and period.ebitda_margin.current_value else None
            if ebitda_margin_val is None:
                ebitda_margin_val = period.operating_margin.current_value if period.operating_margin else None
            eps_val = period.eps.current_value if period.eps else None

            fy = period.fiscal_year
            if not fy and period.period:
                try:
                    fy = int(period.period[:4])
                except (ValueError, IndexError):
                    fy = 0

            if not fy or fy <= 0:
                continue

            rows.append(EarningsModelRow(
                fiscal_year=fy,
                is_estimate=False,
                revenue=revenue,
                revenue_growth=revenue_growth,
                ebitda=ebitda_val,
                ebitda_margin=ebitda_margin_val,
                eps=eps_val,
            ))

    # Deduplicate actuals by fiscal_year, keeping first (most recent period)
    seen_fy: set[int] = set()
    deduped: list[EarningsModelRow] = []
    for row in rows:
        if row.fiscal_year not in seen_fy:
            seen_fy.add(row.fiscal_year)
            deduped.append(row)
    rows = deduped

    # Estimate rows from analyst estimates
    if analyst_estimates:
        # Group by fiscal year, take annual estimates
        actual_years = {r.fiscal_year for r in rows}
        by_year = {}
        for est in analyst_estimates:
            if est.fiscal_quarter is None and est.fiscal_year not in actual_years:
                if est.fiscal_year not in by_year:
                    by_year[est.fiscal_year] = est

        # Track prior-year revenue for chained growth calculation.
        # Use most recent actual revenue; fall back to enriched_financials
        # period[0] if all actuals had None revenue.
        prev_rev: Optional[float] = None
        for r in rows:
            if r.revenue and not r.is_estimate:
                prev_rev = r.revenue
                break
        if prev_rev is None and enriched_financials and enriched_financials.periods:
            first = enriched_financials.periods[0]
            if first.revenue and first.revenue.current_value:
                prev_rev = first.revenue.current_value

        for year in sorted(by_year.keys())[:MAX_ESTIMATE_YEARS]:
            est = by_year[year]
            rev_growth = None
            if est.revenue_estimate_avg and prev_rev and prev_rev > 0:
                rev_growth = (est.revenue_estimate_avg / prev_rev) - 1
            if est.revenue_estimate_avg:
                prev_rev = est.revenue_estimate_avg

            rows.append(EarningsModelRow(
                fiscal_year=est.fiscal_year,
                is_estimate=True,
                revenue=est.revenue_estimate_avg,
                revenue_growth=rev_growth,
                ebitda=None,
                ebitda_margin=None,
                eps=est.eps_estimate_avg,
            ))

    # Sort by fiscal year
    rows.sort(key=lambda r: r.fiscal_year)

    return rows


def format_earnings_model_markdown(rows: List[EarningsModelRow]) -> str:
    """Format earnings model rows as a markdown table."""
    if not rows:
        return "No earnings model data available."

    def fmt_rev(v):
        if v is None:
            return "N/A"
        if abs(v) >= 1e9:
            return f"${v / 1e9:.1f}B"
        return f"${v / 1e6:.0f}M"

    def fmt_pct(v):
        return f"{v * 100:.1f}%" if v is not None else "N/A"

    def fmt_eps(v):
        return f"${v:.2f}" if v is not None else "N/A"

    lines = [
        "| Fiscal Year | Revenue | Rev Growth | EBITDA | EBITDA Margin | EPS | Type |",
        "|---|---|---|---|---|---|---|",
    ]

    for row in rows:
        label = "Est" if row.is_estimate else "Act"
        yr = f"FY{row.fiscal_year}"
        if row.is_estimate:
            yr = f"**{yr}E**"

        lines.append(
            f"| {yr} | {fmt_rev(row.revenue)} | {fmt_pct(row.revenue_growth)} | "
            f"{fmt_rev(row.ebitda)} | {fmt_pct(row.ebitda_margin)} | "
            f"{fmt_eps(row.eps)} | {label} |"
        )

    return "\n".join(lines)


def earnings_rows_to_dict(rows: List[EarningsModelRow]) -> Dict:
    """Serialize earnings model rows for frontend consumption."""
    return {
        "rows": [
            {
                "fiscal_year": r.fiscal_year,
                "is_estimate": r.is_estimate,
                "revenue": r.revenue,
                "revenue_growth": r.revenue_growth,
                "ebitda": r.ebitda,
                "ebitda_margin": r.ebitda_margin,
                "eps": r.eps,
            }
            for r in rows
        ]
    }


def run_earnings_model(
    enriched_financials: Optional[EnrichedFinancials],
    analyst_estimates: Optional[List[AnalystEstimate]],
) -> Tuple[List[EarningsModelRow], AnalysisResult]:
    """Build earnings model and return rows + AnalysisResult."""
    rows = build_earnings_model(enriched_financials, analyst_estimates)
    content = format_earnings_model_markdown(rows)

    result = AnalysisResult(
        section="Earnings Model",
        content=content,
        tokens_used=0,
        success=len(rows) > 0,
        cost_usd=0.0,
    )
    return rows, result
