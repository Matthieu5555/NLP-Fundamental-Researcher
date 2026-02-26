"""
Branding Configuration for Multi-Tenant PDF Reports.

Supports white-labeling for multiple firms, each with multiple analysts.
Configuration is loaded from JSON files, designed for future database integration.

Architecture:
    Firm (e.g., George Research LTD)
    ├── name, primary_color, tool_branding
    └── Analysts
        ├── Analyst 1 (first_name, last_name, email, sector)
        └── Analyst 2 ...
"""

from dataclasses import dataclass
from typing import Optional
import json
import os
import logging

from .colors import PALETTE, hex_to_rgb

logger = logging.getLogger(__name__)

# Default config file path
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'branding', 'default.json'
)


@dataclass(frozen=True)
class FirmConfig:
    """Firm-level branding configuration."""
    firm_id: str
    name: str                    # "George Research LTD"
    primary_color: str           # "#C87A23" (hex color)
    tool_branding: str           # "Research Platform"
    logo_path: Optional[str] = None  # Path to logo PNG (future)

    @classmethod
    def from_dict(cls, data: dict) -> 'FirmConfig':
        return cls(
            firm_id=data.get('firm_id', 'default'),
            name=data.get('name', 'Research Firm'),
            primary_color=data.get('primary_color', PALETTE.brand.primary),
            tool_branding=data.get('tool_branding', 'Research Platform'),
            logo_path=data.get('logo_path')
        )


@dataclass(frozen=True)
class AnalystConfig:
    """Analyst-level configuration linked to their account."""
    analyst_id: str
    first_name: str
    last_name: str
    email: str
    sector: str                  # "Technology & Telecommunications"
    firm_id: str                 # Reference to FirmConfig

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @classmethod
    def from_dict(cls, data: dict) -> 'AnalystConfig':
        return cls(
            analyst_id=data.get('analyst_id', 'default'),
            first_name=data.get('first_name', 'Research'),
            last_name=data.get('last_name', 'Team'),
            email=data.get('email', 'research@firm.com'),
            sector=data.get('sector', 'Multi-Sector'),
            firm_id=data.get('firm_id', 'default')
        )


@dataclass(frozen=True)
class ReportBrandingConfig:
    """Complete branding configuration for a report."""
    firm: FirmConfig
    analyst: AnalystConfig

    def to_dict(self) -> dict:
        return {
            'firm': {
                'firm_id': self.firm.firm_id,
                'name': self.firm.name,
                'primary_color': self.firm.primary_color,
                'tool_branding': self.firm.tool_branding,
                'logo_path': self.firm.logo_path
            },
            'analyst': {
                'analyst_id': self.analyst.analyst_id,
                'first_name': self.analyst.first_name,
                'last_name': self.analyst.last_name,
                'email': self.analyst.email,
                'sector': self.analyst.sector,
                'firm_id': self.analyst.firm_id
            }
        }


def load_branding_config(
    firm_id: str = 'default',
    analyst_id: str = 'default',
    config_path: Optional[str] = None
) -> ReportBrandingConfig:
    """
    Load branding configuration from JSON file.

    Args:
        firm_id: ID of the firm to load config for
        analyst_id: ID of the analyst to load config for
        config_path: Optional path to config JSON file

    Returns:
        ReportBrandingConfig with firm and analyst settings
    """
    path = config_path or os.environ.get('BRANDING_CONFIG_PATH', DEFAULT_CONFIG_PATH)

    try:
        with open(path, 'r') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Branding config not found at {path}, using defaults")
        return get_default_config()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in branding config: {e}")
        return get_default_config()

    # Load firm config
    firms = config_data.get('firms', {})
    firm_data = firms.get(firm_id) or firms.get('default') or {}
    firm = FirmConfig.from_dict(firm_data)

    # Load analyst config
    analysts = config_data.get('analysts', {})
    analyst_data = analysts.get(analyst_id) or analysts.get('default') or {}
    analyst = AnalystConfig.from_dict(analyst_data)

    return ReportBrandingConfig(firm=firm, analyst=analyst)


def get_default_config() -> ReportBrandingConfig:
    """
    Get default branding configuration (George Research LTD).

    Used as fallback when config file is not available.
    """
    firm = FirmConfig(
        firm_id='george',
        name='George Research LTD',
        primary_color=PALETTE.brand.primary,
        tool_branding='Research Platform'
    )

    analyst = AnalystConfig(
        analyst_id='default',
        first_name='Research',
        last_name='Team',
        email='research@george-research.com',
        sector='Multi-Sector',
        firm_id='george'
    )

    return ReportBrandingConfig(firm=firm, analyst=analyst)


# hex_to_rgb is now imported from .colors and re-exported for backwards compatibility
