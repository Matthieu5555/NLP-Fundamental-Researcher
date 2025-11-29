"""
Streamlit UI for George - Your Financial Researcher.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports when run directly by Streamlit
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from datetime import datetime

from src_george_researcher.config import load_config, validate_config
from src_george_researcher.llm import test_connection
from src_george_researcher.data_fetchers.stock_data import (
    fetch_stock_info,
    fetch_historical_data,
    calculate_technical_indicators,
    format_stock_info,
)
from src_george_researcher.data_fetchers.news import fetch_combined_news
from src_george_researcher.data_fetchers.reddit import fetch_reddit_sentiment
from src_george_researcher.orchestrator import run_analysis, run_quick_analysis, format_analysis_report
from src_george_researcher.report_generator import generate_markdown_report, generate_pdf_report


st.set_page_config(
    page_title="Research",
    page_icon="G",
    layout="wide",
)


def init_session_state():
    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None
    if "current_symbol" not in st.session_state:
        st.session_state.current_symbol = None


def render_sidebar():
    st.sidebar.title("Configuration")

    config = load_config()
    is_valid, errors = validate_config(config)

    if is_valid:
        st.sidebar.success("API configured")
        st.sidebar.text(f"Model: {config.openrouter_model}")
    else:
        st.sidebar.error("API not configured")
        for e in errors:
            st.sidebar.text(e)

    st.sidebar.divider()

    st.sidebar.subheader("Analysis Options")

    include_debate = st.sidebar.checkbox("Include Bull/Bear Debate", value=True)
    include_moat = st.sidebar.checkbox("Include Moat Analysis", value=True)
    include_swot = st.sidebar.checkbox("Include SWOT Analysis", value=True)
    debate_rounds = st.sidebar.slider("Debate Rounds", 1, 3, 1)

    return {
        "config": config,
        "is_valid": is_valid,
        "include_debate": include_debate,
        "include_moat": include_moat,
        "include_swot": include_swot,
        "debate_rounds": debate_rounds,
    }


def render_stock_overview(symbol: str):
    """Render basic stock info (no API cost)."""
    info, error = fetch_stock_info(symbol)

    if error:
        st.error(f"Error fetching {symbol}: {error}")
        return None

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        price = f"${info.current_price:.2f}" if info.current_price else "N/A"
        st.metric("Price", price)

    with col2:
        if info.market_cap:
            if info.market_cap >= 1e12:
                cap = f"${info.market_cap/1e12:.2f}T"
            else:
                cap = f"${info.market_cap/1e9:.2f}B"
        else:
            cap = "N/A"
        st.metric("Market Cap", cap)

    with col3:
        pe = f"{info.pe_ratio:.1f}" if info.pe_ratio else "N/A"
        st.metric("P/E Ratio", pe)

    with col4:
        rec = info.recommendation.title() if info.recommendation else "N/A"
        st.metric("Analyst Consensus (YF)", rec)

    with st.expander("Company Details"):
        st.text(f"Sector: {info.sector}")
        st.text(f"Industry: {info.industry}")
        st.text(f"Country: {info.country}")
        if info.business_summary:
            st.write(info.business_summary[:500] + "...")

    return info


def render_price_chart(symbol: str):
    """Render price chart using Streamlit's native charting."""
    history, error = fetch_historical_data(symbol, period="1y")

    if error or history is None:
        st.warning("Price history not available")
        return

    st.subheader("Price History (1 Year)")
    st.line_chart(history["Close"])


def render_technicals(symbol: str):
    """Render technical indicators."""
    technicals, error = calculate_technical_indicators(symbol)

    if error or technicals is None:
        st.warning("Technical data not available")
        return

    st.subheader("Technical Indicators")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Trend", technicals.trend.title())
        rsi = f"{technicals.rsi:.1f}" if technicals.rsi else "N/A"
        st.metric("RSI (14)", rsi)

    with col2:
        sma50 = f"${technicals.sma_50:.2f}" if technicals.sma_50 else "N/A"
        st.metric("SMA 50", sma50)
        sma200 = f"${technicals.sma_200:.2f}" if technicals.sma_200 else "N/A"
        st.metric("SMA 200", sma200)

    with col3:
        macd = f"{technicals.macd:.2f}" if technicals.macd else "N/A"
        st.metric("MACD", macd)
        vol = f"{technicals.volume_ratio:.2f}x" if technicals.volume_ratio else "N/A"
        st.metric("Volume Ratio", vol)


def render_news_sentiment(symbol: str, alpha_vantage_key: str = "", eodhd_key: str = "", company_name: str = ""):
    """Render news sentiment from EODHD/Alpha Vantage."""
    if not alpha_vantage_key and not eodhd_key:
        st.info("Configure news API keys for sentiment")
        return

    news, error = fetch_combined_news(symbol, alpha_vantage_key, eodhd_key, limit=10, company_name=company_name)

    if error:
        st.warning(f"News sentiment unavailable: {error}")
        return

    if not news:
        st.info("No recent news found")
        return

    st.subheader("News Sentiment")

    # Sentiment summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Sentiment", news.overall_label)
    with col2:
        st.metric("Positive", news.bullish_count)
    with col3:
        st.metric("Negative", news.bearish_count)
    with col4:
        st.metric("Neutral", news.neutral_count)

    # Recent articles
    with st.expander(f"Recent News ({len(news.articles)} articles)", expanded=False):
        for article in news.articles:
            sentiment_indicator = "[+]" if article.sentiment_score > 0.15 else "[-]" if article.sentiment_score < -0.15 else "[o]"
            st.markdown(f"{sentiment_indicator} **[{article.title}]({article.url})**")
            st.caption(f"{article.source} | {article.published} | {article.sentiment_label} ({article.sentiment_score:.2f})")
            if article.summary:
                st.text(article.summary[:200] + "..." if len(article.summary) > 200 else article.summary)
            st.markdown("---")


def render_reddit_sentiment(symbol: str, company_name: str = ""):
    """Render Reddit sentiment in Quick View."""
    reddit, error = fetch_reddit_sentiment(symbol, limit=10, company_name=company_name)

    if error:
        st.info(f"Reddit: {error}")
        return

    if not reddit:
        st.info("No Reddit discussions found")
        return

    st.subheader("Reddit Sentiment")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Mentions", reddit.total_mentions)
    with col2:
        st.metric("Total Score", reddit.total_score)
    with col3:
        st.metric("Top Subreddits", ", ".join(reddit.top_subreddits[:2]) if reddit.top_subreddits else "None")

    with st.expander(f"Reddit Discussions ({len(reddit.posts)} posts)", expanded=False):
        for post in reddit.posts[:7]:
            engagement = "[HOT]" if post.score > 100 else "[+]" if post.score > 10 else "[o]"
            st.markdown(f"{engagement} **[{post.title}]({post.url})**")
            st.caption(f"r/{post.subreddit} | Score: {post.score} | Comments: {post.num_comments} | {post.created_utc}")
            if post.selftext:
                st.text(post.selftext[:150] + "..." if len(post.selftext) > 150 else post.selftext)
            st.markdown("---")


def render_sources_tab(result):
    """Render all sources used in the analysis with actual links."""
    st.subheader("Sources Referenced")

    # Yahoo Finance (always used)
    st.markdown("### Financial Data")
    symbol = result.symbol
    st.markdown(f"""
- [Yahoo Finance - {symbol} Quote](https://finance.yahoo.com/quote/{symbol})
- [Yahoo Finance - {symbol} Profile](https://finance.yahoo.com/quote/{symbol}/profile)
- [Yahoo Finance - {symbol} Financials](https://finance.yahoo.com/quote/{symbol}/financials)
- [Yahoo Finance - {symbol} Analysis](https://finance.yahoo.com/quote/{symbol}/analysis)
""")

    # SEC Filing
    if hasattr(result, 'sec_filing') and result.sec_filing and result.sec_filing.filing_url:
        st.markdown("### SEC Filings")
        st.markdown(f"- [10-K Filing ({result.sec_filing.filing_date})]({result.sec_filing.filing_url})")

    # News Articles
    if result.news_sentiment and result.news_sentiment.articles:
        st.markdown("### News Articles")
        for article in result.news_sentiment.articles:
            sentiment_badge = "[+]" if article.sentiment_score > 0.15 else "[-]" if article.sentiment_score < -0.15 else "[o]"
            st.markdown(f"- {sentiment_badge} [{article.title}]({article.url}) - *{article.source}, {article.published}*")

    # Reddit Posts
    if hasattr(result, 'reddit_sentiment') and result.reddit_sentiment and result.reddit_sentiment.posts:
        st.markdown("### Reddit Discussions")
        for post in result.reddit_sentiment.posts[:10]:
            st.markdown(f"- [{post.title}]({post.url}) - *r/{post.subreddit}, {post.created_utc}*")

    # Web Search Results
    if hasattr(result, 'web_search') and result.web_search and result.web_search.results:
        st.markdown("### Web Search Results")
        for item in result.web_search.results:
            st.markdown(f"- [{item.title}]({item.url})")


def render_analysis_results(result, include_swot: bool = True):
    """Render full analysis results."""
    if not result.success and not result.fundamentals_analysis:
        st.error("Analysis failed")
        for e in result.errors:
            st.error(e)
        return

    # Inline success message with download buttons - aligned
    col1, col2, col3 = st.columns([4, 1, 1], vertical_alignment="center")
    with col1:
        st.success(f"Analysis complete - {result.total_tokens} tokens used")
    with col2:
        md_report = generate_markdown_report(result)
        st.download_button(
            label="Download MD",
            data=md_report,
            file_name=f"george_{result.symbol}_{result.timestamp[:10]}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col3:
        pdf_report = generate_pdf_report(result)
        st.download_button(
            label="Download PDF",
            data=pdf_report,
            file_name=f"george_{result.symbol}_{result.timestamp[:10]}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()

    # Tabs for detailed sections - new order
    tab_names = ["Research Summary"]
    if include_swot:
        tab_names.append("SWOT")
    tab_names.extend([
        "Bull Case",
        "Bear Case",
        "Moat Analysis",
        "SEC 10-K",
        "Technicals",
        "All Sources",
    ])

    tabs = st.tabs(tab_names)
    current_tab = 0

    # Research Summary
    with tabs[current_tab]:
        if result.recommendation and result.recommendation.success:
            st.markdown(result.recommendation.content)
        else:
            st.info("Not available")
    current_tab += 1

    # SWOT (if enabled)
    if include_swot:
        with tabs[current_tab]:
            if hasattr(result, 'swot_analysis') and result.swot_analysis and result.swot_analysis.success:
                st.markdown(result.swot_analysis.content)
            else:
                st.info("SWOT analysis not available - enable it in Analysis Options")
        current_tab += 1

    # Bull Case
    with tabs[current_tab]:
        if result.bull_thesis and result.bull_thesis.success:
            st.markdown(result.bull_thesis.content)
        else:
            st.info("Not available")
    current_tab += 1

    # Bear Case
    with tabs[current_tab]:
        if result.bear_thesis and result.bear_thesis.success:
            st.markdown(result.bear_thesis.content)
        else:
            st.info("Not available")
    current_tab += 1

    # Moat Analysis
    with tabs[current_tab]:
        if result.moat_analysis and result.moat_analysis.success:
            st.markdown(result.moat_analysis.content)
        else:
            st.info("Not available")
    current_tab += 1

    # SEC 10-K tab
    with tabs[current_tab]:
        if hasattr(result, 'sec_filing') and result.sec_filing:
            filing = result.sec_filing
            st.markdown(f"**Filing Date:** {filing.filing_date}")
            st.markdown(f"**Fiscal Year:** {filing.fiscal_year}")
            if filing.filing_url:
                st.markdown(f"[View Full Filing on SEC EDGAR]({filing.filing_url})")

            st.subheader("Filing Sections")
            sections = {}
            for chunk in filing.chunks:
                if chunk.section not in sections:
                    sections[chunk.section] = []
                sections[chunk.section].append(chunk.text)

            for section_name, texts in sections.items():
                with st.expander(f"{section_name} ({len(texts)} excerpts)"):
                    for i, text in enumerate(texts[:3]):
                        st.text(text[:500] + "..." if len(text) > 500 else text)
                        if i < 2:
                            st.markdown("---")
        else:
            st.info("SEC 10-K filing not available for this symbol")
    current_tab += 1

    # Technicals (combines Fundamentals + Technicals)
    with tabs[current_tab]:
        if result.fundamentals_analysis and result.fundamentals_analysis.success:
            st.subheader("Fundamentals")
            st.markdown(result.fundamentals_analysis.content)
            st.divider()

        if result.technical_analysis and result.technical_analysis.success:
            st.subheader("Technical Indicators")
            st.markdown(result.technical_analysis.content)
        elif not result.fundamentals_analysis or not result.fundamentals_analysis.success:
            st.info("Not available")
    current_tab += 1

    # All Sources tab - shows actual articles/links
    with tabs[current_tab]:
        render_sources_tab(result)

    if result.errors:
        with st.expander("Warnings"):
            for e in result.errors:
                st.warning(e)


def main():
    init_session_state()

    st.title("George - Your Financial Analyst")

    settings = render_sidebar()

    # Main input
    col1, col2 = st.columns([3, 1])

    with col1:
        symbol = st.text_input(
            "Yahoo Finance Stock Symbol",
            value="AAPL",
            placeholder="Enter ticker (e.g., AAPL, MSFT, GOOGL)"
        ).upper().strip()

    with col2:
        mode = st.selectbox("Mode", ["Quick View", "Full Analysis"])

    if not symbol:
        st.info("Enter a stock symbol to begin")
        return

    st.divider()

    # Quick View - no API cost (except Alpha Vantage news)
    if mode == "Quick View":
        info = render_stock_overview(symbol)
        if info:
            col1, col2 = st.columns(2)
            with col1:
                render_price_chart(symbol)
            with col2:
                render_technicals(symbol)

            st.divider()
            render_news_sentiment(
                symbol,
                alpha_vantage_key=settings["config"].alpha_vantage_key or "",
                eodhd_key=settings["config"].eodhd_key or "",
                company_name=info.name or "",
            )

            st.divider()
            render_reddit_sentiment(symbol, company_name=info.name or "")

    # Full Analysis - uses API
    else:
        if not settings["is_valid"]:
            st.error("Configure API key to run analysis")
            st.info("Set OPENROUTER_API_KEY in .env file")
            return

        # Show basic info first
        render_stock_overview(symbol)

        st.divider()

        # Analysis button
        run_btn = st.button("Run Analysis", type="primary", use_container_width=True)

        if run_btn:
            with st.spinner(f"Analyzing {symbol}... This may take 30-60 seconds"):
                result = run_analysis(
                    symbol=symbol,
                    config=settings["config"],
                    include_debate=settings["include_debate"],
                    include_moat=settings["include_moat"],
                    include_swot=settings.get("include_swot", True),
                    debate_rounds=settings["debate_rounds"],
                )
                st.session_state.analysis_result = result
                st.session_state.current_symbol = symbol

        # Show results if available
        if (st.session_state.analysis_result and
            st.session_state.current_symbol == symbol):
            render_analysis_results(
                st.session_state.analysis_result,
                include_swot=settings.get("include_swot", True)
            )


if __name__ == "__main__":
    main()
