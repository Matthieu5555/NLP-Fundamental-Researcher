"""
Structured analyst overrides for DCF assumptions.

When an analyst expresses a valuation opinion (e.g., "margins will compress 5pp"),
these types translate that into a structured modification to the base DCF model.

The override system preserves the frozen dataclass pattern: the base LLM-generated
assumptions are never mutated. Instead, overrides are applied via pure functions
that produce new frozen DCFAssumptions objects.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class OverrideTarget(Enum):
    """Which DCF assumption field to override.

    Maps 1:1 to DCFAssumptions fields. The override applicator uses this
    to determine which field(s) to modify.
    """
    REVENUE_GROWTH = "revenue_growth"
    GROSS_MARGIN = "gross_margin"
    OPEX_RATIO = "opex_ratio"
    CAPEX_RATIO = "capex_ratio"
    WACC = "wacc"
    TERMINAL_GROWTH = "terminal_growth"
    TAX_RATE = "tax_rate"
    DA_RATIO = "da_ratio"
    SBC_RATIO = "sbc_ratio"
    NWC_CHANGE = "nwc_change"
    FCF_MARGIN = "fcf_margin"
    NET_DEBT = "net_debt"


class OverrideMode(Enum):
    """How to apply the numeric override value.

    ABSOLUTE:   Set the field to this exact value.
                "WACC should be 12%" -> ABSOLUTE, 0.12
    DELTA:      Add this amount to the base value.
                "margins compress 5pp" -> DELTA, -0.05
    MULTIPLIER: Multiply the base value by this factor.
                "growth will be 2x what you projected" -> MULTIPLIER, 2.0
    """
    ABSOLUTE = "absolute"
    DELTA = "delta"
    MULTIPLIER = "multiplier"


@dataclass(frozen=True)
class AssumptionOverride:
    """A single structured override to a DCF assumption.

    Attributes:
        target: Which assumption field to modify.
        mode: How to apply the numeric value (absolute/delta/multiplier).
        value: The numeric value to apply.
        rationale: Analyst's reasoning (from the chat message or note).
        belief_id: Links back to the belief graph node that spawned this override.
        confidence: Analyst's confidence in this override (0.0-1.0).
        year_indices: If set, only apply to these projection years (0-indexed).
                      None means apply uniformly to all years.
    """
    target: OverrideTarget
    mode: OverrideMode
    value: float
    rationale: str
    belief_id: str
    confidence: float = 0.8
    year_indices: Optional[List[int]] = None

    def to_dict(self) -> Dict:
        result = {
            "target": self.target.value,
            "mode": self.mode.value,
            "value": self.value,
            "rationale": self.rationale,
            "belief_id": self.belief_id,
            "confidence": self.confidence,
        }
        if self.year_indices is not None:
            result["year_indices"] = list(self.year_indices)
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> "AssumptionOverride":
        return cls(
            target=OverrideTarget(data["target"]),
            mode=OverrideMode(data["mode"]),
            value=data["value"],
            rationale=data["rationale"],
            belief_id=data["belief_id"],
            confidence=data.get("confidence", 0.8),
            year_indices=data.get("year_indices"),
        )


@dataclass(frozen=True)
class OverrideSet:
    """Collection of analyst overrides to apply to base DCF assumptions.

    Overrides are applied in order. If multiple overrides target the same
    field, they compose: e.g., a DELTA of -0.02 followed by a MULTIPLIER
    of 0.9 first shifts then scales.

    Attributes:
        overrides: Ordered list of overrides to apply.
        timestamp: ISO timestamp of when this set was last modified.
    """
    overrides: List[AssumptionOverride] = field(default_factory=list)
    timestamp: str = ""

    def with_override(self, override: AssumptionOverride) -> "OverrideSet":
        """Return a new OverrideSet with the given override appended."""
        return OverrideSet(
            overrides=list(self.overrides) + [override],
            timestamp=self.timestamp,
        )

    def without_belief(self, belief_id: str) -> "OverrideSet":
        """Return a new OverrideSet with all overrides from a belief removed."""
        return OverrideSet(
            overrides=[o for o in self.overrides if o.belief_id != belief_id],
            timestamp=self.timestamp,
        )

    def targets_affected(self) -> set[OverrideTarget]:
        """Return the set of targets that have at least one override."""
        return {o.target for o in self.overrides}

    def to_dict(self) -> Dict:
        return {
            "overrides": [o.to_dict() for o in self.overrides],
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "OverrideSet":
        return cls(
            overrides=[AssumptionOverride.from_dict(o) for o in data.get("overrides", [])],
            timestamp=data.get("timestamp", ""),
        )
