"""
Comparable Company Agent - LLM narrates the comp table analysis.
"""

import logging
from typing import Optional

from src_george_researcher.analysis_agents import AnalysisResult
from src_george_researcher.data_fetchers.stock_data import StockInfo
from src_george_researcher.llm import call_llm
from src_george_researcher.prompts import COMP_TABLE_SYSTEM
from src_george_researcher.valuation.comp_table import (
    CompTableResult,
    format_comp_table_markdown,
    select_peers,
    fetch_peer_data,
    build_comp_table,
)
from src_george_researcher.valuation.exceptions import PeerFetchError

logger = logging.getLogger(__name__)


def run_comp_analysis(
    api_key: str,
    model: str,
    stock_info: StockInfo,
) -> tuple[Optional[CompTableResult], AnalysisResult]:
    """
    Run comparable company analysis: fetch peers, build table, LLM narrates.

    Returns:
        (CompTableResult or None, AnalysisResult with narrative)
    """
    # Select peers
    peer_tickers = select_peers(
        sector=stock_info.sector,
        industry=stock_info.industry,
        market_cap=stock_info.market_cap,
        target_ticker=stock_info.symbol,
    )

    if not peer_tickers:
        return None, AnalysisResult(
            section="Comparable Companies",
            content="Comparable company analysis could not be performed: no suitable peers identified for this industry.",
            tokens_used=0,
            success=False,
            error="No peers found",
        )

    # Fetch peer data
    logger.info(f"Fetching peer data for {len(peer_tickers)} companies: {peer_tickers}")
    peers = fetch_peer_data(peer_tickers)

    if not peers:
        raise PeerFetchError(f"Failed to fetch data for any peers: {peer_tickers}")

    # Build comp table
    comp_result = build_comp_table(stock_info, peers)
    table_markdown = format_comp_table_markdown(comp_result)

    # LLM narrates
    user_prompt = f"""Here is the comparable company table for {stock_info.name} ({stock_info.symbol}):

{table_markdown}

Current price: ${f"{stock_info.current_price:.2f}" if stock_info.current_price else "N/A"}

Provide your comparable company analysis."""

    response = call_llm(
        api_key=api_key,
        model=model,
        system_prompt=COMP_TABLE_SYSTEM,
        user_prompt=user_prompt,
    )

    # Combine table + narrative
    content = f"{table_markdown}\n\n{response.content}" if response.success else table_markdown

    analysis_result = AnalysisResult(
        section="Comparable Companies",
        content=content,
        tokens_used=response.tokens_used,
        success=True,
        cost_usd=response.cost_usd,
    )

    return comp_result, analysis_result
