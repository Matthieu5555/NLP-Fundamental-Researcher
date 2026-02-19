"""
Test script for the new WeasyPrint-based PDF generator.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.report_builder import ReportState, SectionType, Source
from backend.core.pdf_generator_v2 import generate_pdf_v2
from backend.core.branding_config import get_default_config


def create_test_report():
    """Create a test report state with sample data."""
    report = ReportState(ticker="AAPL")

    # Recommendation section
    report.add_section(
        section_id="recommendation",
        title="Investment Recommendation",
        section_type=SectionType.RECOMMENDATION,
        content="""## BUY Rating - Target Price $250

Apple Inc. remains our top pick in the technology sector. We are initiating coverage with a **BUY** rating and a 12-month price target of $250.

### Key Investment Thesis

- **Services Growth**: Apple's services segment continues to show strong momentum, with 15% YoY growth
- **AI Integration**: The upcoming Apple Intelligence features position the company well for the AI era
- **Ecosystem Lock-in**: With over 2 billion active devices, Apple's ecosystem moat remains unmatched
- **Capital Returns**: $100B+ annual share buybacks provide downside support

### Valuation

Trading at 28x forward P/E, Apple is at a premium to the S&P 500 but justified by:
- Superior margin profile (45% gross margins)
- Recurring revenue growth
- Strong balance sheet ($65B net cash)
"""
    )

    # Full analysis
    report.add_section(
        section_id="full_report",
        title="Full Investment Analysis",
        section_type=SectionType.EXECUTIVE_SUMMARY,
        content="""## Business Overview

Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories worldwide. The company operates through five segments: iPhone, Mac, iPad, Services, and Wearables, Home and Accessories.

## Financial Performance

Apple delivered strong results in FY2024, with revenue of $383B and operating margins of 30.5%. The services segment reached $85B in revenue, growing at 15% YoY despite macro headwinds.

### Revenue Mix
- iPhone: 52% of revenue
- Services: 22% of revenue
- Mac: 8% of revenue
- iPad: 8% of revenue
- Wearables: 10% of revenue

## Competitive Position

Apple maintains a dominant position in premium smartphones with 55% share of devices priced above $600. The company's integrated hardware-software ecosystem creates significant switching costs.

## Growth Drivers

1. **Services**: Expanding to $100B+ by 2026
2. **India Expansion**: Fastest growing major market
3. **Vision Pro**: New product category potential
4. **AI Features**: Apple Intelligence differentiation
"""
    )

    # Bull case
    report.add_section(
        section_id="bull_case",
        title="Bull Case",
        section_type=SectionType.BULL_CASE,
        content="""### Upside Scenario: $300 Target

**AI Super-cycle**: Apple Intelligence drives iPhone upgrade cycle
- 250M+ iPhone installed base due for upgrade
- AI features require A17 Pro or newer chips
- Could drive 15-20% unit growth in FY2025

**Services Acceleration**: 20%+ growth as new offerings scale
- Apple TV+ gaining content traction
- Apple Pay adoption accelerating
- Apple Arcade expanding catalog

**Margin Expansion**: 32%+ operating margins achievable
- Services mix shift (80% gross margins)
- Supply chain efficiency gains
- Pricing power in premium segment
"""
    )

    # Bear case
    report.add_section(
        section_id="bear_case",
        title="Bear Case",
        section_type=SectionType.BEAR_CASE,
        content="""### Downside Scenario: $150 Target

**China Weakness**: 25% of revenue at risk
- Huawei gaining smartphone share
- Geopolitical tensions escalating
- Local competition intensifying

**Regulatory Pressure**: App Store economics challenged
- EU DMA forcing sideloading
- Epic Games ruling implications
- 30% take rate under pressure

**Saturation Risks**: Mature markets growth stalling
- iPhone replacement cycles lengthening
- Premium market share gains limited
- Innovation pace questioned
"""
    )

    # Strategy (SWOT + Future Outlook)
    report.add_section(
        section_id="strategy",
        title="Strategy Analysis",
        section_type=SectionType.STRATEGY,
        content="""## Strengths

- World's most valuable brand
- Vertically integrated ecosystem
- $65B net cash position
- Leading customer satisfaction scores
- R&D capabilities ($30B annual spend)

## Weaknesses

- Heavy iPhone dependence (52% revenue)
- Premium pricing limits market share
- Services growth tied to hardware base
- Limited enterprise penetration

## Opportunities

- AI integration across products
- India market expansion
- Healthcare technology potential
- Automotive sector entry
- Enterprise services growth

## Threats

- China market share erosion
- Regulatory antitrust actions
- Android ecosystem improvements
- Economic downturn impact on premium products
"""
    )

    # Fundamentals
    report.add_section(
        section_id="fundamentals",
        title="Fundamental Analysis",
        section_type=SectionType.FUNDAMENTALS,
        content="""## Financial Metrics

| Metric | FY2024 | FY2023 | Change |
|--------|--------|--------|--------|
| Revenue | $383B | $394B | -2.8% |
| Gross Margin | 45.2% | 44.1% | +110bps |
| Operating Margin | 30.5% | 29.8% | +70bps |
| EPS | $6.42 | $5.89 | +9.0% |
| FCF | $108B | $99B | +9.1% |

## Valuation

- P/E (TTM): 28.5x
- P/E (Forward): 26.2x
- EV/EBITDA: 22.1x
- PEG Ratio: 2.1x

## Balance Sheet

Apple maintains a fortress balance sheet with $65B net cash. The company returns 100%+ of FCF to shareholders through dividends and buybacks.

**Cash Position**: $162B
**Total Debt**: $97B
**Net Cash**: $65B
"""
    )

    # Technicals
    report.add_section(
        section_id="technicals",
        title="Technical Analysis",
        section_type=SectionType.TECHNICALS,
        content="""## Price Action

AAPL is trading in a consolidation pattern after breaking out above the $190 resistance level. The stock is above both the 50-day and 200-day moving averages.

### Key Levels
- **Resistance**: $200, $210, $220
- **Support**: $180, $170, $160
- **52-Week High**: $199.62
- **52-Week Low**: $164.08

## Technical Indicators

- **RSI (14)**: 58 - Neutral
- **MACD**: Bullish crossover
- **Bollinger Bands**: Trading in upper half
- **Volume**: Above average on up days

## Pattern Analysis

The stock is forming a cup-and-handle pattern with a potential breakout target of $220. The pattern has been forming over 6 months with healthy volume characteristics.
"""
    )

    # Moat Analysis
    report.add_section(
        section_id="moat_analysis",
        title="Moat Analysis",
        section_type=SectionType.MOAT_ANALYSIS,
        content="""## Economic Moat: Wide

Apple possesses one of the widest economic moats in the technology sector, driven by multiple sustainable competitive advantages.

### Switching Costs (High)

The Apple ecosystem creates significant switching costs:
- iCloud data migration complexity
- App Store purchase lock-in
- Device interoperability (AirDrop, Handoff)
- Apple Watch requires iPhone

### Brand Premium (High)

Apple commands 40%+ premium over Android competitors:
- Consistent brand perception surveys
- Luxury product positioning
- Aspirational brand status globally

### Network Effects (Moderate)

- iMessage creates social lock-in in US
- App Store developer ecosystem
- AirPlay compatibility network

### Intangible Assets (High)

- 100,000+ patents
- iOS operating system control
- Custom silicon design (M-series, A-series)
"""
    )

    # Sources - need to add sources separately
    sources_section = report.add_section(
        section_id="sources",
        title="Sources",
        section_type=SectionType.SOURCES,
        content="Research sources used in this analysis."
    )
    # Add actual Source objects
    sources_section.sources = [
        Source(id=1, title="Apple Q4 2024 Earnings Call", url="https://investor.apple.com", date="2024-11-01", source_type="filing"),
        Source(id=2, title="Apple 10-K Annual Report", url="https://sec.gov/cgi-bin/browse-edgar", date="2024-10-15", source_type="filing"),
        Source(id=3, title="IDC Smartphone Market Share Report", url="https://idc.com", date="2024-10-20", source_type="research"),
        Source(id=4, title="Counterpoint India Market Analysis", url="https://counterpointresearch.com", date="2024-09-15", source_type="news"),
    ]

    return report


def main():
    """Generate test PDF."""
    print("Creating test report...")
    report_state = create_test_report()

    print("Generating PDF with WeasyPrint...")
    branding = get_default_config()

    try:
        pdf_bytes = generate_pdf_v2(
            report_state=report_state,
            ticker="AAPL",
            branding=branding,
            analyst_sources=[]
        )

        output_path = str(Path(__file__).parent.parent / "AAPL_test_report_v2.pdf")
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)

        print("PDF generated successfully!")
        print(f"Output: {output_path}")
        print(f"Size: {len(pdf_bytes):,} bytes")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
