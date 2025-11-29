"""
Wrapper for the existing orchestrator to handle imports correctly.
"""

import sys
from pathlib import Path

# Change to src directory and add parent to path
src_dir = Path(__file__).parent.parent.parent / 'src_george_researcher'
sys.path.insert(0, str(src_dir.parent))

# Import as module
from src_george_researcher import orchestrator as orch
from src_george_researcher import config as cfg

# Re-export
run_analysis = orch.run_analysis
Config = cfg.Config
load_config = cfg.load_config
