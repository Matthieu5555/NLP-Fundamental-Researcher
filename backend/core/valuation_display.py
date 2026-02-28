"""
Shared valuation display context builder.

Extracts structured valuation data from session_metadata into template-ready
dicts used by both PDF reports and slide decks. Centralizes the computation
so formatting logic is not duplicated across generators.

Single entry point: build_valuation_display() -> ValuationDisplay
"""

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ValuationDisplay:
    """Template-ready valuation display data built from session metadata.

    Each field corresponds to a section of the valuation output. Fields
    default to empty containers so callers can safely iterate or test
    truthiness without None checks.
    """

    dcf_summary: Dict[str, Any] = field(default_factory=dict)
    scenario_summary: Dict[str, Any] = field(default_factory=dict)
    football_ranges: List[Dict[str, Any]] = field(default_factory=list)
    football_current_pct: Optional[float] = None
    football_current_price: Optional[float] = None
    conviction_structured: Dict[str, Any] = field(default_factory=dict)
    conviction_categories: List[Dict[str, Any]] = field(default_factory=list)
    sensitivity_grid: Dict[str, Any] = field(default_factory=dict)
    growth_margin_grid: Dict[str, Any] = field(default_factory=dict)
    earnings_table: Dict[str, Any] = field(default_factory=dict)
    precedent_summary: Dict[str, Any] = field(default_factory=dict)
    comp_summary: Dict[str, Any] = field(default_factory=dict)
    ddm_summary: Dict[str, Any] = field(default_factory=dict)
    earnings_quality: Dict[str, Any] = field(default_factory=dict)
    investment_context: Dict[str, Any] = field(default_factory=dict)

    def to_template_context(self) -> Dict[str, Any]:
        """Flatten to a dict for Jinja2 template contexts that need dict unpacking."""
        return dataclasses.asdict(self)


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _upside_pct(fair_value: Optional[float], current_price: Optional[float]) -> Optional[float]:
    if fair_value and current_price and current_price > 0:
        return round(((fair_value - current_price) / current_price) * 100, 1)
    return None


def _parse_wacc_rationale(rationale: str) -> Dict[str, float]:
    """Parse a WACC rationale string into component floats.

    Handles the format produced by compute_wacc():
      "WACC=9.5%: Ke=11.3% (Rf=4.3% + Beta=1.15 x ERP=5.5% + SP=0.5%), Kd=3.5% after-tax, E/(D+E)=80%"

    Returns empty dict on parse failure or empty input, which lets callers
    fall through to whatever default they prefer.
    """
    if not rationale:
        return {}
    try:
        pct = r'([\d.]+)%'
        flt = r'([\d.]+)'

        wacc_m = re.search(rf'WACC={pct}', rationale)
        ke_m = re.search(rf'Ke={pct}', rationale)
        rf_m = re.search(rf'Rf={pct}', rationale)
        beta_m = re.search(rf'Beta={flt}', rationale)
        erp_m = re.search(rf'ERP={pct}', rationale)
        sp_m = re.search(rf'SP={pct}', rationale)
        kd_m = re.search(rf'Kd={pct}', rationale)
        we_m = re.search(rf'E/\(D\+E\)={pct}', rationale)

        if not (wacc_m and ke_m and rf_m and beta_m and erp_m and kd_m and we_m):
            return {}

        result: Dict[str, float] = {
            "wacc": float(wacc_m.group(1)) / 100,
            "ke": float(ke_m.group(1)) / 100,
            "rf": float(rf_m.group(1)) / 100,
            "beta": float(beta_m.group(1)),
            "erp": float(erp_m.group(1)) / 100,
            "kd": float(kd_m.group(1)) / 100,
            "weight_equity": float(we_m.group(1)) / 100,
            "weight_debt": 1.0 - float(we_m.group(1)) / 100,
        }
        if sp_m:
            result["sp"] = float(sp_m.group(1)) / 100
        return result
    except (ValueError, AttributeError):
        return {}


def _build_dcf_summary(dcf_model: Dict, current_price: Optional[float]) -> Dict:
    if not dcf_model:
        return {}
    assumptions = dcf_model.get("assumptions", {})

    wacc_components = dcf_model.get("wacc_components") or _parse_wacc_rationale(
        assumptions.get("wacc_rationale", "")
    )

    enterprise_value = _safe_float(dcf_model.get("enterprise_value"))
    pv_terminal = _safe_float(dcf_model.get("pv_terminal_value"))
    tv_pct_of_ev = None
    if pv_terminal and enterprise_value and enterprise_value > 0:
        tv_pct_of_ev = round(pv_terminal / enterprise_value * 100, 1)

    summary = {
        "fair_value": dcf_model.get("fair_value_per_share"),
        "current_price": current_price,
        "wacc": assumptions.get("wacc"),
        "terminal_growth_rate": assumptions.get("terminal_growth_rate"),
        "enterprise_value": enterprise_value,
        "fcf_margin": assumptions.get("fcf_margin"),
        "revenue_growth": assumptions.get("revenue_growth_rates", [None])[0],
        "terminal_value": dcf_model.get("terminal_value"),
        "pv_terminal_value": pv_terminal,
        "equity_value": dcf_model.get("equity_value"),
        "shares_outstanding": dcf_model.get("shares_outstanding"),
        "net_debt": dcf_model.get("net_debt"),
        "ev_bridge": dcf_model.get("ev_bridge"),
        "projection_details": dcf_model.get("projection_details", []),
        "wacc_components": wacc_components,
        "terminal_growth_rationale": assumptions.get("terminal_growth_rationale", ""),
        "revenue_growth_rationale": assumptions.get("revenue_growth_rationale", ""),
        "tv_pct_of_ev": tv_pct_of_ev,
    }
    summary["upside_pct"] = _upside_pct(
        _safe_float(summary.get("fair_value")), _safe_float(current_price)
    )
    return summary


def _build_scenario_summary(
    scenario_data: Dict, current_price: Optional[float]
) -> Dict:
    if not scenario_data:
        return {}
    summary: Dict[str, Any] = {}
    for label in ("bull", "base", "bear"):
        s = scenario_data.get(label, {})
        if not s:
            continue
        entry: Dict[str, Any] = {
            "fair_value": s.get("fair_value"),
            "probability": s.get("probability"),
        }
        entry["upside_pct"] = _upside_pct(
            _safe_float(entry.get("fair_value")), _safe_float(current_price)
        )
        # Extract key assumptions for display (revenue growth Y1, WACC, terminal growth)
        raw_assumptions = s.get("assumptions", {})
        if raw_assumptions:
            growth_rates = raw_assumptions.get("revenue_growth_rates", [])
            entry["assumptions"] = {
                "revenue_growth": growth_rates[0] if growth_rates else None,
                "wacc": raw_assumptions.get("wacc"),
                "terminal_growth": raw_assumptions.get("terminal_growth_rate"),
            }
        summary[label] = entry
    summary["weighted_fair_value"] = scenario_data.get("weighted_fair_value")
    return summary


def _build_football_field(
    football_field_data: Dict, current_price: Optional[float]
) -> tuple[List[Dict], Optional[float], Optional[float]]:
    """Return (football_ranges, football_current_pct, football_current_price)."""
    if not football_field_data:
        return [], None, None

    ranges = football_field_data.get("ranges") or []
    price = football_field_data.get("current_price") or current_price

    all_values: List[float] = []
    for r in ranges:
        for key in ("low", "mid", "high"):
            v = _safe_float(r.get(key))
            if v is not None:
                all_values.append(v)
    if price:
        all_values.append(float(price))

    if not all_values:
        return [], None, _safe_float(price)

    global_min = min(all_values) * 0.9
    global_max = max(all_values) * 1.1
    span = global_max - global_min if global_max > global_min else 1

    football_ranges = []
    for r in ranges:
        low = float(r.get("low", 0))
        mid = float(r.get("mid", 0))
        high = float(r.get("high", 0))
        football_ranges.append({
            "method": r.get("method", ""),
            "low": round(low, 2),
            "mid": round(mid, 2),
            "high": round(high, 2),
            "bar_left_pct": round((low - global_min) / span * 100, 1),
            "bar_width_pct": round((high - low) / span * 100, 1),
            "mid_pct": round((mid - global_min) / span * 100, 1),
        })

    current_pct = None
    if price:
        raw_pct = round((float(price) - global_min) / span * 100, 1)
        current_pct = max(2.0, min(98.0, raw_pct))
    return football_ranges, current_pct, _safe_float(price)


def _build_conviction(conviction_data: Dict) -> tuple[Dict, List[Dict]]:
    """Return (conviction_data passthrough, conviction_categories)."""
    if not conviction_data:
        return {}, []
    categories = []
    for cat in conviction_data.get("categories", []):
        score = cat.get("score")
        if score is not None:
            categories.append({
                "name": cat.get("name", ""),
                "score": score,
                "bar_pct": min(round(float(score) * 10, 1), 100),
                "evidence": cat.get("evidence", ""),
            })
    return conviction_data, categories


def _build_sensitivity_grid(
    raw: Optional[Dict], current_price: Optional[float],
    row_key: str = "wacc_values",
    col_key: str = "terminal_growth_values",
) -> Dict:
    """Build a template-ready sensitivity grid with cell classification."""
    if not raw:
        return {}

    wacc_values = raw.get(row_key, raw.get("row_values", []))
    tgr_values = raw.get(col_key, raw.get("col_values", []))
    grid = raw.get("fair_value_grid", [])
    base_row = raw.get("base_wacc_idx", raw.get("base_row_idx"))
    base_col = raw.get("base_tgr_idx", raw.get("base_col_idx"))

    cp = _safe_float(current_price)

    cell_classes: List[List[str]] = []
    for i, row in enumerate(grid):
        row_classes = []
        for j, val in enumerate(row):
            fv = _safe_float(val)
            if base_row is not None and base_col is not None and i == base_row and j == base_col:
                row_classes.append("base")
            elif fv is not None and cp is not None:
                row_classes.append("positive" if fv >= cp else "negative")
            else:
                row_classes.append("")
        cell_classes.append(row_classes)

    return {
        "row_values": wacc_values,
        "col_values": tgr_values,
        "grid": grid,
        "base_row_idx": base_row,
        "base_col_idx": base_col,
        "current_price": cp,
        "cell_classes": cell_classes,
    }


def _build_earnings_table(earnings_data: Optional[Dict]) -> Dict:
    if not earnings_data:
        return {}
    rows = earnings_data.get("rows", [])
    if not rows:
        return {}
    has_estimates = any(r.get("is_estimate", False) for r in rows)
    return {"rows": rows, "has_estimates": has_estimates}


def _build_comp_summary(comps_data: Optional[Dict]) -> Dict:
    """Build structured comparable company analysis from CompsTableResult data."""
    if not comps_data:
        return {}
    target = comps_data.get("target", {})
    peers = comps_data.get("peers", [])
    medians = comps_data.get("medians", {})
    implied_values = comps_data.get("implied_values", {})
    if not peers and not any(implied_values.values()):
        return {}
    return {
        "target": target,
        "peers": peers,
        "medians": medians,
        "implied_values": implied_values,
    }


def _build_ddm_summary(ddm_data: Optional[Dict]) -> Dict:
    """Build DDM display data. Returns empty dict if DDM is not applicable."""
    if not ddm_data:
        return {}
    if not ddm_data.get("is_applicable"):
        return {}
    return {
        "blended_value": _safe_float(ddm_data.get("blended_value")),
        "gordon_growth_value": _safe_float(ddm_data.get("gordon_growth_value")),
        "h_model_value": _safe_float(ddm_data.get("h_model_value")),
        "cost_of_equity": _safe_float(ddm_data.get("cost_of_equity")),
        "current_dividend": _safe_float(ddm_data.get("current_dividend")),
        "long_term_growth": _safe_float(ddm_data.get("long_term_growth")),
        "payout_ratio": _safe_float(ddm_data.get("payout_ratio")),
    }


def _build_earnings_quality_summary(eq_data: Optional[Dict]) -> Dict:
    """Build earnings quality callout data."""
    if not eq_data:
        return {}
    quality_score = _safe_float(eq_data.get("quality_score"))
    if quality_score is None:
        return {}
    accrual_quality = eq_data.get("accrual_quality", "")
    cash_conversion = _safe_float(eq_data.get("cash_conversion_ratio"))
    red_flags = eq_data.get("red_flags", [])
    # Filter to medium/high severity, take top 3
    notable_flags = [
        f for f in red_flags
        if f.get("severity") in ("medium", "high")
    ][:3]
    return {
        "quality_score": quality_score,
        "accrual_quality": accrual_quality,
        "cash_conversion_ratio": cash_conversion,
        "red_flags": notable_flags,
    }


def _build_precedent_summary(precedent_data: Optional[Dict]) -> Dict:
    if not precedent_data:
        return {}
    deals = precedent_data.get("deals", [])
    medians = {
        "ev_revenue": precedent_data.get("median_ev_to_revenue"),
        "ev_ebitda": precedent_data.get("median_ev_to_ebitda"),
        "premium": precedent_data.get("median_premium"),
    }
    implied_values = {
        "ev_revenue": precedent_data.get("implied_value_ev_revenue"),
        "ev_ebitda": precedent_data.get("implied_value_ev_ebitda"),
    }
    if not deals and not any(medians.values()):
        return {}
    return {"deals": deals, "medians": medians, "implied_values": implied_values}


def build_valuation_display(
    session_metadata: Dict[str, Any], current_price: Optional[float] = None
) -> ValuationDisplay:
    """
    Build template-ready valuation display data from session metadata.

    Called by PDF, slide, DOCX, and PPTX generators so that valuation
    visualizations are computed once, identically.

    Args:
        session_metadata: session.metadata dict with valuation pipeline outputs.
        current_price: current stock price for upside/downside calculations.

    Returns:
        ValuationDisplay with all template-ready valuation fields.
    """
    dcf_model = session_metadata.get("dcf", {})
    scenario_data = session_metadata.get("scenarios", {})
    football_field_data = session_metadata.get("football_field", {})
    conviction_raw = session_metadata.get("conviction", {})

    dcf_summary = _build_dcf_summary(dcf_model, current_price)
    scenario_summary = _build_scenario_summary(scenario_data, current_price)
    football_ranges, football_current_pct, football_current_price = _build_football_field(
        football_field_data, current_price
    )
    conviction_data, conviction_categories = _build_conviction(conviction_raw)

    sensitivity_grid = _build_sensitivity_grid(
        session_metadata.get("sensitivity"),
        current_price,
        row_key="wacc_values",
        col_key="terminal_growth_values",
    )
    growth_margin_grid = _build_sensitivity_grid(
        session_metadata.get("sensitivity_operating"),
        current_price,
        row_key="growth_values",
        col_key="margin_values",
    )
    earnings_table = _build_earnings_table(
        session_metadata.get("earnings_model")
    )
    precedent_summary = _build_precedent_summary(
        session_metadata.get("precedents")
    )
    comp_summary = _build_comp_summary(
        session_metadata.get("comps")
    )
    ddm_summary = _build_ddm_summary(
        session_metadata.get("ddm")
    )
    earnings_quality = _build_earnings_quality_summary(
        session_metadata.get("earnings_quality_data")
    )

    investment_context = session_metadata.get("investment_context", {})

    return ValuationDisplay(
        dcf_summary=dcf_summary,
        scenario_summary=scenario_summary,
        football_ranges=football_ranges,
        football_current_pct=football_current_pct,
        football_current_price=football_current_price,
        conviction_structured=conviction_data,
        conviction_categories=conviction_categories,
        sensitivity_grid=sensitivity_grid,
        growth_margin_grid=growth_margin_grid,
        earnings_table=earnings_table,
        precedent_summary=precedent_summary,
        comp_summary=comp_summary,
        ddm_summary=ddm_summary,
        earnings_quality=earnings_quality,
        investment_context=investment_context,
    )
