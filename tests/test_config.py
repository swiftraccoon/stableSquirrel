"""Tests for configuration management."""

import tempfile
from pathlib import Path

from stable_squirrel.config import Config, load_config, save_config


def test_default_config():
    """Test default configuration values."""
    config = Config()

    assert config.ingestion.polling_interval == 1.0
    assert config.ingestion.supported_formats == [".wav", ".mp3", ".m4a"]
    assert config.transcription.model_name == "large-v2"
    assert config.transcription.enable_diarization is True
    assert config.database.create_tables is True
    assert config.web.enable_docs is True
    assert config.alerts.enabled is False


def test_config_serialization():
    """Test config can be saved and loaded."""
    config = Config()
    config.transcription.model_name = "base"
    config.ingestion.polling_interval = 2.0

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_path = Path(f.name)

    try:
        save_config(config, config_path)
        loaded_config = load_config(config_path)

        assert loaded_config.transcription.model_name == "base"
        assert loaded_config.ingestion.polling_interval == 2.0
    finally:
        config_path.unlink()


def test_load_nonexistent_config():
    """Test loading a config file that doesn't exist creates default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "nonexistent.yaml"

        config = load_config(config_path)

        # Should create default config
        assert config.transcription.model_name == "large-v2"

        # Should create the file
        assert config_path.exists()
