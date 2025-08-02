"""Basic tests to ensure project structure is working."""

from stable_squirrel.config import Config


def test_config_creation():
    """Test that we can create a default config."""
    config = Config()
    assert config.ingestion.polling_interval == 1.0
    assert config.transcription.model_name == "large-v2"
    assert (
        config.database.connection_url
        == "postgresql://stable_squirrel:changeme@localhost:5432/stable_squirrel"
    )


def test_package_import():
    """Test that we can import the main package."""
    import stable_squirrel

    assert stable_squirrel is not None
