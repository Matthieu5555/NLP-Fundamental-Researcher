"""Tests for the configuration module."""

import os
import pytest
from unittest.mock import patch
from pathlib import Path

from src_george_researcher.config import (
    Config,
    load_config,
    validate_config,
    ensure_directories,
)


class TestConfig:
    """Tests for the Config dataclass."""

    def test_config_is_frozen(self, mock_config):
        """Test that Config is immutable."""
        with pytest.raises(AttributeError):
            mock_config.openrouter_api_key = "new-key"

    def test_paths_are_pathlib(self, mock_config):
        """Test that path fields use pathlib.Path."""
        assert isinstance(mock_config.data_dir, Path)
        assert isinstance(mock_config.embeddings_dir, Path)

    def test_config_attributes(self, mock_config):
        """Test that Config has all expected attributes."""
        assert hasattr(mock_config, 'openrouter_api_key')
        assert hasattr(mock_config, 'openrouter_model')
        assert hasattr(mock_config, 'alpha_vantage_key')
        assert hasattr(mock_config, 'eodhd_key')
        assert hasattr(mock_config, 'google_api_key')
        assert hasattr(mock_config, 'data_dir')
        assert hasattr(mock_config, 'embeddings_dir')
        assert hasattr(mock_config, 'chunk_size')
        assert hasattr(mock_config, 'chunk_overlap')
        assert hasattr(mock_config, 'max_debate_rounds')


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_loads_from_environment(self):
        """Test that config loads from environment variables."""
        test_env = {
            "OPENROUTER_API_KEY": "test-api-key",
            "OPENROUTER_MODEL": "test-model",
            "DATA_DIR": "/custom/data",
        }

        with patch.dict(os.environ, test_env, clear=False):
            config = load_config()

        assert config.openrouter_api_key == "test-api-key"
        assert config.openrouter_model == "test-model"
        assert config.data_dir == Path("/custom/data")

    def test_uses_defaults_when_not_set(self):
        """Test that missing env vars use defaults."""
        # Clear relevant env vars
        env_without_keys = {k: v for k, v in os.environ.items()
                           if not k.startswith("OPENROUTER")}

        with patch.dict(os.environ, env_without_keys, clear=True):
            config = load_config()

        assert config.openrouter_api_key == ""  # Default empty
        assert config.openrouter_model == "moonshotai/kimi-k2.5"  # Default model

    def test_loads_optional_keys(self):
        """Test that optional API keys are loaded when present."""
        test_env = {
            "OPENROUTER_API_KEY": "test-key",
            "ALPHA_VANTAGE_API_KEY": "av-key",
            "EODHD_API_KEY": "eodhd-key",
            "GOOGLE_API_KEY": "google-key",
        }

        with patch.dict(os.environ, test_env, clear=False):
            config = load_config()

        assert config.alpha_vantage_key == "av-key"
        assert config.eodhd_key == "eodhd-key"
        assert config.google_api_key == "google-key"


class TestValidateConfig:
    """Tests for the validate_config function."""

    def test_valid_config(self, mock_config):
        """Test validation passes with valid config."""
        is_valid, errors = validate_config(mock_config)
        assert is_valid is True
        assert len(errors) == 0

    def test_missing_api_key(self):
        """Test validation fails without API key."""
        config = Config(
            openrouter_api_key="",  # Missing!
            openrouter_model="test",
            alpha_vantage_key=None,
            eodhd_key=None,
            google_api_key=None,
            data_dir=Path("/tmp"),
            embeddings_dir=Path("/tmp"),
            chunk_size=1000,
            chunk_overlap=100,
            max_debate_rounds=2,
        )

        is_valid, errors = validate_config(config)
        assert is_valid is False
        assert len(errors) > 0
        assert "OPENROUTER_API_KEY" in errors[0]


class TestEnsureDirectories:
    """Tests for the ensure_directories function."""

    def test_creates_directories(self, tmp_path):
        """Test that directories are created if missing."""
        config = Config(
            openrouter_api_key="test",
            openrouter_model="test",
            alpha_vantage_key=None,
            eodhd_key=None,
            google_api_key=None,
            data_dir=tmp_path / "new_data",
            embeddings_dir=tmp_path / "new_embeddings",
            chunk_size=1000,
            chunk_overlap=100,
            max_debate_rounds=2,
        )

        # Directories shouldn't exist yet
        assert not config.data_dir.exists()
        assert not config.embeddings_dir.exists()

        ensure_directories(config)

        # Now they should exist
        assert config.data_dir.exists()
        assert config.embeddings_dir.exists()

    def test_handles_existing_directories(self, tmp_path):
        """Test that existing directories don't cause errors."""
        data_dir = tmp_path / "existing_data"
        embeddings_dir = tmp_path / "existing_embeddings"
        data_dir.mkdir()
        embeddings_dir.mkdir()

        config = Config(
            openrouter_api_key="test",
            openrouter_model="test",
            alpha_vantage_key=None,
            eodhd_key=None,
            google_api_key=None,
            data_dir=data_dir,
            embeddings_dir=embeddings_dir,
            chunk_size=1000,
            chunk_overlap=100,
            max_debate_rounds=2,
        )

        # Should not raise
        ensure_directories(config)

        assert config.data_dir.exists()
        assert config.embeddings_dir.exists()
