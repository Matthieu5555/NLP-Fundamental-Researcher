"""
Football Field Valuation Summary.

Aggregates all valuation methods into a single comparable range view:
- DCF (bull/base/bear from scenarios)
- Comparable companies (P/E, EV/EBITDA, EV/Revenue implied)
- Precedent transactions (EV/Revenue, EV/EBITDA implied)
- Current price overlay

Pure aggregation — no LLM calls.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ValuationRange:
    """A single valuation method's range."""
    method: str         # e.g., "DCF (Scenario)", "Comps - P/E"
    low: float
    mid: float
    high: float
    source: str = ""    # e.g., "Bear/Base/Bull", "Peer median"

    def to_dict(self) -> Dict:
        return {
            "method": self.method,
            "low": self.low,
            "mid": self.mid,
            "high": self.high,
            "source": self.source,
        }


@dataclass(frozen=True)
class FootballFieldResult:
    """Complete football field summary."""
    ranges: List[ValuationRange]
    current_price: float
    weighted_fair_value: Optional[float]   # From scenario analysis
    consensus_target: Optional[float]      # Analyst consensus

    def to_dict(self) -> Dict:
        return {
            "ranges": [r.to_dict() for r in self.ranges],
            "current_price": self.current_price,
            "weighted_fair_value": self.weighted_fair_value,
            "consensus_target": self.consensus_target,
        }


def build_football_field(
    current_price: float,
    # DCF scenario results
    dcf_bear: Optional[float] = None,
    dcf_base: Optional[float] = None,
    dcf_bull: Optional[float] = None,
    weighted_fair_value: Optional[float] = None,
    # Comp implied values
    comp_pe_implied: Optional[float] = None,
    comp_fwd_pe_implied: Optional[float] = None,
    comp_ev_revenue_implied: Optional[float] = None,
    comp_ev_ebitda_implied: Optional[float] = None,
    # Precedent transaction implied
    precedent_ev_revenue: Optional[float] = None,
    precedent_ev_ebitda: Optional[float] = None,
    # Analyst consensus
    consensus_target: Optional[float] = None,
) -> FootballFieldResult:
    """
    Build football field by aggregating all available valuation methods.

    Each method contributes a range bar. Methods with insufficient data are skipped.
    """
    ranges = []

    # DCF Scenarios (bear → base → bull)
    if dcf_bear is not None and dcf_base is not None and dcf_bull is not None:
        ranges.append(ValuationRange(
            method="DCF (Scenario)",
            low=dcf_bear,
            mid=dcf_base,
            high=dcf_bull,
            source="Bear / Base / Bull",
        ))

    # Comp-implied values as individual bars with +/- 15% range
    _add_comp_range(ranges, "Comps - P/E", comp_pe_implied)
    _add_comp_range(ranges, "Comps - Fwd P/E", comp_fwd_pe_implied)
    _add_comp_range(ranges, "Comps - EV/Revenue", comp_ev_revenue_implied)
    _add_comp_range(ranges, "Comps - EV/EBITDA", comp_ev_ebitda_implied)

    # Precedent transactions (include control premium note)
    _add_comp_range(ranges, "M&A - EV/Revenue", precedent_ev_revenue, source="Incl. control premium")
    _add_comp_range(ranges, "M&A - EV/EBITDA", precedent_ev_ebitda, source="Incl. control premium")

    # Analyst consensus as a tight range
    if consensus_target and consensus_target > 0:
        ranges.append(ValuationRange(
            method="Analyst Consensus",
            low=consensus_target * 0.90,
            mid=consensus_target,
            high=consensus_target * 1.10,
            source="Street consensus +/-10%",
        ))

    return FootballFieldResult(
        ranges=ranges,
        current_price=current_price,
        weighted_fair_value=weighted_fair_value,
        consensus_target=consensus_target,
    )


def _add_comp_range(
    ranges: List[ValuationRange],
    method: str,
    value: Optional[float],
    spread: float = 0.15,
    source: str = "Peer median",
):
    """Add a comp-derived range with symmetric spread around implied value."""
    if value is not None and value > 0:
        ranges.append(ValuationRange(
            method=method,
            low=value * (1 - spread),
            mid=value,
            high=value * (1 + spread),
            source=source,
        ))


def format_football_field_markdown(result: FootballFieldResult) -> str:
    """Format football field as markdown summary."""
    if not result.ranges:
        return "**Valuation Summary**: Insufficient data for football field comparison."

    lines = [
        "**Valuation Football Field**\n",
        f"Current Price: **${result.current_price:.2f}**",
    ]

    if result.weighted_fair_value:
        upside = ((result.weighted_fair_value / result.current_price) - 1) * 100 if result.current_price > 0 else 0
        lines.append(f"Probability-Weighted Fair Value: **${result.weighted_fair_value:.2f}** "
                     f"({'Upside' if upside > 0 else 'Downside'}: {abs(upside):.1f}%)\n")

    lines.append("| Method | Low | Mid | High | Source |")
    lines.append("|---|---|---|---|---|")

    for r in result.ranges:
        lines.append(
            f"| {r.method} | ${r.low:.2f} | **${r.mid:.2f}** | ${r.high:.2f} | {r.source} |"
        )

    # Summary statistics
    all_mids = [r.mid for r in result.ranges if r.mid > 0]
    all_lows = [r.low for r in result.ranges if r.low > 0]
    all_highs = [r.high for r in result.ranges if r.high > 0]

    if all_mids:
        avg_mid = sum(all_mids) / len(all_mids)
        overall_low = min(all_lows) if all_lows else 0
        overall_high = max(all_highs) if all_highs else 0
        lines.append(f"\n**Cross-Method Range**: ${overall_low:.2f} - ${overall_high:.2f} "
                     f"(Average midpoint: ${avg_mid:.2f})")

    return "\n".join(lines)
