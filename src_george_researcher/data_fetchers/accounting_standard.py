"""
Accounting Standard Detection and Normalization Flagging.

Detects reporting standard (US GAAP vs IFRS vs other) based on exchange,
and flags key comparability differences.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class AccountingStandard(Enum):
    US_GAAP = "US GAAP"
    IFRS = "IFRS"
    UNKNOWN = "Unknown"


@dataclass
class NormalizationFlag:
    """A single accounting difference flag."""
    item: str                # e.g., "R&D Capitalization"
    description: str         # What the difference is
    impact: str              # "high", "medium", "low"
    direction: str           # How it affects comparisons


@dataclass
class NormalizationResult:
    """Result of accounting standard detection and normalization."""
    standard_detected: AccountingStandard
    exchange: Optional[str] = None
    country: Optional[str] = None
    adjustments_flagged: List[NormalizationFlag] = field(default_factory=list)
    comparability_confidence: str = "high"  # "high", "medium", "low"
    disclosure: str = ""

    def to_dict(self) -> dict:
        return {
            "standard_detected": self.standard_detected.value,
            "exchange": self.exchange,
            "country": self.country,
            "comparability_confidence": self.comparability_confidence,
            "adjustments_flagged": [
                {"item": f.item, "description": f.description,
                 "impact": f.impact, "direction": f.direction}
                for f in self.adjustments_flagged
            ],
            "disclosure": self.disclosure,
        }


# US exchanges (FinancialDatasets.ai primary coverage)
US_EXCHANGES = {
    "NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "NMS", "NCM", "NGM", "NYQ",
    "NAS", "OTC", "PINK", "CBOE",
}

# Known IFRS exchanges
IFRS_EXCHANGES = {
    "LSE", "LON",           # London
    "FRA", "ETR", "XETRA",  # Germany
    "PAR", "EPA",           # France
    "AMS",                   # Netherlands
    "BRU",                   # Belgium
    "MIL", "BIT",           # Italy
    "MAD", "BME",           # Spain
    "STO",                   # Sweden
    "HEL",                   # Finland
    "CPH",                   # Denmark
    "OSL",                   # Norway
    "ASX",                   # Australia
    "HKG", "HKSE",          # Hong Kong
    "JSE",                   # South Africa
    "TSX",                   # Toronto (IFRS adopted)
    "SGX",                   # Singapore
    "NSE", "BSE",           # India
}


def detect_standard(
    exchange: Optional[str] = None,
    country: Optional[str] = None,
) -> AccountingStandard:
    """Detect likely accounting standard from exchange and country."""
    if exchange:
        exchange_upper = exchange.upper()
        if exchange_upper in US_EXCHANGES or any(us in exchange_upper for us in ["NYSE", "NASDAQ"]):
            return AccountingStandard.US_GAAP
        if exchange_upper in IFRS_EXCHANGES:
            return AccountingStandard.IFRS

    if country:
        country_lower = country.lower()
        if country_lower in ("united states", "us", "usa"):
            return AccountingStandard.US_GAAP
        # Most of the world uses IFRS
        ifrs_countries = {"united kingdom", "uk", "germany", "france", "australia",
                         "canada", "india", "hong kong", "singapore", "south africa",
                         "brazil", "mexico", "italy", "spain", "netherlands"}
        if country_lower in ifrs_countries:
            return AccountingStandard.IFRS

    return AccountingStandard.UNKNOWN


def flag_differences(
    standard: AccountingStandard,
) -> List[NormalizationFlag]:
    """Flag key GAAP vs IFRS differences that affect valuation comparability."""
    if standard == AccountingStandard.US_GAAP or standard == AccountingStandard.UNKNOWN:
        return []

    # IFRS vs US GAAP differences
    return [
        NormalizationFlag(
            item="R&D Capitalization",
            description="IFRS allows capitalization of development costs; US GAAP expenses all R&D",
            impact="medium",
            direction="IFRS may report higher assets and lower OpEx for R&D-intensive firms",
        ),
        NormalizationFlag(
            item="Inventory (LIFO)",
            description="IFRS prohibits LIFO; US GAAP allows it",
            impact="low",
            direction="US GAAP LIFO users may have lower inventory values and higher COGS in inflationary periods",
        ),
        NormalizationFlag(
            item="Impairment Reversal",
            description="IFRS allows reversal of impairment losses (except goodwill); US GAAP prohibits",
            impact="low",
            direction="IFRS companies may show recovery gains that US GAAP cannot",
        ),
        NormalizationFlag(
            item="Lease Classification",
            description="Both use right-of-use model post-ASC 842/IFRS 16, but IFRS 16 has single model (no operating vs finance distinction for lessees)",
            impact="low",
            direction="Largely converged; minor differences in sub-lease accounting",
        ),
    ]


def detect_and_flag(
    exchange: Optional[str] = None,
    country: Optional[str] = None,
) -> NormalizationResult:
    """
    Detect accounting standard and flag comparability differences.

    For US companies via FDS, this is straightforward (US GAAP, high confidence).
    For non-US, flags differences rather than attempting mechanical conversion.
    """
    standard = detect_standard(exchange, country)
    flags = flag_differences(standard)

    if standard == AccountingStandard.US_GAAP:
        confidence = "high"
        disclosure = "Financial data reported under US GAAP (SEC filings via FinancialDatasets.ai)."
    elif standard == AccountingStandard.IFRS:
        confidence = "medium"
        disclosure = (
            "Financial data reported under IFRS. Key comparability differences with US GAAP peers are flagged below. "
            "Mechanical conversion has not been attempted due to insufficient footnote-level data. "
            "Analysts should adjust for R&D capitalization when comparing to US GAAP peers."
        )
    else:
        confidence = "low"
        disclosure = (
            "Accounting standard could not be determined. Financial comparisons should be "
            "interpreted with caution. Manual review of reporting standard recommended."
        )

    return NormalizationResult(
        standard_detected=standard,
        exchange=exchange,
        country=country,
        adjustments_flagged=flags,
        comparability_confidence=confidence,
        disclosure=disclosure,
    )
