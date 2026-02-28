"""
DCF Agent - Uses LLM to reason about DCF assumptions, then runs deterministic engine.

Flow:
1. Extract financial history from enriched financials
2. Call LLM to generate assumptions with rationale
3. Validate and bound-check assumptions
4. Run calculate_dcf() for the math
5. Format narrative result
"""

import json
import logging
from typing import Optional, List

from src_george_researcher.analysis_agents import AnalysisResult
from src_george_researcher.data_fetchers.stock_data import StockInfo
from src_george_researcher.data_fetchers.us.financial_datasets_client import (
    FinancialStatement,
    AnalystEstimate,
)
from src_george_researcher.analysis.shared.growth_metrics import EnrichedFinancials
from src_george_researcher.llm import call_llm
from src_george_researcher.prompts import DCF_ASSUMPTIONS_SYSTEM
from src_george_researcher.valuation.dcf_engine import (
    DCFAssumptions,
    DCFResult,
    EVBridge,
    WACCComponents,
    calculate_dcf,
    compute_wacc,
)
from src_george_researcher.valuation.exceptions import AssumptionParseError, InsufficientDataError
from src_george_researcher.valuation.constants import (
    MAX_GROWTH_RATE, MIN_FCF_MARGIN, MAX_FCF_MARGIN,
    MIN_WACC, MAX_WACC, MIN_TERMINAL_GROWTH,
    MAX_HISTORICAL_PERIODS, MAX_ANALYST_ESTIMATES,
    DEFAULT_REVENUE_GROWTH, DEFAULT_FCF_MARGIN, DEFAULT_WACC, DEFAULT_TERMINAL_GROWTH,
)
from src_george_researcher.analysis.strategic_assessment import StrategicAssessment

logger = logging.getLogger(__name__)

# Conservative defaults if LLM parsing fails
DEFAULT_ASSUMPTIONS = DCFAssumptions(
    revenue_growth_rates=DEFAULT_REVENUE_GROWTH,
    fcf_margin=DEFAULT_FCF_MARGIN,
    wacc=DEFAULT_WACC,
    terminal_growth_rate=DEFAULT_TERMINAL_GROWTH,
    revenue_growth_rationale="Conservative defaults used due to parsing failure.",
    fcf_margin_rationale="Conservative defaults used due to parsing failure.",
    wacc_rationale="Conservative defaults used due to parsing failure.",
    terminal_growth_rationale="Conservative defaults used due to parsing failure.",
)


def _extract_financial_history(
    enriched_financials: Optional[EnrichedFinancials],
    financials: Optional[List[FinancialStatement]],
) -> str:
    """Build a text summary of financial history for the LLM."""
    lines = []

    if enriched_financials and enriched_financials.periods:
        lines.append("## Revenue & Margin History (Annual)")
        for period in enriched_financials.periods[:MAX_HISTORICAL_PERIODS]:
            rev = period.revenue.current_value if period.revenue else None
            rev_growth = period.revenue.yoy_change if period.revenue else None
            fcf = period.free_cash_flow.current_value if period.free_cash_flow else None
            gm = period.gross_margin.current_value if period.gross_margin else None
            om = period.operating_margin.current_value if period.operating_margin else None
            ebitda = period.ebitda.current_value if period.ebitda else None
            da = period.depreciation_and_amortization.current_value if period.depreciation_and_amortization else None
            sbc = period.stock_based_compensation.current_value if period.stock_based_compensation else None
            capex = period.capex.current_value if period.capex else None
            rev_str = f"${rev / 1e9:.1f}B" if rev else "N/A"
            growth_str = f"{rev_growth * 100:.1f}%" if rev_growth is not None else "N/A"
            fcf_str = f"${fcf / 1e9:.1f}B" if fcf else "N/A"
            gm_str = f"{gm * 100:.1f}%" if gm else "N/A"
            om_str = f"{om * 100:.1f}%" if om else "N/A"
            ebitda_str = f"${ebitda / 1e9:.1f}B" if ebitda else "N/A"
            da_str = f"${da / 1e9:.1f}B" if da else "N/A"
            sbc_str = f"${sbc / 1e9:.1f}B" if sbc else "N/A"
            capex_str = f"${capex / 1e9:.1f}B" if capex else "N/A"
            lines.append(f"  {period.period}: Revenue={rev_str}, YoY={growth_str}, "
                        f"Gross Margin={gm_str}, Op Margin={om_str}, "
                        f"EBITDA={ebitda_str}, D&A={da_str}, SBC={sbc_str}, "
                        f"CapEx={capex_str}, FCF={fcf_str}")
            # Flag high SBC
            if sbc and rev and rev > 0 and (sbc / rev) > 0.05:
                lines.append(f"    ⚠ SBC is {sbc / rev * 100:.1f}% of revenue — significant dilution risk")

        if enriched_financials.revenue_cagr_3y:
            lines.append(f"  3-Year Revenue CAGR: {enriched_financials.revenue_cagr_3y * 100:.1f}%")
        if enriched_financials.revenue_cagr_5y:
            lines.append(f"  5-Year Revenue CAGR: {enriched_financials.revenue_cagr_5y * 100:.1f}%")

    if financials:
        lines.append("\n## Balance Sheet (Latest)")
        latest = financials[0]
        if latest.cash_and_equivalents:
            lines.append(f"  Cash: ${latest.cash_and_equivalents / 1e9:.1f}B")
        if latest.total_debt:
            lines.append(f"  Total Debt: ${latest.total_debt / 1e9:.1f}B")
        net_debt = (latest.total_debt or 0) - (latest.cash_and_equivalents or 0)
        lines.append(f"  Net Debt: ${net_debt / 1e9:.1f}B")

    return "\n".join(lines) if lines else "No financial history available."


def _parse_assumptions(
    response_text: str,
    computed_wacc: Optional[float] = None,
    wacc_rationale: str = "",
) -> Optional[DCFAssumptions]:
    """Parse LLM JSON response into DCFAssumptions.

    If computed_wacc is provided, it overrides the LLM's WACC guess.
    Supports both legacy (fcf_margin) and decomposed (gross_margins) formats.
    """
    try:
        # Try to extract JSON from response (may have markdown code blocks)
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)

        growth_rates = data.get("revenue_growth_rates", [0.05, 0.04, 0.03, 0.03, 0.02])
        terminal_growth = data.get("terminal_growth_rate", 0.025)

        # Validate growth rates
        growth_rates = [max(-MAX_GROWTH_RATE, min(MAX_GROWTH_RATE, r)) for r in growth_rates]

        # Use computed WACC if available, otherwise use LLM's estimate
        wacc = computed_wacc if computed_wacc else data.get("wacc", 0.10)
        wacc = max(MIN_WACC, min(MAX_WACC, wacc))
        # Terminal growth must stay ≥1pp below WACC to avoid infinite terminal value
        terminal_growth = max(MIN_TERMINAL_GROWTH, min(wacc - 0.01, terminal_growth))

        # Check if decomposed model data is present
        gross_margins = data.get("gross_margins")
        if gross_margins:
            # Decomposed model
            def _clamp_list(vals, lo, hi):
                return [max(lo, min(hi, v)) for v in vals] if vals else None

            return DCFAssumptions(
                revenue_growth_rates=growth_rates,
                wacc=wacc,
                terminal_growth_rate=terminal_growth,
                projection_years=data.get("projection_years", 5),
                gross_margins=_clamp_list(gross_margins, 0.0, 0.95),
                opex_as_pct_revenue=_clamp_list(data.get("opex_as_pct_revenue"), 0.05, 0.80),
                da_as_pct_revenue=max(0, min(0.20, data.get("da_as_pct_revenue", 0.04))),
                sbc_as_pct_revenue=max(0, min(0.15, data.get("sbc_as_pct_revenue", 0.02))),
                capex_as_pct_revenue=_clamp_list(data.get("capex_as_pct_revenue"), 0.01, 0.25),
                nwc_change_pct=max(0, min(0.15, data.get("nwc_change_pct", 0.05))),
                tax_rate=max(0.10, min(0.35, data.get("tax_rate", 0.21))),
                revenue_growth_rationale=data.get("revenue_growth_rationale", ""),
                margin_rationale=data.get("margin_rationale", ""),
                wacc_rationale=wacc_rationale or data.get("wacc_rationale", ""),
                terminal_growth_rationale=data.get("terminal_growth_rationale", ""),
            )
        else:
            # Legacy flat FCF margin model
            fcf_margin = data.get("fcf_margin", 0.15)
            fcf_margin = max(MIN_FCF_MARGIN, min(MAX_FCF_MARGIN, fcf_margin))

            return DCFAssumptions(
                revenue_growth_rates=growth_rates,
                fcf_margin=fcf_margin,
                wacc=wacc,
                terminal_growth_rate=terminal_growth,
                projection_years=data.get("projection_years", 5),
                revenue_growth_rationale=data.get("revenue_growth_rationale", ""),
                fcf_margin_rationale=data.get("fcf_margin_rationale", ""),
                wacc_rationale=wacc_rationale or data.get("wacc_rationale", ""),
                terminal_growth_rationale=data.get("terminal_growth_rationale", ""),
            )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise AssumptionParseError(f"Failed to parse DCF assumptions: {e}") from e


def _format_dcf_narrative(result: DCFResult) -> str:
    """Format DCF result as markdown for the report section."""
    a = result.assumptions
    direction = "undervalued" if result.upside_downside_pct > 0 else "overvalued"
    abs_pct = abs(result.upside_downside_pct)

    lines = [
        f"**DCF Fair Value: ${result.fair_value_per_share:.2f}** | "
        f"Current Price: {f'${result.current_price:.2f}' if result.current_price else 'N/A'} | "
        f"{'Upside' if result.upside_downside_pct > 0 else 'Downside'}: {abs_pct:.1f}%\n",

        f"Our discounted cash flow model suggests the stock is approximately {abs_pct:.1f}% "
        f"{direction} at current levels. The model projects revenue growing from "
        f"${result.base_revenue / 1e9:.1f}B to ${result.projected_revenues[-1] / 1e9:.1f}B "
        f"over {a.projection_years} years, generating cumulative free cash flow of "
        f"${sum(result.projected_fcfs) / 1e9:.1f}B.\n",
    ]

    # Assumptions table — decomposed or legacy
    lines.append("**Key Assumptions**\n")
    lines.append("| Assumption | Value | Rationale |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Revenue Growth (Yr 1-{a.projection_years}) | "
        f"{', '.join(f'{r*100:.1f}%' for r in a.revenue_growth_rates)} | "
        f"{a.revenue_growth_rationale or 'Based on historical trends'} |"
    )

    if a.is_decomposed:
        gm = a.gross_margins or []
        gm_str = f"{gm[0]*100:.0f}%-{gm[-1]*100:.0f}%" if len(gm) >= 2 else f"{gm[0]*100:.0f}%" if gm else "N/A"
        lines.append(f"| Gross Margin | {gm_str} | {a.margin_rationale or 'Based on historical trajectory'} |")
        opex = a.opex_as_pct_revenue or []
        if opex:
            opex_str = f"{opex[0]*100:.0f}%-{opex[-1]*100:.0f}%" if len(opex) >= 2 else f"{opex[0]*100:.0f}%"
            lines.append(f"| OpEx % Revenue | {opex_str} | Operating leverage from scale |")
        lines.append(f"| D&A % Revenue | {a.da_as_pct_revenue*100:.1f}% | Steady-state depreciation |")
        if a.sbc_as_pct_revenue > 0.005:
            lines.append(f"| SBC % Revenue | {a.sbc_as_pct_revenue*100:.1f}% | Added back to UFCF (dilution noted) |")
        capex = a.capex_as_pct_revenue or []
        if capex:
            capex_str = f"{capex[0]*100:.0f}%-{capex[-1]*100:.0f}%" if len(capex) >= 2 else f"{capex[0]*100:.0f}%"
            lines.append(f"| CapEx % Revenue | {capex_str} | Investment intensity |")
        lines.append(f"| Tax Rate | {a.tax_rate*100:.0f}% | Effective rate |")
    else:
        lines.append(f"| FCF Margin | {a.fcf_margin*100:.1f}% | {a.fcf_margin_rationale or 'Based on recent performance'} |")

    lines.append(f"| WACC | {a.wacc*100:.1f}% | {a.wacc_rationale or 'Computed from CAPM'} |")
    lines.append(f"| Terminal Growth | {a.terminal_growth_rate*100:.1f}% | {a.terminal_growth_rationale or 'Long-run GDP growth proxy'} |")
    lines.append("")

    # Projection table
    if result.projection_details:
        lines.append("**Projection Summary (Decomposed)**\n")
        lines.append("| Year | Revenue | Gross Profit | EBITDA | EBIT | FCF | Discounted FCF |")
        lines.append("|---|---|---|---|---|---|---|")
        for d in result.projection_details:
            lines.append(
                f"| {d.year} | ${d.revenue/1e9:.1f}B | ${d.gross_profit/1e9:.1f}B | "
                f"${d.ebitda/1e9:.1f}B | ${d.ebit/1e9:.1f}B | "
                f"${d.fcf/1e9:.1f}B | ${d.discounted_fcf/1e9:.1f}B |"
            )
    else:
        lines.append("**Projection Summary**\n")
        lines.append("| Year | Revenue | FCF | Discounted FCF |")
        lines.append("|---|---|---|---|")
        for i in range(a.projection_years):
            lines.append(
                f"| {i + 1} | ${result.projected_revenues[i] / 1e9:.1f}B | "
                f"${result.projected_fcfs[i] / 1e9:.1f}B | "
                f"${result.discounted_fcfs[i] / 1e9:.1f}B |"
            )

    lines.extend([
        "",
        f"| Terminal Value | | | | | ${result.terminal_value / 1e9:.1f}B | ${result.pv_terminal_value / 1e9:.1f}B |"
        if result.projection_details else
        f"| Terminal Value | | ${result.terminal_value / 1e9:.1f}B | ${result.pv_terminal_value / 1e9:.1f}B |",
        "",
        "**Valuation Bridge**\n",
        f"| Component | Value |",
        f"|---|---|",
        f"| PV of FCFs | ${sum(result.discounted_fcfs) / 1e9:.1f}B |",
        f"| PV of Terminal Value | ${result.pv_terminal_value / 1e9:.1f}B |",
        f"| Enterprise Value | ${result.enterprise_value / 1e9:.1f}B |",
    ])

    # Full EV bridge if available, otherwise simple net debt line
    if result.ev_bridge:
        bridge = result.ev_bridge
        lines.append(f"| Less: Net Debt | ${bridge.net_debt / 1e9:.1f}B |")
        if bridge.minority_interest:
            lines.append(f"| Less: Minority Interest | ${bridge.minority_interest / 1e9:.1f}B |")
        if bridge.preferred_stock:
            lines.append(f"| Less: Preferred Stock | ${bridge.preferred_stock / 1e9:.1f}B |")
        if bridge.pension_deficit:
            lines.append(f"| Less: Pension Deficit | ${bridge.pension_deficit / 1e9:.1f}B |")
        if bridge.equity_investments:
            lines.append(f"| Plus: Equity Investments | ${bridge.equity_investments / 1e9:.1f}B |")
    else:
        lines.append(f"| Less: Net Debt | ${result.net_debt / 1e9:.1f}B |")

    lines.extend([
        f"| Equity Value | ${result.equity_value / 1e9:.1f}B |",
        f"| Shares Outstanding | {result.shares_outstanding / 1e9:.2f}B |",
        f"| **Fair Value / Share** | **${result.fair_value_per_share:.2f}** |",
    ])

    return "\n".join(lines)


def _build_dcf_context(
    stock_info: StockInfo,
    enriched_financials: Optional[EnrichedFinancials],
    financials: Optional[List[FinancialStatement]],
    analyst_estimates: Optional[List[AnalystEstimate]],
    strategic_assessment: Optional[StrategicAssessment] = None,
) -> str:
    """Build the LLM prompt with company context for DCF assumption generation."""
    financial_history = _extract_financial_history(enriched_financials, financials)

    estimates_text = ""
    if analyst_estimates:
        est_lines = ["## Analyst Estimates"]
        for est in analyst_estimates[:MAX_ANALYST_ESTIMATES]:
            if est.revenue_estimate_avg:
                est_lines.append(
                    f"  FY{est.fiscal_year}: Revenue ${est.revenue_estimate_avg / 1e9:.1f}B, "
                    f"EPS ${est.eps_estimate_avg:.2f}" if est.eps_estimate_avg else ""
                )
        estimates_text = "\n".join(est_lines)

    strategic_text = ""
    if strategic_assessment:
        strategic_text = "\n" + strategic_assessment.format_for_dcf_context()

    return f"""Analyze this company and provide DCF assumptions.

**Company**: {stock_info.name} ({stock_info.symbol})
**Sector**: {stock_info.sector or 'Unknown'}
**Industry**: {stock_info.industry or 'Unknown'}
**Current Price**: ${f"{stock_info.current_price:.2f}" if stock_info.current_price else "N/A"}
**Market Cap**: ${f"{stock_info.market_cap / 1e9:.1f}B" if stock_info.market_cap else "N/A"}
**Beta**: {stock_info.beta or 'N/A'}

{financial_history}

{estimates_text}
{strategic_text}

IMPORTANT INSTRUCTIONS:
- Use addressable market estimates to bound your revenue growth assumptions (revenue cannot exceed the obtainable market without gaining share)
- Use competitive intensity scores to inform margin trajectory (high rivalry = margin pressure)
- Use macro risk flags to calibrate WACC and terminal growth rate
- Provide decomposed assumptions: gross margins, opex ratio, D&A, capex, tax rate, and NWC change

Based on this data, provide your DCF assumptions as JSON."""


def run_dcf_analysis(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    enriched_financials: Optional[EnrichedFinancials],
    financials: Optional[List[FinancialStatement]],
    analyst_estimates: Optional[List[AnalystEstimate]] = None,
    sentiment_report: str = "",
    strategic_assessment: Optional[StrategicAssessment] = None,
    assumption_overrides: Optional[dict] = None,
) -> tuple[Optional[DCFResult], AnalysisResult]:
    """
    Run DCF analysis: LLM reasons about assumptions, engine runs the math.

    Args:
        assumption_overrides: Dict of DCFAssumptions field overrides from the
            analyst. These are hard overrides: the analyst's values replace
            the LLM's unconditionally. Applied after LLM parsing, before
            calculation.

    Returns:
        (DCFResult or None, AnalysisResult with narrative)
    """
    # Extract inputs
    base_revenue = stock_info.revenue
    current_price = stock_info.current_price
    shares_outstanding = stock_info.shares_outstanding

    # Get net debt from financials
    net_debt = 0.0
    if financials:
        latest = financials[0]
        net_debt = (latest.total_debt or 0) - (latest.cash_and_equivalents or 0)

    # Validate critical inputs
    if not base_revenue or base_revenue <= 0:
        return None, AnalysisResult(
            section="DCF Valuation",
            content="DCF analysis could not be performed: base revenue data is unavailable.",
            tokens_used=0,
            success=False,
            error="Missing base revenue",
        )

    if not shares_outstanding or shares_outstanding <= 0:
        return None, AnalysisResult(
            section="DCF Valuation",
            content="DCF analysis could not be performed: shares outstanding data is unavailable.",
            tokens_used=0,
            success=False,
            error="Missing shares outstanding",
        )

    if not current_price or current_price <= 0:
        return None, AnalysisResult(
            section="DCF Valuation",
            content="DCF analysis could not be performed: current price data is unavailable.",
            tokens_used=0,
            success=False,
            error="Missing current price",
        )

    # Compute WACC from market data
    interest_expense = None
    total_debt_val = None
    if financials:
        latest = financials[0]
        interest_expense = getattr(latest, 'interest_expense', None)
        total_debt_val = latest.total_debt

    wacc_result = compute_wacc(
        beta=stock_info.beta,
        market_cap=stock_info.market_cap,
        total_debt=total_debt_val,
        interest_expense=interest_expense,
        current_price=stock_info.current_price,
        shares_outstanding=stock_info.shares_outstanding,
    )
    computed_wacc = wacc_result.wacc
    wacc_rationale = wacc_result.rationale

    # Build context for LLM
    user_prompt = _build_dcf_context(stock_info, enriched_financials, financials, analyst_estimates, strategic_assessment)

    # Call LLM
    response = call_llm(
        api_key=api_key,
        model=model,
        system_prompt=DCF_ASSUMPTIONS_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.1,
    )

    # Parse assumptions
    assumptions = None
    if response.success:
        try:
            assumptions = _parse_assumptions(response.content, computed_wacc, wacc_rationale)
        except AssumptionParseError as e:
            logger.warning(str(e))

    if assumptions is None:
        logger.warning("Using default DCF assumptions (LLM parsing failed)")
        assumptions = DEFAULT_ASSUMPTIONS

    # Apply analyst overrides (hard replacement, analyst's word is final)
    if assumption_overrides:
        logger.info(f"Applying analyst overrides to DCF: {list(assumption_overrides.keys())}")
        assumptions = assumptions.with_overrides(assumption_overrides)

    # Build EV bridge (CFA-standard enterprise value to equity bridge)
    ev_bridge = EVBridge.from_net_debt(net_debt)

    # Run DCF calculation
    dcf_result = calculate_dcf(
        base_revenue=base_revenue,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
        current_price=current_price,
        assumptions=assumptions,
        ev_bridge=ev_bridge,
        wacc_components=wacc_result,
    )

    # Format narrative
    narrative = _format_dcf_narrative(dcf_result)

    analysis_result = AnalysisResult(
        section="DCF Valuation",
        content=narrative,
        tokens_used=response.tokens_used,
        success=True,
        cost_usd=response.cost_usd,
    )

    return dcf_result, analysis_result
