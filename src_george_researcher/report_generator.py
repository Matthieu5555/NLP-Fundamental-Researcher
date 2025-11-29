"""
Report generation for George - exports analysis to downloadable formats.
"""
from io import BytesIO
from fpdf import FPDF


def generate_markdown_report(analysis) -> str:
    """
    Generate a comprehensive markdown report from FullAnalysis.

    Args:
        analysis: FullAnalysis object from orchestrator

    Returns:
        Markdown formatted report string
    """
    lines = [
        f"# Research Report: {analysis.symbol}",
        "",
        f"**Generated:** {analysis.timestamp}",
        "",
        "---",
        "",
    ]

    # Stock Overview
    if analysis.stock_info:
        info = analysis.stock_info
        lines.extend([
            "## Company Overview",
            "",
            f"**{info.name}** ({analysis.symbol})",
            "",
            f"- **Sector:** {info.sector or 'N/A'}",
            f"- **Industry:** {info.industry or 'N/A'}",
            f"- **Country:** {info.country or 'N/A'}",
            "",
        ])

        if info.current_price:
            lines.append(f"- **Current Price:** ${info.current_price:.2f}")
        if info.market_cap:
            cap = f"${info.market_cap/1e9:.2f}B" if info.market_cap >= 1e9 else f"${info.market_cap/1e6:.2f}M"
            lines.append(f"- **Market Cap:** {cap}")
        if info.pe_ratio:
            lines.append(f"- **P/E Ratio:** {info.pe_ratio:.1f}")
        if info.recommendation:
            lines.append(f"- **Analyst Consensus:** {info.recommendation.upper()}")

        lines.extend(["", "---", ""])

    # Research Summary
    if analysis.recommendation and analysis.recommendation.success:
        lines.extend([
            "## Research Summary",
            "",
            analysis.recommendation.content,
            "",
            "---",
            "",
        ])

    # SWOT Analysis
    if hasattr(analysis, 'swot_analysis') and analysis.swot_analysis and analysis.swot_analysis.success:
        lines.extend([
            "## SWOT Analysis",
            "",
            analysis.swot_analysis.content,
            "",
            "---",
            "",
        ])

    # Bull/Bear Cases
    if analysis.bull_thesis and analysis.bull_thesis.success:
        lines.extend([
            "## Bull Case",
            "",
            analysis.bull_thesis.content,
            "",
            "---",
            "",
        ])

    if analysis.bear_thesis and analysis.bear_thesis.success:
        lines.extend([
            "## Bear Case",
            "",
            analysis.bear_thesis.content,
            "",
            "---",
            "",
        ])

    # Moat Analysis
    if analysis.moat_analysis and analysis.moat_analysis.success:
        lines.extend([
            "## Economic Moat Analysis",
            "",
            analysis.moat_analysis.content,
            "",
            "---",
            "",
        ])

    # Technicals (combined with fundamentals)
    if analysis.fundamentals_analysis and analysis.fundamentals_analysis.success:
        lines.extend([
            "## Fundamental Analysis",
            "",
            analysis.fundamentals_analysis.content,
            "",
        ])

    if analysis.technical_analysis and analysis.technical_analysis.success:
        lines.extend([
            "## Technical Analysis",
            "",
            analysis.technical_analysis.content,
            "",
            "---",
            "",
        ])

    # News Sentiment
    if analysis.news_sentiment:
        news = analysis.news_sentiment
        lines.extend([
            "## News Sentiment",
            "",
            f"**Overall Sentiment:** {news.overall_label} (score: {news.overall_sentiment:.2f})",
            f"**Breakdown:** {news.bullish_count} bullish, {news.bearish_count} bearish, {news.neutral_count} neutral",
            "",
            "### Recent Headlines",
            "",
        ])
        for article in news.articles[:5]:
            indicator = "[+]" if article.sentiment_score > 0.15 else "[-]" if article.sentiment_score < -0.15 else "[o]"
            lines.append(f"- {indicator} [{article.title}]({article.url})")
            lines.append(f"  - Source: {article.source} | {article.published} | {article.sentiment_label}")

        lines.extend(["", "---", ""])

    # Reddit Sentiment
    if analysis.reddit_sentiment:
        reddit = analysis.reddit_sentiment
        lines.extend([
            "## Reddit Sentiment",
            "",
            f"**Total Mentions:** {reddit.total_mentions}",
            f"**Total Engagement:** {reddit.total_score} upvotes",
            f"**Top Subreddits:** {', '.join(reddit.top_subreddits)}",
            "",
            "### Top Discussions",
            "",
        ])
        for post in reddit.posts[:5]:
            lines.append(f"- [{post.title}]({post.url})")
            lines.append(f"  - r/{post.subreddit} | Score: {post.score} | Comments: {post.num_comments}")

        lines.extend(["", "---", ""])

    # Footer
    lines.extend([
        "## Disclaimer",
        "",
        "This analysis is generated by AI and is for informational purposes only. "
        "It does not constitute financial advice. Always do your own research and consult "
        "with a qualified financial advisor before making investment decisions.",
        "",
        "---",
        "",
        f"*Report generated by George - Research Assistant*",
        f"*Total tokens used: {analysis.total_tokens}*",
    ])

    return "\n".join(lines)


class GeorgePDF(FPDF):
    """Custom PDF class for George reports."""

    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'George Research Report', align='R')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, title, ln=True)
        self.ln(2)

    def chapter_body(self, body):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(40, 40, 40)
        # Handle encoding issues
        safe_body = body.encode('latin-1', 'replace').decode('latin-1')
        self.multi_cell(0, 5, safe_body)
        self.ln(5)


def generate_pdf_report(analysis) -> bytes:
    """
    Generate a PDF report from FullAnalysis.

    Args:
        analysis: FullAnalysis object from orchestrator

    Returns:
        PDF as bytes
    """
    pdf = GeorgePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 15, f'Research Report: {analysis.symbol}', ln=True, align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f'Generated: {analysis.timestamp}', ln=True, align='C')
    pdf.ln(10)

    # Company Overview
    if analysis.stock_info:
        info = analysis.stock_info
        pdf.chapter_title('Company Overview')

        overview_lines = [f"{info.name} ({analysis.symbol})"]
        overview_lines.append(f"Sector: {info.sector or 'N/A'} | Industry: {info.industry or 'N/A'}")

        if info.current_price:
            overview_lines.append(f"Price: ${info.current_price:.2f}")
        if info.market_cap:
            cap = f"${info.market_cap/1e9:.2f}B" if info.market_cap >= 1e9 else f"${info.market_cap/1e6:.2f}M"
            overview_lines.append(f"Market Cap: {cap}")
        if info.pe_ratio:
            overview_lines.append(f"P/E Ratio: {info.pe_ratio:.1f}")
        if info.recommendation:
            overview_lines.append(f"Analyst Consensus: {info.recommendation.upper()}")

        pdf.chapter_body('\n'.join(overview_lines))

    # Research Summary
    if analysis.recommendation and analysis.recommendation.success:
        pdf.chapter_title('Research Summary')
        pdf.chapter_body(analysis.recommendation.content)

    # SWOT Analysis
    if hasattr(analysis, 'swot_analysis') and analysis.swot_analysis and analysis.swot_analysis.success:
        pdf.chapter_title('SWOT Analysis')
        pdf.chapter_body(analysis.swot_analysis.content)

    # Bull Case
    if analysis.bull_thesis and analysis.bull_thesis.success:
        pdf.chapter_title('Bull Case')
        pdf.chapter_body(analysis.bull_thesis.content)

    # Bear Case
    if analysis.bear_thesis and analysis.bear_thesis.success:
        pdf.chapter_title('Bear Case')
        pdf.chapter_body(analysis.bear_thesis.content)

    # Moat Analysis
    if analysis.moat_analysis and analysis.moat_analysis.success:
        pdf.chapter_title('Economic Moat Analysis')
        pdf.chapter_body(analysis.moat_analysis.content)

    # Fundamentals
    if analysis.fundamentals_analysis and analysis.fundamentals_analysis.success:
        pdf.chapter_title('Fundamental Analysis')
        pdf.chapter_body(analysis.fundamentals_analysis.content)

    # Technical Analysis
    if analysis.technical_analysis and analysis.technical_analysis.success:
        pdf.chapter_title('Technical Analysis')
        pdf.chapter_body(analysis.technical_analysis.content)

    # News Sentiment
    if analysis.news_sentiment:
        news = analysis.news_sentiment
        pdf.chapter_title('News Sentiment')
        sentiment_text = f"Overall: {news.overall_label} (score: {news.overall_sentiment:.2f})\n"
        sentiment_text += f"Breakdown: {news.bullish_count} bullish, {news.bearish_count} bearish, {news.neutral_count} neutral\n\n"
        sentiment_text += "Recent Headlines:\n"
        for article in news.articles[:5]:
            indicator = "[+]" if article.sentiment_score > 0.15 else "[-]" if article.sentiment_score < -0.15 else "[o]"
            sentiment_text += f"{indicator} {article.title}\n"
            sentiment_text += f"   {article.source} | {article.published}\n"
        pdf.chapter_body(sentiment_text)

    # Reddit Sentiment
    if analysis.reddit_sentiment:
        reddit = analysis.reddit_sentiment
        pdf.chapter_title('Reddit Sentiment')
        reddit_text = f"Total Mentions: {reddit.total_mentions}\n"
        reddit_text += f"Total Engagement: {reddit.total_score} upvotes\n"
        reddit_text += f"Top Subreddits: {', '.join(reddit.top_subreddits)}\n\n"
        reddit_text += "Top Discussions:\n"
        for post in reddit.posts[:5]:
            reddit_text += f"- {post.title}\n"
            reddit_text += f"  r/{post.subreddit} | Score: {post.score}\n"
        pdf.chapter_body(reddit_text)

    # Disclaimer
    pdf.chapter_title('Disclaimer')
    pdf.chapter_body(
        "This analysis is generated by AI and is for informational purposes only. "
        "It does not constitute financial advice. Always do your own research and consult "
        "with a qualified financial advisor before making investment decisions.\n\n"
        f"Total tokens used: {analysis.total_tokens}"
    )

    # Return as bytes
    return bytes(pdf.output())
