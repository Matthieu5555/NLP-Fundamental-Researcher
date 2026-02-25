"""
Cost tracking for analysis workflows.

Tracks per-API costs for transparent billing display in the frontend.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple


# FDS API costs (as of Dec 2024)
FDS_COSTS = {
    "company_facts": 0.00,      # FREE
    "financials": 0.02,
    "prices": 0.01,
    "news": 0.02,
    "insider_trades": 0.02,
    "analyst_estimates": 0.02,
}


@dataclass
class CostBreakdown:
    """
    Per-API cost tracking for analysis workflows.

    Used to display itemized costs in the frontend's green cost window.

    Example output:
        Gemini Search (Web Access)     $0.17
        Claude Sonnet (LLM)            $0.08
        FinancialDatasets.ai           $0.09
        ─────────────────────────────────────
        Total                          $0.34
    """

    # Shared resources (used by both US and Non-US)
    gemini_search: float = 0.0
    openrouter_llm: float = 0.0

    # FDS costs (US only)
    fds_company_facts: float = 0.0
    fds_financials: float = 0.0
    fds_prices: float = 0.0
    fds_news: float = 0.0
    fds_insider_trades: float = 0.0
    fds_analyst_estimates: float = 0.0

    # Non-US costs
    alpha_vantage: float = 0.0

    # LLM model used (for display)
    llm_model: str = "Claude Sonnet"

    def set_model(self, model: str) -> None:
        """Set the LLM model name for display."""
        # Extract friendly name from OpenRouter model ID
        if "kimi-k2.5" in model.lower():
            self.llm_model = "Kimi K2.5"
        elif "kimi-k2" in model.lower():
            self.llm_model = "Kimi K2"
        elif "claude-sonnet-4" in model.lower():
            self.llm_model = "Claude Sonnet 4.6"
        elif "claude-opus-4" in model.lower():
            self.llm_model = "Claude Opus 4.6"
        elif "gpt-5.2-pro" in model.lower():
            self.llm_model = "GPT-5.2 Pro"
        elif "gpt-5-nano" in model.lower():
            self.llm_model = "GPT-5 Nano"
        elif "llama-4-scout" in model.lower():
            self.llm_model = "Llama 4 Scout"
        elif "gemini-3.1-pro" in model.lower():
            self.llm_model = "Gemini 3.1 Pro"
        elif "gemini-3-flash" in model.lower():
            self.llm_model = "Gemini 3 Flash"
        elif "deepseek" in model.lower():
            self.llm_model = "DeepSeek V3.2"
        elif "qwen3.5" in model.lower():
            self.llm_model = "Qwen 3.5"
        elif "qwen3-coder" in model.lower():
            self.llm_model = "Qwen 3 Coder"
        elif "qwen" in model.lower():
            self.llm_model = "Qwen"
        elif "glm-5" in model.lower():
            self.llm_model = "GLM-5"
        elif "glm-4" in model.lower():
            self.llm_model = "GLM-4.7"
        elif "gemini" in model.lower():
            self.llm_model = "Gemini"
        else:
            # Use the model ID with some cleanup
            self.llm_model = model.replace("anthropic/", "").replace("google/", "").replace("-", " ").title()

    @property
    def total(self) -> float:
        """Total cost across all APIs."""
        return (
            self.gemini_search +
            self.openrouter_llm +
            self.fds_company_facts +
            self.fds_financials +
            self.fds_prices +
            self.fds_news +
            self.fds_insider_trades +
            self.fds_analyst_estimates +
            self.alpha_vantage
        )

    @property
    def fds_total(self) -> float:
        """Total FDS costs."""
        return (
            self.fds_company_facts +
            self.fds_financials +
            self.fds_prices +
            self.fds_news +
            self.fds_insider_trades +
            self.fds_analyst_estimates
        )

    def add_llm_cost(self, cost: float) -> None:
        """Add cost from an LLM call."""
        self.openrouter_llm += cost

    def add_gemini_cost(self, cost: float) -> None:
        """Add cost from a Gemini search call."""
        self.gemini_search += cost

    def add_fds_cost(self, endpoint: str) -> None:
        """Add cost for an FDS API call."""
        cost = FDS_COSTS.get(endpoint, 0.0)
        if endpoint == "company_facts":
            self.fds_company_facts += cost
        elif endpoint == "financials":
            self.fds_financials += cost
        elif endpoint == "prices":
            self.fds_prices += cost
        elif endpoint == "news":
            self.fds_news += cost
        elif endpoint == "insider_trades":
            self.fds_insider_trades += cost
        elif endpoint == "analyst_estimates":
            self.fds_analyst_estimates += cost

    def to_display_dict(self) -> Dict[str, float]:
        """
        Generate display dictionary for frontend.

        Groups FDS costs together, only includes non-zero items.

        Returns:
            Dict mapping display name to cost in USD
        """
        items = {}

        if self.gemini_search > 0:
            items["Gemini Search (Web Access)"] = round(self.gemini_search, 4)

        if self.openrouter_llm > 0:
            items[f"{self.llm_model} (LLM)"] = round(self.openrouter_llm, 4)

        if self.fds_total > 0:
            items["FinancialDatasets.ai (US Data)"] = round(self.fds_total, 4)

        if self.alpha_vantage > 0:
            items["Alpha Vantage (News)"] = round(self.alpha_vantage, 4)

        return items

    def to_detailed_dict(self) -> Dict[str, float]:
        """
        Generate detailed breakdown with individual FDS endpoints.

        Used for debugging or detailed cost analysis.
        """
        items = {}

        if self.gemini_search > 0:
            items["gemini_search"] = self.gemini_search
        if self.openrouter_llm > 0:
            items["openrouter_llm"] = self.openrouter_llm
        if self.fds_company_facts > 0:
            items["fds_company_facts"] = self.fds_company_facts
        if self.fds_financials > 0:
            items["fds_financials"] = self.fds_financials
        if self.fds_prices > 0:
            items["fds_prices"] = self.fds_prices
        if self.fds_news > 0:
            items["fds_news"] = self.fds_news
        if self.fds_insider_trades > 0:
            items["fds_insider_trades"] = self.fds_insider_trades
        if self.fds_analyst_estimates > 0:
            items["fds_analyst_estimates"] = self.fds_analyst_estimates
        if self.alpha_vantage > 0:
            items["alpha_vantage"] = self.alpha_vantage

        return items

    def to_display_list(self) -> List[Tuple[str, float]]:
        """
        Generate ordered list for frontend display.

        Returns list of (name, cost) tuples, ordered by cost descending.
        """
        items = self.to_display_dict()
        return sorted(items.items(), key=lambda x: x[1], reverse=True)

    def merge(self, other: "CostBreakdown") -> "CostBreakdown":
        """Merge another CostBreakdown into this one."""
        return CostBreakdown(
            gemini_search=self.gemini_search + other.gemini_search,
            openrouter_llm=self.openrouter_llm + other.openrouter_llm,
            fds_company_facts=self.fds_company_facts + other.fds_company_facts,
            fds_financials=self.fds_financials + other.fds_financials,
            fds_prices=self.fds_prices + other.fds_prices,
            fds_news=self.fds_news + other.fds_news,
            fds_insider_trades=self.fds_insider_trades + other.fds_insider_trades,
            fds_analyst_estimates=self.fds_analyst_estimates + other.fds_analyst_estimates,
            alpha_vantage=self.alpha_vantage + other.alpha_vantage,
            llm_model=self.llm_model,
        )

    def __repr__(self) -> str:
        return f"CostBreakdown(total=${self.total:.4f})"
