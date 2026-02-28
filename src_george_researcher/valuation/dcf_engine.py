"""
Pure Python DCF (Discounted Cash Flow) calculator.

No LLM calls - deterministic math only. The DCF agent provides assumptions;
this module runs the calculation.

Supports two modes:
1. Legacy: flat fcf_margin applied to revenue
2. Decomposed: full income-statement-driven FCF build with gross margins,
   opex, D&A, capex, NWC, and tax rate
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# WACC Computation
# =============================================================================

# Default market assumptions
DEFAULT_RISK_FREE_RATE = 0.043   # 10Y Treasury ~4.3%
DEFAULT_EQUITY_RISK_PREMIUM = 0.055  # Long-run ERP ~5.5%
DEFAULT_BETA = 1.0

# Kroll/Duff & Phelps size premium schedule (2024 SBBI).
# Applied to cost of equity: Ke = Rf + Beta*ERP + Size_Premium.
# Thresholds in USD market cap.
SIZE_PREMIUM_SCHEDULE: List[tuple[float, float]] = [
    (50e9, 0.000),   # Mega-cap  (>$50B): no premium
    (10e9, 0.005),   # Large-cap ($10-50B): +50bps
    (2e9,  0.010),   # Mid-cap   ($2-10B):  +100bps
    (300e6, 0.015),  # Small-cap ($300M-2B): +150bps
    (0,    0.030),   # Micro-cap (<$300M):   +300bps
]


def _lookup_size_premium(market_cap: Optional[float]) -> float:
    """Compute size premium from market cap using Kroll/Duff & Phelps schedule."""
    if not market_cap or market_cap <= 0:
        return 0.010  # Mid-cap default when unknown
    for threshold, premium in SIZE_PREMIUM_SCHEDULE:
        if market_cap >= threshold:
            return premium
    return SIZE_PREMIUM_SCHEDULE[-1][1]


@dataclass(frozen=True)
class WACCComponents:
    """Decomposed WACC build-up.

    Supports tuple unpacking via __iter__ so existing callsites that do
    ``wacc, rationale = compute_wacc(...)`` continue to work unchanged.
    New code can access individual components for the Assumptions sheet.
    """
    risk_free_rate: float
    beta: float
    equity_risk_premium: float
    size_premium: float
    cost_of_equity: float          # Ke = Rf + Beta*ERP + SP
    kd_pretax: float
    tax_rate: float
    kd_aftertax: float             # Kd * (1 - tax)
    weight_equity: float
    weight_debt: float
    wacc: float

    @property
    def rationale(self) -> str:
        sp_str = f" + SP={self.size_premium*100:.1f}%" if self.size_premium > 0 else ""
        return (
            f"WACC={self.wacc*100:.1f}%: Ke={self.cost_of_equity*100:.1f}% "
            f"(Rf={self.risk_free_rate*100:.1f}% + "
            f"Beta={self.beta:.2f} x ERP={self.equity_risk_premium*100:.1f}%{sp_str}), "
            f"Kd={self.kd_aftertax*100:.1f}% after-tax, "
            f"E/(D+E)={self.weight_equity*100:.0f}%"
        )

    def __iter__(self):
        """Yield (wacc, rationale) for backward-compatible tuple unpacking."""
        yield self.wacc
        yield self.rationale

    def to_dict(self) -> Dict:
        return {
            "risk_free_rate": self.risk_free_rate,
            "beta": self.beta,
            "equity_risk_premium": self.equity_risk_premium,
            "size_premium": self.size_premium,
            "cost_of_equity": self.cost_of_equity,
            "kd_pretax": self.kd_pretax,
            "tax_rate": self.tax_rate,
            "kd_aftertax": self.kd_aftertax,
            "weight_equity": self.weight_equity,
            "weight_debt": self.weight_debt,
            "wacc": self.wacc,
        }


def compute_wacc(
    beta: Optional[float] = None,
    market_cap: Optional[float] = None,
    total_debt: Optional[float] = None,
    interest_expense: Optional[float] = None,
    tax_rate: float = 0.21,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    equity_risk_premium: float = DEFAULT_EQUITY_RISK_PREMIUM,
    size_premium: Optional[float] = None,
    current_price: Optional[float] = None,
    shares_outstanding: Optional[float] = None,
) -> WACCComponents:
    """
    Compute WACC from CAPM components with size premium.

    Ke = Risk-free rate + Beta * ERP + Size Premium
    Kd = Interest expense / total debt * (1 - tax rate)
    WACC = Ke * (E/(D+E)) + Kd * (D/(D+E))

    Size premium is computed from market cap using Kroll/Duff & Phelps
    schedule if not explicitly provided.

    Returns:
        WACCComponents with all build-up fields. Supports tuple unpacking
        as (wacc, rationale) for backward compatibility.
    """
    beta_used = beta if beta and beta > 0 else DEFAULT_BETA

    # Size premium (Kroll/Duff & Phelps)
    sp = size_premium if size_premium is not None else _lookup_size_premium(market_cap)

    # Cost of equity (CAPM + size premium)
    ke = risk_free_rate + beta_used * equity_risk_premium + sp

    # Cost of debt
    kd_pretax = 0.0
    if total_debt and total_debt > 0 and interest_expense:
        kd_pretax = abs(interest_expense) / total_debt
    else:
        kd_pretax = risk_free_rate + 0.015  # 150bps spread (investment-grade default)
    kd_aftertax = kd_pretax * (1 - tax_rate)

    # Capital structure weights: derive market cap from price * shares if missing
    equity = market_cap if market_cap and market_cap > 0 else None
    if not equity and current_price and shares_outstanding:
        derived = current_price * shares_outstanding
        if derived > 0:
            equity = derived
            logger.info("Derived market_cap from price * shares: %.2f", equity)
        else:
            logger.warning(
                "Derived market_cap non-positive (price=%.2f, shares=%.0f); ignoring",
                current_price, shares_outstanding,
            )
    debt = total_debt or 0
    total_capital = (equity or 0) + debt

    if total_capital > 0 and equity and equity > 0:
        weight_equity = equity / total_capital
        weight_debt = debt / total_capital
    elif total_capital > 0:
        # No equity value available: use conservative public-company default
        logger.warning("No market cap data; defaulting to 85%% equity weight")
        weight_equity = 0.85
        weight_debt = 0.15
    else:
        weight_equity = 1.0
        weight_debt = 0.0

    wacc = ke * weight_equity + kd_aftertax * weight_debt

    # Clamp to reasonable range
    wacc = max(0.05, min(0.20, wacc))

    return WACCComponents(
        risk_free_rate=risk_free_rate,
        beta=beta_used,
        equity_risk_premium=equity_risk_premium,
        size_premium=sp,
        cost_of_equity=ke,
        kd_pretax=kd_pretax,
        tax_rate=tax_rate,
        kd_aftertax=kd_aftertax,
        weight_equity=weight_equity,
        weight_debt=weight_debt,
        wacc=wacc,
    )


def _pad_or_truncate(values: List[float], n: int, default: float = None) -> List[float]:
    """Pad a list to length n by repeating the last value, or truncate."""
    if not values:
        return [default or 0.0] * n
    if len(values) >= n:
        return list(values[:n])
    last = values[-1]
    return list(values) + [last] * (n - len(values))


@dataclass(frozen=True)
class DCFAssumptions:
    """Assumptions for a DCF model, typically generated by LLM.

    Supports both legacy (flat fcf_margin) and decomposed margin models.
    If gross_margins is provided, the decomposed model is used.
    """
    revenue_growth_rates: List[float]   # e.g. [0.12, 0.10, 0.08, 0.06, 0.04]
    wacc: float                          # e.g. 0.095
    terminal_growth_rate: float          # e.g. 0.025
    projection_years: int = 5

    # Legacy: single flat FCF margin
    fcf_margin: float = 0.0

    # Decomposed margin model (optional - used when gross_margins is provided)
    gross_margins: Optional[List[float]] = None        # per-year gross margin
    opex_as_pct_revenue: Optional[List[float]] = None  # SG&A + R&D as % revenue
    da_as_pct_revenue: float = 0.0                     # D&A as % revenue (stable)
    sbc_as_pct_revenue: float = 0.0                    # SBC as % revenue
    capex_as_pct_revenue: Optional[List[float]] = None # per-year capex intensity
    nwc_change_pct: float = 0.0                        # NWC as % of revenue delta
    tax_rate: float = 0.21                             # Effective tax rate

    # LLM rationale strings (for frontend tooltips)
    revenue_growth_rationale: str = ""
    fcf_margin_rationale: str = ""
    margin_rationale: str = ""
    wacc_rationale: str = ""
    terminal_growth_rationale: str = ""

    @property
    def is_decomposed(self) -> bool:
        """True if decomposed margin model should be used."""
        return self.gross_margins is not None and len(self.gross_margins) > 0

    def with_overrides(self, overrides: Dict) -> "DCFAssumptions":
        """Construct a new DCFAssumptions with analyst overrides applied.

        Since DCFAssumptions is frozen, this creates a new instance with
        specified fields replaced. The analyst's values are authoritative
        and are not clamped or adjusted.

        Args:
            overrides: dict mapping field names to override values.
                       Only known DCFAssumptions fields are applied.

        Returns:
            New DCFAssumptions with overrides applied.
        """
        if not overrides:
            return self

        current = self.to_dict()
        # Also include fields that to_dict() conditionally omits
        if not self.is_decomposed:
            current.setdefault("gross_margins", None)
            current.setdefault("opex_as_pct_revenue", None)
            current.setdefault("capex_as_pct_revenue", None)
            current.setdefault("da_as_pct_revenue", self.da_as_pct_revenue)
            current.setdefault("sbc_as_pct_revenue", self.sbc_as_pct_revenue)
            current.setdefault("nwc_change_pct", self.nwc_change_pct)
            current.setdefault("tax_rate", self.tax_rate)
            current.setdefault("margin_rationale", self.margin_rationale)
        else:
            current.setdefault("fcf_margin", self.fcf_margin)
            current.setdefault("fcf_margin_rationale", self.fcf_margin_rationale)

        for key, value in overrides.items():
            if key in current or hasattr(self, key):
                current[key] = value

        constructor_fields = {
            "revenue_growth_rates", "wacc", "terminal_growth_rate",
            "projection_years", "fcf_margin", "gross_margins",
            "opex_as_pct_revenue", "da_as_pct_revenue", "sbc_as_pct_revenue",
            "capex_as_pct_revenue", "nwc_change_pct", "tax_rate",
            "revenue_growth_rationale", "fcf_margin_rationale",
            "margin_rationale", "wacc_rationale", "terminal_growth_rationale",
        }
        filtered = {k: v for k, v in current.items() if k in constructor_fields}

        overridden_fields = list(overrides.keys())
        override_note = f" [Analyst override: {', '.join(overridden_fields)}]"
        for field_name in overridden_fields:
            rationale_key = f"{field_name}_rationale"
            if rationale_key in filtered:
                filtered[rationale_key] = (
                    filtered.get(rationale_key, "") + override_note
                ).strip()

        return DCFAssumptions(**filtered)

    def to_dict(self) -> Dict:
        result = {
            "revenue_growth_rates": list(self.revenue_growth_rates),
            "wacc": self.wacc,
            "terminal_growth_rate": self.terminal_growth_rate,
            "projection_years": self.projection_years,
            "revenue_growth_rationale": self.revenue_growth_rationale,
            "wacc_rationale": self.wacc_rationale,
            "terminal_growth_rationale": self.terminal_growth_rationale,
        }
        if self.is_decomposed:
            result.update({
                "gross_margins": list(self.gross_margins) if self.gross_margins else [],
                "opex_as_pct_revenue": list(self.opex_as_pct_revenue) if self.opex_as_pct_revenue else [],
                "da_as_pct_revenue": self.da_as_pct_revenue,
                "sbc_as_pct_revenue": self.sbc_as_pct_revenue,
                "capex_as_pct_revenue": list(self.capex_as_pct_revenue) if self.capex_as_pct_revenue else [],
                "nwc_change_pct": self.nwc_change_pct,
                "tax_rate": self.tax_rate,
                "margin_rationale": self.margin_rationale,
            })
        else:
            result["fcf_margin"] = self.fcf_margin
            result["fcf_margin_rationale"] = self.fcf_margin_rationale
        return result


@dataclass(frozen=True)
class EVBridge:
    """Enterprise Value to Equity Value bridge.

    Full CFA-standard bridge:
        Equity Value = EV - Net Debt - Minority Interest - Preferred Stock
                       - Pension Deficit + Equity Investments

    Components default to 0 when data is unavailable (common for FDS/yfinance),
    which gracefully degrades to the simpler EV - Net Debt calculation.
    """
    net_debt: float                        # Total debt - cash & equivalents
    minority_interest: float = 0.0         # Non-controlling interests
    preferred_stock: float = 0.0           # Liquidation value of preferred equity
    pension_deficit: float = 0.0           # Unfunded pension/OPEB obligations
    equity_investments: float = 0.0        # Non-operating equity stakes (add back)

    @property
    def total_deductions(self) -> float:
        """Total amount subtracted from EV to get equity value."""
        return (
            self.net_debt
            + self.minority_interest
            + self.preferred_stock
            + self.pension_deficit
            - self.equity_investments
        )

    def equity_value(self, enterprise_value: float) -> float:
        """Compute equity value from enterprise value."""
        return enterprise_value - self.total_deductions

    def to_dict(self) -> Dict:
        result: Dict = {"net_debt": self.net_debt}
        if self.minority_interest:
            result["minority_interest"] = self.minority_interest
        if self.preferred_stock:
            result["preferred_stock"] = self.preferred_stock
        if self.pension_deficit:
            result["pension_deficit"] = self.pension_deficit
        if self.equity_investments:
            result["equity_investments"] = self.equity_investments
        result["total_deductions"] = self.total_deductions
        return result

    @classmethod
    def from_net_debt(cls, net_debt: float) -> "EVBridge":
        """Convenience constructor for backward compatibility."""
        return cls(net_debt=net_debt)


@dataclass(frozen=True)
class DCFProjectionYear:
    """Detailed projection for a single year in the decomposed model."""
    year: int
    revenue: float
    gross_profit: float
    opex: float
    ebitda: float
    da: float
    ebit: float
    nopat: float
    capex: float
    nwc_change: float
    sbc: float
    fcf: float
    discounted_fcf: float


@dataclass(frozen=True)
class DCFResult:
    """Complete DCF valuation output."""
    base_revenue: float
    projected_revenues: List[float]
    projected_fcfs: List[float]
    discounted_fcfs: List[float]
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float
    net_debt: float
    equity_value: float
    shares_outstanding: float
    fair_value_per_share: float
    current_price: float
    upside_downside_pct: float
    assumptions: DCFAssumptions
    # Detailed year-by-year projections (only for decomposed model)
    projection_details: List[DCFProjectionYear] = field(default_factory=list)
    # Full EV bridge breakdown (None for legacy callers)
    ev_bridge: Optional[EVBridge] = None
    # Decomposed WACC build-up (None for old sessions)
    wacc_components: Optional[WACCComponents] = None

    def to_dict(self) -> Dict:
        result = {
            "fair_value_per_share": self.fair_value_per_share,
            "current_price": self.current_price,
            "upside_downside_pct": self.upside_downside_pct,
            "enterprise_value": self.enterprise_value,
            "equity_value": self.equity_value,
            "base_revenue": self.base_revenue,
            "projected_revenues": self.projected_revenues,
            "projected_fcfs": self.projected_fcfs,
            "discounted_fcfs": self.discounted_fcfs,
            "terminal_value": self.terminal_value,
            "pv_terminal_value": self.pv_terminal_value,
            "net_debt": self.net_debt,
            "shares_outstanding": self.shares_outstanding,
            "assumptions": self.assumptions.to_dict(),
        }
        if self.ev_bridge:
            result["ev_bridge"] = self.ev_bridge.to_dict()
        if self.wacc_components:
            result["wacc_components"] = self.wacc_components.to_dict()
        if self.projection_details:
            result["projection_details"] = [
                {
                    "year": d.year, "revenue": d.revenue,
                    "gross_profit": d.gross_profit, "opex": d.opex,
                    "ebitda": d.ebitda, "da": d.da, "ebit": d.ebit,
                    "nopat": d.nopat, "capex": d.capex,
                    "nwc_change": d.nwc_change, "sbc": d.sbc,
                    "fcf": d.fcf, "discounted_fcf": d.discounted_fcf,
                }
                for d in self.projection_details
            ]
        return result


def calculate_dcf(
    base_revenue: float,
    net_debt: float,
    shares_outstanding: float,
    current_price: float,
    assumptions: DCFAssumptions,
    ev_bridge: Optional[EVBridge] = None,
    wacc_components: Optional[WACCComponents] = None,
) -> DCFResult:
    """
    Run a DCF calculation.

    If ev_bridge is provided, uses the full EV-to-equity bridge (minority interests,
    preferred stock, pension deficit, etc.). Otherwise falls back to simple net_debt.

    If assumptions.is_decomposed is True, uses the full income-statement-driven
    FCF build. Otherwise falls back to the legacy flat FCF margin approach.
    """
    bridge = ev_bridge or EVBridge.from_net_debt(net_debt)
    if assumptions.is_decomposed:
        result = _calculate_dcf_decomposed(base_revenue, bridge, shares_outstanding, current_price, assumptions)
    else:
        result = _calculate_dcf_legacy(base_revenue, bridge, shares_outstanding, current_price, assumptions)
    # Attach WACC components if provided (frozen dataclass, so rebuild)
    if wacc_components and result.wacc_components is None:
        result = DCFResult(
            base_revenue=result.base_revenue,
            projected_revenues=result.projected_revenues,
            projected_fcfs=result.projected_fcfs,
            discounted_fcfs=result.discounted_fcfs,
            terminal_value=result.terminal_value,
            pv_terminal_value=result.pv_terminal_value,
            enterprise_value=result.enterprise_value,
            net_debt=result.net_debt,
            equity_value=result.equity_value,
            shares_outstanding=result.shares_outstanding,
            fair_value_per_share=result.fair_value_per_share,
            current_price=result.current_price,
            upside_downside_pct=result.upside_downside_pct,
            assumptions=result.assumptions,
            projection_details=result.projection_details,
            ev_bridge=result.ev_bridge,
            wacc_components=wacc_components,
        )
    return result


def _calculate_dcf_legacy(
    base_revenue: float,
    ev_bridge: EVBridge,
    shares_outstanding: float,
    current_price: float,
    assumptions: DCFAssumptions,
) -> DCFResult:
    """Legacy DCF: flat FCF margin applied to projected revenue."""
    n = assumptions.projection_years
    growth_rates = _pad_or_truncate(assumptions.revenue_growth_rates, n, 0.03)

    # Project revenues
    projected_revenues = []
    rev = base_revenue
    for rate in growth_rates:
        rev = rev * (1 + rate)
        projected_revenues.append(rev)

    # Apply FCF margin
    projected_fcfs = [rev * assumptions.fcf_margin for rev in projected_revenues]

    # Discount FCFs
    discounted_fcfs = []
    for i, fcf in enumerate(projected_fcfs):
        discount_factor = (1 + assumptions.wacc) ** (i + 1)
        discounted_fcfs.append(fcf / discount_factor)

    # Terminal value (Gordon Growth Model)
    final_fcf = projected_fcfs[-1]
    terminal_value = final_fcf * (1 + assumptions.terminal_growth_rate) / (
        assumptions.wacc - assumptions.terminal_growth_rate
    )

    pv_terminal_value = terminal_value / ((1 + assumptions.wacc) ** n)
    enterprise_value = sum(discounted_fcfs) + pv_terminal_value
    equity_value = ev_bridge.equity_value(enterprise_value)
    fair_value_per_share = equity_value / shares_outstanding if shares_outstanding > 0 else 0

    upside_downside_pct = (
        ((fair_value_per_share / current_price) - 1) * 100
        if current_price > 0
        else 0
    )

    return DCFResult(
        base_revenue=base_revenue,
        projected_revenues=projected_revenues,
        projected_fcfs=projected_fcfs,
        discounted_fcfs=discounted_fcfs,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal_value,
        enterprise_value=enterprise_value,
        net_debt=ev_bridge.net_debt,
        equity_value=equity_value,
        shares_outstanding=shares_outstanding,
        fair_value_per_share=fair_value_per_share,
        current_price=current_price,
        upside_downside_pct=upside_downside_pct,
        assumptions=assumptions,
        ev_bridge=ev_bridge,
    )


def _calculate_dcf_decomposed(
    base_revenue: float,
    ev_bridge: EVBridge,
    shares_outstanding: float,
    current_price: float,
    assumptions: DCFAssumptions,
) -> DCFResult:
    """
    Decomposed DCF: full income-statement-driven FCF build.

    FCF = NOPAT + D&A - CapEx - delta_NWC + SBC add-back
    Where:
      Revenue = base * (1 + growth)
      Gross Profit = Revenue * gross_margin
      EBITDA = Gross Profit - OpEx
      EBIT = EBITDA - D&A
      NOPAT = EBIT * (1 - tax_rate)
      FCF = NOPAT + D&A - CapEx - delta_NWC + SBC
    """
    n = assumptions.projection_years
    growth_rates = _pad_or_truncate(assumptions.revenue_growth_rates, n, 0.03)
    gross_margins = _pad_or_truncate(assumptions.gross_margins or [], n, 0.50)
    opex_pcts = _pad_or_truncate(assumptions.opex_as_pct_revenue or [], n, 0.20)
    capex_pcts = _pad_or_truncate(assumptions.capex_as_pct_revenue or [], n, 0.05)

    projected_revenues = []
    projected_fcfs = []
    discounted_fcfs = []
    projection_details = []

    prev_revenue = base_revenue

    for i in range(n):
        # Revenue
        revenue = prev_revenue * (1 + growth_rates[i])

        # Gross Profit
        gross_profit = revenue * gross_margins[i]

        # OpEx (SG&A + R&D as % of revenue)
        opex = revenue * opex_pcts[i]

        # EBITDA = Gross Profit - OpEx
        ebitda = gross_profit - opex

        # D&A
        da = revenue * assumptions.da_as_pct_revenue

        # EBIT = EBITDA - D&A
        ebit = ebitda - da

        # NOPAT = EBIT * (1 - tax)
        nopat = ebit * (1 - assumptions.tax_rate)

        # CapEx
        capex = revenue * capex_pcts[i]

        # NWC change (% of revenue delta)
        revenue_delta = revenue - prev_revenue
        nwc_change = revenue_delta * assumptions.nwc_change_pct

        # SBC add-back (non-cash expense already deducted from NOPAT through OpEx,
        # but conventionally added back for UFCF)
        sbc = revenue * assumptions.sbc_as_pct_revenue

        # FCF = NOPAT + D&A - CapEx - delta_NWC + SBC add-back
        fcf = nopat + da - capex - nwc_change + sbc

        # Discount
        discount_factor = (1 + assumptions.wacc) ** (i + 1)
        discounted_fcf = fcf / discount_factor

        projected_revenues.append(revenue)
        projected_fcfs.append(fcf)
        discounted_fcfs.append(discounted_fcf)

        projection_details.append(DCFProjectionYear(
            year=i + 1,
            revenue=revenue,
            gross_profit=gross_profit,
            opex=opex,
            ebitda=ebitda,
            da=da,
            ebit=ebit,
            nopat=nopat,
            capex=capex,
            nwc_change=nwc_change,
            sbc=sbc,
            fcf=fcf,
            discounted_fcf=discounted_fcf,
        ))

        prev_revenue = revenue

    # Terminal value
    final_fcf = projected_fcfs[-1]
    terminal_value = final_fcf * (1 + assumptions.terminal_growth_rate) / (
        assumptions.wacc - assumptions.terminal_growth_rate
    )
    pv_terminal_value = terminal_value / ((1 + assumptions.wacc) ** n)

    enterprise_value = sum(discounted_fcfs) + pv_terminal_value
    equity_value = ev_bridge.equity_value(enterprise_value)
    fair_value_per_share = equity_value / shares_outstanding if shares_outstanding > 0 else 0

    upside_downside_pct = (
        ((fair_value_per_share / current_price) - 1) * 100
        if current_price > 0
        else 0
    )

    return DCFResult(
        base_revenue=base_revenue,
        projected_revenues=projected_revenues,
        projected_fcfs=projected_fcfs,
        discounted_fcfs=discounted_fcfs,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal_value,
        enterprise_value=enterprise_value,
        net_debt=ev_bridge.net_debt,
        equity_value=equity_value,
        shares_outstanding=shares_outstanding,
        fair_value_per_share=fair_value_per_share,
        current_price=current_price,
        upside_downside_pct=upside_downside_pct,
        assumptions=assumptions,
        projection_details=projection_details,
        ev_bridge=ev_bridge,
    )
