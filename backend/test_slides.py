"""
Test script for the McKinsey-style slide deck generator.

Reuses the same test report from test_pdf_v2.py.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.slides_generator import generate_slides
from backend.core.branding_config import get_default_config
from backend.test_pdf_v2 import create_test_report


def main():
    """Generate test slide deck."""
    print("Creating test report...")
    report_state = create_test_report()

    print("Generating slides with WeasyPrint...")
    branding = get_default_config()

    try:
        slides_bytes = generate_slides(
            report_state=report_state,
            ticker="AAPL",
            branding=branding,
            analyst_sources=[]
        )

        output_path = str(Path(__file__).parent.parent / "AAPL_test_slides.pdf")
        with open(output_path, 'wb') as f:
            f.write(slides_bytes)

        print("Slides generated successfully!")
        print(f"Output: {output_path}")
        print(f"Size: {len(slides_bytes):,} bytes")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
