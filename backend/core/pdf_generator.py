"""
PDF Report Generator.

Converts ReportState to professional PDF documents using fpdf2.
"""

from fpdf import FPDF
from datetime import datetime
from typing import List
from .report_builder import ReportState, Section, SectionType


class PDFGenerator:
    """Generate professional PDF reports from ReportState objects."""

    def __init__(self):
        """Initialize PDF generator with default settings."""
        self.page_width = 210  # A4 width in mm
        self.page_height = 297  # A4 height in mm
        self.margin = 20
        self.effective_width = self.page_width - (2 * self.margin)

    def generate_report(self, report_state: ReportState, ticker: str) -> bytes:
        """
        Generate a complete PDF report.

        Args:
            report_state: ReportState object containing report data
            ticker: Stock ticker symbol

        Returns:
            bytes: PDF file as bytes
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Generate report components
        self._add_cover_page(pdf, ticker, report_state.created_at)
        self._add_table_of_contents(pdf, report_state.sections)
        self._add_sections(pdf, report_state.sections)
        self._add_disclaimer(pdf)

        # Return PDF as bytes (output returns bytearray in dest='S' mode)
        return bytes(pdf.output(dest='S'))

    def _add_cover_page(self, pdf: FPDF, ticker: str, created_at: datetime):
        """Add professional cover page."""
        pdf.add_page()

        # Title
        pdf.set_font('Arial', 'B', 28)
        pdf.cell(0, 30, '', 0, 1)  # Spacing
        pdf.cell(0, 20, 'Financial Analysis Report', 0, 1, 'C')

        # Ticker
        pdf.set_font('Arial', 'B', 36)
        pdf.cell(0, 20, ticker, 0, 1, 'C')

        # Date
        pdf.set_font('Arial', '', 14)
        pdf.cell(0, 10, '', 0, 1)  # Spacing
        pdf.cell(0, 10, f'Generated: {created_at.strftime("%B %d, %Y")}', 0, 1, 'C')

        # Footer on cover
        pdf.set_y(250)
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 10, 'Generated with George Financial Analyst v2.0', 0, 1, 'C')
        pdf.cell(0, 5, 'AI-Powered Multi-Agent Analysis', 0, 1, 'C')

    def _add_table_of_contents(self, pdf: FPDF, sections: dict):
        """Add table of contents."""
        pdf.add_page()

        pdf.set_font('Arial', 'B', 18)
        pdf.cell(0, 10, 'Table of Contents', 0, 1)
        pdf.ln(5)

        pdf.set_font('Arial', '', 12)

        # List sections in order
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

        toc_entries = []

        # Add sections in standard order
        for section_type in section_order:
            for section_id, section in sections.items():
                if section.section_type == section_type:
                    toc_entries.append(section.title)

        # Add custom sections
        for section_id, section in sections.items():
            if section.section_type == SectionType.CUSTOM:
                toc_entries.append(section.title)

        # Print TOC entries
        for entry in toc_entries:
            pdf.cell(10, 8, '- ', 0, 0)
            pdf.cell(0, 8, entry, 0, 1)

    def _add_sections(self, pdf: FPDF, sections: dict):
        """Add all report sections."""
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
            for section_id, section in sections.items():
                if section.section_type == section_type:
                    self._add_section(pdf, section)

        # Add custom sections
        for section_id, section in sections.items():
            if section.section_type == SectionType.CUSTOM:
                self._add_section(pdf, section)

    def _add_section(self, pdf: FPDF, section: Section):
        """Add a single section to the PDF."""
        pdf.add_page()

        # Section title
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, section.title, 0, 1)
        pdf.ln(3)

        # Section metadata
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(0, 5, f'Last updated: {section.last_updated.strftime("%Y-%m-%d %H:%M")} | Version: {section.version}', 0, 1)
        pdf.ln(5)

        # Section content
        pdf.set_font('Arial', '', 11)

        # Split content into paragraphs and format
        paragraphs = section.content.split('\n\n')

        for para in paragraphs:
            if not para.strip():
                continue

            # Check for markdown headers
            if para.startswith('###'):
                pdf.set_font('Arial', 'B', 12)
                pdf.multi_cell(0, 6, para.replace('###', '').strip())
                pdf.set_font('Arial', '', 11)
                pdf.ln(2)
            elif para.startswith('##'):
                pdf.set_font('Arial', 'B', 13)
                pdf.multi_cell(0, 7, para.replace('##', '').strip())
                pdf.set_font('Arial', '', 11)
                pdf.ln(3)
            elif para.startswith('**') and para.endswith('**'):
                # Bold text
                pdf.set_font('Arial', 'B', 11)
                pdf.multi_cell(0, 6, para.replace('**', ''))
                pdf.set_font('Arial', '', 11)
                pdf.ln(2)
            elif para.startswith('-') or para.startswith('*'):
                # Bullet points
                lines = para.split('\n')
                for line in lines:
                    if line.strip().startswith('-') or line.strip().startswith('*'):
                        bullet_text = line.strip()[1:].strip()
                        pdf.cell(10, 6, '', 0, 0)  # Indent
                        pdf.multi_cell(0, 6, f'- {bullet_text}')
                pdf.ln(2)
            else:
                # Regular paragraph
                pdf.multi_cell(0, 6, para.strip())
                pdf.ln(3)

        # Sources
        if section.sources:
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 6, 'Sources:', 0, 1)
            pdf.set_font('Arial', '', 9)

            for source in section.sources:
                pdf.cell(10, 5, '', 0, 0)  # Indent
                pdf.multi_cell(0, 5, f'- {source}')

    def _add_disclaimer(self, pdf: FPDF):
        """Add disclaimer page."""
        pdf.add_page()

        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, 'Disclaimer', 0, 1)
        pdf.ln(5)

        pdf.set_font('Arial', '', 10)

        disclaimer_text = """This analysis is generated by AI using multiple specialized agents and should not be considered as financial advice.

The information contained in this report is based on publicly available data and AI-powered analysis. While we strive for accuracy, the analysis may contain errors, omissions, or outdated information.

Key Points:

- This is not financial, investment, or trading advice
- Always conduct your own research and due diligence
- Consult with qualified financial advisors before making investment decisions
- Past performance does not guarantee future results
- All investments carry risk, including potential loss of principal
- Market conditions can change rapidly

The AI analysis includes multiple perspectives (fundamental, technical, bull case, bear case, etc.) to provide a comprehensive view. However, these perspectives may conflict and should be evaluated in the context of your own investment goals and risk tolerance.

Data sources include publicly available financial data, SEC filings, news articles, and market data. The accuracy and timeliness of this data cannot be guaranteed.

By using this report, you acknowledge that all investment decisions are your own responsibility."""

        paragraphs = disclaimer_text.split('\n\n')
        for para in paragraphs:
            # Just render all paragraphs directly
            pdf.multi_cell(0, 5, para.strip())
            pdf.ln(3)

        # Footer
        pdf.ln(10)
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(0, 5, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
        pdf.cell(0, 5, 'George Financial Analyst v2.0 - AI-Powered Multi-Agent Analysis', 0, 1, 'C')
