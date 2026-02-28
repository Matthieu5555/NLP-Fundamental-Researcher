"""
Dynamic report builder for financial analysis.

Manages report sections, updates, and export to markdown/PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class SectionType(Enum):
    """
    Standard report section types for financial analysis.

    Each section type corresponds to a specific aspect of stock analysis.
    The enum values are used as identifiers in serialization and routing.
    Values match the canonical keys in shared/section_registry.json.
    """
    INVESTMENT_THESIS = "investment_thesis"   # Rating, thesis, valuation context, key risks/catalysts
    FUNDAMENTALS = "fundamentals"             # Financial health, profitability, growth, management signals
    TECHNICALS = "technicals"                 # Price action and technical indicators
    BULL_CASE = "bull_case"                   # Positive investment thesis and catalysts
    BEAR_CASE = "bear_case"                   # Negative thesis, risks, and potential downsides
    MOAT = "moat"                             # Competitive advantages assessment
    STRATEGY = "strategy"                     # Strategic position + Future Outlook analysis
    INDUSTRY = "industry"                     # Industry dynamics, competitive forces, market sizing
    RECOMMENDATION = "recommendation"         # Final investment recommendation (buy/hold/sell)
    DCF = "dcf"                               # DCF model and fair value
    COMPS = "comps"                           # Comparable company analysis
    EARNINGS_MODEL = "earnings_model"         # Earnings model summary table
    SENSITIVITY = "sensitivity"               # Sensitivity analysis grid
    CONVICTION = "conviction"                 # Conviction scoring
    SCENARIOS = "scenarios"                   # Bull/Base/Bear scenario modeling
    PRECEDENTS = "precedents"                 # M&A precedent transactions
    FOOTBALL_FIELD = "football_field"         # Valuation football field summary
    FINANCIALS = "financials"                 # Income, balance sheet, cash flow
    SOURCES = "sources"                       # Bibliography and citation references
    CUSTOM = "custom"                         # User-defined custom section type


@dataclass
class Source:
    """Structured source reference for citations."""
    id: int                     # Citation number [1], [2], etc.
    title: str                  # "Apple Q3 Earnings Report"
    url: str                    # https://...
    source_type: str            # "news" | "filing" | "api" | "search"
    date: str                   # "2024-12-01" or "N/A"
    snippet: Optional[str] = None  # Brief excerpt

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source_type': self.source_type,
            'date': self.date,
            'snippet': self.snippet
        }


@dataclass
class AnalystSource:
    """Analyst belief as a citable source [A1], [A2], etc."""
    id: str                     # "A1", "A2", etc.
    belief_content: str         # The belief statement
    insight_type: str           # "confirmed_fact", "risk_identified", etc.
    section: str                # Target section
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'belief_content': self.belief_content,
            'insight_type': self.insight_type,
            'section': self.section,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'AnalystSource':
        """Deserialize from dictionary."""
        return cls(
            id=data['id'],
            belief_content=data['belief_content'],
            insight_type=data['insight_type'],
            section=data['section'],
            timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now()
        )

    def to_citation_text(self) -> str:
        """Format for PDF sources section."""
        # Clean up the belief content for citation
        content = self.belief_content
        # Remove "The analyst believes" prefix if present
        prefixes_to_remove = [
            "The analyst believes that ",
            "The analyst believes ",
            "The analyst confirmed that ",
            "The analyst confirmed ",
        ]
        for prefix in prefixes_to_remove:
            if content.lower().startswith(prefix.lower()):
                content = content[len(prefix):]
                break
        # Ensure first letter is lowercase for "It is our belief that..."
        if content and content[0].isupper():
            content = content[0].lower() + content[1:]
        return f"It is our belief that {content}"


@dataclass
class Section:
    """Represents a section of the analysis report."""
    title: str
    content: str  # markdown format
    section_type: SectionType
    sources: List = field(default_factory=list)  # List[Source] or List[str] for backwards compat
    last_updated: datetime = field(default_factory=datetime.now)
    confidence: float = 0.7  # LLM confidence in this section
    version: int = 1

    def update(self, new_content: str, sources: List = None):
        """Update section content. Deduplicates sources by URL."""
        self.content = new_content
        if sources:
            # Build set of existing URLs for deduplication
            existing_urls = set()
            for existing in self.sources:
                if hasattr(existing, 'url'):
                    existing_urls.add(existing.url.lower().strip())
                elif isinstance(existing, str):
                    existing_urls.add(existing.lower().strip())

            # Only add sources that don't already exist
            for src in sources:
                if hasattr(src, 'url'):
                    url_key = src.url.lower().strip()
                elif isinstance(src, str):
                    url_key = src.lower().strip()
                else:
                    url_key = str(src).lower().strip()

                if url_key not in existing_urls:
                    self.sources.append(src)
                    existing_urls.add(url_key)
        self.last_updated = datetime.now()
        self.version += 1

    def to_markdown(self) -> str:
        """
        Export section as markdown.

        This is a pure function - no side effects, only reads data.
        """
        md = f"## {self.title}\n\n"
        md += self.content + "\n\n"

        if self.sources:
            md += "**Sources:**\n"
            for source in self.sources:
                if isinstance(source, Source):
                    md += f"- [{source.id}] {source.title} - {source.url}\n"
                else:
                    md += f"- {source}\n"
            md += "\n"

        return md

    def to_dict(self) -> Dict:
        """Serialize section to dictionary."""
        # Handle both Source objects and plain strings
        serialized_sources = []
        for source in self.sources:
            if isinstance(source, Source):
                serialized_sources.append(source.to_dict())
            else:
                serialized_sources.append(source)

        return {
            'title': self.title,
            'content': self.content,
            'section_type': self.section_type.value,
            'sources': serialized_sources,
            'last_updated': self.last_updated.isoformat(),
            'confidence': self.confidence,
            'version': self.version
        }


@dataclass
class ReportState:
    """
    Manages the complete analysis report.

    Tracks sections, metadata, and version history.
    """
    ticker: str
    sections: Dict[str, Section] = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    excluded_source_ids: List[int] = field(default_factory=list)  # Sources analyst has excluded

    def add_section(
        self,
        section_id: str,
        title: str,
        content: str,
        section_type: SectionType = SectionType.CUSTOM,
        sources: List[str] = None
    ) -> Section:
        """
        Add a new section to the report.

        Args:
            section_id: Unique identifier for the section
            title: Section title
            content: Markdown content
            section_type: Type of section
            sources: List of source citations

        Returns:
            Section: The created section
        """
        section = Section(
            title=title,
            content=content,
            section_type=section_type,
            sources=sources or []
        )
        self.sections[section_id] = section
        self.last_updated = datetime.now()
        self.version += 1
        return section

    def update_section(
        self,
        section_id: str,
        new_content: str,
        sources: List[str] = None
    ):
        """Update an existing section, or create it if it doesn't exist."""
        if section_id in self.sections:
            self.sections[section_id].update(new_content, sources)
            self.last_updated = datetime.now()
            self.version += 1
        else:
            # Create the section with a default title based on section_id
            # Display names and types use canonical keys from shared/section_registry.json
            section_titles = {
                "investment_thesis": "Investment Thesis",
                "recommendation": "Recommendation",
                "fundamentals": "Fundamental Analysis",
                "moat": "Competitive Moat",
                "strategy": "Strategic Assessment",
                "industry": "Industry Dynamics",
                "bull_case": "Bull Case",
                "bear_case": "Bear Case",
                "technicals": "Technical Analysis",
                "dcf": "DCF Valuation",
                "comps": "Comparable Companies",
                "earnings_model": "Earnings Model",
                "sensitivity": "Sensitivity Analysis",
                "conviction": "Conviction & Rating",
                "scenarios": "Scenario Analysis",
                "precedents": "Precedent Transactions",
                "football_field": "Valuation Summary",
            }
            section_types = {
                "investment_thesis": SectionType.INVESTMENT_THESIS,
                "recommendation": SectionType.RECOMMENDATION,
                "fundamentals": SectionType.FUNDAMENTALS,
                "moat": SectionType.MOAT,
                "strategy": SectionType.STRATEGY,
                "industry": SectionType.INDUSTRY,
                "bull_case": SectionType.BULL_CASE,
                "bear_case": SectionType.BEAR_CASE,
                "technicals": SectionType.TECHNICALS,
                "dcf": SectionType.DCF,
                "comps": SectionType.COMPS,
                "earnings_model": SectionType.EARNINGS_MODEL,
                "sensitivity": SectionType.SENSITIVITY,
                "conviction": SectionType.CONVICTION,
                "scenarios": SectionType.SCENARIOS,
                "precedents": SectionType.PRECEDENTS,
                "football_field": SectionType.FOOTBALL_FIELD,
            }
            title = section_titles.get(section_id, section_id.replace("_", " ").title())
            section_type = section_types.get(section_id, SectionType.CUSTOM)
            self.add_section(section_id, title, new_content, section_type, sources)

    def get_section(self, section_id: str) -> Optional[Section]:
        """Get a section by ID."""
        return self.sections.get(section_id)

    def add_source(
        self,
        title: str,
        url: str,
        source_type: str = "unknown",
        date: str = "N/A",
        snippet: Optional[str] = None
    ):
        """Add a source to the sources section."""
        # Create sources section if it doesn't exist
        if "sources" not in self.sections:
            self.add_section(
                "sources",
                "Sources",
                "",
                SectionType.SOURCES
            )

        # Generate source ID
        source_id = len(self.sections.get("sources", Section(title="", content="", section_type=SectionType.SOURCES)).sources) + 1

        # Create source object
        source = Source(
            id=source_id,
            title=title,
            url=url,
            source_type=source_type,
            date=date,
            snippet=snippet
        )

        # Add to sources section
        if "sources" in self.sections:
            self.sections["sources"].sources.append(source)
            self.last_updated = datetime.now()

    def remove_section(self, section_id: str):
        """Remove a section from the report."""
        if section_id in self.sections:
            del self.sections[section_id]
            self.last_updated = datetime.now()
            self.version += 1

    def to_markdown(self) -> str:
        """
        Export the complete report as markdown.

        Returns:
            str: Full markdown document
        """
        # Header
        md = f"# Financial Analysis Report: {self.ticker}\n\n"
        md += f"**Generated:** {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        md += f"**Last Updated:** {self.last_updated.strftime('%Y-%m-%d %H:%M:%S')}\n"
        md += f"**Version:** {self.version}\n\n"
        md += "---\n\n"

        # Table of contents
        md += "## Table of Contents\n\n"
        for section_id, section in self.sections.items():
            md += f"- [{section.title}](#{section_id})\n"
        md += "\n---\n\n"

        # Sections in order
        section_order = [
            SectionType.INVESTMENT_THESIS,
            SectionType.CONVICTION,
            SectionType.FOOTBALL_FIELD,
            SectionType.DCF,
            SectionType.SCENARIOS,
            SectionType.COMPS,
            SectionType.PRECEDENTS,
            SectionType.EARNINGS_MODEL,
            SectionType.SENSITIVITY,
            SectionType.FINANCIALS,
            SectionType.FUNDAMENTALS,
            SectionType.MOAT,
            SectionType.STRATEGY,
            SectionType.INDUSTRY,
            SectionType.BULL_CASE,
            SectionType.BEAR_CASE,
            SectionType.TECHNICALS,
            SectionType.RECOMMENDATION,
            SectionType.SOURCES,
        ]

        # Add sections in standard order
        for section_type in section_order:
            for section_id, section in self.sections.items():
                if section.section_type == section_type:
                    md += f'<a id="{section_id}"></a>\n'
                    md += section.to_markdown()
                    md += "---\n\n"

        # Add custom sections last
        for section_id, section in self.sections.items():
            if section.section_type == SectionType.CUSTOM:
                md += f'<a id="{section_id}"></a>\n'
                md += section.to_markdown()
                md += "---\n\n"

        # Footer
        md += "## Disclaimer\n\n"
        md += "*This analysis is generated by AI and should not be considered as financial advice. "
        md += "Always conduct your own research and consult with qualified financial advisors "
        md += "before making investment decisions.*\n\n"
        md += "Generated with George Research\n"

        return md

    def summarize(self) -> str:
        """
        Create a brief summary of the report for LLM context.

        Returns:
            str: Short summary of report structure and key points
        """
        summary = f"Report for {self.ticker}:\n"
        summary += f"- {len(self.sections)} sections\n"
        summary += f"- Last updated: {self.last_updated.strftime('%Y-%m-%d %H:%M')}\n"
        summary += "\nSections:\n"

        for section_id, section in self.sections.items():
            summary += f"  - {section.title} ({len(section.content)} chars)\n"

        return summary

    def to_dict(self) -> Dict:
        """Serialize report to dictionary."""
        return {
            'ticker': self.ticker,
            'sections': {
                section_id: section.to_dict()
                for section_id, section in self.sections.items()
            },
            'metadata': self.metadata,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'excluded_source_ids': self.excluded_source_ids
        }

    def get_stats(self) -> Dict:
        """Get report statistics."""
        total_chars = sum(len(s.content) for s in self.sections.values())
        total_sources = sum(len(s.sources) for s in self.sections.values())

        return {
            'ticker': self.ticker,
            'section_count': len(self.sections),
            'total_characters': total_chars,
            'total_sources': total_sources,
            'version': self.version,
            'age_hours': (datetime.now() - self.created_at).total_seconds() / 3600
        }
