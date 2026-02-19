"""
Analysis package for strategic company evaluation.

Contains:
- us/     - US company analysis with FinancialDatasets.ai integration
- non_us/ - Non-US company analysis with yfinance + Gemini Search
- shared/ - Shared utilities (cost tracking, etc.)

US companies get full data access via FinancialDatasets.ai.
Non-US companies use yfinance + Gemini Search with limited data.
See data_fetchers/limitations.py for data availability details.
"""

from .us import (
    FinancialStatements,
    FinancialHighlight,
    analyze_financial_statements,
    format_financial_statements_for_report,
)

from .non_us import (
    run_analysis as run_non_us_analysis,
    FullAnalysis as NonUSFullAnalysis,
)

__all__ = [
    # US exports
    "FinancialStatements",
    "FinancialHighlight",
    "analyze_financial_statements",
    "format_financial_statements_for_report",
    # Non-US exports
    "run_non_us_analysis",
    "NonUSFullAnalysis",
]
