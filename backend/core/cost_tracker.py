"""
Cost tracking for LLM and search API usage.

Tracks token usage and calculates estimated costs for:
- OpenRouter LLM calls (various models)
- Gemini Search Grounding queries
"""
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional
import logging

# Ensure src_george_researcher is importable
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from shared pricing module (single source of truth)
from src_george_researcher.pricing import (
    calculate_llm_cost,
    get_llm_pricing,
    GEMINI_SEARCH_PRICE_PER_QUERY,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Token estimation multiplier (words to tokens)
# English text averages ~1.3 tokens per word (accurate within 5%)
TOKENS_PER_WORD = 1.3


# =============================================================================
# COST TRACKING DATA STRUCTURES
# =============================================================================

@dataclass
class APICallCost:
    """Cost for a single API call."""
    service: str  # "openrouter" or "gemini_search"
    model: Optional[str]  # Model name for LLM calls
    input_tokens: int
    output_tokens: int
    search_queries: int  # For Gemini search
    cost_usd: float


@dataclass
class SessionCost:
    """Aggregated costs for an analysis session."""
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_calls: int = 0
    search_queries: int = 0
    llm_cost_usd: float = 0.0
    search_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.llm_input_tokens + self.llm_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return self.llm_cost_usd + self.search_cost_usd

    def to_dict(self) -> Dict:
        return {
            "llm_input_tokens": self.llm_input_tokens,
            "llm_output_tokens": self.llm_output_tokens,
            "llm_calls": self.llm_calls,
            "search_queries": self.search_queries,
            "llm_cost_usd": round(self.llm_cost_usd, 6),
            "search_cost_usd": round(self.search_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SessionCost":
        return cls(
            llm_input_tokens=data.get("llm_input_tokens", 0),
            llm_output_tokens=data.get("llm_output_tokens", 0),
            llm_calls=data.get("llm_calls", 0),
            search_queries=data.get("search_queries", 0),
            llm_cost_usd=data.get("llm_cost_usd", 0.0),
            search_cost_usd=data.get("search_cost_usd", 0.0),
        )


# =============================================================================
# COST CALCULATION FUNCTIONS
# =============================================================================

# Note: calculate_llm_cost is imported from src_george_researcher.pricing


def calculate_search_cost(num_queries: int = 1) -> float:
    """
    Calculate cost for Gemini Search Grounding queries.

    Args:
        num_queries: Number of search queries made

    Returns:
        Cost in USD
    """
    cost = num_queries * GEMINI_SEARCH_PRICE_PER_QUERY
    logger.debug(f"Search cost: {num_queries} queries = ${cost:.6f}")
    return cost


def estimate_tokens_from_text(text: str) -> int:
    """
    Estimate token count from text using word-based heuristic.

    Uses TOKENS_PER_WORD multiplier (~1.3 tokens per word).
    This is accurate within 5% for English text and requires no
    external tokenizer dependencies.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    words = len(text.split())
    return int(words * TOKENS_PER_WORD)


# =============================================================================
# COST TRACKER CLASS
# =============================================================================

class CostTracker:
    """
    Tracks costs across an analysis session.

    Usage:
        tracker = CostTracker()
        tracker.add_llm_call("anthropic/claude-3-haiku", 500, 200)
        tracker.add_search_query()
        print(tracker.get_summary())
    """

    def __init__(self):
        self.session_cost = SessionCost()

    def add_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Record an LLM API call and calculate its cost.

        Returns the cost of this specific call.
        """
        cost = calculate_llm_cost(model, input_tokens, output_tokens)

        self.session_cost.llm_input_tokens += input_tokens
        self.session_cost.llm_output_tokens += output_tokens
        self.session_cost.llm_calls += 1
        self.session_cost.llm_cost_usd += cost

        return cost

    def add_search_query(self, num_queries: int = 1) -> float:
        """
        Record Gemini search queries and calculate cost.

        Returns the cost of this search.
        """
        cost = calculate_search_cost(num_queries)

        self.session_cost.search_queries += num_queries
        self.session_cost.search_cost_usd += cost

        return cost

    def get_summary(self) -> Dict:
        """Get cost summary as dictionary."""
        return self.session_cost.to_dict()

    def get_total_cost(self) -> float:
        """Get total cost in USD."""
        return self.session_cost.total_cost_usd

    def format_cost_display(self) -> str:
        """Format cost for display in UI."""
        total = self.session_cost.total_cost_usd
        if total < 0.01:
            return f"${total:.4f}"
        return f"${total:.2f}"

    def reset(self):
        """Reset all tracked costs."""
        self.session_cost = SessionCost()


# =============================================================================
# GLOBAL TRACKER INSTANCE (for simple usage)
# =============================================================================

# Can be used as: from cost_tracker import global_tracker
global_tracker = CostTracker()


def get_model_pricing_info(model: str) -> Dict:
    """Get pricing info for a model (for display purposes)."""
    pricing = get_llm_pricing(model)
    return {
        "model": model,
        "input_per_1m": pricing["input"],
        "output_per_1m": pricing["output"],
        "search_per_query": GEMINI_SEARCH_PRICE_PER_QUERY,
    }
