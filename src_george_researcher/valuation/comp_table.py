"""
Comparable Company Table builder.

Fetches peer data via yfinance and calculates relative valuation metrics.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional
from statistics import median

from src_george_researcher.data_fetchers.stock_data import StockInfo, fetch_stock_info

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompPeerData:
    """Valuation and operating metrics for a single company."""
    ticker: str
    name: str
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    ps_ratio: Optional[float] = None
    ev_to_revenue: Optional[float] = None
    price_to_fcf: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    revenue_growth: Optional[float] = None
    roe: Optional[float] = None


@dataclass(frozen=True)
class CompTableResult:
    """Complete comparable company analysis result."""
    target: CompPeerData
    peers: List[CompPeerData]
    medians: Dict[str, Optional[float]]
    implied_values: Dict[str, Optional[float]]


# Static peer mapping by industry (top industries, 4-6 peers each)
INDUSTRY_PEERS = {
    "Software—Infrastructure": ["MSFT", "ORCL", "CRM", "NOW", "SNOW", "PANW"],
    "Software—Application": ["CRM", "ADBE", "INTU", "WDAY", "NOW", "HUBS"],
    "Internet Content & Information": ["GOOGL", "META", "SNAP", "PINS", "RDDT"],
    "Internet Retail": ["AMZN", "BABA", "JD", "PDD", "MELI", "SE"],
    "Semiconductors": ["NVDA", "AMD", "INTC", "AVGO", "QCOM", "TXN", "MU"],
    "Semiconductor Equipment & Materials": ["ASML", "AMAT", "LRCX", "KLAC", "TER"],
    "Consumer Electronics": ["AAPL", "SONY", "SSNLF", "LG"],
    "Information Technology Services": ["ACN", "IBM", "CTSH", "INFY", "WIT"],
    "Electronic Components": ["APH", "TEL", "GLW", "JBL", "FLEX"],
    "Drug Manufacturers—General": ["JNJ", "PFE", "MRK", "LLY", "ABBV", "NVS"],
    "Drug Manufacturers—Specialty & Generic": ["TEVA", "MYL", "VTRS", "ENDP"],
    "Biotechnology": ["AMGN", "GILD", "BIIB", "REGN", "VRTX", "MRNA"],
    "Medical Devices": ["MDT", "ABT", "SYK", "BSX", "ISRG", "EW"],
    "Banks—Diversified": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
    "Banks—Regional": ["USB", "PNC", "TFC", "FITB", "MTB", "HBAN"],
    "Insurance—Diversified": ["BRK-B", "AIG", "MET", "PRU", "ALL"],
    "Capital Markets": ["GS", "MS", "SCHW", "BLK", "ICE", "CME"],
    "Aerospace & Defense": ["LMT", "RTX", "NOC", "BA", "GD", "HII"],
    "Auto Manufacturers": ["TSLA", "F", "GM", "TM", "HMC", "STLA"],
    "Beverages—Non-Alcoholic": ["KO", "PEP", "MNST", "CELH"],
    "Beverages—Alcoholic": ["DEO", "BUD", "SAM", "STZ", "TAP"],
    "Packaged Foods": ["NESN", "PG", "KHC", "GIS", "K", "CAG"],
    "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "DRI", "QSR"],
    "Specialty Retail": ["HD", "LOW", "TJX", "ROST", "BBY", "WSM"],
    "Discount Stores": ["WMT", "COST", "TGT", "DG", "DLTR"],
    "Oil & Gas Integrated": ["XOM", "CVX", "COP", "EOG", "SLB", "OXY"],
    "Utilities—Regulated Electric": ["NEE", "DUK", "SO", "D", "AEP", "SRE"],
    "REIT—Diversified": ["PLD", "AMT", "EQIX", "SPG", "O", "WELL"],
    "Communication Services": ["GOOGL", "META", "DIS", "NFLX", "T", "VZ"],
    "Telecom Services": ["T", "VZ", "TMUS", "CMCSA"],
}

# Sector-level fallback
SECTOR_PEERS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "CRM"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY"],
    "Financial Services": ["JPM", "BAC", "GS", "BLK", "MS", "V"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST", "CL"],
    "Communication Services": ["GOOGL", "META", "DIS", "NFLX", "T", "VZ"],
    "Industrials": ["HON", "UNP", "CAT", "DE", "GE", "LMT"],
    "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "OXY"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE"],
    "Real Estate": ["PLD", "AMT", "EQIX", "SPG", "O", "WELL"],
    "Basic Materials": ["LIN", "APD", "SHW", "ECL", "DD", "NEM"],
}


def _market_cap_bucket(mcap: float) -> str:
    """Classify market cap into size bucket."""
    if mcap >= 200e9:
        return "mega"
    elif mcap >= 10e9:
        return "large"
    elif mcap >= 2e9:
        return "mid"
    elif mcap >= 300e6:
        return "small"
    return "micro"


# Adjacent buckets that are comparable
_ADJACENT_BUCKETS = {
    "mega": {"mega", "large"},
    "large": {"mega", "large", "mid"},
    "mid": {"large", "mid", "small"},
    "small": {"mid", "small", "micro"},
    "micro": {"small", "micro"},
}


def select_peers(
    sector: Optional[str],
    industry: Optional[str],
    market_cap: Optional[float],
    target_ticker: str,
    max_peers: int = 5,
    peer_market_caps: Optional[Dict[str, float]] = None,
) -> List[str]:
    """Select peer tickers based on industry, sector, and market cap bucket.

    Size-adjusted: only compares within +/- 1 size bucket (mega/large/mid/small/micro).
    peer_market_caps can be provided to filter by size without extra API calls.
    """
    candidates = []

    # Try industry-specific peers first
    if industry and industry in INDUSTRY_PEERS:
        candidates = [t for t in INDUSTRY_PEERS[industry] if t != target_ticker]

    # Fall back to sector
    if len(candidates) < 3 and sector and sector in SECTOR_PEERS:
        sector_peers = [t for t in SECTOR_PEERS[sector] if t != target_ticker and t not in candidates]
        candidates.extend(sector_peers)

    # Size-filter if we have market cap data for peers
    if market_cap and peer_market_caps:
        target_bucket = _market_cap_bucket(market_cap)
        allowed = _ADJACENT_BUCKETS.get(target_bucket, {target_bucket})
        size_filtered = [
            t for t in candidates
            if t in peer_market_caps and _market_cap_bucket(peer_market_caps[t]) in allowed
        ]
        # Use filtered list if it still has enough peers, otherwise keep all
        if len(size_filtered) >= 3:
            candidates = size_filtered

    return candidates[:max_peers]


def _stock_info_to_peer(info: StockInfo) -> CompPeerData:
    """Convert StockInfo to CompPeerData."""
    return CompPeerData(
        ticker=info.symbol,
        name=info.name,
        market_cap=info.market_cap,
        pe_ratio=info.pe_ratio,
        forward_pe=info.forward_pe,
        ev_to_ebitda=info.ev_to_ebitda,
        ps_ratio=info.ps_ratio,
        ev_to_revenue=info.ev_to_revenue,
        price_to_fcf=info.price_to_fcf,
        gross_margin=info.gross_margin,
        operating_margin=info.operating_margin,
        revenue_growth=info.revenue_growth,
        roe=info.roe,
    )


def fetch_peer_data(tickers: List[str], max_workers: int = 5) -> List[CompPeerData]:
    """Fetch peer data concurrently via yfinance."""
    results = []

    def _fetch_one(ticker: str) -> Optional[CompPeerData]:
        info, error = fetch_stock_info(ticker)
        if info:
            return _stock_info_to_peer(info)
        logger.warning(f"Failed to fetch peer {ticker}: {error}")
        return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    return results


def _safe_median(values: List[Optional[float]]) -> Optional[float]:
    """Calculate median from a list that may contain None values."""
    clean = [v for v in values if v is not None]
    return median(clean) if clean else None


def build_comp_table(
    target_info: StockInfo,
    peers: List[CompPeerData],
) -> CompTableResult:
    """Build comparable company table with medians and implied values."""
    target = _stock_info_to_peer(target_info)

    # Calculate medians across peers
    metric_fields = [
        "pe_ratio", "forward_pe", "ev_to_ebitda", "ps_ratio",
        "ev_to_revenue", "price_to_fcf", "gross_margin",
        "operating_margin", "revenue_growth", "roe",
    ]

    medians = {}
    for field in metric_fields:
        values = [getattr(p, field) for p in peers]
        medians[field] = _safe_median(values)

    # Calculate implied fair values from peer medians
    implied_values = {}
    current_price = target_info.current_price or 0

    # PE-implied value: if target EPS is known
    if target_info.eps and medians.get("pe_ratio"):
        implied_values["pe_implied"] = target_info.eps * medians["pe_ratio"]

    # Forward PE implied
    if target_info.forward_pe and current_price and medians.get("forward_pe"):
        fwd_eps = current_price / target_info.forward_pe if target_info.forward_pe > 0 else None
        if fwd_eps:
            implied_values["forward_pe_implied"] = fwd_eps * medians["forward_pe"]

    # EV/Revenue implied: Equity Value = Implied EV - Net Debt
    if (target_info.revenue and target_info.shares_outstanding and medians.get("ev_to_revenue")):
        implied_ev = target_info.revenue * medians["ev_to_revenue"]
        implied_mcap = implied_ev - (target_info.net_debt or 0)
        if implied_mcap > 0:
            implied_values["ev_revenue_implied"] = implied_mcap / target_info.shares_outstanding

    # EV/EBITDA implied: same EV-to-equity bridge
    if (target_info.ev_to_ebitda and target_info.shares_outstanding
            and medians.get("ev_to_ebitda") and target_info.enterprise_value):
        # Back out EBITDA from target's own EV/EBITDA
        target_ebitda = target_info.enterprise_value / target_info.ev_to_ebitda if target_info.ev_to_ebitda > 0 else None
        if target_ebitda:
            implied_ev_ebitda = target_ebitda * medians["ev_to_ebitda"]
            implied_mcap_ebitda = implied_ev_ebitda - (target_info.net_debt or 0)
            if implied_mcap_ebitda > 0:
                implied_values["ev_ebitda_implied"] = implied_mcap_ebitda / target_info.shares_outstanding

    return CompTableResult(
        target=target,
        peers=peers,
        medians=medians,
        implied_values=implied_values,
    )


def format_comp_table_markdown(result: CompTableResult) -> str:
    """Format CompTableResult as a markdown table."""
    def fmt_pct(v):
        return f"{v * 100:.1f}%" if v is not None else "N/A"

    def fmt_x(v):
        return f"{v:.1f}x" if v is not None else "N/A"

    def fmt_mcap(v):
        if v is None:
            return "N/A"
        if v >= 1e12:
            return f"${v / 1e12:.1f}T"
        return f"${v / 1e9:.0f}B"

    def fmt_price(v):
        return f"${v:.2f}" if v is not None else "N/A"

    lines = [
        "| Company | Mkt Cap | P/E | Fwd P/E | EV/EBITDA | P/S | Gross Margin | Op Margin | Rev Growth |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    # Target row (highlighted)
    t = result.target
    lines.append(
        f"| **{t.ticker}** | {fmt_mcap(t.market_cap)} | {fmt_x(t.pe_ratio)} | "
        f"{fmt_x(t.forward_pe)} | {fmt_x(t.ev_to_ebitda)} | {fmt_x(t.ps_ratio)} | "
        f"{fmt_pct(t.gross_margin)} | {fmt_pct(t.operating_margin)} | {fmt_pct(t.revenue_growth)} |"
    )

    # Peer rows
    for p in result.peers:
        lines.append(
            f"| {p.ticker} | {fmt_mcap(p.market_cap)} | {fmt_x(p.pe_ratio)} | "
            f"{fmt_x(p.forward_pe)} | {fmt_x(p.ev_to_ebitda)} | {fmt_x(p.ps_ratio)} | "
            f"{fmt_pct(p.gross_margin)} | {fmt_pct(p.operating_margin)} | {fmt_pct(p.revenue_growth)} |"
        )

    # Medians row
    m = result.medians
    lines.append(
        f"| **Median** | - | {fmt_x(m.get('pe_ratio'))} | "
        f"{fmt_x(m.get('forward_pe'))} | {fmt_x(m.get('ev_to_ebitda'))} | {fmt_x(m.get('ps_ratio'))} | "
        f"{fmt_pct(m.get('gross_margin'))} | {fmt_pct(m.get('operating_margin'))} | {fmt_pct(m.get('revenue_growth'))} |"
    )

    # Implied values
    if result.implied_values:
        lines.append("\n**Implied Fair Values from Peer Multiples**\n")
        lines.append("| Method | Implied Price |")
        lines.append("|---|---|")
        for method, value in result.implied_values.items():
            label = method.replace("_implied", "").replace("_", " ").title()
            lines.append(f"| {label} | {fmt_price(value)} |")

    return "\n".join(lines)
