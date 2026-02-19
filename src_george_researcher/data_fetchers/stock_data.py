"""
Stock data fetching functions using yfinance.
Pure functional interface - no classes, no side effects.

API Info:
- yfinance is a free, unofficial Yahoo Finance API wrapper
- No API key required
- No documented rate limits, but excessive requests may be throttled
- All functions return (result, error) tuples for consistent error handling

Exception Handling:
- yfinance can raise various exceptions (HTTPError, JSONDecodeError, etc.)
- We catch broad Exception intentionally to provide clean error messages
"""
import yfinance as yf
import pandas as pd
from typing import Optional
from dataclasses import dataclass

from .cache import cached


@dataclass(frozen=True)
class StockInfo:
    """Immutable stock information container.

    Supports both yfinance data (original schema) and FinancialDatasets.ai data.
    All fields except symbol and name are optional for flexibility.
    """
    symbol: str
    name: str
    # Core info - all optional to support both data sources
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    business_summary: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    # Price data
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    # Valuation ratios
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None  # yfinance name
    pb_ratio: Optional[float] = None  # FDS name (alias)
    ps_ratio: Optional[float] = None
    price_to_fcf: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    ev_to_revenue: Optional[float] = None
    # Profitability
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    gross_margin: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    roi: Optional[float] = None
    # Financial health
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    # Growth
    revenue: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    free_cash_flow: Optional[float] = None
    # Risk/volatility
    beta: Optional[float] = None
    # 52-week range (supports both naming conventions)
    week_52_high: Optional[float] = None  # yfinance name
    week_52_low: Optional[float] = None  # yfinance name
    high_52w: Optional[float] = None  # FDS name (alias)
    low_52w: Optional[float] = None  # FDS name (alias)
    # Volume
    avg_volume: Optional[float] = None
    # Share info
    shares_outstanding: Optional[float] = None
    float_shares: Optional[float] = None
    # Ownership
    held_by_institutions: Optional[float] = None
    held_by_insiders: Optional[float] = None
    # Short interest
    short_ratio: Optional[float] = None
    short_percent: Optional[float] = None
    # Analyst data
    target_price: Optional[float] = None
    recommendation: Optional[str] = None  # yfinance name
    analyst_rating: Optional[str] = None  # FDS name (alias)
    num_analysts: Optional[int] = None
    # Dividend/earnings
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None


@dataclass(frozen=True)
class TechnicalIndicators:
    """Immutable technical indicators container.

    Supports both yfinance (original) and FDS (extended) data.
    Core fields work with both sources.
    """
    # Core fields (required)
    current_price: float

    # Moving averages (optional)
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None

    # Momentum indicators
    rsi: Optional[float] = None  # yfinance name
    rsi_14: Optional[float] = None  # FDS name (alias)
    macd: Optional[float] = None
    macd_signal: Optional[float] = None  # FDS extended
    macd_histogram: Optional[float] = None  # FDS extended
    atr: Optional[float] = None  # Average True Range

    # Volume
    volume_ratio: Optional[float] = None
    avg_volume_20d: Optional[int] = None  # FDS extended

    # 52-week range
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None

    # Price changes (FDS extended)
    price_change_1d: Optional[float] = None
    price_change_1w: Optional[float] = None
    price_change_1m: Optional[float] = None
    price_change_3m: Optional[float] = None
    price_change_ytd: Optional[float] = None

    # Trend determination
    trend: Optional[str] = None

    # Metadata
    symbol: Optional[str] = None


@cached("yfinance_info", ticker_param="symbol")
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
                # Extended metrics for PDF reports
                exchange=info.get("exchange"),
                eps=info.get("trailingEps"),
                dividend_yield=info.get("dividendYield"),
                shares_outstanding=info.get("sharesOutstanding"),
                price_to_fcf=info.get("priceToFreeCashFlow") or info.get("priceToFreeCashflows"),
                ev_to_ebitda=info.get("enterpriseToEbitda"),
                ev_to_revenue=info.get("enterpriseToRevenue"),
                gross_margin=info.get("grossMargins"),
                roi=info.get("returnOnInvestment"),
            ),
            None,
        )
    except Exception as e:
        return (None, str(e))


@cached("yfinance_history", ticker_param="symbol")
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
    Calculate technical indicators from historical data using yfinance.

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

        # Validate we have sufficient data
        if len(close) == 0:
            return (None, "No price data available")

        current_price = float(close.iloc[-1])

        # Moving averages
        sma_20 = float(close.rolling(window=20).mean().iloc[-1]) if len(close) >= 20 else None
        sma_50 = float(close.rolling(window=50).mean().iloc[-1]) if len(close) >= 50 else None
        sma_200 = float(close.rolling(window=200).mean().iloc[-1]) if len(close) >= 200 else None

        # RSI (14-day)
        rsi = None
        if len(close) >= 14:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = float(100 - (100 / (1 + rs)).iloc[-1])

        # MACD with signal line
        macd = None
        macd_signal = None
        macd_histogram = None
        if len(close) >= 26:
            ema_12 = close.ewm(span=12, adjust=False).mean()
            ema_26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd = float(macd_line.iloc[-1])
            macd_signal = float(signal_line.iloc[-1])
            macd_histogram = float((macd_line - signal_line).iloc[-1])

        # ATR
        atr = None
        if len(close) >= 14:
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = float(tr.rolling(window=14).mean().iloc[-1])

        # Volume metrics
        avg_volume = volume.rolling(window=20).mean().iloc[-1] if len(volume) >= 20 else (volume.mean() if len(volume) > 0 else 0)
        volume_ratio = float(volume.iloc[-1] / avg_volume) if len(volume) > 0 and avg_volume > 0 else 1.0

        # 52-week high/low
        year_data = close.iloc[-252:] if len(close) >= 252 else close
        high_52w = float(year_data.max())
        low_52w = float(year_data.min())

        # Price changes
        price_change_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) >= 2 else None
        price_change_1w = float((close.iloc[-1] / close.iloc[-5] - 1) * 100) if len(close) >= 5 else None
        price_change_1m = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else None
        price_change_3m = float((close.iloc[-1] / close.iloc[-63] - 1) * 100) if len(close) >= 63 else None

        # Trend
        trend = "neutral"
        if sma_50 and sma_200:
            if current_price > sma_50 > sma_200:
                trend = "bullish"
            elif current_price < sma_50 < sma_200:
                trend = "bearish"

        return (
            TechnicalIndicators(
                symbol=symbol,
                current_price=current_price,
                sma_20=sma_20,
                sma_50=sma_50,
                sma_200=sma_200,
                rsi=rsi,
                rsi_14=rsi,  # Alias
                macd=macd,
                macd_signal=macd_signal,
                macd_histogram=macd_histogram,
                atr=atr,
                volume_ratio=volume_ratio,
                avg_volume_20d=int(avg_volume) if avg_volume else None,
                high_52w=high_52w,
                low_52w=low_52w,
                price_change_1d=price_change_1d,
                price_change_1w=price_change_1w,
                price_change_1m=price_change_1m,
                price_change_3m=price_change_3m,
                trend=trend,
            ),
            None,
        )
    except Exception as e:
        return (None, str(e))


def calculate_bollinger_bands(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0
) -> pd.DataFrame:
    """
    Calculate Bollinger Bands.

    Args:
        close: Series of closing prices
        window: Moving average window (default 20)
        num_std: Number of standard deviations (default 2)

    Returns:
        DataFrame with columns: upper, middle, lower
    """
    middle = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)

    return pd.DataFrame({
        'upper': upper,
        'middle': middle,
        'lower': lower
    })


def calculate_macd_full(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> pd.DataFrame:
    """
    Calculate MACD line, signal line, and histogram.

    Args:
        close: Series of closing prices
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line EMA period (default 9)

    Returns:
        DataFrame with columns: macd, signal, histogram
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame({
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    })


def calculate_rsi_series(
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Calculate RSI as a full series.

    Args:
        close: Series of closing prices
        period: RSI period (default 14)

    Returns:
        Series of RSI values
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


@cached("yfinance_chart", ticker_param="symbol")
def fetch_chart_data(
    symbol: str,
    period: str = "1y",
    interval: str = "1d"
) -> tuple[Optional[dict], Optional[str]]:
    """
    Fetch OHLCV data with all indicator timeseries for charting.

    Args:
        symbol: Stock ticker symbol
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Data interval (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)

    Returns:
        (chart_data dict or None, error_message or None)
    """
    history, error = fetch_historical_data(symbol, period, interval)
    if error or history is None:
        return (None, error)

    try:
        close = history['Close']
        high = history['High']
        low = history['Low']
        open_price = history['Open']
        volume = history['Volume']

        # Calculate all indicators as timeseries
        sma_20 = close.rolling(window=20).mean()
        sma_50 = close.rolling(window=50).mean()
        sma_200 = close.rolling(window=200).mean()

        # Bollinger Bands
        bb = calculate_bollinger_bands(close)

        # RSI
        rsi = calculate_rsi_series(close)

        # MACD
        macd_data = calculate_macd_full(close)

        # Convert timestamps to Unix seconds
        def to_unix(ts):
            return int(ts.timestamp())

        # Format OHLCV data
        ohlcv = []
        for idx in history.index:
            ohlcv.append({
                'time': to_unix(idx),
                'open': round(float(open_price[idx]), 2),
                'high': round(float(high[idx]), 2),
                'low': round(float(low[idx]), 2),
                'close': round(float(close[idx]), 2),
                'volume': int(volume[idx])
            })

        # Format indicator series
        def format_line_series(series, name='value'):
            result = []
            for idx, val in series.items():
                if pd.notna(val):
                    result.append({
                        'time': to_unix(idx),
                        name: round(float(val), 4)
                    })
            return result

        def format_bollinger_series(bb_df):
            result = []
            for idx in bb_df.index:
                if pd.notna(bb_df['upper'][idx]):
                    result.append({
                        'time': to_unix(idx),
                        'upper': round(float(bb_df['upper'][idx]), 2),
                        'middle': round(float(bb_df['middle'][idx]), 2),
                        'lower': round(float(bb_df['lower'][idx]), 2)
                    })
            return result

        def format_macd_series(macd_df):
            result = []
            for idx in macd_df.index:
                if pd.notna(macd_df['macd'][idx]):
                    result.append({
                        'time': to_unix(idx),
                        'macd': round(float(macd_df['macd'][idx]), 4),
                        'signal': round(float(macd_df['signal'][idx]), 4),
                        'histogram': round(float(macd_df['histogram'][idx]), 4)
                    })
            return result

        # Calculate price change
        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[0])
        price_change = current_price - prev_price
        price_change_pct = (price_change / prev_price) * 100

        # Get latest indicator values for summary
        latest_sma_20 = float(sma_20.iloc[-1]) if pd.notna(sma_20.iloc[-1]) else None
        latest_sma_50 = float(sma_50.iloc[-1]) if pd.notna(sma_50.iloc[-1]) else None
        latest_sma_200 = float(sma_200.iloc[-1]) if pd.notna(sma_200.iloc[-1]) else None
        latest_rsi = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None
        latest_macd = float(macd_data['macd'].iloc[-1]) if pd.notna(macd_data['macd'].iloc[-1]) else None
        latest_signal = float(macd_data['signal'].iloc[-1]) if pd.notna(macd_data['signal'].iloc[-1]) else None

        # Trend determination
        trend = "neutral"
        if latest_sma_50 and latest_sma_200:
            if current_price > latest_sma_50 > latest_sma_200:
                trend = "bullish"
            elif current_price < latest_sma_50 < latest_sma_200:
                trend = "bearish"

        # Volume ratio
        avg_volume = volume.rolling(window=20).mean().iloc[-1]
        volume_ratio = float(volume.iloc[-1] / avg_volume) if avg_volume > 0 else 1.0

        return ({
            'ticker': symbol,
            'period': period,
            'interval': interval,
            'current_price': round(current_price, 2),
            'price_change': round(price_change, 2),
            'price_change_pct': round(price_change_pct, 2),
            'ohlcv': ohlcv,
            'indicators': {
                'sma_20': format_line_series(sma_20, 'value'),
                'sma_50': format_line_series(sma_50, 'value'),
                'sma_200': format_line_series(sma_200, 'value'),
                'bollinger': format_bollinger_series(bb),
                'rsi': format_line_series(rsi, 'value'),
                'macd': format_macd_series(macd_data)
            },
            'summary': {
                'sma_20': round(latest_sma_20, 2) if latest_sma_20 else None,
                'sma_50': round(latest_sma_50, 2) if latest_sma_50 else None,
                'sma_200': round(latest_sma_200, 2) if latest_sma_200 else None,
                'rsi': round(latest_rsi, 2) if latest_rsi else None,
                'macd': round(latest_macd, 4) if latest_macd else None,
                'macd_signal': round(latest_signal, 4) if latest_signal else None,
                'trend': trend,
                'volume_ratio': round(volume_ratio, 2)
            }
        }, None)

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
  P/S: {fmt_ratio(info.ps_ratio)} | P/FCF: {fmt_ratio(info.price_to_fcf)}
  EV/EBITDA: {fmt_ratio(info.ev_to_ebitda)} | EV/Revenue: {fmt_ratio(info.ev_to_revenue)}

Profitability:
  Gross Margin: {fmt_pct(info.gross_margin)}
  Operating Margin: {fmt_pct(info.operating_margin)}
  Profit Margin: {fmt_pct(info.profit_margin)}
  ROE: {fmt_pct(info.roe)} | ROA: {fmt_pct(info.roa)}

Growth:
  Revenue Growth: {fmt_pct(info.revenue_growth)}
  Earnings Growth: {fmt_pct(info.earnings_growth)}

Financial Health:
  Current Ratio: {fmt_ratio(info.current_ratio)} | Quick Ratio: {fmt_ratio(info.quick_ratio)}
  Debt/Equity: {fmt_ratio(info.debt_to_equity)}
  Beta: {fmt_ratio(info.beta)}

Analyst:
  Target Price: {target}
  Recommendation: {rec}"""
