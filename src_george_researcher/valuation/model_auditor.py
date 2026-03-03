"""
LLM-powered model auditor for valuation outputs.

Runs a single cheap LLM call (Gemini Flash) after all valuation computations
are complete. Produces structured warnings, section commentary, precedent
relevance assessments, and assumption notes consumed by Excel, PDF, and
slides generators.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src_george_researcher.llm import call_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditWarning:
    severity: str          # "critical" | "warning" | "info"
    section: str           # "dcf" | "precedents" | "scenarios" etc.
    message: str
    metric: str = ""       # for Excel cell targeting


@dataclass(frozen=True)
class DealRelevance:
    deal: str
    relevance: str         # "high" | "medium" | "low"
    reason: str


@dataclass(frozen=True)
class ModelAudit:
    warnings: List[AuditWarning] = field(default_factory=list)
    section_commentary: Dict[str, str] = field(default_factory=dict)
    precedent_relevance: List[DealRelevance] = field(default_factory=list)
    assumption_notes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "warnings": [
                {"severity": w.severity, "section": w.section,
                 "message": w.message, "metric": w.metric}
                for w in self.warnings
            ],
            "section_commentary": dict(self.section_commentary),
            "precedent_relevance": [
                {"deal": d.deal, "relevance": d.relevance, "reason": d.reason}
                for d in self.precedent_relevance
            ],
            "assumption_notes": dict(self.assumption_notes),
        }


EMPTY_AUDIT = ModelAudit()


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

AUDIT_SYSTEM_PROMPT = """\
You are a senior equity research analyst reviewing a financial model's outputs \
for internal quality control. Your job is to flag questionable assumptions, \
provide brief contextual commentary on each valuation section, assess the \
relevance of precedent transactions, and document key assumption sources.

Respond ONLY with a JSON object matching this schema (no markdown, no preamble):
{
  "warnings": [{"severity": "critical|warning|info", "section": "...", "message": "...", "metric": "..."}],
  "section_commentary": {"dcf": "...", "precedents": "...", "scenarios": "...", "earnings_model": "..."},
  "precedent_relevance": [{"deal": "Acquirer/Target", "relevance": "high|medium|low", "reason": "..."}],
  "assumption_notes": {"wacc": "...", "terminal_growth": "...", "base_revenue": "..."}
}

Rules:
- Be specific and quantitative. Reference actual numbers from the input.
- Flag WACC below 6% or above 16% as warning. Below 4% or above 18% as critical.
- Flag terminal value > 85% of EV as warning, > 95% as critical.
- Flag scenario upside > 50% on companies with market cap > $100B as warning.
- For precedent relevance, consider whether the target's business model, size, \
  and growth profile match the subject company.
- Keep each commentary to 1-3 sentences. No filler.
"""


def _build_audit_prompt(
    company_context: Dict[str, Any],
    valuation_results: Dict[str, Any],
) -> str:
    """Build a concise (~2000 token) user prompt from structured valuation data."""
    lines = []

    # Company context
    ctx = company_context
    lines.append(f"Company: {ctx.get('name', '?')} ({ctx.get('ticker', '?')})")
    lines.append(f"Sector: {ctx.get('sector', 'Unknown')}")
    mc = ctx.get("market_cap")
    if mc:
        lines.append(f"Market Cap: ${mc / 1e9:.1f}B")
    rev = ctx.get("revenue")
    if rev:
        lines.append(f"Revenue: ${rev / 1e9:.1f}B")
    lines.append(f"Current Price: ${ctx.get('current_price', 0):.2f}")
    lines.append("")

    # DCF
    dcf = valuation_results.get("dcf", {})
    if dcf:
        lines.append("--- DCF ---")
        lines.append(f"Fair Value/Share: ${dcf.get('fair_value_per_share', 0):.2f}")
        wacc_comp = dcf.get("wacc_components", {})
        if wacc_comp:
            lines.append(f"WACC: {wacc_comp.get('wacc', 0) * 100:.1f}%")
            lines.append(f"  Rf={wacc_comp.get('risk_free_rate', 0) * 100:.1f}%, "
                         f"Beta={wacc_comp.get('beta', 0):.2f}, "
                         f"ERP={wacc_comp.get('equity_risk_premium', 0) * 100:.1f}%, "
                         f"Ke={wacc_comp.get('cost_of_equity', 0) * 100:.1f}%, "
                         f"Equity Wt={wacc_comp.get('weight_equity', 0) * 100:.0f}%")
        assumptions = dcf.get("assumptions", {})
        lines.append(f"Terminal Growth: {assumptions.get('terminal_growth_rate', 0) * 100:.1f}%")
        lines.append(f"PV Terminal Value: ${dcf.get('pv_terminal_value', 0) / 1e9:.1f}B")
        ev = dcf.get("enterprise_value", 0)
        tv_pct = (dcf.get("pv_terminal_value", 0) / ev * 100) if ev else 0
        lines.append(f"TV as % of EV: {tv_pct:.1f}%")
        lines.append("")

    # Scenarios
    scenarios = valuation_results.get("scenarios", {})
    if scenarios:
        lines.append("--- Scenarios ---")
        for case_name in ("bull", "base", "bear"):
            case = scenarios.get(case_name, {})
            fv = case.get("fair_value", 0) or case.get("result", {}).get("fair_value_per_share", 0)
            prob = case.get("probability", 0)
            prob_display = prob * 100 if prob <= 1 else prob
            lines.append(f"  {case_name.title()}: ${fv:.2f} (prob {prob_display:.0f}%)")
        lines.append(f"Weighted Fair Value: ${scenarios.get('weighted_fair_value', 0):.2f}")
        cp = ctx.get("current_price", 0)
        wfv = scenarios.get("weighted_fair_value", 0)
        if cp and cp > 0:
            lines.append(f"Implied Upside: {(wfv / cp - 1) * 100:.1f}%")
        lines.append("")

    # Precedents
    prec = valuation_results.get("precedents", {})
    if prec:
        lines.append("--- Precedent Transactions ---")
        if rev:
            lines.append(f"Subject company revenue: ${rev / 1e9:.1f}B")
        for deal in prec.get("deals", []):
            deal_val = deal.get("deal_value_usd")
            val_str = f", Deal=${deal_val / 1e9:.1f}B" if deal_val else ""
            lines.append(f"  {deal.get('acquirer', '?')}/{deal.get('target', '?')}: "
                         f"Premium={_fmt_pct(deal.get('premium_pct'))}, "
                         f"EV/EBITDA={deal.get('ev_to_ebitda', 'N/A')}{val_str}")
        lines.append("")

    # Comps
    comps = valuation_results.get("comps", {})
    if comps:
        medians = comps.get("median_multiples", {})
        if medians:
            lines.append("--- Comps Median Multiples ---")
            for k, v in medians.items():
                lines.append(f"  {k}: {v}")
            lines.append("")

    # Conviction
    conv = valuation_results.get("conviction", {})
    if conv:
        lines.append(f"Conviction: {conv.get('rating', '?')} "
                     f"(score {conv.get('overall_score', '?')}/100, "
                     f"confidence {conv.get('confidence', '?')})")
        lines.append("")

    # Earnings model summary
    em = valuation_results.get("earnings_model", {})
    if em:
        em_rows = em.get("rows", [])
        if em_rows:
            lines.append("--- Earnings Model ---")
            for row in em_rows[-3:]:
                g = row.get("revenue_growth")
                g_str = f"{g * 100:.1f}%" if g is not None else "N/A"
                lines.append(f"  FY{row.get('fiscal_year', '?')}: "
                             f"Rev=${(row.get('revenue') or 0) / 1e9:.1f}B, "
                             f"Growth={g_str}")

    return "\n".join(lines)


def _fmt_pct(val: Any) -> str:
    if val is None:
        return "N/A"
    return f"{float(val) * 100:.1f}%"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_audit_response(content: str) -> ModelAudit:
    """Parse LLM JSON into ModelAudit, raising on invalid structure."""
    text = content.strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    data = json.loads(text)

    warnings = [
        AuditWarning(
            severity=w.get("severity", "info"),
            section=w.get("section", ""),
            message=w.get("message", ""),
            metric=w.get("metric", ""),
        )
        for w in data.get("warnings", [])
    ]

    precedent_relevance = [
        DealRelevance(
            deal=d.get("deal", ""),
            relevance=d.get("relevance", "medium"),
            reason=d.get("reason", ""),
        )
        for d in data.get("precedent_relevance", [])
    ]

    return ModelAudit(
        warnings=warnings,
        section_commentary=data.get("section_commentary", {}),
        precedent_relevance=precedent_relevance,
        assumption_notes=data.get("assumption_notes", {}),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _deterministic_checks(
    company_context: Dict[str, Any],
    valuation_results: Dict[str, Any],
) -> List[AuditWarning]:
    """Run simple numerical checks that should never depend on LLM judgment.

    These catch obvious model issues (WACC out of range, terminal value
    dominating EV, implausible fair values) deterministically so they
    cannot be missed even if the LLM hallucinates or ignores them.
    """
    warnings: List[AuditWarning] = []
    dcf = valuation_results.get("dcf", {})

    # WACC range checks
    wacc_comp = dcf.get("wacc_components", {})
    wacc = wacc_comp.get("wacc")
    if wacc is not None:
        if wacc < 0.04 or wacc > 0.18:
            warnings.append(AuditWarning(
                severity="critical", section="dcf",
                message=f"WACC of {wacc*100:.1f}% is outside plausible range [4%-18%]",
                metric="wacc",
            ))
        elif wacc < 0.06 or wacc > 0.16:
            warnings.append(AuditWarning(
                severity="warning", section="dcf",
                message=f"WACC of {wacc*100:.1f}% is outside typical range [6%-16%]",
                metric="wacc",
            ))

    # Terminal value as % of EV
    ev = dcf.get("enterprise_value", 0)
    pv_tv = dcf.get("pv_terminal_value", 0)
    if ev and ev > 0:
        tv_pct = pv_tv / ev
        if tv_pct > 0.95:
            warnings.append(AuditWarning(
                severity="critical", section="dcf",
                message=f"Terminal value is {tv_pct*100:.0f}% of EV (>95%); near-term cash flows are negligible",
                metric="tv_pct",
            ))
        elif tv_pct > 0.85:
            warnings.append(AuditWarning(
                severity="warning", section="dcf",
                message=f"Terminal value is {tv_pct*100:.0f}% of EV (>85%); valuation heavily depends on terminal assumptions",
                metric="tv_pct",
            ))

    # Fair value vs current price sanity
    fair_value = dcf.get("fair_value_per_share", 0)
    current_price = company_context.get("current_price", 0)
    if fair_value and current_price and current_price > 0:
        ratio = fair_value / current_price
        if ratio > 5.0 or ratio < 0.1:
            warnings.append(AuditWarning(
                severity="warning", section="dcf",
                message=f"Fair value ${fair_value:.2f} is {ratio:.1f}x current price ${current_price:.2f}; verify assumptions",
                metric="fair_value",
            ))

    # Equity weight sanity
    weight_equity = wacc_comp.get("weight_equity")
    if weight_equity is not None:
        if weight_equity < 0.10:
            warnings.append(AuditWarning(
                severity="warning", section="dcf",
                message=f"Equity weight of {weight_equity*100:.0f}% is unusually low (<10%)",
                metric="weight_equity",
            ))
        elif weight_equity > 0.99:
            warnings.append(AuditWarning(
                severity="warning", section="dcf",
                message=f"Equity weight of {weight_equity*100:.1f}% implies near-zero debt; verify capital structure",
                metric="weight_equity",
            ))

    return warnings


def audit_valuation_model(
    company_context: Dict[str, Any],
    valuation_results: Dict[str, Any],
    api_key: str,
    model: str,
) -> ModelAudit:
    """Run deterministic checks then a single LLM call to audit the model.

    Deterministic checks run first and always produce results. The LLM call
    adds commentary, precedent relevance, and assumption notes. On LLM
    failure, the deterministic warnings are still returned.
    """
    det_warnings = _deterministic_checks(company_context, valuation_results)
    user_prompt = _build_audit_prompt(company_context, valuation_results)

    try:
        response = call_llm(
            api_key=api_key,
            model=model,
            system_prompt=AUDIT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=2048,
        )
    except Exception:
        logger.warning("Model auditor LLM call failed", exc_info=True)
        return ModelAudit(warnings=det_warnings)

    if not response.success:
        logger.warning("Model auditor LLM returned error: %s", response.error)
        return ModelAudit(warnings=det_warnings)

    try:
        llm_audit = _parse_audit_response(response.content)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Model auditor failed to parse LLM response: %s", exc)
        return ModelAudit(warnings=det_warnings)

    # Merge: deterministic warnings first, then LLM warnings
    merged_warnings = det_warnings + list(llm_audit.warnings)
    return ModelAudit(
        warnings=merged_warnings,
        section_commentary=llm_audit.section_commentary,
        precedent_relevance=llm_audit.precedent_relevance,
        assumption_notes=llm_audit.assumption_notes,
    )
