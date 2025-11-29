#!/usr/bin/env python3
"""
George - Your Financial Researcher

Launch the Streamlit application.
Run with: streamlit run main.py
"""
import subprocess
import sys
from pathlib import Path


def main():
    """Launch the Streamlit app."""
    app_path = Path(__file__).parent / "src_george_researcher" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])


if __name__ == "__main__":
    main()
