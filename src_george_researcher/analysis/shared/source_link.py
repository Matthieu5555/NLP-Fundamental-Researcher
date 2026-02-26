"""
SourceLink dataclass — canonical representation of a research source.

All source link dicts (``{"title": ..., "url": ..., "source_type": ..., "date": ...}``)
should be created as ``SourceLink`` instances and converted to dicts only at the
serialization boundary (i.e., in backend JSON responses).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLink:
    """Immutable reference to a research source used in analysis citations.

    Fields
    ------
    title:       Human-readable name of the source (e.g. "Yahoo Finance - AAPL").
    url:         Canonical URL of the source.  Always "url", never "uri".
    source_type: Category tag — one of: "api", "news", "search", "research".
    date:        ISO date string or short label (e.g. "2025-01-15", "recent").
                 Empty string when no date is available.
    """

    title: str
    url: str
    source_type: str
    date: str = ""

    def to_dict(self) -> dict:
        """Serialize to the legacy dict shape expected by backend serialization code."""
        return {
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "date": self.date,
        }
