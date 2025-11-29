"""
Dynamic report builder for financial analysis.

Manages report sections, updates, and export to markdown/PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class SectionType(Enum):
    """Standard report section types."""
    EXECUTIVE_SUMMARY = "executive_summary"
    FUNDAMENTALS = "fundamentals"
    TECHNICALS = "technicals"
    BULL_CASE = "bull_case"
    BEAR_CASE = "bear_case"
    MOAT_ANALYSIS = "moat_analysis"
    SWOT = "swot"
    SENTIMENT = "sentiment"
    RISKS = "risks"
    RECOMMENDATION = "recommendation"
    CUSTOM = "custom"


@dataclass
class Section:
    """Represents a section of the analysis report."""
    title: str
    content: str  # markdown format
    section_type: SectionType
    sources: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    confidence: float = 0.7  # LLM confidence in this section
    version: int = 1

    def update(self, new_content: str, sources: List[str] = None):
        """Update section content."""
        self.content = new_content
        if sources:
            self.sources.extend(sources)
        self.last_updated = datetime.now()
        self.version += 1

    def to_markdown(self) -> str:
        """Export section as markdown."""
        md = f"## {self.title}\n\n"
        md += self.content + "\n\n"

        if self.sources:
            md += "**Sources:**\n"
            for source in self.sources:
                md += f"- {source}\n"
            md += "\n"

        return md

    def to_dict(self) -> Dict:
        """Serialize section to dictionary."""
        return {
            'title': self.title,
            'content': self.content,
            'section_type': self.section_type.value,
            'sources': self.sources,
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
        """Update an existing section."""
        if section_id in self.sections:
            self.sections[section_id].update(new_content, sources)
            self.last_updated = datetime.now()
            self.version += 1
        else:
            raise KeyError(f"Section {section_id} not found")

    def get_section(self, section_id: str) -> Optional[Section]:
        """Get a section by ID."""
        return self.sections.get(section_id)

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
            SectionType.EXECUTIVE_SUMMARY,
            SectionType.FUNDAMENTALS,
            SectionType.TECHNICALS,
            SectionType.SENTIMENT,
            SectionType.BULL_CASE,
            SectionType.BEAR_CASE,
            SectionType.MOAT_ANALYSIS,
            SectionType.SWOT,
            SectionType.RISKS,
            SectionType.RECOMMENDATION
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
        md += f"Generated with George Financial Analyst v2.0\n"

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
            'last_updated': self.last_updated.isoformat()
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
