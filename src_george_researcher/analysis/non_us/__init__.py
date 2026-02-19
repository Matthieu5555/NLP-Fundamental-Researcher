"""
Non-US Company Analysis Module.

This module provides analysis capabilities for non-US companies using
publicly available data sources (yfinance + Gemini Search).

Limitations compared to US analysis:
- No detailed financial statements (Income, Balance, Cash Flow)
- No insider trading activity
- No analyst consensus estimates
- No SEC filings access
- No segmented revenue data

See data_fetchers/limitations.py for full documentation.

Exports:
    run_analysis         - Main analysis function for non-US companies
    FullAnalysis         - Analysis result dataclass
"""

from src_george_researcher.analysis.non_us.orchestrator import (
    run_analysis,
    FullAnalysis,
)

__all__ = ["run_analysis", "FullAnalysis"]
