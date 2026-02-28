"""
Non-US Company Analysis Orchestrator.

This module provides the orchestration layer for analyzing non-US companies
using publicly available data sources.

Data Sources Used:
- Yahoo Finance (yfinance): Stock data, basic financials, historical prices
- Gemini Search: Real-time web research and news

Limitations (compared to US analysis):
- No detailed financial statements from FinancialDatasets.ai
- No insider trading activity data
- No analyst consensus estimates
- No SEC filings (10-K, 10-Q, 8-K)
- No segmented revenue data

The analysis pipeline includes:
1. Stock data fetch (yfinance)
2. Technical indicators calculation
3. News sentiment analysis
4. Web research via Gemini Search
5. Fundamental analysis (limited data)
6. Technical analysis
7. Bull/Bear thesis generation
8. Moat analysis
9. Strategy analysis (Strategic Position + Future Outlook)
10. Final recommendation

This module wraps the legacy orchestrator from src_george_researcher/orchestrator.py
for organizational consistency with the US analysis module structure.

Usage:
    from src_george_researcher.analysis.non_us import run_analysis

    result = run_analysis(
        symbol="ASML",
        config=config,
        include_debate=True,
        include_moat=True,
        include_strategy=True,
        progress_callback=my_callback,
    )
"""

# Re-export from legacy orchestrator for backward compatibility
# The actual implementation remains in src_george_researcher/orchestrator.py
# This wrapper provides organizational consistency with analysis/us/ structure

from src_george_researcher.orchestrator import (
    FullAnalysis,
    run_analysis,
    filter_relevant_sources,
)

# Re-export limitations utilities
from src_george_researcher.data_fetchers.limitations import (
    get_limitation_message,
    get_analysis_disclaimer,
    get_available_features,
    get_unavailable_features,
    NON_US_AVAILABLE_FEATURES,
    NON_US_UNAVAILABLE_FEATURES,
)

__all__ = [
    "FullAnalysis",
    "run_analysis",
    "filter_relevant_sources",
    "get_limitation_message",
    "get_analysis_disclaimer",
    "get_available_features",
    "get_unavailable_features",
    "NON_US_AVAILABLE_FEATURES",
    "NON_US_UNAVAILABLE_FEATURES",
]
