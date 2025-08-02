"""Configuration management for Stable Squirrel."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class APIKeyConfig(BaseModel):
    """Configuration for an individual API key."""

    key: str
    description: Optional[str] = None
    allowed_ips: Optional[list[str]] = None  # If set, only these IPs can use this key
    allowed_systems: Optional[list[str]] = None  # If set, only these system IDs can use this key


class IngestionConfig(BaseModel):
    """Configuration for the RdioScanner ingestion API."""

    # API authentication
    api_key: Optional[str] = None  # Legacy single API key (deprecated)
    api_keys: list[APIKeyConfig] = Field(default_factory=list)  # Enhanced API key config

    # Polling settings (for compatibility with tests)
    polling_interval: float = 1.0  # Interval for checking new files
    supported_formats: list[str] = Field(default=[".wav", ".mp3", ".m4a"])  # Supported audio formats

    # Security settings
    enable_file_validation: bool = True
    max_file_size_mb: int = 100  # Maximum file size in MB
    min_file_size_kb: int = 1  # Minimum file size in KB
    max_uploads_per_minute: int = 10  # Per IP rate limit
    max_uploads_per_hour: int = 100  # Per IP rate limit

    # Node tracking for security
    track_upload_sources: bool = True  # Track which nodes/systems upload files
    require_system_id: bool = True  # Require system ID for all uploads

    # Additional security settings
    log_all_uploads: bool = False  # Log all upload attempts
    security_event_retention_days: int = 365  # Security event retention period


class TranscriptionConfig(BaseModel):
    """Configuration for the transcription service."""

    model_name: str = "large-v2"
    device: str = "auto"
    batch_size: int = 16
    enable_diarization: bool = True
    language: Optional[str] = None

    # Performance optimization settings
    queue_size: int = 10000  # Maximum transcription queue size
    num_workers: int = 4  # Number of background transcription workers
    max_file_size_mb: int = 100  # Maximum audio file size in MB
    cleanup_interval_minutes: int = 5  # How often to clean up temp files

    # Advanced model settings
    compute_type: str = "auto"  # float16 for GPU, int8 for CPU
    chunk_length: int = 30  # Audio chunk length for processing
    use_pipeline_cache: bool = True  # Cache model pipeline for speed


class DatabaseConfig(BaseModel):
    """Configuration for TimescaleDB database."""

    host: str = "localhost"
    port: int = 5432
    database: str = "stable_squirrel"
    username: str = "stable_squirrel"
    password: str = "changeme"

    # Connection pooling for high throughput
    min_pool_size: int = 5
    max_pool_size: int = 20

    # Schema management
    create_tables: bool = True
    enable_timescale: bool = True

    @property
    def connection_url(self) -> str:
        """Build PostgreSQL connection URL."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class WebConfig(BaseModel):
    """Configuration for the web interface."""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default=["*"])
    enable_docs: bool = True


class AlertConfig(BaseModel):
    """Configuration for alerting."""

    enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None


class Config(BaseModel):
    """Main configuration model."""

    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    alerts: AlertConfig = Field(default_factory=AlertConfig)


def load_config(config_path: Path | str) -> Config:
    """Load configuration from a YAML file."""
    config_path = Path(config_path)
    if not config_path.exists():
        # Create a default config file
        default_config = Config()
        save_config(default_config, config_path)
        return default_config

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    return Config(**data)


def save_config(config: Config, config_path: Path) -> None:
    """Save configuration to a YAML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False)
