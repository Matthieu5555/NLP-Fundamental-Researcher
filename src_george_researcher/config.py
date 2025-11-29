"""
Configuration management for George Financial Researcher.
Uses environment variables and functional patterns.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env from project root (parent of src_george_researcher)
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


@dataclass(frozen=True)
class Config:
    """Immutable configuration container."""
    openrouter_api_key: str
    openrouter_model: str
    alpha_vantage_key: Optional[str]
    eodhd_key: Optional[str]
    tavily_key: Optional[str]
    data_dir: Path
    embeddings_dir: Path
    chunk_size: int
    chunk_overlap: int
    max_debate_rounds: int


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku"),
        alpha_vantage_key=os.getenv("ALPHA_VANTAGE_API_KEY"),
        eodhd_key=os.getenv("EODHD_API_KEY"),
        tavily_key=os.getenv("TAVILY_API_KEY"),
        data_dir=Path(os.getenv("DATA_DIR", "./data")),
        embeddings_dir=Path(os.getenv("EMBEDDINGS_DIR", "./embeddings")),
        chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "100")),
        max_debate_rounds=int(os.getenv("MAX_DEBATE_ROUNDS", "2")),
    )


def ensure_directories(config: Config) -> None:
    """Create required directories if they don't exist."""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.embeddings_dir.mkdir(parents=True, exist_ok=True)


def validate_config(config: Config) -> tuple[bool, list[str]]:
    """
    Validate configuration.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    if not config.openrouter_api_key:
        errors.append("OPENROUTER_API_KEY not set")

    return (len(errors) == 0, errors)
