# Import existing analysis modules
import sys
from pathlib import Path

# Add src_george_researcher to Python path
src_path = Path(__file__).parent.parent.parent / 'src_george_researcher'
sys.path.insert(0, str(src_path))
