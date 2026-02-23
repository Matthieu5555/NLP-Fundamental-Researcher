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
    implied_value_from_revenue: Optional[float]  # per share
    implied_value_from_ebitda: Optional[float]   # per share
    narrative: str = ""

    def to_dict(self) -> Dict:
        return {
            "deals": [d.to_dict() for d in self.deals],
            "median_ev_revenue": self.median_ev_revenue,
            "median_ev_ebitda": self.median_ev_ebitda,
            "median_premium": self.median_premium,
            "implied_value_from_revenue": self.implied_value_from_revenue,
            "implied_value_from_ebitda": self.implied_value_from_ebitda,
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
    user_prompt = f"""Extract M&A transaction details from these search results about recent deals in the {industry} ({sector}) industry:

{search_results[:4000]}

Focus on transactions from the last 3-5 years that are most comparable to companies in this sector."""

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

    # Parse deals
    deals = _parse_deals(response.content)

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

    result = PrecedentTransactionResult(
        deals=deals,
        median_ev_revenue=median_ev_rev,
        median_ev_ebitda=median_ev_ebitda,
        median_premium=median_premium,
        implied_value_from_revenue=implied_from_rev,
        implied_value_from_ebitda=implied_from_ebitda,
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
                ev_to_revenue=d.get("ev_to_revenue"),
                ev_to_ebitda=d.get("ev_to_ebitda"),
                premium_pct=d.get("premium_pct"),
                description=d.get("description", ""),
            ))
        except Exception as e:
            logger.warning(f"Skipping malformed deal: {e}")

    return deals


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
        lines.append("*Note: Transaction multiples embed a control premium (typically 20-40%) "
                     "over trading multiples. Adjust downward for minority investment valuation.*")

    return "\n".join(lines)
