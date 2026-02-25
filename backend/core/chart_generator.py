"""
Chart Generator for PDF Reports using Matplotlib.

Generates static price charts styled with firm's branding colors
for embedding in PDF reports.
"""

import io
import logging
from typing import Optional, Tuple
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Non-GUI backend for server use
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

logger = logging.getLogger(__name__)


def hex_to_rgb_normalized(hex_color: str) -> Tuple[float, float, float]:
    """Convert hex color to normalized RGB tuple (0-1 range for matplotlib)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return (0.78, 0.48, 0.14)  # Default orange
    try:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (r / 255, g / 255, b / 255)
    except ValueError:
        return (0.78, 0.48, 0.14)


def format_price(x: float, pos: int) -> str:
    """Format price for y-axis labels."""
    if x >= 1000:
        return f'${x/1000:.0f}K'
    elif x >= 1:
        return f'${x:.0f}'
    else:
        return f'${x:.2f}'


def generate_price_chart(
    ticker: str,
    primary_color: str = '#C87A23',
    period: str = '15y',
    figsize: Tuple[int, int] = (10, 4)
) -> Optional[bytes]:
    """
    Generate a price history chart as PNG bytes.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        primary_color: Hex color for the line (firm's branding color)
        period: Historical period (default "15y" for 15 years)
        figsize: Figure size in inches (width, height)

    Returns:
        PNG bytes suitable for embedding in PDF, or None on error
    """
    # sys.path configured in backend/main.py
    from src_george_researcher.data_fetchers.stock_data import fetch_historical_data

    # Fetch historical data
    df, error = fetch_historical_data(ticker, period=period, interval='1mo')

    if error or df is None or df.empty:
        logger.error(f"Failed to fetch historical data for {ticker}: {error}")
        return None

    # Convert primary color to matplotlib format
    line_color = hex_to_rgb_normalized(primary_color)

    # Create figure with clean styling
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    ax.set_facecolor('white')

    # Plot the closing prices
    dates = df.index
    prices = df['Close']

    ax.plot(dates, prices, color=line_color, linewidth=2, alpha=0.9)

    # Fill under the line with light color
    ax.fill_between(dates, prices, alpha=0.15, color=line_color)

    # Style the axes
    ax.set_xlabel('')
    ax.set_ylabel('Price', fontsize=10, color='#666666')

    # Format y-axis as currency
    ax.yaxis.set_major_formatter(FuncFormatter(format_price))

    # Format x-axis dates
    ax.xaxis.set_major_locator(mdates.YearLocator(2))  # Every 2 years
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    # Grid styling
    ax.grid(True, alpha=0.3, linestyle='-', color='#E5E5E5')
    ax.set_axisbelow(True)

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#CCCCCC')
    ax.spines['bottom'].set_color('#CCCCCC')

    # Tick styling
    ax.tick_params(axis='both', colors='#666666', labelsize=9)

    # Title
    years = '15' if period == '15y' else period.replace('y', '')
    ax.set_title(
        f'{ticker} - {years}-Year Price History',
        fontsize=12,
        fontweight='bold',
        color='#333333',
        pad=10
    )

    # Add current price annotation
    current_price = prices.iloc[-1]
    current_date = dates[-1]
    ax.annotate(
        f'${current_price:.2f}',
        xy=(current_date, current_price),
        xytext=(10, 10),
        textcoords='offset points',
        fontsize=10,
        fontweight='bold',
        color=line_color,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=line_color, alpha=0.8)
    )

    # Tight layout
    plt.tight_layout()

    # Save to bytes buffer
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)

    buffer.seek(0)
    return buffer.getvalue()


def generate_mini_chart(
    ticker: str,
    primary_color: str = '#C87A23',
    period: str = '1y',
    figsize: Tuple[int, int] = (4, 2)
) -> Optional[bytes]:
    """
    Generate a small sparkline-style chart for inline use.

    Args:
        ticker: Stock ticker symbol
        primary_color: Hex color for the line
        period: Historical period (default "1y")
        figsize: Figure size in inches

    Returns:
        PNG bytes or None on error
    """
    # sys.path configured in backend/main.py
    from src_george_researcher.data_fetchers.stock_data import fetch_historical_data

    df, error = fetch_historical_data(ticker, period=period, interval='1d')

    if error or df is None or df.empty:
        return None

    line_color = hex_to_rgb_normalized(primary_color)

    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    ax.set_facecolor('white')

    prices = df['Close']
    ax.plot(prices.index, prices, color=line_color, linewidth=1.5)
    ax.fill_between(prices.index, prices, alpha=0.1, color=line_color)

    # Minimal styling for sparkline
    ax.axis('off')
    plt.tight_layout(pad=0)

    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight',
                facecolor='white', edgecolor='none', pad_inches=0)
    plt.close(fig)

    buffer.seek(0)
    return buffer.getvalue()


def generate_sidebar_chart(
    ticker: str,
    primary_color: str = '#2563EB',
    period: str = '10y',
    figsize: Tuple[float, float] = (3.5, 1.8)
) -> Optional[bytes]:
    """
    Generate a compact chart for the sidebar of the first page.

    This chart is designed to fit in the right column (~40% width)
    and give an at-a-glance view of the stock's price history.

    Args:
        ticker: Stock ticker symbol
        primary_color: Hex color for the line (firm branding)
        period: Historical period (default "10y")
        figsize: Figure size in inches (width, height)

    Returns:
        PNG bytes suitable for PDF sidebar, or None on error
    """
    # sys.path configured in backend/main.py
    from src_george_researcher.data_fetchers.stock_data import fetch_historical_data

    # Use weekly data for cleaner 10-year chart
    interval = '1wk' if period in ['5y', '10y', '15y', 'max'] else '1d'
    df, error = fetch_historical_data(ticker, period=period, interval=interval)

    if error or df is None or df.empty:
        logger.warning(f"Could not generate sidebar chart for {ticker}: {error}")
        return None

    line_color = hex_to_rgb_normalized(primary_color)

    # Create compact figure
    fig, ax = plt.subplots(figsize=figsize, facecolor='white')
    ax.set_facecolor('white')

    dates = df.index
    prices = df['Close']

    # Plot line with area fill
    ax.plot(dates, prices, color=line_color, linewidth=1.2, alpha=0.9)
    ax.fill_between(dates, prices, alpha=0.12, color=line_color)

    # Minimal axis styling
    ax.set_xlabel('')
    ax.set_ylabel('')

    # Format y-axis
    ax.yaxis.set_major_formatter(FuncFormatter(format_price))
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position('right')

    # Format x-axis - show years only
    if period in ['10y', '15y', 'max']:
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
    else:
        ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    # Light grid
    ax.grid(True, alpha=0.2, linestyle='-', color='#E5E5E5')
    ax.set_axisbelow(True)

    # Remove all spines for cleaner look
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Smaller tick labels
    ax.tick_params(axis='both', colors='#888888', labelsize=7, length=0)

    # Very tight layout
    plt.tight_layout(pad=0.2)

    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=120, bbox_inches='tight',
                facecolor='white', edgecolor='none', pad_inches=0.02)
    plt.close(fig)

    buffer.seek(0)
    return buffer.getvalue()


def generate_technical_chart(
    ticker: str,
    primary_color: str = '#2563EB',
    period: str = '1y',
    figsize: Tuple[float, float] = (10, 8)
) -> Optional[bytes]:
    """
    Generate a full technical analysis chart for the appendix.

    Multi-panel layout:
    - Main panel: Price with Bollinger Bands and SMAs
    - Sub-panel 1: RSI indicator (0-100)
    - Sub-panel 2: MACD with signal line and histogram
    - Sub-panel 3: Volume bars

    Args:
        ticker: Stock ticker symbol
        primary_color: Hex color for primary elements
        period: Historical period (default "1y")
        figsize: Figure size in inches

    Returns:
        PNG bytes for full-page chart, or None on error
    """
    # sys.path configured in backend/main.py
    from src_george_researcher.data_fetchers.stock_data import (
        fetch_historical_data,
        calculate_bollinger_bands,
        calculate_macd_full,
        calculate_rsi_series
    )

    df, error = fetch_historical_data(ticker, period=period, interval='1d')
    if error or df is None or df.empty:
        logger.error(f"Failed to fetch data for technical chart: {error}")
        return None

    line_color = hex_to_rgb_normalized(primary_color)

    # Calculate indicators
    close = df['Close']
    volume = df['Volume']

    sma_50 = close.rolling(window=50).mean()
    bb = calculate_bollinger_bands(close)
    rsi = calculate_rsi_series(close)
    macd_data = calculate_macd_full(close)

    # Create figure with subplots
    fig = plt.figure(figsize=figsize, facecolor='white')

    # Grid spec for different panel heights
    gs = fig.add_gridspec(4, 1, height_ratios=[3, 1, 1, 1], hspace=0.05)

    # Panel 1: Price with Bollinger Bands
    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor('white')

    # Bollinger Bands - fill between
    ax1.fill_between(df.index, bb['upper'], bb['lower'],
                     alpha=0.1, color=line_color, label='Bollinger Bands')
    ax1.plot(df.index, bb['upper'], color=line_color, alpha=0.3, linewidth=0.8)
    ax1.plot(df.index, bb['lower'], color=line_color, alpha=0.3, linewidth=0.8)
    ax1.plot(df.index, bb['middle'], color=line_color, alpha=0.5,
             linewidth=1, linestyle='--', label='SMA 20')

    # Price line
    ax1.plot(df.index, close, color=line_color, linewidth=1.5, label='Close')

    # SMA 50
    ax1.plot(df.index, sma_50, color='#F59E0B', linewidth=1,
             linestyle='--', label='SMA 50', alpha=0.8)

    ax1.set_ylabel('Price', fontsize=9, color='#666666')
    ax1.yaxis.set_major_formatter(FuncFormatter(format_price))
    ax1.legend(loc='upper left', fontsize=7, framealpha=0.9)
    ax1.grid(True, alpha=0.2, color='#E5E5E5')
    ax1.set_xticklabels([])

    # Title
    ax1.set_title(f'{ticker} - Technical Analysis', fontsize=12,
                  fontweight='bold', color='#333333', pad=10)

    # Panel 2: RSI
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.set_facecolor('white')
    ax2.plot(df.index, rsi, color=line_color, linewidth=1)
    ax2.axhline(y=70, color='#EF4444', linestyle='--', linewidth=0.8, alpha=0.7)
    ax2.axhline(y=30, color='#22C55E', linestyle='--', linewidth=0.8, alpha=0.7)
    ax2.axhline(y=50, color='#9CA3AF', linestyle='--', linewidth=0.5, alpha=0.5)
    ax2.fill_between(df.index, rsi, 50, where=(rsi >= 50),
                     alpha=0.2, color=line_color)
    ax2.fill_between(df.index, rsi, 50, where=(rsi < 50),
                     alpha=0.2, color='#EF4444')
    ax2.set_ylabel('RSI', fontsize=9, color='#666666')
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.2, color='#E5E5E5')
    ax2.set_xticklabels([])

    # Panel 3: MACD
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax3.set_facecolor('white')
    ax3.plot(df.index, macd_data['macd'], color=line_color,
             linewidth=1, label='MACD')
    ax3.plot(df.index, macd_data['signal'], color='#F59E0B',
             linewidth=1, label='Signal')

    # Histogram
    colors = ['#22C55E' if v >= 0 else '#EF4444' for v in macd_data['histogram']]
    ax3.bar(df.index, macd_data['histogram'], color=colors, alpha=0.5, width=0.8)

    ax3.axhline(y=0, color='#9CA3AF', linestyle='-', linewidth=0.5)
    ax3.set_ylabel('MACD', fontsize=9, color='#666666')
    ax3.legend(loc='upper left', fontsize=7, framealpha=0.9)
    ax3.grid(True, alpha=0.2, color='#E5E5E5')
    ax3.set_xticklabels([])

    # Panel 4: Volume
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    ax4.set_facecolor('white')

    # Color bars based on price direction
    price_change = close.diff()
    colors = ['#22C55E' if c >= 0 else '#EF4444' for c in price_change]
    ax4.bar(df.index, volume, color=colors, alpha=0.6, width=0.8)

    # Volume moving average
    vol_ma = volume.rolling(window=20).mean()
    ax4.plot(df.index, vol_ma, color=line_color, linewidth=1, alpha=0.7)

    ax4.set_ylabel('Volume', fontsize=9, color='#666666')
    ax4.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x/1e6:.0f}M'))
    ax4.grid(True, alpha=0.2, color='#E5E5E5')

    # Format x-axis on bottom panel
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax4.tick_params(axis='x', rotation=45, labelsize=8)

    # Style all axes
    for ax in [ax1, ax2, ax3, ax4]:
        for spine in ax.spines.values():
            spine.set_color('#DDDDDD')
        ax.tick_params(axis='both', colors='#666666', labelsize=8)

    plt.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)

    buffer.seek(0)
    return buffer.getvalue()
