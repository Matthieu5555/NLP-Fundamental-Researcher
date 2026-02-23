"""
Custom exceptions for the valuation module.

Allows callers to distinguish between different failure modes:
- Malformed LLM responses (AssumptionParseError)
- Missing or invalid financial data (InsufficientDataError)
- Peer company fetch failures (PeerFetchError)
"""


class ValuationError(Exception):
    """Base exception for all valuation module errors."""


class AssumptionParseError(ValuationError):
    """LLM response could not be parsed into valid assumptions."""


class InsufficientDataError(ValuationError):
    """Required financial data is missing or invalid for the calculation."""


class PeerFetchError(ValuationError):
    """Failed to fetch peer company data for comparable analysis."""
