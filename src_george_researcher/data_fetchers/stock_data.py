"""
Stock data fetching functions using yfinance.
Pure functional interface - no classes, no side effects.
"""
import yfinance as yf
import pandas as pd
from typing import Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class StockInfo:
    """Immutable stock information container."""
    symbol: str
    name: str
    sector: str
    industry: str
    country: str
    business_summary: str
    current_price: Optional[float]
    market_cap: Optional[float]
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    peg_ratio: Optional[float]
    price_to_book: Optional[float]
    profit_margin: Optional[float]
    operating_margin: Optional[float]
    roe: Optional[float]
    roa: Optional[float]
    revenue_growth: Optional[float]
    earnings_growth: Optional[float]
    current_ratio: Optional[float]
    debt_to_equity: Optional[float]
    beta: Optional[float]
    week_52_high: Optional[float]
    week_52_low: Optional[float]
    target_price: Optional[float]
    recommendation: Optional[str]


@dataclass(frozen=True)
class TechnicalIndicators:
    """Immutable technical indicators container."""
    current_price: float
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    rsi: Optional[float]
    macd: Optional[float]
    atr: Optional[float]
    volume_ratio: Optional[float]
    trend: str


def fetch_stock_info(symbol: str) -> tuple[Optional[StockInfo], Optional[str]]:
    """
    Fetch stock information from yfinance.

    Returns:
        (StockInfo or None, error_message or None)
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        if not info or info.get("regularMarketPrice") is None:
            return (None, f"No data found for {symbol}")

        return (
            StockInfo(
                symbol=symbol,
                name=info.get("longName", info.get("shortName", symbol)),
                sector=info.get("sector", "N/A"),
                industry=info.get("industry", "N/A"),
                country=info.get("country", "N/A"),
                business_summary=info.get("longBusinessSummary", ""),
                current_price=info.get("currentPrice", info.get("regularMarketPrice")),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                forward_pe=info.get("forwardPE"),
                peg_ratio=info.get("pegRatio"),
                price_to_book=info.get("priceToBook"),
                profit_margin=info.get("profitMargins"),
                operating_margin=info.get("operatingMargins"),
                roe=info.get("returnOnEquity"),
                roa=info.get("returnOnAssets"),
                revenue_growth=info.get("revenueGrowth"),
                earnings_growth=info.get("earningsGrowth"),
                current_ratio=info.get("currentRatio"),
                debt_to_equity=info.get("debtToEquity"),
                beta=info.get("beta"),
                week_52_high=info.get("fiftyTwoWeekHigh"),
                week_52_low=info.get("fiftyTwoWeekLow"),
                target_price=info.get("targetMeanPrice"),
                recommendation=info.get("recommendationKey"),
            ),
            None,
        )
    except Exception as e:
        return (None, str(e))


def fetch_historical_data(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Fetch historical price data.

    Returns:
        (DataFrame or None, error_message or None)
    """
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period=period, interval=interval)

        if history.empty:
            return (None, f"No historical data for {symbol}")

        return (history, None)
    except Exception as e:
        return (None, str(e))


def calculate_technical_indicators(
    symbol: str,
    period: str = "1y",
) -> tuple[Optional[TechnicalIndicators], Optional[str]]:
    """
    Calculate technical indicators from historical data.

    Returns:
        (TechnicalIndicators or None, error_message or None)
    """
    history_result = fetch_historical_data(symbol, period)
    history, error = history_result

    if error or history is None:
        return (None, error)

    try:
        close = history["Close"]
        high = history["High"]
        low = history["Low"]
        volume = history["Volume"]

        current_price = close.iloc[-1]

        # Moving averages
        sma_20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
        sma_50 = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else None
        sma_200 = close.rolling(window=200).mean().iloc[-1] if len(close) >= 200 else None

        # RSI
        rsi = None
        if len(close) >= 14:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = float(100 - (100 / (1 + rs)).iloc[-1])

        # MACD
        macd = None
        if len(close) >= 26:
            ema_12 = close.ewm(span=12, adjust=False).mean()
            ema_26 = close.ewm(span=26, adjust=False).mean()
            macd = float((ema_12 - ema_26).iloc[-1])

        # ATR
        atr = None
        if len(close) >= 14:
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = float(tr.rolling(window=14).mean().iloc[-1])

        # Volume ratio
        avg_volume = volume.rolling(window=20).mean().iloc[-1]
        volume_ratio = float(volume.iloc[-1] / avg_volume) if avg_volume > 0 else 1.0

        # Trend
        trend = "neutral"
        if sma_50 and sma_200:
            if current_price > sma_50 > sma_200:
                trend = "bullish"
            elif current_price < sma_50 < sma_200:
                trend = "bearish"

        return (
            TechnicalIndicators(
                current_price=float(current_price),
                sma_20=float(sma_20) if sma_20 else None,
                sma_50=float(sma_50) if sma_50 else None,
                sma_200=float(sma_200) if sma_200 else None,
                rsi=rsi,
                macd=macd,
                atr=atr,
                volume_ratio=volume_ratio,
                trend=trend,
            ),
            None,
        )
    except Exception as e:
        return (None, str(e))


def format_stock_info(info: StockInfo) -> str:
    """Format stock info as a readable string."""
    def fmt_pct(v: Optional[float]) -> str:
        return f"{v * 100:.1f}%" if v is not None else "N/A"

    def fmt_num(v: Optional[float]) -> str:
        if v is None:
            return "N/A"
        if v >= 1e12:
            return f"${v/1e12:.2f}T"
        if v >= 1e9:
            return f"${v/1e9:.2f}B"
        if v >= 1e6:
            return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"

    def fmt_ratio(v: Optional[float]) -> str:
        return f"{v:.2f}" if v is not None else "N/A"

    def fmt_price(v: Optional[float]) -> str:
        return f"${v:.2f}" if v is not None else "N/A"

    price = fmt_price(info.current_price)
    low_52 = fmt_price(info.week_52_low)
    high_52 = fmt_price(info.week_52_high)
    target = fmt_price(info.target_price)
    rec = info.recommendation.upper() if info.recommendation else "N/A"

    return f"""Company: {info.name} ({info.symbol})
Sector: {info.sector} | Industry: {info.industry}
Country: {info.country}

Price: {price}
Market Cap: {fmt_num(info.market_cap)}
52W Range: {low_52} - {high_52}

Valuation:
  P/E: {fmt_ratio(info.pe_ratio)} | Forward P/E: {fmt_ratio(info.forward_pe)}
  PEG: {fmt_ratio(info.peg_ratio)} | P/B: {fmt_ratio(info.price_to_book)}

Profitability:
  Profit Margin: {fmt_pct(info.profit_margin)}
  Operating Margin: {fmt_pct(info.operating_margin)}
  ROE: {fmt_pct(info.roe)} | ROA: {fmt_pct(info.roa)}

Growth:
  Revenue Growth: {fmt_pct(info.revenue_growth)}
  Earnings Growth: {fmt_pct(info.earnings_growth)}

Financial Health:
  Current Ratio: {fmt_ratio(info.current_ratio)}
  Debt/Equity: {fmt_ratio(info.debt_to_equity)}
  Beta: {fmt_ratio(info.beta)}

Analyst:
  Target Price: {target}
  Recommendation: {rec}"""
