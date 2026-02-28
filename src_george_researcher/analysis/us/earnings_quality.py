"""
Earnings Quality Forensics.

Quantitative red-flag detection based on accrual analysis and cash conversion.
All pure math — no LLM calls.

Metrics:
- Balance sheet accruals: (Delta NOA) / Avg Total Assets
- Cash flow accruals: (NI - CFO) / Avg Total Assets
- Cash conversion ratio: CFO / NI
- Accrual quality classification: clean / moderate / aggressive
- Red flags list with severity
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AccrualQuality(Enum):
    """Classification of earnings accrual quality."""
    CLEAN = "clean"           # Low accruals, strong cash conversion
    MODERATE = "moderate"     # Some accrual buildup, acceptable
    AGGRESSIVE = "aggressive" # High accruals, potential manipulation risk


class RedFlagSeverity(Enum):
    """Severity of an earnings quality red flag."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class RedFlag:
    """A single earnings quality concern."""
    description: str
    severity: RedFlagSeverity
    metric: str
    value: Optional[float] = None
    threshold: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "severity": self.severity.value,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class EarningsQualityReport:
    """Complete earnings quality assessment."""
    # Core metrics
    bs_accrual_ratio: Optional[float]       # (Delta NOA) / Avg Total Assets
    cf_accrual_ratio: Optional[float]       # (NI - CFO) / Avg Total Assets
    cash_conversion_ratio: Optional[float]  # CFO / NI
    fcf_to_net_income: Optional[float]      # FCF / NI

    # Multi-year trends
    cash_conversion_trend: Optional[List[float]]  # CFO/NI for each year
    accrual_trend: Optional[List[float]]           # CF accrual ratio for each year

    # Classification
    accrual_quality: AccrualQuality
    quality_score: int  # 0-100, higher is better

    # Red flags
    red_flags: List[RedFlag]

    # Summary
    rationale: str

    def to_dict(self) -> Dict:
        return {
            "bs_accrual_ratio": self.bs_accrual_ratio,
            "cf_accrual_ratio": self.cf_accrual_ratio,
            "cash_conversion_ratio": self.cash_conversion_ratio,
            "fcf_to_net_income": self.fcf_to_net_income,
            "cash_conversion_trend": self.cash_conversion_trend,
            "accrual_trend": self.accrual_trend,
            "accrual_quality": self.accrual_quality.value,
            "quality_score": self.quality_score,
            "red_flags": [f.to_dict() for f in self.red_flags],
            "rationale": self.rationale,
        }


# Thresholds for accrual quality classification
# Based on Sloan (1996) accrual anomaly research
BS_ACCRUAL_CLEAN = 0.05       # <5% of assets
BS_ACCRUAL_AGGRESSIVE = 0.10  # >10% of assets
CF_ACCRUAL_CLEAN = 0.05
CF_ACCRUAL_AGGRESSIVE = 0.10
CASH_CONVERSION_HEALTHY = 0.80   # CFO >= 80% of NI
CASH_CONVERSION_CONCERN = 0.50   # CFO < 50% of NI


def assess_earnings_quality(
    statements: List[Dict],
) -> Optional[EarningsQualityReport]:
    """
    Assess earnings quality from financial statement data.

    Args:
        statements: List of financial statement dicts, most recent first.
            Expected keys: net_income, operating_cash_flow, free_cash_flow,
            total_assets, total_liabilities, total_equity, cash_and_equivalents,
            total_debt.

    Returns:
        EarningsQualityReport, or None if insufficient data.
    """
    if len(statements) < 2:
        return None

    current = statements[0]
    previous = statements[1]

    ni = current.get("net_income")
    cfo = current.get("operating_cash_flow")
    fcf = current.get("free_cash_flow")
    curr_assets = current.get("total_assets")
    prev_assets = previous.get("total_assets")

    if ni is None or cfo is None or curr_assets is None or prev_assets is None:
        return None

    avg_assets = (curr_assets + prev_assets) / 2
    if avg_assets <= 0:
        return None

    # Balance sheet accrual ratio: (Delta NOA) / Avg Total Assets
    # NOA = (Total Assets - Cash) - (Total Liabilities - Total Debt)
    bs_accrual = _compute_bs_accrual_ratio(current, previous, avg_assets)

    # Cash flow accrual ratio: (NI - CFO) / Avg Total Assets
    cf_accrual = (ni - cfo) / avg_assets if avg_assets > 0 else None

    # Cash conversion ratio: CFO / NI
    cash_conversion = cfo / ni if ni and ni != 0 else None

    # FCF / NI
    fcf_to_ni = fcf / ni if ni and ni != 0 and fcf is not None else None

    # Multi-year trends
    cash_conversion_trend = []
    accrual_trend = []
    for i in range(len(statements) - 1):
        s = statements[i]
        s_prev = statements[i + 1]
        s_ni = s.get("net_income")
        s_cfo = s.get("operating_cash_flow")
        s_assets = s.get("total_assets")
        s_prev_assets = s_prev.get("total_assets")

        if s_ni and s_ni != 0 and s_cfo is not None:
            cash_conversion_trend.append(s_cfo / s_ni)

        if s_ni is not None and s_cfo is not None and s_assets and s_prev_assets:
            s_avg = (s_assets + s_prev_assets) / 2
            if s_avg > 0:
                accrual_trend.append((s_ni - s_cfo) / s_avg)

    # Detect red flags
    red_flags = _detect_red_flags(
        bs_accrual=bs_accrual,
        cf_accrual=cf_accrual,
        cash_conversion=cash_conversion,
        fcf_to_ni=fcf_to_ni,
        cash_conversion_trend=cash_conversion_trend,
        accrual_trend=accrual_trend,
        ni=ni,
        cfo=cfo,
    )

    # Classify quality
    accrual_quality = _classify_quality(bs_accrual, cf_accrual, cash_conversion)

    # Score 0-100
    quality_score = _compute_quality_score(
        bs_accrual=bs_accrual,
        cf_accrual=cf_accrual,
        cash_conversion=cash_conversion,
        fcf_to_ni=fcf_to_ni,
        red_flag_count=len(red_flags),
    )

    # Build rationale
    rationale = _build_rationale(accrual_quality, quality_score, red_flags, cash_conversion)

    return EarningsQualityReport(
        bs_accrual_ratio=bs_accrual,
        cf_accrual_ratio=cf_accrual,
        cash_conversion_ratio=cash_conversion,
        fcf_to_net_income=fcf_to_ni,
        cash_conversion_trend=cash_conversion_trend or None,
        accrual_trend=accrual_trend or None,
        accrual_quality=accrual_quality,
        quality_score=quality_score,
        red_flags=red_flags,
        rationale=rationale,
    )


def _compute_bs_accrual_ratio(
    current: Dict, previous: Dict, avg_assets: float
) -> Optional[float]:
    """Compute balance sheet accrual ratio from NOA changes."""
    def noa(stmt: Dict) -> Optional[float]:
        assets = stmt.get("total_assets")
        cash = stmt.get("cash_and_equivalents", 0) or 0
        liabilities = stmt.get("total_liabilities")
        debt = stmt.get("total_debt", 0) or 0
        if assets is None or liabilities is None:
            return None
        return (assets - cash) - (liabilities - debt)

    curr_noa = noa(current)
    prev_noa = noa(previous)
    if curr_noa is None or prev_noa is None or avg_assets <= 0:
        return None
    return (curr_noa - prev_noa) / avg_assets


def _detect_red_flags(
    bs_accrual: Optional[float],
    cf_accrual: Optional[float],
    cash_conversion: Optional[float],
    fcf_to_ni: Optional[float],
    cash_conversion_trend: List[float],
    accrual_trend: List[float],
    ni: float,
    cfo: float,
) -> List[RedFlag]:
    """Detect earnings quality red flags."""
    flags = []

    # High balance sheet accruals
    if bs_accrual is not None and abs(bs_accrual) > BS_ACCRUAL_AGGRESSIVE:
        flags.append(RedFlag(
            description=f"High balance sheet accruals ({bs_accrual*100:.1f}% of assets) suggest earnings may not be sustainable",
            severity=RedFlagSeverity.HIGH,
            metric="bs_accrual_ratio",
            value=bs_accrual,
            threshold=BS_ACCRUAL_AGGRESSIVE,
        ))

    # High cash flow accruals
    if cf_accrual is not None and cf_accrual > CF_ACCRUAL_AGGRESSIVE:
        flags.append(RedFlag(
            description=f"Cash flow accruals ({cf_accrual*100:.1f}% of assets) indicate earnings significantly exceed cash generation",
            severity=RedFlagSeverity.HIGH,
            metric="cf_accrual_ratio",
            value=cf_accrual,
            threshold=CF_ACCRUAL_AGGRESSIVE,
        ))

    # Poor cash conversion
    if cash_conversion is not None and ni > 0:
        if cash_conversion < CASH_CONVERSION_CONCERN:
            flags.append(RedFlag(
                description=f"Operating cash flow is only {cash_conversion*100:.0f}% of net income — investigate accrual quality",
                severity=RedFlagSeverity.HIGH,
                metric="cash_conversion",
                value=cash_conversion,
                threshold=CASH_CONVERSION_CONCERN,
            ))
        elif cash_conversion < CASH_CONVERSION_HEALTHY:
            flags.append(RedFlag(
                description=f"Cash conversion of {cash_conversion*100:.0f}% is below healthy threshold",
                severity=RedFlagSeverity.MEDIUM,
                metric="cash_conversion",
                value=cash_conversion,
                threshold=CASH_CONVERSION_HEALTHY,
            ))

    # Positive NI but negative CFO
    if ni > 0 and cfo < 0:
        flags.append(RedFlag(
            description="Positive net income but negative operating cash flow — major earnings quality concern",
            severity=RedFlagSeverity.HIGH,
            metric="ni_vs_cfo",
            value=cfo,
        ))

    # Negative FCF with positive NI
    if fcf_to_ni is not None and ni > 0 and fcf_to_ni < 0:
        flags.append(RedFlag(
            description="Positive net income but negative free cash flow — heavy capital requirements or poor cash management",
            severity=RedFlagSeverity.MEDIUM,
            metric="fcf_to_ni",
            value=fcf_to_ni,
        ))

    # Deteriorating cash conversion trend (3+ years of decline)
    if len(cash_conversion_trend) >= 3:
        declining = all(
            cash_conversion_trend[i] < cash_conversion_trend[i + 1]
            for i in range(min(3, len(cash_conversion_trend) - 1))
        )
        if declining:
            flags.append(RedFlag(
                description="Cash conversion has declined for 3+ consecutive years — deteriorating earnings quality",
                severity=RedFlagSeverity.MEDIUM,
                metric="cash_conversion_trend",
            ))

    # Rising accruals trend
    if len(accrual_trend) >= 3:
        rising = all(
            accrual_trend[i] > accrual_trend[i + 1]
            for i in range(min(3, len(accrual_trend) - 1))
        )
        if rising and accrual_trend[0] > CF_ACCRUAL_CLEAN:
            flags.append(RedFlag(
                description="Accruals have been rising for 3+ years — potential earnings management",
                severity=RedFlagSeverity.MEDIUM,
                metric="accrual_trend",
            ))

    return flags


def _classify_quality(
    bs_accrual: Optional[float],
    cf_accrual: Optional[float],
    cash_conversion: Optional[float],
) -> AccrualQuality:
    """Classify overall accrual quality."""
    aggressive_signals = 0
    clean_signals = 0

    if bs_accrual is not None:
        if abs(bs_accrual) > BS_ACCRUAL_AGGRESSIVE:
            aggressive_signals += 1
        elif abs(bs_accrual) < BS_ACCRUAL_CLEAN:
            clean_signals += 1

    if cf_accrual is not None:
        if cf_accrual > CF_ACCRUAL_AGGRESSIVE:
            aggressive_signals += 1
        elif cf_accrual < CF_ACCRUAL_CLEAN:
            clean_signals += 1

    if cash_conversion is not None:
        if cash_conversion < CASH_CONVERSION_CONCERN:
            aggressive_signals += 1
        elif cash_conversion > CASH_CONVERSION_HEALTHY:
            clean_signals += 1

    if aggressive_signals >= 2:
        return AccrualQuality.AGGRESSIVE
    if clean_signals >= 2:
        return AccrualQuality.CLEAN
    return AccrualQuality.MODERATE


def _compute_quality_score(
    bs_accrual: Optional[float],
    cf_accrual: Optional[float],
    cash_conversion: Optional[float],
    fcf_to_ni: Optional[float],
    red_flag_count: int,
) -> int:
    """Compute 0-100 quality score. Higher is better."""
    score = 70  # Start at baseline

    # BS accruals: +-15 points
    if bs_accrual is not None:
        if abs(bs_accrual) < BS_ACCRUAL_CLEAN:
            score += 10
        elif abs(bs_accrual) > BS_ACCRUAL_AGGRESSIVE:
            score -= 15

    # CF accruals: +-15 points
    if cf_accrual is not None:
        if cf_accrual < CF_ACCRUAL_CLEAN:
            score += 10
        elif cf_accrual > CF_ACCRUAL_AGGRESSIVE:
            score -= 15

    # Cash conversion: +-15 points
    if cash_conversion is not None:
        if cash_conversion > 1.2:
            score += 15
        elif cash_conversion > CASH_CONVERSION_HEALTHY:
            score += 10
        elif cash_conversion < CASH_CONVERSION_CONCERN:
            score -= 15
        elif cash_conversion < CASH_CONVERSION_HEALTHY:
            score -= 5

    # FCF quality: +-10 points
    if fcf_to_ni is not None:
        if fcf_to_ni > 1.0:
            score += 10
        elif fcf_to_ni < 0:
            score -= 10

    # Red flag penalty
    score -= red_flag_count * 5

    return max(0, min(100, score))


def _build_rationale(
    quality: AccrualQuality,
    score: int,
    flags: List[RedFlag],
    cash_conversion: Optional[float],
) -> str:
    """Build human-readable quality assessment."""
    parts = [f"Earnings quality: {quality.value} (score: {score}/100)."]

    if cash_conversion is not None:
        parts.append(f"Cash conversion ratio: {cash_conversion:.2f}x.")

    high_flags = [f for f in flags if f.severity == RedFlagSeverity.HIGH]
    if high_flags:
        parts.append(f"{len(high_flags)} high-severity concern(s) detected.")
    elif not flags:
        parts.append("No material red flags identified.")

    return " ".join(parts)
