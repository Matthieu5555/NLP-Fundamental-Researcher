"""
Financial growth metrics computation.

Computes YoY (Year-over-Year) and QoQ (Quarter-over-Quarter) changes
for all financial statement line items, with color coding hints.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class GrowthMetric:
    """A single metric with its growth rates."""
    name: str
    current_value: Optional[float]
    yoy_change: Optional[float] = None      # e.g., 0.152 for +15.2%
    qoq_change: Optional[float] = None      # e.g., -0.031 for -3.1%
    yoy_delta: Optional[float] = None       # Absolute change (for margins)

    @property
    def yoy_pct(self) -> Optional[str]:
        """Format YoY as percentage string."""
        if self.yoy_change is None:
            return None
        sign = "+" if self.yoy_change >= 0 else ""
        return f"{sign}{self.yoy_change * 100:.1f}%"

    @property
    def qoq_pct(self) -> Optional[str]:
        """Format QoQ as percentage string."""
        if self.qoq_change is None:
            return None
        sign = "+" if self.qoq_change >= 0 else ""
        return f"{sign}{self.qoq_change * 100:.1f}%"

    @property
    def yoy_color(self) -> str:
        """Color hint for YoY change (green/red/neutral)."""
        if self.yoy_change is None:
            return "neutral"
        # For most metrics, positive is good
        if self.yoy_change > 0.01:  # >1%
            return "green"
        elif self.yoy_change < -0.01:  # <-1%
            return "red"
        return "neutral"

    @property
    def qoq_color(self) -> str:
        """Color hint for QoQ change."""
        if self.qoq_change is None:
            return "neutral"
        if self.qoq_change > 0.01:
            return "green"
        elif self.qoq_change < -0.01:
            return "red"
        return "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.current_value,
            "yoy_change": self.yoy_change,
            "yoy_pct": self.yoy_pct,
            "yoy_color": self.yoy_color,
            "qoq_change": self.qoq_change,
            "qoq_pct": self.qoq_pct,
            "qoq_color": self.qoq_color,
        }


@dataclass
class EnrichedPeriod:
    """A single financial period with all metrics enriched."""
    period: str                              # e.g., "2024-09-30"
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    period_type: str = "annual"              # "annual" or "quarterly"

    # Income Statement metrics
    revenue: Optional[GrowthMetric] = None
    gross_profit: Optional[GrowthMetric] = None
    operating_income: Optional[GrowthMetric] = None
    net_income: Optional[GrowthMetric] = None
    eps: Optional[GrowthMetric] = None

    # Margins (computed)
    gross_margin: Optional[GrowthMetric] = None
    operating_margin: Optional[GrowthMetric] = None
    net_margin: Optional[GrowthMetric] = None

    # Balance Sheet metrics
    total_assets: Optional[GrowthMetric] = None
    total_liabilities: Optional[GrowthMetric] = None
    total_equity: Optional[GrowthMetric] = None
    cash: Optional[GrowthMetric] = None
    total_debt: Optional[GrowthMetric] = None

    # Cash Flow metrics
    operating_cash_flow: Optional[GrowthMetric] = None
    free_cash_flow: Optional[GrowthMetric] = None
    capex: Optional[GrowthMetric] = None

    # Computed ratios
    debt_to_equity: Optional[GrowthMetric] = None
    current_ratio: Optional[GrowthMetric] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "period": self.period,
            "fiscal_year": self.fiscal_year,
            "fiscal_quarter": self.fiscal_quarter,
            "period_type": self.period_type,
        }

        # Add all metrics that exist
        for attr in ["revenue", "gross_profit", "operating_income", "net_income",
                     "eps", "gross_margin", "operating_margin", "net_margin",
                     "total_assets", "total_liabilities", "total_equity",
                     "cash", "total_debt", "operating_cash_flow",
                     "free_cash_flow", "capex", "debt_to_equity", "current_ratio"]:
            metric = getattr(self, attr)
            if metric is not None:
                result[attr] = metric.to_dict()

        return result


@dataclass
class EnrichedFinancials:
    """
    Complete enriched financials for a company.

    Contains multiple periods with YoY/QoQ computed for each line item.
    """
    ticker: str
    company_name: str
    periods: List[EnrichedPeriod] = field(default_factory=list)

    # Summary metrics (latest period)
    latest_revenue: Optional[float] = None
    revenue_cagr_3y: Optional[float] = None   # 3-year CAGR
    revenue_cagr_5y: Optional[float] = None   # 5-year CAGR
    avg_gross_margin: Optional[float] = None
    avg_operating_margin: Optional[float] = None
    avg_net_margin: Optional[float] = None

    # Trend indicators
    revenue_trend: str = "stable"             # "growing", "declining", "stable"
    margin_trend: str = "stable"              # "expanding", "compressing", "stable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "periods": [p.to_dict() for p in self.periods],
            "summary": {
                "latest_revenue": self.latest_revenue,
                "revenue_cagr_3y": self.revenue_cagr_3y,
                "revenue_cagr_5y": self.revenue_cagr_5y,
                "avg_gross_margin": self.avg_gross_margin,
                "avg_operating_margin": self.avg_operating_margin,
                "avg_net_margin": self.avg_net_margin,
                "revenue_trend": self.revenue_trend,
                "margin_trend": self.margin_trend,
            }
        }

    def format_for_agent(self) -> str:
        """
        Format enriched financials as text for LLM consumption.

        Outputs a structured summary with all growth metrics highlighted.
        """
        lines = [
            f"# {self.company_name} ({self.ticker}) - Financial Analysis",
            "",
            "## Summary Metrics",
            f"- Revenue CAGR (3Y): {self._fmt_pct(self.revenue_cagr_3y)}",
            f"- Revenue CAGR (5Y): {self._fmt_pct(self.revenue_cagr_5y)}",
            f"- Avg Gross Margin: {self._fmt_pct(self.avg_gross_margin)}",
            f"- Avg Operating Margin: {self._fmt_pct(self.avg_operating_margin)}",
            f"- Revenue Trend: {self.revenue_trend.upper()}",
            f"- Margin Trend: {self.margin_trend.upper()}",
            "",
            "## Period-by-Period Analysis",
        ]

        for period in self.periods:
            lines.append("")
            lines.append(f"### {period.period} (FY{period.fiscal_year})")

            if period.revenue:
                lines.append(f"**Revenue**: ${self._fmt_num(period.revenue.current_value)} "
                           f"({period.revenue.yoy_pct or 'N/A'} YoY)")

            if period.gross_margin:
                lines.append(f"**Gross Margin**: {self._fmt_pct(period.gross_margin.current_value)} "
                           f"({self._fmt_delta(period.gross_margin.yoy_delta)} YoY)")

            if period.operating_margin:
                lines.append(f"**Operating Margin**: {self._fmt_pct(period.operating_margin.current_value)} "
                           f"({self._fmt_delta(period.operating_margin.yoy_delta)} YoY)")

            if period.net_income:
                lines.append(f"**Net Income**: ${self._fmt_num(period.net_income.current_value)} "
                           f"({period.net_income.yoy_pct or 'N/A'} YoY)")

            if period.free_cash_flow:
                lines.append(f"**Free Cash Flow**: ${self._fmt_num(period.free_cash_flow.current_value)} "
                           f"({period.free_cash_flow.yoy_pct or 'N/A'} YoY)")

            if period.debt_to_equity and period.debt_to_equity.current_value is not None:
                lines.append(f"**Debt/Equity**: {period.debt_to_equity.current_value:.2f}x")

        return "\n".join(lines)

    def _fmt_num(self, val: Optional[float]) -> str:
        """Format large numbers with B/M suffix."""
        if val is None:
            return "N/A"
        if abs(val) >= 1e9:
            return f"{val / 1e9:.1f}B"
        if abs(val) >= 1e6:
            return f"{val / 1e6:.1f}M"
        return f"{val:,.0f}"

    def _fmt_pct(self, val: Optional[float]) -> str:
        """Format as percentage."""
        if val is None:
            return "N/A"
        return f"{val * 100:.1f}%"

    def _fmt_delta(self, val: Optional[float]) -> str:
        """Format margin delta in percentage points."""
        if val is None:
            return "N/A"
        sign = "+" if val >= 0 else ""
        return f"{sign}{val * 100:.1f}pp"


def _compute_pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Compute percentage change between two values."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


def _compute_margin(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Compute margin ratio."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _compute_cagr(start_value: Optional[float], end_value: Optional[float], years: int) -> Optional[float]:
    """Compute Compound Annual Growth Rate."""
    if start_value is None or end_value is None or start_value <= 0 or years <= 0:
        return None
    return (end_value / start_value) ** (1 / years) - 1


def compute_growth_metrics(
    statements: List[Any],  # List of FinancialStatement from FDS
    ticker: str,
    company_name: str,
) -> EnrichedFinancials:
    """
    Compute YoY and QoQ growth metrics for all financial line items.

    Args:
        statements: List of FinancialStatement objects from FDS client
        ticker: Stock ticker symbol
        company_name: Company name for display

    Returns:
        EnrichedFinancials with all growth metrics computed
    """
    if not statements:
        return EnrichedFinancials(ticker=ticker, company_name=company_name)

    # Sort by period date (newest first)
    sorted_stmts = sorted(statements, key=lambda x: x.report_period, reverse=True)

    enriched_periods = []

    for i, stmt in enumerate(sorted_stmts):
        # Find YoY comparison (same period last year)
        yoy_stmt = None
        for prev_stmt in sorted_stmts[i+1:]:
            # Skip if fiscal_year is missing on either statement
            if stmt.fiscal_year is None or prev_stmt.fiscal_year is None:
                continue
            if prev_stmt.fiscal_year == stmt.fiscal_year - 1:
                if stmt.period == "annual" or prev_stmt.fiscal_quarter == stmt.fiscal_quarter:
                    yoy_stmt = prev_stmt
                    break

        # Find QoQ comparison (previous quarter)
        qoq_stmt = None
        if i + 1 < len(sorted_stmts):
            qoq_stmt = sorted_stmts[i + 1]

        # Compute margins
        gross_margin = _compute_margin(stmt.gross_profit, stmt.revenue)
        operating_margin = _compute_margin(stmt.operating_income, stmt.revenue)
        net_margin = _compute_margin(stmt.net_income, stmt.revenue)

        # YoY margins for delta
        yoy_gross_margin = _compute_margin(yoy_stmt.gross_profit, yoy_stmt.revenue) if yoy_stmt else None
        yoy_operating_margin = _compute_margin(yoy_stmt.operating_income, yoy_stmt.revenue) if yoy_stmt else None
        yoy_net_margin = _compute_margin(yoy_stmt.net_income, yoy_stmt.revenue) if yoy_stmt else None

        # Debt to equity ratio
        debt_to_equity = None
        if stmt.total_debt and stmt.total_equity and stmt.total_equity != 0:
            debt_to_equity = stmt.total_debt / stmt.total_equity

        # Build enriched period
        period = EnrichedPeriod(
            period=stmt.report_period,
            fiscal_year=stmt.fiscal_year,
            fiscal_quarter=stmt.fiscal_quarter,
            period_type=stmt.period,

            # Income Statement
            revenue=GrowthMetric(
                name="Revenue",
                current_value=stmt.revenue,
                yoy_change=_compute_pct_change(stmt.revenue, yoy_stmt.revenue if yoy_stmt else None),
                qoq_change=_compute_pct_change(stmt.revenue, qoq_stmt.revenue if qoq_stmt else None),
            ),
            gross_profit=GrowthMetric(
                name="Gross Profit",
                current_value=stmt.gross_profit,
                yoy_change=_compute_pct_change(stmt.gross_profit, yoy_stmt.gross_profit if yoy_stmt else None),
                qoq_change=_compute_pct_change(stmt.gross_profit, qoq_stmt.gross_profit if qoq_stmt else None),
            ),
            operating_income=GrowthMetric(
                name="Operating Income",
                current_value=stmt.operating_income,
                yoy_change=_compute_pct_change(stmt.operating_income, yoy_stmt.operating_income if yoy_stmt else None),
                qoq_change=_compute_pct_change(stmt.operating_income, qoq_stmt.operating_income if qoq_stmt else None),
            ),
            net_income=GrowthMetric(
                name="Net Income",
                current_value=stmt.net_income,
                yoy_change=_compute_pct_change(stmt.net_income, yoy_stmt.net_income if yoy_stmt else None),
                qoq_change=_compute_pct_change(stmt.net_income, qoq_stmt.net_income if qoq_stmt else None),
            ),
            eps=GrowthMetric(
                name="EPS",
                current_value=stmt.earnings_per_share,
                yoy_change=_compute_pct_change(stmt.earnings_per_share, yoy_stmt.earnings_per_share if yoy_stmt else None),
                qoq_change=_compute_pct_change(stmt.earnings_per_share, qoq_stmt.earnings_per_share if qoq_stmt else None),
            ),

            # Margins
            gross_margin=GrowthMetric(
                name="Gross Margin",
                current_value=gross_margin,
                yoy_delta=gross_margin - yoy_gross_margin if gross_margin and yoy_gross_margin else None,
            ),
            operating_margin=GrowthMetric(
                name="Operating Margin",
                current_value=operating_margin,
                yoy_delta=operating_margin - yoy_operating_margin if operating_margin and yoy_operating_margin else None,
            ),
            net_margin=GrowthMetric(
                name="Net Margin",
                current_value=net_margin,
                yoy_delta=net_margin - yoy_net_margin if net_margin and yoy_net_margin else None,
            ),

            # Balance Sheet
            total_assets=GrowthMetric(
                name="Total Assets",
                current_value=stmt.total_assets,
                yoy_change=_compute_pct_change(stmt.total_assets, yoy_stmt.total_assets if yoy_stmt else None),
            ),
            total_liabilities=GrowthMetric(
                name="Total Liabilities",
                current_value=stmt.total_liabilities,
                yoy_change=_compute_pct_change(stmt.total_liabilities, yoy_stmt.total_liabilities if yoy_stmt else None),
            ),
            total_equity=GrowthMetric(
                name="Total Equity",
                current_value=stmt.total_equity,
                yoy_change=_compute_pct_change(stmt.total_equity, yoy_stmt.total_equity if yoy_stmt else None),
            ),
            cash=GrowthMetric(
                name="Cash & Equivalents",
                current_value=stmt.cash_and_equivalents,
                yoy_change=_compute_pct_change(stmt.cash_and_equivalents, yoy_stmt.cash_and_equivalents if yoy_stmt else None),
            ),
            total_debt=GrowthMetric(
                name="Total Debt",
                current_value=stmt.total_debt,
                yoy_change=_compute_pct_change(stmt.total_debt, yoy_stmt.total_debt if yoy_stmt else None),
            ),

            # Cash Flow
            operating_cash_flow=GrowthMetric(
                name="Operating Cash Flow",
                current_value=stmt.operating_cash_flow,
                yoy_change=_compute_pct_change(stmt.operating_cash_flow, yoy_stmt.operating_cash_flow if yoy_stmt else None),
            ),
            free_cash_flow=GrowthMetric(
                name="Free Cash Flow",
                current_value=stmt.free_cash_flow,
                yoy_change=_compute_pct_change(stmt.free_cash_flow, yoy_stmt.free_cash_flow if yoy_stmt else None),
            ),
            capex=GrowthMetric(
                name="Capital Expenditure",
                current_value=stmt.capital_expenditure,
                yoy_change=_compute_pct_change(stmt.capital_expenditure, yoy_stmt.capital_expenditure if yoy_stmt else None),
            ),

            # Ratios
            debt_to_equity=GrowthMetric(
                name="Debt/Equity",
                current_value=debt_to_equity,
            ),
        )

        enriched_periods.append(period)

    # Compute summary metrics
    result = EnrichedFinancials(
        ticker=ticker,
        company_name=company_name,
        periods=enriched_periods,
    )

    if enriched_periods:
        latest = enriched_periods[0]
        result.latest_revenue = latest.revenue.current_value if latest.revenue else None

        # Compute average margins
        margins = [p.gross_margin.current_value for p in enriched_periods if p.gross_margin and p.gross_margin.current_value]
        result.avg_gross_margin = sum(margins) / len(margins) if margins else None

        op_margins = [p.operating_margin.current_value for p in enriched_periods if p.operating_margin and p.operating_margin.current_value]
        result.avg_operating_margin = sum(op_margins) / len(op_margins) if op_margins else None

        net_margins = [p.net_margin.current_value for p in enriched_periods if p.net_margin and p.net_margin.current_value]
        result.avg_net_margin = sum(net_margins) / len(net_margins) if net_margins else None

        # Compute CAGRs
        revenues = [(p.fiscal_year, p.revenue.current_value) for p in enriched_periods
                   if p.revenue and p.revenue.current_value and p.fiscal_year]
        if len(revenues) >= 2:
            revenues_sorted = sorted(revenues, key=lambda x: x[0])
            years_diff = revenues_sorted[-1][0] - revenues_sorted[0][0]
            if years_diff >= 3:
                # Find 3-year CAGR
                for year, rev in revenues_sorted:
                    if revenues_sorted[-1][0] - year == 3:
                        result.revenue_cagr_3y = _compute_cagr(rev, revenues_sorted[-1][1], 3)
                        break
            if years_diff >= 5:
                result.revenue_cagr_5y = _compute_cagr(revenues_sorted[0][1], revenues_sorted[-1][1], years_diff)

        # Determine trends
        if len(enriched_periods) >= 2:
            recent_revenues = [p.revenue.current_value for p in enriched_periods[:3]
                             if p.revenue and p.revenue.current_value]
            if len(recent_revenues) >= 2:
                if all(recent_revenues[i] > recent_revenues[i+1] for i in range(len(recent_revenues)-1)):
                    result.revenue_trend = "growing"
                elif all(recent_revenues[i] < recent_revenues[i+1] for i in range(len(recent_revenues)-1)):
                    result.revenue_trend = "declining"

            recent_margins = [p.operating_margin.current_value for p in enriched_periods[:3]
                            if p.operating_margin and p.operating_margin.current_value]
            if len(recent_margins) >= 2:
                if all(recent_margins[i] > recent_margins[i+1] for i in range(len(recent_margins)-1)):
                    result.margin_trend = "expanding"
                elif all(recent_margins[i] < recent_margins[i+1] for i in range(len(recent_margins)-1)):
                    result.margin_trend = "compressing"

    return result
