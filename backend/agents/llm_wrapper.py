"""
Wrapper for the existing LLM module.
"""

import sys
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent to path for src_george_researcher
src_dir = Path(__file__).parent.parent.parent / 'src_george_researcher'
sys.path.insert(0, str(src_dir.parent))

# Import the module
from src_george_researcher import llm as llm_module
from src_george_researcher import config

# Re-export original function
call_llm = llm_module.call_llm

# Create wrapper function that matches expected signature
def get_llm_response(prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
    """Wrapper around call_llm to match expected interface."""
    logger.info(f"LLM request - prompt length: {len(prompt)}, system prompt length: {len(system_prompt)}")

    cfg = config.load_config()

    result = call_llm(
        user_prompt=prompt,
        system_prompt=system_prompt,
        api_key=cfg.openrouter_api_key,
        model=cfg.openrouter_model,
        temperature=temperature
    )

    logger.info(f"LLM response - success: {result.success}, tokens: {result.tokens_used}")

    if not result.success:
        logger.error(f"LLM error: {result.error}")
        return f"Error: {result.error}"

    # Return the content string, not the LLMResponse object
    return result.content
