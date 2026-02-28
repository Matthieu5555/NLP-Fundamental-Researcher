"""
Precedent Transaction Analysis.

Uses Gemini Search to find recent M&A deals in the target's industry,
then extracts deal multiples for valuation comparison.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src_george_researcher.analysis_agents import AnalysisResult
from src_george_researcher.llm import call_llm

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrecedentDeal:
    """A single M&A transaction with extracted multiples."""
    acquirer: str
    target: str
    date: str                          # "2024-Q3" or "2024"
    deal_value_usd: Optional[float]    # Total deal value
    ev_to_revenue: Optional[float]
    ev_to_ebitda: Optional[float]
    premium_pct: Optional[float]       # Control premium over pre-deal price
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            "acquirer": self.acquirer,
            "target": self.target,
            "date": self.date,
            "deal_value_usd": self.deal_value_usd,
            "ev_to_revenue": self.ev_to_revenue,
            "ev_to_ebitda": self.ev_to_ebitda,
            "premium_pct": self.premium_pct,
            "description": self.description,
        }


@dataclass(frozen=True)
class PrecedentTransactionResult:
    """Complete precedent transaction analysis."""
    deals: List[PrecedentDeal]
    median_ev_revenue: Optional[float]
    median_ev_ebitda: Optional[float]
    median_premium: Optional[float]
    implied_value_from_revenue: Optional[float]  # per share (includes control premium)
    implied_value_from_ebitda: Optional[float]   # per share (includes control premium)
    # Minority-adjusted values (control premium stripped)
    minority_adj_value_from_revenue: Optional[float] = None
    minority_adj_value_from_ebitda: Optional[float] = None
    control_premium_used: float = 0.25  # Default 25% control premium
    narrative: str = ""

    def to_dict(self) -> Dict:
        return {
            "deals": [d.to_dict() for d in self.deals],
            "median_ev_revenue": self.median_ev_revenue,
            "median_ev_ebitda": self.median_ev_ebitda,
            "median_premium": self.median_premium,
            "implied_value_from_revenue": self.implied_value_from_revenue,
            "implied_value_from_ebitda": self.implied_value_from_ebitda,
            "minority_adj_value_from_revenue": self.minority_adj_value_from_revenue,
            "minority_adj_value_from_ebitda": self.minority_adj_value_from_ebitda,
            "control_premium_used": self.control_premium_used,
            "narrative": self.narrative,
        }


PRECEDENT_EXTRACT_SYSTEM = """You are a senior M&A analyst. Given search results about recent M&A transactions in a specific industry, extract deal details as structured JSON.

Return a JSON object with a "deals" array. Each deal should have:
{
  "acquirer": "Company Name",
  "target": "Company Name",
  "date": "YYYY" or "YYYY-QN",
  "deal_value_usd": number or null (in dollars, not millions),
  "ev_to_revenue": number or null,
  "ev_to_ebitda": number or null,
  "premium_pct": number or null (as decimal, e.g. 0.30 for 30%),
  "description": "Brief description of the deal rationale"
}

Rules:
- Only include deals where at least one valuation multiple is available or can be estimated
- Convert all values to USD if in other currencies
- If a multiple is described as "approximately X times revenue", use that as ev_to_revenue
- Premium should be the premium over the pre-announcement share price
- Maximum 8 deals, prioritize most recent and most relevant
- If no deals are found, return {"deals": []}
- CRITICAL: Exclude deals where the subject company was the ACQUIRER. We need deals where comparable peers were acquired, not bolt-on acquisitions made BY the subject company.
- Prefer deals where the TARGET is comparable in scale and business mix to the subject company. Small tuck-in acquisitions of pre-revenue targets carry inflated multiples that are not comparable.
- For large-cap companies (revenue > $10B), prioritize deals involving similarly-sized targets over deals for niche/small targets.

Return ONLY the JSON object, no other text."""


def run_precedent_analysis(
    api_key: str,
    model: str,
    company_name: str,
    industry: str,
    sector: str,
    revenue: Optional[float] = None,
    ebitda: Optional[float] = None,
    net_debt: Optional[float] = None,
    shares_outstanding: Optional[float] = None,
    search_results: str = "",
) -> tuple[Optional[PrecedentTransactionResult], AnalysisResult]:
    """
    Extract precedent transactions from search results and compute implied values.

    Args:
        search_results: Pre-fetched Gemini Search results about M&A in the industry

    Returns:
        (PrecedentTransactionResult or None, AnalysisResult)
    """
    if not search_results:
        return None, AnalysisResult(
            section="Precedent Transactions",
            content="No M&A search results available for precedent transaction analysis.",
            tokens_used=0,
            success=False,
            error="No search data",
        )

    # Ask LLM to extract structured deal data
    revenue_context = ""
    if revenue:
        if revenue >= 1e9:
            revenue_context = f"\nThe subject company ({company_name}) has ~${revenue / 1e9:.1f}B in revenue. Exclude any deals where {company_name} was the acquirer. Prefer targets of comparable scale."
        else:
            revenue_context = f"\nThe subject company ({company_name}) has ~${revenue / 1e6:.0f}M in revenue. Exclude any deals where {company_name} was the acquirer. Prefer targets of comparable scale."

    user_prompt = f"""Extract M&A transaction details from these search results about recent deals in the {industry} ({sector}) industry:

{search_results[:4000]}

Focus on transactions from the last 3-5 years where the TARGET company is comparable to peers of {company_name}.{revenue_context}"""

    response = call_llm(
        api_key=api_key,
        model=model,
        system_prompt=PRECEDENT_EXTRACT_SYSTEM,
        user_prompt=user_prompt,
    )

    if not response.success:
        return None, AnalysisResult(
            section="Precedent Transactions",
            content=f"Precedent transaction extraction failed: {response.error}",
            tokens_used=response.tokens_used,
            success=False,
            error=response.error,
            cost_usd=response.cost_usd,
        )

    # Parse deals and filter out self-as-acquirer / bolt-on outliers
    deals = _parse_deals(response.content)
    deals = _filter_deals(deals, company_name, revenue)

    if not deals:
        return None, AnalysisResult(
            section="Precedent Transactions",
            content="No comparable M&A transactions found in recent search results.",
            tokens_used=response.tokens_used,
            success=True,
            cost_usd=response.cost_usd,
        )

    # Compute medians
    from statistics import median

    ev_revs = [d.ev_to_revenue for d in deals if d.ev_to_revenue is not None]
    ev_ebitdas = [d.ev_to_ebitda for d in deals if d.ev_to_ebitda is not None]
    premiums = [d.premium_pct for d in deals if d.premium_pct is not None]

    median_ev_rev = median(ev_revs) if ev_revs else None
    median_ev_ebitda = median(ev_ebitdas) if ev_ebitdas else None
    median_premium = median(premiums) if premiums else None

    # Compute implied values (EV → Equity → per share)
    implied_from_rev = None
    implied_from_ebitda = None
    debt_adj = net_debt or 0

    if median_ev_rev and revenue and shares_outstanding and shares_outstanding > 0:
        implied_ev = revenue * median_ev_rev
        implied_equity = implied_ev - debt_adj
        if implied_equity > 0:
            implied_from_rev = implied_equity / shares_outstanding

    if median_ev_ebitda and ebitda and shares_outstanding and shares_outstanding > 0:
        implied_ev = ebitda * median_ev_ebitda
        implied_equity = implied_ev - debt_adj
        if implied_equity > 0:
            implied_from_ebitda = implied_equity / shares_outstanding

    # Compute minority-adjusted values by stripping control premium
    # Use median premium from deals if available, otherwise default 25%
    control_premium = median_premium if median_premium and 0.05 < median_premium < 0.60 else 0.25
    minority_adj_rev = implied_from_rev / (1 + control_premium) if implied_from_rev else None
    minority_adj_ebitda = implied_from_ebitda / (1 + control_premium) if implied_from_ebitda else None

    result = PrecedentTransactionResult(
        deals=deals,
        median_ev_revenue=median_ev_rev,
        median_ev_ebitda=median_ev_ebitda,
        median_premium=median_premium,
        implied_value_from_revenue=implied_from_rev,
        implied_value_from_ebitda=implied_from_ebitda,
        minority_adj_value_from_revenue=minority_adj_rev,
        minority_adj_value_from_ebitda=minority_adj_ebitda,
        control_premium_used=control_premium,
    )

    content = format_precedent_markdown(result)

    analysis = AnalysisResult(
        section="Precedent Transactions",
        content=content,
        tokens_used=response.tokens_used,
        success=True,
        cost_usd=response.cost_usd,
    )

    return result, analysis


def _normalize_premium(value: Optional[float]) -> Optional[float]:
    """Normalize premium from LLM output: convert percentage-as-integer to decimal.

    LLMs sometimes return 30 meaning 30% instead of 0.30. Values above 5.0 are
    almost certainly "percentage as integer" (e.g., 30 meaning 30%). Values
    between 2.0 and 5.0 are ambiguous but treated as real multiples (e.g., 2.5
    meaning 250% premium, which occurs in biotech M&A). The old threshold of
    2.0 incorrectly mangled legitimate premiums like 2.5x.
    Clamp to [-0.50, 5.0] to reject garbage values.
    """
    if value is None:
        return None
    if abs(value) > 5.0:
        value = value / 100.0
    elif abs(value) > 2.0:
        logger.info(
            "Premium value %.2f in ambiguous zone (2.0-5.0); treating as real multiple",
            value,
        )
    return max(-0.50, min(5.0, value))


def _normalize_multiple(value: Optional[float], ceiling: float = 200.0) -> Optional[float]:
    """Clamp EV multiples to a sane range, rejecting garbage."""
    if value is None:
        return None
    if value < 0 or value > ceiling:
        return None
    return value


def _parse_deals(content: str) -> List[PrecedentDeal]:
    """Parse LLM JSON response into PrecedentDeal list."""
    import json

    # Extract JSON from response
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning("Failed to parse precedent transaction JSON")
                return []
        else:
            return []

    deals_raw = data.get("deals", [])
    deals = []

    for d in deals_raw:
        try:
            deals.append(PrecedentDeal(
                acquirer=d.get("acquirer", "Unknown"),
                target=d.get("target", "Unknown"),
                date=str(d.get("date", "")),
                deal_value_usd=d.get("deal_value_usd"),
                ev_to_revenue=_normalize_multiple(d.get("ev_to_revenue")),
                ev_to_ebitda=_normalize_multiple(d.get("ev_to_ebitda")),
                premium_pct=_normalize_premium(d.get("premium_pct")),
                description=d.get("description", ""),
            ))
        except Exception as e:
            logger.warning(f"Skipping malformed deal: {e}")

    return deals


# Threshold above which EV/Revenue multiples are flagged as likely bolt-on
# acquisitions of small targets by large-cap acquirers.
BOLT_ON_EV_REVENUE_CAP = 10.0
# Revenue threshold (USD) above which we apply the bolt-on filter.
LARGE_CAP_REVENUE_THRESHOLD = 10e9


def _filter_deals(
    deals: List[PrecedentDeal],
    company_name: str,
    revenue: Optional[float],
) -> List[PrecedentDeal]:
    """Remove deals where the subject company was the acquirer or multiples
    indicate a bolt-on acquisition of a much smaller target.

    Logs filtered deals so the analyst can see what was excluded.
    """
    filtered: List[PrecedentDeal] = []
    name_lower = company_name.lower().strip()

    for deal in deals:
        acquirer_lower = deal.acquirer.lower().strip()

        # Exclude deals where the subject company was the acquirer
        if name_lower in acquirer_lower or acquirer_lower in name_lower:
            logger.info(
                "Precedent filter: excluded self-as-acquirer deal %s -> %s",
                deal.acquirer, deal.target,
            )
            continue

        # For large-cap subjects, cap outlier EV/Revenue multiples
        if (revenue and revenue > LARGE_CAP_REVENUE_THRESHOLD
                and deal.ev_to_revenue is not None
                and deal.ev_to_revenue > BOLT_ON_EV_REVENUE_CAP):
            logger.info(
                "Precedent filter: excluded likely bolt-on deal %s -> %s (EV/Rev %.1fx)",
                deal.acquirer, deal.target, deal.ev_to_revenue,
            )
            continue

        filtered.append(deal)

    return filtered


def format_precedent_markdown(result: PrecedentTransactionResult) -> str:
    """Format precedent transaction analysis as markdown."""
    def fmt_x(v):
        return f"{v:.1f}x" if v is not None else "N/A"

    def fmt_pct(v):
        return f"{v * 100:.0f}%" if v is not None else "N/A"

    def fmt_val(v):
        if v is None:
            return "N/A"
        if v >= 1e9:
            return f"${v / 1e9:.1f}B"
        if v >= 1e6:
            return f"${v / 1e6:.0f}M"
        return f"${v:,.0f}"

    lines = [
        "**Precedent M&A Transactions**\n",
        "| Date | Acquirer | Target | Deal Value | EV/Revenue | EV/EBITDA | Premium |",
        "|---|---|---|---|---|---|---|",
    ]

    for d in result.deals:
        lines.append(
            f"| {d.date} | {d.acquirer} | {d.target} | {fmt_val(d.deal_value_usd)} | "
            f"{fmt_x(d.ev_to_revenue)} | {fmt_x(d.ev_to_ebitda)} | {fmt_pct(d.premium_pct)} |"
        )

    lines.append("")
    lines.append(f"**Median Multiples**: EV/Revenue {fmt_x(result.median_ev_revenue)} | "
                 f"EV/EBITDA {fmt_x(result.median_ev_ebitda)} | "
                 f"Control Premium {fmt_pct(result.median_premium)}")

    if result.implied_value_from_revenue or result.implied_value_from_ebitda:
        lines.append("")
        lines.append("**Implied Values (includes control premium)**")
        if result.implied_value_from_revenue:
            lines.append(f"- From EV/Revenue: ${result.implied_value_from_revenue:.2f}")
        if result.implied_value_from_ebitda:
            lines.append(f"- From EV/EBITDA: ${result.implied_value_from_ebitda:.2f}")

        lines.append("")
        lines.append(f"**Minority-Adjusted Values** (control premium stripped: {result.control_premium_used*100:.0f}%)")
        if result.minority_adj_value_from_revenue:
            lines.append(f"- From EV/Revenue: ${result.minority_adj_value_from_revenue:.2f}")
        if result.minority_adj_value_from_ebitda:
            lines.append(f"- From EV/EBITDA: ${result.minority_adj_value_from_ebitda:.2f}")

    return "\n".join(lines)
