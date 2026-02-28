"""
Financial Statement Analysis for US Companies

Analyzes financial statements from FinancialDatasets.ai to produce:
- 3-statement summary (Income, Balance Sheet, Cash Flow)
- Key financial ratios
- Highlighted anomalies and notable findings
- 5-year trend analysis
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HighlightType(Enum):
    """Type of financial highlight/anomaly."""
    POSITIVE = "positive"      # Green - good signal
    NEGATIVE = "negative"      # Red - warning/concern
    NEUTRAL = "neutral"        # Blue - notable but not directional
    ATTENTION = "attention"    # Yellow - needs further investigation


@dataclass
class FinancialHighlight:
    """A highlighted finding from financial analysis."""
    title: str
    description: str
    highlight_type: HighlightType
    metric_name: str
    current_value: Optional[float] = None
    previous_value: Optional[float] = None
    change_percent: Optional[float] = None
    section: str = "general"  # income, balance, cashflow, ratios

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "type": self.highlight_type.value,
            "metric": self.metric_name,
            "current": self.current_value,
            "previous": self.previous_value,
            "change_pct": self.change_percent,
            "section": self.section,
        }


@dataclass
class IncomeStatementSummary:
    """Summarized income statement for a period."""
    period: str
    fiscal_year: int
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    eps_diluted: Optional[float] = None

    # Calculated margins
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None

    # YoY growth rates (calculated by comparing to previous year)
    revenue_yoy: Optional[float] = None
    gross_profit_yoy: Optional[float] = None
    operating_income_yoy: Optional[float] = None
    net_income_yoy: Optional[float] = None
    eps_yoy: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "fiscal_year": self.fiscal_year,
            "revenue": self.revenue,
            "gross_profit": self.gross_profit,
            "operating_income": self.operating_income,
            "net_income": self.net_income,
            "eps": self.eps,
            "eps_diluted": self.eps_diluted,
            "gross_margin": self.gross_margin,
            "operating_margin": self.operating_margin,
            "net_margin": self.net_margin,
            # YoY growth rates
            "revenue_yoy": self.revenue_yoy,
            "gross_profit_yoy": self.gross_profit_yoy,
            "operating_income_yoy": self.operating_income_yoy,
            "net_income_yoy": self.net_income_yoy,
            "eps_yoy": self.eps_yoy,
        }


@dataclass
class BalanceSheetSummary:
    """Summarized balance sheet for a period."""
    period: str
    fiscal_year: int
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    cash: Optional[float] = None
    total_debt: Optional[float] = None

    # Calculated ratios
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_assets: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "fiscal_year": self.fiscal_year,
            "total_assets": self.total_assets,
            "total_liabilities": self.total_liabilities,
            "total_equity": self.total_equity,
            "cash": self.cash,
            "total_debt": self.total_debt,
            "debt_to_equity": self.debt_to_equity,
            "current_ratio": self.current_ratio,
            "debt_to_assets": self.debt_to_assets,
        }


@dataclass
class CashFlowSummary:
    """Summarized cash flow statement for a period."""
    period: str
    fiscal_year: int
    operating_cash_flow: Optional[float] = None
    investing_cash_flow: Optional[float] = None
    financing_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None
    capex: Optional[float] = None

    # Calculated metrics
    fcf_margin: Optional[float] = None  # FCF / Revenue
    capex_to_revenue: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "fiscal_year": self.fiscal_year,
            "operating_cf": self.operating_cash_flow,
            "investing_cf": self.investing_cash_flow,
            "financing_cf": self.financing_cash_flow,
            "free_cash_flow": self.free_cash_flow,
            "capex": self.capex,
            "fcf_margin": self.fcf_margin,
            "capex_to_revenue": self.capex_to_revenue,
        }


@dataclass
class FinancialRatios:
    """Comprehensive financial ratios."""
    period: str
    fiscal_year: int

    # Profitability
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None  # Return on Equity
    roa: Optional[float] = None  # Return on Assets
    roic: Optional[float] = None  # Return on Invested Capital

    # Liquidity
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    cash_ratio: Optional[float] = None

    # Leverage
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None
    interest_coverage: Optional[float] = None
    equity_multiplier: Optional[float] = None  # Total Assets / Equity (DuPont)

    # Efficiency
    asset_turnover: Optional[float] = None
    inventory_turnover: Optional[float] = None
    receivables_turnover: Optional[float] = None

    # DuPont 5-factor decomposition
    dupont_tax_burden: Optional[float] = None         # NI / Pretax
    dupont_interest_burden: Optional[float] = None     # Pretax / EBIT
    dupont_operating_margin: Optional[float] = None    # EBIT / Revenue
    dupont_asset_turnover: Optional[float] = None      # Revenue / Assets
    dupont_equity_multiplier: Optional[float] = None   # Assets / Equity

    # Per-share metrics
    revenue_per_share: Optional[float] = None
    book_value_per_share: Optional[float] = None
    fcf_per_share: Optional[float] = None

    # Cash flow
    fcf_yield: Optional[float] = None
    operating_cf_to_debt: Optional[float] = None
    fcf_to_net_income: Optional[float] = None  # Cash conversion quality

    # Valuation ratios (require current price)
    pe_ratio: Optional[float] = None  # Price to Earnings
    pb_ratio: Optional[float] = None  # Price to Book
    ps_ratio: Optional[float] = None  # Price to Sales
    pfcf_ratio: Optional[float] = None  # Price to FCF

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "fiscal_year": self.fiscal_year,
            "profitability": {
                "gross_margin": self.gross_margin,
                "operating_margin": self.operating_margin,
                "net_margin": self.net_margin,
                "roe": self.roe,
                "roa": self.roa,
                "roic": self.roic,
            },
            "liquidity": {
                "current_ratio": self.current_ratio,
                "quick_ratio": self.quick_ratio,
                "cash_ratio": self.cash_ratio,
            },
            "leverage": {
                "debt_to_equity": self.debt_to_equity,
                "debt_to_assets": self.debt_to_assets,
                "interest_coverage": self.interest_coverage,
                "equity_multiplier": self.equity_multiplier,
            },
            "efficiency": {
                "asset_turnover": self.asset_turnover,
                "inventory_turnover": self.inventory_turnover,
                "receivables_turnover": self.receivables_turnover,
            },
            "dupont": {
                "tax_burden": self.dupont_tax_burden,
                "interest_burden": self.dupont_interest_burden,
                "operating_margin": self.dupont_operating_margin,
                "asset_turnover": self.dupont_asset_turnover,
                "equity_multiplier": self.dupont_equity_multiplier,
            },
            "per_share": {
                "revenue_per_share": self.revenue_per_share,
                "book_value_per_share": self.book_value_per_share,
                "fcf_per_share": self.fcf_per_share,
            },
            "cash_flow": {
                "fcf_yield": self.fcf_yield,
                "operating_cf_to_debt": self.operating_cf_to_debt,
                "fcf_to_net_income": self.fcf_to_net_income,
            },
            "valuation": {
                "pe_ratio": self.pe_ratio,
                "pb_ratio": self.pb_ratio,
                "ps_ratio": self.ps_ratio,
                "pfcf_ratio": self.pfcf_ratio,
            },
        }


@dataclass
class FinancialStatements:
    """Complete financial statements analysis result."""
    ticker: str
    company_name: str
    is_available: bool = True

    # 5 years of data
    income_statements: List[IncomeStatementSummary] = field(default_factory=list)
    balance_sheets: List[BalanceSheetSummary] = field(default_factory=list)
    cash_flows: List[CashFlowSummary] = field(default_factory=list)
    ratios: List[FinancialRatios] = field(default_factory=list)

    # Highlights and anomalies
    highlights: List[FinancialHighlight] = field(default_factory=list)

    # Summary text for reports
    summary: str = ""

    # Error message if not available
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "is_available": self.is_available,
            "income_statements": [s.to_dict() for s in self.income_statements],
            "balance_sheets": [s.to_dict() for s in self.balance_sheets],
            "cash_flows": [s.to_dict() for s in self.cash_flows],
            "ratios": [r.to_dict() for r in self.ratios],
            "highlights": [h.to_dict() for h in self.highlights],
            "summary": self.summary,
            "error": self.error,
        }


def _safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Safely divide two numbers, returning None if invalid."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _calc_change_pct(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Calculate percentage change between two values."""
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def _format_large_number(value: Optional[float]) -> str:
    """Format large numbers as human-readable strings."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"${value/1e12:.2f}T"
    elif abs_val >= 1e9:
        return f"${value/1e9:.2f}B"
    elif abs_val >= 1e6:
        return f"${value/1e6:.2f}M"
    elif abs_val >= 1e3:
        return f"${value/1e3:.2f}K"
    else:
        return f"${value:.2f}"


def _format_pct(value: Optional[float]) -> str:
    """Format a decimal as percentage."""
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _format_ratio(value: Optional[float]) -> str:
    """Format a ratio."""
    if value is None:
        return "N/A"
    return f"{value:.2f}x"


def analyze_financial_statements(
    ticker: str,
    company_name: str,
    financials_data: List[Any],
    period: str = "annual",
    current_price: Optional[float] = None,
    shares_outstanding: Optional[float] = None,
    yf_ratios: Optional[Dict[str, Any]] = None,
) -> FinancialStatements:
    """
    Analyze financial statements from FDS data.

    Args:
        ticker: Stock ticker symbol
        company_name: Company name
        financials_data: List of FinancialStatement objects from FDS
        period: "annual" or "quarterly"
        current_price: Current stock price for valuation ratios
        shares_outstanding: Shares outstanding for per-share metrics
        yf_ratios: Pre-computed ratios from yfinance as fallback

    Returns:
        FinancialStatements with analysis, ratios, and highlights
    """
    yf_ratios = yf_ratios or {}
    if not financials_data:
        return FinancialStatements(
            ticker=ticker,
            company_name=company_name,
            is_available=False,
            error="No financial data available"
        )

    result = FinancialStatements(
        ticker=ticker,
        company_name=company_name,
        is_available=True,
    )

    # Process each period (limit to 5 years)
    for i, stmt in enumerate(financials_data[:5]):
        # Income Statement
        gross_margin = _safe_divide(stmt.gross_profit, stmt.revenue)
        operating_margin = _safe_divide(stmt.operating_income, stmt.revenue)
        net_margin = _safe_divide(stmt.net_income, stmt.revenue)

        income = IncomeStatementSummary(
            period=stmt.report_period,
            fiscal_year=stmt.fiscal_year or 0,
            revenue=stmt.revenue,
            gross_profit=stmt.gross_profit,
            operating_income=stmt.operating_income,
            net_income=stmt.net_income,
            eps=stmt.earnings_per_share,
            eps_diluted=stmt.earnings_per_share_diluted,
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            net_margin=net_margin,
        )
        result.income_statements.append(income)

        # Balance Sheet
        debt_to_equity = _safe_divide(stmt.total_debt, stmt.total_equity)
        debt_to_assets = _safe_divide(stmt.total_debt, stmt.total_assets)

        balance = BalanceSheetSummary(
            period=stmt.report_period,
            fiscal_year=stmt.fiscal_year or 0,
            total_assets=stmt.total_assets,
            total_liabilities=stmt.total_liabilities,
            total_equity=stmt.total_equity,
            cash=stmt.cash_and_equivalents,
            total_debt=stmt.total_debt,
            debt_to_equity=debt_to_equity,
            debt_to_assets=debt_to_assets,
        )
        result.balance_sheets.append(balance)

        # Cash Flow
        fcf_margin = _safe_divide(stmt.free_cash_flow, stmt.revenue)
        capex_to_revenue = _safe_divide(
            abs(stmt.capital_expenditure) if stmt.capital_expenditure else None,
            stmt.revenue
        )

        cashflow = CashFlowSummary(
            period=stmt.report_period,
            fiscal_year=stmt.fiscal_year or 0,
            operating_cash_flow=stmt.operating_cash_flow,
            investing_cash_flow=stmt.investing_cash_flow,
            financing_cash_flow=stmt.financing_cash_flow,
            free_cash_flow=stmt.free_cash_flow,
            capex=stmt.capital_expenditure,
            fcf_margin=fcf_margin,
            capex_to_revenue=capex_to_revenue,
        )
        result.cash_flows.append(cashflow)

        # Calculate comprehensive ratios from FDS data
        roe = _safe_divide(stmt.net_income, stmt.total_equity)
        roa = _safe_divide(stmt.net_income, stmt.total_assets)
        asset_turnover = _safe_divide(stmt.revenue, stmt.total_assets)
        equity_multiplier = _safe_divide(stmt.total_assets, stmt.total_equity)

        # ROIC: NOPAT / Invested Capital (CFA standard)
        # NOPAT = EBIT * (1 - effective_tax_rate)
        # Invested Capital = Total Equity + Total Debt - Cash
        invested_capital = None
        roic = None
        if stmt.total_equity is not None and stmt.total_debt is not None:
            cash = stmt.cash_and_equivalents or 0
            invested_capital = stmt.total_equity + stmt.total_debt - cash

        if invested_capital and invested_capital > 0 and stmt.operating_income is not None:
            # Compute effective tax rate: tax_paid / pretax_income
            pretax = (stmt.operating_income - (stmt.interest_expense or 0))
            effective_tax_rate = 1.0 - _safe_divide(stmt.net_income, pretax) if pretax and pretax > 0 else 0.21
            if effective_tax_rate is None or effective_tax_rate < 0 or effective_tax_rate > 0.50:
                effective_tax_rate = 0.21  # fallback to US statutory
            nopat = stmt.operating_income * (1 - effective_tax_rate)
            roic = nopat / invested_capital

        # Interest coverage ratio
        interest_coverage = _safe_divide(stmt.operating_income, stmt.interest_expense) if stmt.interest_expense and stmt.interest_expense > 0 else None

        # DuPont 5-factor decomposition: ROE = tax_burden * interest_burden * op_margin * asset_turnover * equity_multiplier
        pretax_income = (stmt.operating_income - (stmt.interest_expense or 0)) if stmt.operating_income is not None else None
        dupont_tax_burden = _safe_divide(stmt.net_income, pretax_income)          # NI / Pretax
        dupont_interest_burden = _safe_divide(pretax_income, stmt.operating_income) # Pretax / EBIT
        dupont_operating_margin = operating_margin                                  # EBIT / Revenue
        dupont_asset_turnover = asset_turnover                                      # Revenue / Assets
        dupont_equity_multiplier = equity_multiplier                                # Assets / Equity

        # FCF to Net Income (quality of earnings indicator)
        fcf_to_net_income = _safe_divide(stmt.free_cash_flow, stmt.net_income)

        # Per-share metrics
        book_value_per_share = None
        revenue_per_share = None
        fcf_per_share = None
        pe_ratio = None
        pb_ratio = None
        ps_ratio = None
        pfcf_ratio = None
        current_ratio = None
        quick_ratio = None

        if shares_outstanding and shares_outstanding > 0:
            book_value_per_share = _safe_divide(stmt.total_equity, shares_outstanding)
            revenue_per_share = _safe_divide(stmt.revenue, shares_outstanding)
            fcf_per_share = _safe_divide(stmt.free_cash_flow, shares_outstanding)

        # For the most recent period, use yfinance ratios as fallback
        if i == 0:
            # Use yfinance ROE/ROA if FDS data is missing
            if roe is None and yf_ratios.get("roe"):
                roe = yf_ratios["roe"]
            if roa is None and yf_ratios.get("roa"):
                roa = yf_ratios["roa"]
            if gross_margin is None and yf_ratios.get("gross_margin"):
                gross_margin = yf_ratios["gross_margin"]
            if operating_margin is None and yf_ratios.get("operating_margin"):
                operating_margin = yf_ratios["operating_margin"]
            if net_margin is None and yf_ratios.get("profit_margin"):
                net_margin = yf_ratios["profit_margin"]
            if debt_to_equity is None and yf_ratios.get("debt_to_equity"):
                # yfinance returns debt_to_equity as a percentage (e.g., 50.0 for 0.5x)
                debt_to_equity = yf_ratios["debt_to_equity"] / 100 if yf_ratios["debt_to_equity"] and yf_ratios["debt_to_equity"] > 10 else yf_ratios["debt_to_equity"]
            if current_ratio is None and yf_ratios.get("current_ratio"):
                current_ratio = yf_ratios["current_ratio"]
            if quick_ratio is None and yf_ratios.get("quick_ratio"):
                quick_ratio = yf_ratios["quick_ratio"]

            # Use yfinance book value as fallback for book_value_per_share
            if book_value_per_share is None and yf_ratios.get("book_value"):
                book_value_per_share = yf_ratios["book_value"]

            # Valuation ratios - prefer yfinance pre-computed values
            pe_ratio = yf_ratios.get("pe_ratio")
            pb_ratio = yf_ratios.get("pb_ratio")
            ps_ratio = yf_ratios.get("ps_ratio")

            # Calculate P/FCF if not available from yfinance
            if current_price and fcf_per_share and fcf_per_share > 0:
                pfcf_ratio = current_price / fcf_per_share

        ratios = FinancialRatios(
            period=stmt.report_period,
            fiscal_year=stmt.fiscal_year or 0,
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            net_margin=net_margin,
            roe=roe,
            roa=roa,
            roic=roic,
            current_ratio=current_ratio,
            quick_ratio=quick_ratio,
            debt_to_equity=debt_to_equity,
            debt_to_assets=debt_to_assets,
            equity_multiplier=equity_multiplier,
            asset_turnover=asset_turnover,
            interest_coverage=interest_coverage,
            fcf_yield=fcf_margin,
            fcf_to_net_income=fcf_to_net_income,
            book_value_per_share=book_value_per_share,
            revenue_per_share=revenue_per_share,
            fcf_per_share=fcf_per_share,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            ps_ratio=ps_ratio,
            pfcf_ratio=pfcf_ratio,
            dupont_tax_burden=dupont_tax_burden,
            dupont_interest_burden=dupont_interest_burden,
            dupont_operating_margin=dupont_operating_margin,
            dupont_asset_turnover=dupont_asset_turnover,
            dupont_equity_multiplier=dupont_equity_multiplier,
        )
        result.ratios.append(ratios)

    # Calculate YoY growth for income statements
    # Data is ordered most recent first, so we compare each period to the next one (previous year)
    for i in range(len(result.income_statements) - 1):
        current = result.income_statements[i]
        previous = result.income_statements[i + 1]

        # Calculate YoY growth as percentage change
        if previous.revenue and current.revenue:
            current.revenue_yoy = _calc_change_pct(current.revenue, previous.revenue)
        if previous.gross_profit and current.gross_profit:
            current.gross_profit_yoy = _calc_change_pct(current.gross_profit, previous.gross_profit)
        if previous.operating_income and current.operating_income:
            current.operating_income_yoy = _calc_change_pct(current.operating_income, previous.operating_income)
        if previous.net_income and current.net_income:
            current.net_income_yoy = _calc_change_pct(current.net_income, previous.net_income)
        if previous.eps and current.eps:
            current.eps_yoy = _calc_change_pct(current.eps, previous.eps)

    # Generate highlights by analyzing trends and anomalies
    result.highlights = _generate_highlights(result)

    # Generate summary text
    result.summary = _generate_summary(result)

    return result


# =============================================================================
# Highlight Detection Functions
# Each function detects a specific type of financial highlight.
# =============================================================================


def _detect_revenue_highlights(current, previous) -> List[FinancialHighlight]:
    """Detect notable revenue changes."""
    highlights = []
    rev_change = _calc_change_pct(current.revenue, previous.revenue)
    if rev_change is None:
        return highlights

    if rev_change > 20:
        highlights.append(FinancialHighlight(
            title="Strong Revenue Growth",
            description=f"Revenue grew {rev_change:.1f}% YoY to {_format_large_number(current.revenue)}",
            highlight_type=HighlightType.POSITIVE,
            metric_name="revenue",
            current_value=current.revenue,
            previous_value=previous.revenue,
            change_percent=rev_change,
            section="income",
        ))
    elif rev_change < -10:
        highlights.append(FinancialHighlight(
            title="Revenue Decline",
            description=f"Revenue declined {abs(rev_change):.1f}% YoY to {_format_large_number(current.revenue)}",
            highlight_type=HighlightType.NEGATIVE,
            metric_name="revenue",
            current_value=current.revenue,
            previous_value=previous.revenue,
            change_percent=rev_change,
            section="income",
        ))
    return highlights


def _detect_net_income_highlights(current, previous) -> List[FinancialHighlight]:
    """Detect notable net income changes."""
    highlights = []
    ni_change = _calc_change_pct(current.net_income, previous.net_income)
    if ni_change is None:
        return highlights

    if ni_change > 30:
        highlights.append(FinancialHighlight(
            title="Earnings Surge",
            description=f"Net income increased {ni_change:.1f}% YoY to {_format_large_number(current.net_income)}",
            highlight_type=HighlightType.POSITIVE,
            metric_name="net_income",
            current_value=current.net_income,
            previous_value=previous.net_income,
            change_percent=ni_change,
            section="income",
        ))
    elif ni_change < -20:
        highlights.append(FinancialHighlight(
            title="Earnings Decline",
            description=f"Net income dropped {abs(ni_change):.1f}% YoY to {_format_large_number(current.net_income)}",
            highlight_type=HighlightType.NEGATIVE,
            metric_name="net_income",
            current_value=current.net_income,
            previous_value=previous.net_income,
            change_percent=ni_change,
            section="income",
        ))
    return highlights


def _detect_margin_highlights(current, previous) -> List[FinancialHighlight]:
    """Detect operating margin expansion or compression."""
    highlights = []
    if not (current.operating_margin and previous.operating_margin):
        return highlights

    margin_change = (current.operating_margin - previous.operating_margin) * 100
    if margin_change > 3:
        highlights.append(FinancialHighlight(
            title="Margin Expansion",
            description=f"Operating margin improved by {margin_change:.1f}pp to {_format_pct(current.operating_margin)}",
            highlight_type=HighlightType.POSITIVE,
            metric_name="operating_margin",
            current_value=current.operating_margin,
            previous_value=previous.operating_margin,
            change_percent=margin_change,
            section="income",
        ))
    elif margin_change < -3:
        highlights.append(FinancialHighlight(
            title="Margin Compression",
            description=f"Operating margin declined by {abs(margin_change):.1f}pp to {_format_pct(current.operating_margin)}",
            highlight_type=HighlightType.NEGATIVE,
            metric_name="operating_margin",
            current_value=current.operating_margin,
            previous_value=previous.operating_margin,
            change_percent=margin_change,
            section="income",
        ))
    return highlights


def _detect_gross_margin_highlights(current) -> List[FinancialHighlight]:
    """Detect high gross margin indicating competitive advantage."""
    highlights = []
    if current.gross_margin and current.gross_margin > 0.5:
        highlights.append(FinancialHighlight(
            title="High Gross Margin",
            description=f"Gross margin of {_format_pct(current.gross_margin)} suggests pricing power or competitive advantage",
            highlight_type=HighlightType.POSITIVE,
            metric_name="gross_margin",
            current_value=current.gross_margin,
            section="income",
        ))
    return highlights


def _detect_debt_highlights(current_bs) -> List[FinancialHighlight]:
    """Detect debt-related concerns or strengths."""
    highlights = []
    if not (current_bs and current_bs.debt_to_equity):
        return highlights

    if current_bs.debt_to_equity > 2.0:
        highlights.append(FinancialHighlight(
            title="High Leverage",
            description=f"Debt/Equity ratio of {_format_ratio(current_bs.debt_to_equity)} indicates significant leverage risk",
            highlight_type=HighlightType.NEGATIVE,
            metric_name="debt_to_equity",
            current_value=current_bs.debt_to_equity,
            section="balance",
        ))
    elif current_bs.debt_to_equity < 0.3:
        highlights.append(FinancialHighlight(
            title="Low Debt",
            description=f"Conservative Debt/Equity of {_format_ratio(current_bs.debt_to_equity)} provides financial flexibility",
            highlight_type=HighlightType.POSITIVE,
            metric_name="debt_to_equity",
            current_value=current_bs.debt_to_equity,
            section="balance",
        ))
    return highlights


def _detect_cash_position_highlights(current_bs) -> List[FinancialHighlight]:
    """Detect net cash position."""
    highlights = []
    if not (current_bs and current_bs.cash and current_bs.total_debt):
        return highlights

    net_debt = current_bs.total_debt - current_bs.cash
    if net_debt < 0:
        highlights.append(FinancialHighlight(
            title="Net Cash Position",
            description=f"Cash exceeds debt by {_format_large_number(abs(net_debt))} - strong financial position",
            highlight_type=HighlightType.POSITIVE,
            metric_name="net_cash",
            current_value=abs(net_debt),
            section="balance",
        ))
    return highlights


def _detect_cash_flow_highlights(current_cf, current_income) -> List[FinancialHighlight]:
    """Detect cash flow quality and concerns."""
    highlights = []
    if not current_cf:
        return highlights

    if current_cf.free_cash_flow:
        if current_cf.free_cash_flow < 0:
            highlights.append(FinancialHighlight(
                title="Negative Free Cash Flow",
                description=f"FCF of {_format_large_number(current_cf.free_cash_flow)} may require external financing",
                highlight_type=HighlightType.ATTENTION,
                metric_name="fcf",
                current_value=current_cf.free_cash_flow,
                section="cashflow",
            ))
        elif current_cf.fcf_margin and current_cf.fcf_margin > 0.15:
            highlights.append(FinancialHighlight(
                title="Strong Cash Generation",
                description=f"FCF margin of {_format_pct(current_cf.fcf_margin)} indicates excellent cash conversion",
                highlight_type=HighlightType.POSITIVE,
                metric_name="fcf_margin",
                current_value=current_cf.fcf_margin,
                section="cashflow",
            ))

    if current_cf.operating_cash_flow and current_income.net_income:
        ocf_to_ni = current_cf.operating_cash_flow / current_income.net_income if current_income.net_income != 0 else None
        if ocf_to_ni and ocf_to_ni < 0.7:
            highlights.append(FinancialHighlight(
                title="Earnings Quality Concern",
                description=f"Operating cash flow is only {ocf_to_ni:.1f}x net income - investigate accruals",
                highlight_type=HighlightType.ATTENTION,
                metric_name="ocf_to_ni",
                current_value=ocf_to_ni,
                section="cashflow",
            ))
        elif ocf_to_ni and ocf_to_ni > 1.3:
            highlights.append(FinancialHighlight(
                title="Strong Earnings Quality",
                description=f"Operating cash flow exceeds net income by {((ocf_to_ni-1)*100):.0f}% - high-quality earnings",
                highlight_type=HighlightType.POSITIVE,
                metric_name="ocf_to_ni",
                current_value=ocf_to_ni,
                section="cashflow",
            ))
    return highlights


def _detect_roe_highlights(ratios) -> List[FinancialHighlight]:
    """Detect return on equity strengths or weaknesses."""
    highlights = []
    if not ratios:
        return highlights

    current_ratios = ratios[0]
    if not current_ratios.roe:
        return highlights

    if current_ratios.roe > 0.20:
        highlights.append(FinancialHighlight(
            title="High Return on Equity",
            description=f"ROE of {_format_pct(current_ratios.roe)} indicates efficient capital utilization",
            highlight_type=HighlightType.POSITIVE,
            metric_name="roe",
            current_value=current_ratios.roe,
            section="ratios",
        ))
    elif current_ratios.roe < 0.05:
        highlights.append(FinancialHighlight(
            title="Low Return on Equity",
            description=f"ROE of {_format_pct(current_ratios.roe)} suggests poor capital efficiency",
            highlight_type=HighlightType.NEGATIVE,
            metric_name="roe",
            current_value=current_ratios.roe,
            section="ratios",
        ))
    return highlights


def _generate_highlights(data: FinancialStatements) -> List[FinancialHighlight]:
    """
    Generate highlights by analyzing financial data for notable patterns.

    Orchestrates calls to specialized detection functions for each highlight type.
    """
    if len(data.income_statements) < 2:
        return []

    current = data.income_statements[0]
    previous = data.income_statements[1]
    current_cf = data.cash_flows[0] if data.cash_flows else None
    current_bs = data.balance_sheets[0] if data.balance_sheets else None

    highlights = []
    highlights.extend(_detect_revenue_highlights(current, previous))
    highlights.extend(_detect_net_income_highlights(current, previous))
    highlights.extend(_detect_margin_highlights(current, previous))
    highlights.extend(_detect_gross_margin_highlights(current))
    highlights.extend(_detect_debt_highlights(current_bs))
    highlights.extend(_detect_cash_position_highlights(current_bs))
    highlights.extend(_detect_cash_flow_highlights(current_cf, current))
    highlights.extend(_detect_roe_highlights(data.ratios))

    return highlights


def _generate_summary(data: FinancialStatements) -> str:
    """Generate a text summary of the financial analysis."""
    if not data.income_statements:
        return "Financial data not available."

    current = data.income_statements[0]
    current_bs = data.balance_sheets[0] if data.balance_sheets else None
    current_cf = data.cash_flows[0] if data.cash_flows else None

    lines = [f"## Financial Summary for {data.ticker}\n"]

    # Revenue and Profitability
    lines.append("### Profitability")
    lines.append(f"- Revenue: {_format_large_number(current.revenue)}")
    lines.append(f"- Net Income: {_format_large_number(current.net_income)}")
    lines.append(f"- Gross Margin: {_format_pct(current.gross_margin)}")
    lines.append(f"- Operating Margin: {_format_pct(current.operating_margin)}")
    lines.append(f"- Net Margin: {_format_pct(current.net_margin)}")
    lines.append(f"- EPS: ${current.eps:.2f}" if current.eps else "- EPS: N/A")

    # Balance Sheet
    if current_bs:
        lines.append("\n### Balance Sheet")
        lines.append(f"- Total Assets: {_format_large_number(current_bs.total_assets)}")
        lines.append(f"- Total Equity: {_format_large_number(current_bs.total_equity)}")
        lines.append(f"- Cash: {_format_large_number(current_bs.cash)}")
        lines.append(f"- Total Debt: {_format_large_number(current_bs.total_debt)}")
        lines.append(f"- Debt/Equity: {_format_ratio(current_bs.debt_to_equity)}")

    # Cash Flow
    if current_cf:
        lines.append("\n### Cash Flow")
        lines.append(f"- Operating CF: {_format_large_number(current_cf.operating_cash_flow)}")
        lines.append(f"- Free Cash Flow: {_format_large_number(current_cf.free_cash_flow)}")
        lines.append(f"- FCF Margin: {_format_pct(current_cf.fcf_margin)}")

    # Highlights
    if data.highlights:
        lines.append("\n### Key Findings")
        for h in data.highlights[:5]:  # Top 5 highlights
            icon = "✅" if h.highlight_type == HighlightType.POSITIVE else "⚠️" if h.highlight_type == HighlightType.NEGATIVE else "📊"
            lines.append(f"- {icon} **{h.title}**: {h.description}")

    return "\n".join(lines)


def format_financial_statements_for_report(data: FinancialStatements) -> str:
    """
    Format financial statements for inclusion in PDF/markdown reports.

    Returns markdown-formatted financial data with tables and highlights.
    """
    if not data.is_available:
        return f"Financial statements not available for {data.ticker}. {data.error or ''}"

    lines = [f"# Financial Statements: {data.ticker}\n"]

    # Income Statement Table
    if data.income_statements:
        lines.append("## Income Statement (in millions)\n")
        lines.append("| Metric | " + " | ".join(s.period[:7] for s in data.income_statements[:5]) + " |")
        lines.append("|--------|" + "|".join(["-------"] * min(5, len(data.income_statements))) + "|")

        # Revenue row
        lines.append("| Revenue | " + " | ".join(
            f"${s.revenue/1e6:,.0f}" if s.revenue else "N/A"
            for s in data.income_statements[:5]
        ) + " |")

        # Gross Profit row
        lines.append("| Gross Profit | " + " | ".join(
            f"${s.gross_profit/1e6:,.0f}" if s.gross_profit else "N/A"
            for s in data.income_statements[:5]
        ) + " |")

        # Operating Income row
        lines.append("| Operating Income | " + " | ".join(
            f"${s.operating_income/1e6:,.0f}" if s.operating_income else "N/A"
            for s in data.income_statements[:5]
        ) + " |")

        # Net Income row
        lines.append("| Net Income | " + " | ".join(
            f"${s.net_income/1e6:,.0f}" if s.net_income else "N/A"
            for s in data.income_statements[:5]
        ) + " |")

        # EPS row
        lines.append("| EPS | " + " | ".join(
            f"${s.eps:.2f}" if s.eps else "N/A"
            for s in data.income_statements[:5]
        ) + " |")

        # Margins
        lines.append("| Gross Margin | " + " | ".join(
            f"{s.gross_margin*100:.1f}%" if s.gross_margin else "N/A"
            for s in data.income_statements[:5]
        ) + " |")

        lines.append("| Net Margin | " + " | ".join(
            f"{s.net_margin*100:.1f}%" if s.net_margin else "N/A"
            for s in data.income_statements[:5]
        ) + " |")

    # Balance Sheet Table
    if data.balance_sheets:
        lines.append("\n## Balance Sheet (in millions)\n")
        lines.append("| Metric | " + " | ".join(s.period[:7] for s in data.balance_sheets[:5]) + " |")
        lines.append("|--------|" + "|".join(["-------"] * min(5, len(data.balance_sheets))) + "|")

        lines.append("| Total Assets | " + " | ".join(
            f"${s.total_assets/1e6:,.0f}" if s.total_assets else "N/A"
            for s in data.balance_sheets[:5]
        ) + " |")

        lines.append("| Total Equity | " + " | ".join(
            f"${s.total_equity/1e6:,.0f}" if s.total_equity else "N/A"
            for s in data.balance_sheets[:5]
        ) + " |")

        lines.append("| Cash | " + " | ".join(
            f"${s.cash/1e6:,.0f}" if s.cash else "N/A"
            for s in data.balance_sheets[:5]
        ) + " |")

        lines.append("| Total Debt | " + " | ".join(
            f"${s.total_debt/1e6:,.0f}" if s.total_debt else "N/A"
            for s in data.balance_sheets[:5]
        ) + " |")

        lines.append("| Debt/Equity | " + " | ".join(
            f"{s.debt_to_equity:.2f}x" if s.debt_to_equity else "N/A"
            for s in data.balance_sheets[:5]
        ) + " |")

    # Cash Flow Table
    if data.cash_flows:
        lines.append("\n## Cash Flow Statement (in millions)\n")
        lines.append("| Metric | " + " | ".join(s.period[:7] for s in data.cash_flows[:5]) + " |")
        lines.append("|--------|" + "|".join(["-------"] * min(5, len(data.cash_flows))) + "|")

        lines.append("| Operating CF | " + " | ".join(
            f"${s.operating_cash_flow/1e6:,.0f}" if s.operating_cash_flow else "N/A"
            for s in data.cash_flows[:5]
        ) + " |")

        lines.append("| Free Cash Flow | " + " | ".join(
            f"${s.free_cash_flow/1e6:,.0f}" if s.free_cash_flow else "N/A"
            for s in data.cash_flows[:5]
        ) + " |")

        lines.append("| CapEx | " + " | ".join(
            f"${s.capex/1e6:,.0f}" if s.capex else "N/A"
            for s in data.cash_flows[:5]
        ) + " |")

        lines.append("| FCF Margin | " + " | ".join(
            f"{s.fcf_margin*100:.1f}%" if s.fcf_margin else "N/A"
            for s in data.cash_flows[:5]
        ) + " |")

    # Key Ratios Table
    if data.ratios:
        lines.append("\n## Key Financial Ratios\n")
        lines.append("| Metric | " + " | ".join(s.period[:7] for s in data.ratios[:5]) + " |")
        lines.append("|--------|" + "|".join(["-------"] * min(5, len(data.ratios))) + "|")

        # Profitability ratios
        lines.append("| ROE | " + " | ".join(
            f"{s.roe*100:.1f}%" if s.roe else "N/A"
            for s in data.ratios[:5]
        ) + " |")

        lines.append("| ROA | " + " | ".join(
            f"{s.roa*100:.1f}%" if s.roa else "N/A"
            for s in data.ratios[:5]
        ) + " |")

        lines.append("| ROIC | " + " | ".join(
            f"{s.roic*100:.1f}%" if s.roic else "N/A"
            for s in data.ratios[:5]
        ) + " |")

        # Efficiency
        lines.append("| Asset Turnover | " + " | ".join(
            f"{s.asset_turnover:.2f}x" if s.asset_turnover else "N/A"
            for s in data.ratios[:5]
        ) + " |")

        # DuPont Analysis
        lines.append("| Equity Multiplier | " + " | ".join(
            f"{s.equity_multiplier:.2f}x" if s.equity_multiplier else "N/A"
            for s in data.ratios[:5]
        ) + " |")

        # Quality of Earnings
        lines.append("| FCF/Net Income | " + " | ".join(
            f"{s.fcf_to_net_income:.2f}x" if s.fcf_to_net_income else "N/A"
            for s in data.ratios[:5]
        ) + " |")

        # Valuation ratios (only for most recent period)
        current_ratios = data.ratios[0] if data.ratios else None
        if current_ratios:
            lines.append("\n## Current Valuation Ratios\n")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            if current_ratios.pe_ratio:
                lines.append(f"| P/E Ratio | {current_ratios.pe_ratio:.1f}x |")
            if current_ratios.pb_ratio:
                lines.append(f"| P/B Ratio | {current_ratios.pb_ratio:.2f}x |")
            if current_ratios.ps_ratio:
                lines.append(f"| P/S Ratio | {current_ratios.ps_ratio:.2f}x |")
            if current_ratios.pfcf_ratio:
                lines.append(f"| P/FCF Ratio | {current_ratios.pfcf_ratio:.1f}x |")
            if current_ratios.book_value_per_share:
                lines.append(f"| Book Value/Share | ${current_ratios.book_value_per_share:.2f} |")

    # Highlights Section
    if data.highlights:
        lines.append("\n## Key Findings & Highlights\n")

        positive = [h for h in data.highlights if h.highlight_type == HighlightType.POSITIVE]
        negative = [h for h in data.highlights if h.highlight_type == HighlightType.NEGATIVE]
        attention = [h for h in data.highlights if h.highlight_type in (HighlightType.ATTENTION, HighlightType.NEUTRAL)]

        if positive:
            lines.append("### Positive Signals")
            for h in positive:
                lines.append(f"- **{h.title}**: {h.description}")

        if negative:
            lines.append("\n### Areas of Concern")
            for h in negative:
                lines.append(f"- **{h.title}**: {h.description}")

        if attention:
            lines.append("\n### Items to Watch")
            for h in attention:
                lines.append(f"- **{h.title}**: {h.description}")

    return "\n".join(lines)
