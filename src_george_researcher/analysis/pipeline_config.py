"""
Pipeline configuration — single source of truth for step counts.

All step numbers for the US and non-US analysis pipelines are defined here.
Import US_TOTAL_STEPS / NON_US_TOTAL_STEPS instead of hardcoding 25/14/27.

USStep enum values ARE the step numbers reported to the frontend progress bar.
Adding a step: append to the end. Removing: delete it (IntEnum auto-renumbers).
"""

from enum import IntEnum


class USStep(IntEnum):
    """US analysis pipeline steps — sequential, no gaps, no duplicates."""
    # Phase A: Data Fetching
    FETCH_COMPANY_FACTS = 1
    FETCH_FINANCIALS = 2
    FETCH_PRICES = 3
    FETCH_INSIDER_TRADES = 4
    FETCH_ANALYST_ESTIMATES = 5
    FETCH_NEWS = 6
    WEB_SEARCH_1 = 7
    WEB_SEARCH_2 = 8

    # Phase B: Analysis Agents
    FUNDAMENTALS = 9
    INSIDER_ANALYSIS = 10
    TECHNICAL_ANALYSIS = 11
    STRATEGIC_ASSESSMENT = 12
    STRATEGY_ANALYSIS = 13
    MOAT_ANALYSIS = 14

    # Phase C: Valuation Models
    DCF_VALUATION = 15
    COMP_TABLE = 16
    EARNINGS_MODEL = 17
    SENSITIVITY = 18
    SCENARIOS = 19
    PRECEDENT_MA = 20
    FOOTBALL_FIELD = 21

    # Phase D: Bull/Bear Debate
    BULL_ROUND_1 = 22
    BEAR_ROUND_1 = 23
    BULL_ROUND_2 = 24
    BEAR_ROUND_2 = 25

    # Phase E: Synthesis
    RECOMMENDATION = 26
    CONVICTION = 27
    INVESTMENT_THESIS = 28


# These are the values used everywhere: job models, queue defaults, SSE streams.
# Import these instead of writing 27 or 14.
US_TOTAL_STEPS: int = max(USStep)       # 27
NON_US_TOTAL_STEPS: int = 14            # Non-US pipeline is simpler, unchanged
