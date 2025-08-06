# Stable Squirrel

SDR audio transcription system that receives MP3 files from SDRTrunk and transcribes them using WhisperX.

## Current Features

- **SDRTrunk Integration**: Receives MP3 audio via RdioScanner HTTP API endpoint (`/api/call-upload`)
- **Transcription**: WhisperX speech-to-text with speaker diarization
- **Storage**: PostgreSQL/TimescaleDB for transcriptions and metadata
- **Search**: Full-text search API for finding transcriptions
- **Authentication**: API key validation for upload security
- **File Validation**: Checks file size and type, rate limiting per IP

## Planned Features

- Enhanced multi-key authentication with IP restrictions
- Real-time security event monitoring
- Keyword alerts and notifications
- LLM integration for transcription analysis
- Performance metrics and monitoring

## Requirements

- Python 3.12+
- PostgreSQL 14+ (TimescaleDB recommended)
- 8GB+ RAM (more for larger WhisperX models)
- Optional: NVIDIA GPU for faster transcription

## Installation

```bash
# Clone repository
git clone https://github.com/swiftraccoon/stableSquirrel.git
cd stableSquirrel

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with uv (recommended)
uv pip install -e .

# Or install with pip
pip install -e .
```

## Setup

### 1. Database

```bash
# Option A: Use development database (requires Podman/Docker)
make db-dev

# Option B: Use existing PostgreSQL
# Create database and user:
psql -U postgres
CREATE DATABASE stable_squirrel;
CREATE USER stable_squirrel WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE stable_squirrel TO stable_squirrel;
```

### 2. Configuration

```bash
# Copy example configuration
cp config.yaml.example config.yaml

# Edit config.yaml - minimum required settings:
# - database.password
# - ingestion.api_key (for security)
```

### 3. Run

```bash
python -m stable_squirrel
```

API will be available at `http://localhost:8000`

## Usage

### Configure SDRTrunk

1. In SDRTrunk, add new streaming configuration
2. Select "RdioScanner HTTP"
3. Set URL: `http://your-server:8000/api/call-upload`
4. Set API Key to match your config.yaml

### API Examples

Upload audio (simulating SDRTrunk):

```bash
curl -X POST http://localhost:8000/api/call-upload \
  -F "audio=@audio.mp3" \
  -F "key=your-api-key" \
  -F "system=123" \
  -F "dateTime=1704067200"
```

Search transcriptions:

```bash
curl "http://localhost:8000/api/v1/transcriptions/search?q=keyword"
```

View API docs: `http://localhost:8000/docs`

## Configuration Guide

Key settings in `config.yaml`:

```yaml
ingestion:
  api_key: "your-secure-key"  # Required for uploads
  max_file_size_mb: 50        # Maximum upload size
  max_uploads_per_minute: 10  # Rate limiting

database:
  host: "localhost"
  database: "stable_squirrel"
  username: "stable_squirrel"
  password: "changeme"        # Must change!

transcription:
  model_name: "base"          # WhisperX model size
  device: "auto"              # auto/cpu/cuda
  enable_diarization: true    # Speaker detection
```

## Deployment

### Development

```bash
make run-dev
```

### Production with systemd

```bash
sudo make install-systemd
sudo systemctl enable --now stable-squirrel
```

### Production with Podman

```bash
make podman-build
make podman-run
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
make test

# Format code
make format

# Lint
make lint
```

## Troubleshooting

### Database Connection Failed

- Check PostgreSQL is running
- Verify credentials in config.yaml
- Ensure database exists

### Out of Memory During Transcription

- Use smaller WhisperX model (tiny/base)
- Reduce batch_size in config
- Add more RAM

### GPU Not Detected

- Install CUDA drivers
- Install PyTorch with CUDA support
- Set device: "cpu" to use CPU only

## Documentation

- [Detailed Installation](docs/INSTALLATION.md)
- [Configuration Reference](docs/CONFIGURATION.md)
- [API Documentation](docs/API_REFERENCE.md)
- [Database Schema](docs/DATABASE_DESIGN.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Support

- Issues: [GitHub Issues](https://github.com/swiftraccoon/stableSquirrel/issues)
- Discussions: [GitHub Discussions](https://github.com/swiftraccoon/stableSquirrel/discussions)
