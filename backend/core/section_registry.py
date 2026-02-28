"""
Canonical section registry for all analysis output paths.

Reads from shared/section_registry.json (the single source of truth) and
provides typed access to every section and metadata key used across the
frontend, PDF report, PDF slides, and Excel generators.

All backend modules should reference SECTIONS and use display_name() /
is_valid_key() instead of hardcoding section strings. The frontend imports
the same JSON file directly.

The registry enforces the naming convention:
  - Section keys and metadata keys share the same canonical name
  - Snake_case in Python, camelCase in JavaScript
  - No _data / _model / _analysis / _table suffixes
  - Display names are Title Case, used for PDF headings and slide titles

Usage:
    from core.section_registry import SECTIONS, display_name, is_valid_key

    name = display_name("dcf")           # "DCF Valuation"
    valid = is_valid_key("dcf_model")    # False (old key)
    keys = narrative_keys()              # all narrative section keys
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent.parent.parent / "shared" / "section_registry.json"


@dataclass(frozen=True)
class SectionEntry:
    """A single entry in the section registry."""
    key: str
    display: str
    type: str
    group: str


def _load_registry() -> Dict[str, SectionEntry]:
    """Load the section registry from shared/section_registry.json."""
    try:
        with open(REGISTRY_PATH, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Failed to load section registry from %s: %s", REGISTRY_PATH, e)
        raise RuntimeError(f"Cannot load section registry: {e}") from e

    return {
        key: SectionEntry(key=key, display=entry["display"], type=entry["type"], group=entry["group"])
        for key, entry in data["sections"].items()
    }


# Module-level singleton, loaded once at import time
SECTIONS: Dict[str, SectionEntry] = _load_registry()

# Precomputed sets for fast membership checks
VALID_KEYS: FrozenSet[str] = frozenset(SECTIONS.keys())
NARRATIVE_KEYS: FrozenSet[str] = frozenset(k for k, v in SECTIONS.items() if v.type == "narrative")
VALUATION_KEYS: FrozenSet[str] = frozenset(k for k, v in SECTIONS.items() if v.type == "valuation")


def display_name(key: str) -> str:
    """Get the display name for a section key, or return the key itself if unknown."""
    entry = SECTIONS.get(key)
    if entry is None:
        logger.warning("Unknown section key: %s", key)
        return key
    return entry.display


def is_valid_key(key: str) -> bool:
    """Check whether a key is a recognized canonical section key."""
    return key in VALID_KEYS


def narrative_keys() -> FrozenSet[str]:
    """All narrative (prose) section keys."""
    return NARRATIVE_KEYS


def valuation_keys() -> FrozenSet[str]:
    """All valuation (structured data) section keys."""
    return VALUATION_KEYS
