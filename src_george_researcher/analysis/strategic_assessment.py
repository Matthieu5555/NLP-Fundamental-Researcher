"""
Strategic Assessment - Industry dynamics, competitive structure, and market sizing.

Produces structured JSON + narrative for external risk factors, competitive forces,
and addressable market, feeding into strategy-informed DCF assumptions.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src_george_researcher.analysis_agents import AnalysisResult
from src_george_researcher.analysis.shared.parsing import extract_json_from_llm_response
from src_george_researcher.data_fetchers.stock_data import StockInfo
from src_george_researcher.llm import call_llm

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PESTELResult:
    """External risk factor scores and narratives."""
    political_risk: int = 3        # 1-5 scale
    economic_sensitivity: int = 3
    social_trends: int = 3
    tech_disruption_risk: int = 3
    environmental_exposure: int = 3
    legal_regulatory_risk: int = 3
    narrative: str = ""

    def to_dict(self) -> Dict:
        return {
            "political_risk": self.political_risk,
            "economic_sensitivity": self.economic_sensitivity,
            "social_trends": self.social_trends,
            "tech_disruption_risk": self.tech_disruption_risk,
            "environmental_exposure": self.environmental_exposure,
            "legal_regulatory_risk": self.legal_regulatory_risk,
            "narrative": self.narrative,
        }


@dataclass
class PortersResult:
    """Competitive force scores and narratives."""
    supplier_power: int = 3        # 1-5 scale (1=weak, 5=strong)
    buyer_power: int = 3
    competitive_rivalry: int = 3
    threat_of_substitutes: int = 3
    threat_of_new_entrants: int = 3
    narrative: str = ""

    @property
    def avg_force(self) -> float:
        return (self.supplier_power + self.buyer_power + self.competitive_rivalry +
                self.threat_of_substitutes + self.threat_of_new_entrants) / 5.0

    def to_dict(self) -> Dict:
        return {
            "supplier_power": self.supplier_power,
            "buyer_power": self.buyer_power,
            "competitive_rivalry": self.competitive_rivalry,
            "threat_of_substitutes": self.threat_of_substitutes,
            "threat_of_new_entrants": self.threat_of_new_entrants,
            "avg_force": round(self.avg_force, 1),
            "narrative": self.narrative,
        }


@dataclass
class MarketSizingResult:
    """Addressable market estimation (total, serviceable, obtainable)."""
    tam_usd: Optional[float] = None    # Total Addressable Market
    sam_usd: Optional[float] = None    # Serviceable Addressable Market
    som_usd: Optional[float] = None    # Serviceable Obtainable Market
    market_share_pct: Optional[float] = None
    growth_rate: Optional[float] = None  # Market CAGR
    narrative: str = ""

    def to_dict(self) -> Dict:
        return {
            "tam_usd": self.tam_usd,
            "sam_usd": self.sam_usd,
            "som_usd": self.som_usd,
            "market_share_pct": self.market_share_pct,
            "growth_rate": self.growth_rate,
            "narrative": self.narrative,
        }


@dataclass
class GrowthDriver:
    """A single revenue growth driver segment."""
    segment: str
    current_revenue: Optional[float] = None
    growth_rate: Optional[float] = None
    rationale: str = ""


@dataclass
class StrategicAssessment:
    """Complete strategic assessment output."""
    pestel: PESTELResult = field(default_factory=PESTELResult)
    porters: PortersResult = field(default_factory=PortersResult)
    market_sizing: MarketSizingResult = field(default_factory=MarketSizingResult)
    growth_drivers: List[GrowthDriver] = field(default_factory=list)
    insider_ownership_pct: Optional[float] = None
    capital_allocation_quality: Optional[str] = None  # "excellent", "good", "mixed", "poor"
    narrative: str = ""

    def to_dict(self) -> Dict:
        return {
            "pestel": self.pestel.to_dict(),
            "porters": self.porters.to_dict(),
            "market_sizing": self.market_sizing.to_dict(),
            "growth_drivers": [
                {"segment": d.segment, "current_revenue": d.current_revenue,
                 "growth_rate": d.growth_rate, "rationale": d.rationale}
                for d in self.growth_drivers
            ],
            "insider_ownership_pct": self.insider_ownership_pct,
            "capital_allocation_quality": self.capital_allocation_quality,
        }

    def format_for_dcf_context(self) -> str:
        """Format strategic assessment as text for DCF agent consumption."""
        lines = ["## Strategic Assessment Summary"]

        # Market sizing
        ms = self.market_sizing
        if ms.tam_usd:
            lines.append(f"\n**Market Sizing**: Total addressable=${ms.tam_usd/1e9:.0f}B, "
                        f"Serviceable=${ms.sam_usd/1e9:.0f}B, Obtainable=${ms.som_usd/1e9:.0f}B"
                        if ms.sam_usd and ms.som_usd else f"\n**Total Addressable Market**: ${ms.tam_usd/1e9:.0f}B")
            if ms.market_share_pct:
                lines.append(f"  Current market share: {ms.market_share_pct:.1f}%")
            if ms.growth_rate:
                lines.append(f"  Market CAGR: {ms.growth_rate*100:.1f}%")

        # Competitive forces summary
        p = self.porters
        lines.append(f"\n**Competitive Intensity** (avg: {p.avg_force:.1f}/5):")
        lines.append(f"  Supplier Power={p.supplier_power}/5, Buyer Power={p.buyer_power}/5, "
                    f"Rivalry={p.competitive_rivalry}/5, Substitutes={p.threat_of_substitutes}/5, "
                    f"New Entrants={p.threat_of_new_entrants}/5")
        if p.avg_force <= 2.5:
            lines.append("  → Favorable competitive structure supports margin expansion")
        elif p.avg_force >= 3.5:
            lines.append("  → Intense competitive forces constrain margin potential")

        # External risk flags
        pe = self.pestel
        high_risks = []
        if pe.political_risk >= 4: high_risks.append("political")
        if pe.tech_disruption_risk >= 4: high_risks.append("tech disruption")
        if pe.legal_regulatory_risk >= 4: high_risks.append("regulatory")
        if pe.environmental_exposure >= 4: high_risks.append("environmental")
        if high_risks:
            lines.append(f"\n**Macro Risk Flags**: Elevated {', '.join(high_risks)} risk")

        # Growth drivers
        if self.growth_drivers:
            lines.append("\n**Growth Drivers**:")
            for d in self.growth_drivers[:4]:
                rev_str = f" (${d.current_revenue/1e9:.1f}B)" if d.current_revenue else ""
                gr_str = f" growing {d.growth_rate*100:.0f}%" if d.growth_rate else ""
                lines.append(f"  - {d.segment}{rev_str}{gr_str}: {d.rationale}")

        return "\n".join(lines)


# =============================================================================
# Prompts
# =============================================================================

STRATEGIC_ASSESSMENT_SYSTEM = """You are a senior strategy consultant producing a structured strategic assessment for a buy-side equity analyst. Your analysis will directly feed into DCF valuation assumptions.

Return ONLY valid JSON matching this schema. No other text before or after.

```json
{
  "pestel": {
    "political_risk": 2,
    "economic_sensitivity": 3,
    "social_trends": 2,
    "tech_disruption_risk": 4,
    "environmental_exposure": 1,
    "legal_regulatory_risk": 3,
    "narrative": "Concise regulatory and macro risk narrative (2-3 sentences per factor that scores 3+)."
  },
  "porters": {
    "supplier_power": 2,
    "buyer_power": 3,
    "competitive_rivalry": 4,
    "threat_of_substitutes": 2,
    "threat_of_new_entrants": 2,
    "narrative": "Concise competitive dynamics narrative explaining the industry structure."
  },
  "market_sizing": {
    "tam_usd": 500000000000,
    "sam_usd": 120000000000,
    "som_usd": 25000000000,
    "market_share_pct": 8.5,
    "growth_rate": 0.12,
    "narrative": "Market sizing rationale with sources."
  },
  "growth_drivers": [
    {
      "segment": "Cloud Services",
      "current_revenue": 50000000000,
      "growth_rate": 0.25,
      "rationale": "Driven by enterprise migration."
    }
  ],
  "capital_allocation_quality": "good"
}
```

Scoring guide (1-5 scale):
- External Risk Factors (pestel): 1=minimal risk, 5=severe risk
- Competitive Forces (porters): 1=weak force (favorable), 5=strong force (unfavorable)

Be evidence-based. If you lack data for market sizing, provide reasonable estimates with caveats. Revenue figures in USD (not billions).
Growth drivers should be the company's actual business segments where identifiable."""


# =============================================================================
# Runner
# =============================================================================

def run_strategic_assessment(
    api_key: str,
    model: str,
    stock_info: StockInfo,
    fundamentals_analysis: str = "",
    sentiment_report: str = "",
) -> tuple[Optional[StrategicAssessment], AnalysisResult]:
    """
    Run strategic assessment: external risk factors, competitive forces, and market sizing.

    Returns:
        (StrategicAssessment or None, AnalysisResult with narrative)
    """
    user_prompt = f"""Produce a strategic assessment for {stock_info.name} ({stock_info.symbol}).

**Company**: {stock_info.name} ({stock_info.symbol})
**Sector**: {stock_info.sector or 'Unknown'}
**Industry**: {stock_info.industry or 'Unknown'}
**Market Cap**: ${f"{stock_info.market_cap / 1e9:.1f}B" if stock_info.market_cap else "N/A"}
**Revenue**: ${f"{stock_info.revenue / 1e9:.1f}B" if stock_info.revenue else "N/A"}
**Business**: {(stock_info.business_summary or '')[:800]}

**Fundamentals Context**:
{fundamentals_analysis[:1200]}

**Recent News/Sentiment**:
{sentiment_report[:600]}

Provide external risk assessment, competitive force analysis, addressable market sizing, and growth driver analysis."""

    response = call_llm(
        api_key=api_key,
        model=model,
        system_prompt=STRATEGIC_ASSESSMENT_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.15,
    )

    assessment = None
    narrative_parts = []

    if response.success:
        try:
            data = extract_json_from_llm_response(response.content)
            if isinstance(data, dict):
                assessment = _parse_strategic_assessment(data)
                narrative_parts = _build_narrative(assessment)
        except Exception as e:
            logger.warning(f"Failed to parse strategic assessment: {e}")

    if assessment is None:
        assessment = StrategicAssessment()
        narrative_parts = ["Strategic assessment could not be fully determined."]

    narrative = "\n\n".join(narrative_parts)
    assessment.narrative = narrative

    analysis_result = AnalysisResult(
        section="External Forces",
        content=narrative,
        tokens_used=response.tokens_used,
        success=assessment is not None,
        cost_usd=response.cost_usd,
    )

    return assessment, analysis_result


def _parse_strategic_assessment(data: dict) -> StrategicAssessment:
    """Parse JSON into StrategicAssessment."""
    def clamp(v, lo=1, hi=5):
        return max(lo, min(hi, int(v))) if v is not None else 3

    pestel_data = data.get("pestel", {})
    pestel = PESTELResult(
        political_risk=clamp(pestel_data.get("political_risk")),
        economic_sensitivity=clamp(pestel_data.get("economic_sensitivity")),
        social_trends=clamp(pestel_data.get("social_trends")),
        tech_disruption_risk=clamp(pestel_data.get("tech_disruption_risk")),
        environmental_exposure=clamp(pestel_data.get("environmental_exposure")),
        legal_regulatory_risk=clamp(pestel_data.get("legal_regulatory_risk")),
        narrative=pestel_data.get("narrative", ""),
    )

    porters_data = data.get("porters", {})
    porters = PortersResult(
        supplier_power=clamp(porters_data.get("supplier_power")),
        buyer_power=clamp(porters_data.get("buyer_power")),
        competitive_rivalry=clamp(porters_data.get("competitive_rivalry")),
        threat_of_substitutes=clamp(porters_data.get("threat_of_substitutes")),
        threat_of_new_entrants=clamp(porters_data.get("threat_of_new_entrants")),
        narrative=porters_data.get("narrative", ""),
    )

    ms_data = data.get("market_sizing", {})
    market_sizing = MarketSizingResult(
        tam_usd=ms_data.get("tam_usd"),
        sam_usd=ms_data.get("sam_usd"),
        som_usd=ms_data.get("som_usd"),
        market_share_pct=ms_data.get("market_share_pct"),
        growth_rate=ms_data.get("growth_rate"),
        narrative=ms_data.get("narrative", ""),
    )

    growth_drivers = []
    for d in data.get("growth_drivers", []):
        growth_drivers.append(GrowthDriver(
            segment=d.get("segment", "Unknown"),
            current_revenue=d.get("current_revenue"),
            growth_rate=d.get("growth_rate"),
            rationale=d.get("rationale", ""),
        ))

    return StrategicAssessment(
        pestel=pestel,
        porters=porters,
        market_sizing=market_sizing,
        growth_drivers=growth_drivers,
        capital_allocation_quality=data.get("capital_allocation_quality"),
    )


def _build_narrative(assessment: StrategicAssessment) -> List[str]:
    """Build markdown narrative from structured assessment."""
    parts = []

    # External risk factors
    pe = assessment.pestel
    parts.append("**Regulatory & Macro Environment**\n\n" + (pe.narrative or
        f"Political risk: {pe.political_risk}/5. Economic sensitivity: {pe.economic_sensitivity}/5. "
        f"Tech disruption risk: {pe.tech_disruption_risk}/5. Regulatory risk: {pe.legal_regulatory_risk}/5."))

    # Competitive dynamics
    p = assessment.porters
    parts.append("**Competitive Dynamics**\n\n" + (p.narrative or
        f"Average competitive intensity: {p.avg_force:.1f}/5. "
        f"Supplier power: {p.supplier_power}/5, Buyer power: {p.buyer_power}/5, "
        f"Rivalry: {p.competitive_rivalry}/5, Substitutes: {p.threat_of_substitutes}/5, "
        f"New entrants: {p.threat_of_new_entrants}/5."))

    # Market Sizing
    ms = assessment.market_sizing
    if ms.tam_usd:
        sizing_text = f"**Addressable Market**\n\n"
        sizing_text += ms.narrative or (
            f"Total addressable market: ${ms.tam_usd/1e9:.0f}B" +
            (f", serviceable market: ${ms.sam_usd/1e9:.0f}B" if ms.sam_usd else "") +
            (f", obtainable market: ${ms.som_usd/1e9:.0f}B" if ms.som_usd else "") +
            (f". Market share: {ms.market_share_pct:.1f}%." if ms.market_share_pct else "") +
            (f" Market CAGR: {ms.growth_rate*100:.1f}%." if ms.growth_rate else ""))
        parts.append(sizing_text)

    # Growth Drivers
    if assessment.growth_drivers:
        drivers_text = "**Growth Drivers**\n\n"
        for d in assessment.growth_drivers:
            rev = f" (${d.current_revenue/1e9:.1f}B)" if d.current_revenue else ""
            gr = f", growing ~{d.growth_rate*100:.0f}%" if d.growth_rate else ""
            drivers_text += f"{d.segment}{rev}{gr}: {d.rationale}\n\n"
        parts.append(drivers_text.strip())

    return parts
