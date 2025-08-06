# Quick Start Guide

Get Stable Squirrel running with SDRTrunk in 15 minutes.

## Prerequisites

- Python 3.12+
- Podman (for TimescaleDB)
- SDRTrunk configured and running

## 1. Install Stable Squirrel

```bash
# Clone and setup
git clone https://github.com/swiftraccoon/stableSquirrel.git
cd stableSquirrel

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv install -e ".[dev]"
```

## 2. Start Database

```bash
# Start TimescaleDB
make db-dev
```

## 3. Configure Application

```bash
# Copy example config
cp config.yaml.example config.yaml

# Edit config.yaml - minimal required changes:
```

```yaml
database:
  password: "changeme"  # Match the database container password

ingestion:
  api_key: "your-secure-api-key-here"  # Set API key for SDRTrunk

transcription:
  model_name: "base"  # Start with smaller model for testing
  device: "cpu"       # Use GPU if available: "cuda"
```

## 4. Start Application

```bash
# Run the application
make run

# Or for development with debug logging
make run-dev

# Service starts on http://localhost:8000
# RdioScanner API endpoint: http://localhost:8000/api/call-upload
```

## 5. Configure SDRTrunk

In SDRTrunk, add a Call Audio Recorder:

1. File → Edit Audio Recorders
2. Add → RdioScanner Call Upload
3. Configure:
   - Server: `http://localhost:8000`
   - API Key: `your-secure-api-key-here` (from step 3)
   - System ID: `100` (any unique number)
4. Save and Enable the recorder

## 6. Verify Installation

```bash
# Check system health
curl http://localhost:8000/api/system-health

# Expected response:
{
  "status": "healthy",
  "database": {"healthy": true},
  "task_queue": {"status": "healthy"}
}
```

## Success!

When SDRTrunk records a call, you should see:

1. Upload logs in Stable Squirrel console
2. Transcription processing in background queue
3. Database entries for calls and transcriptions

## Monitor Activity

```bash
# View logs
tail -f stable_squirrel.log

# Check queue status
curl http://localhost:8000/api/queue-stats

# Browse API documentation
open http://localhost:8000/docs
```

## Common Issues

### Database connection refused

```bash
# Check if database is running
podman ps

# Check database logs
podman logs timescaledb-dev

# Restart database
make db-stop
make db-dev
```

### SDRTrunk upload failed

```bash
# Test API key
curl -X POST http://localhost:8000/api/call-upload \
  -F "key=your-secure-api-key-here" \
  -F "system=100" \
  -F "test=1"

# Should return: "incomplete call data: no talkgroup"
# If you get "Invalid API key", check your config.yaml
```

### Transcription not working

```bash
# Check logs for WhisperX errors
grep "WhisperX" stable_squirrel.log

# Try smaller model if out of memory
# Edit config.yaml: model_name: "tiny"
```

## Next Steps

- [Security Configuration](SECURITY.md) - Enhanced API key setup  
- [API Documentation](API_REFERENCE.md) - Full API reference
- [Monitoring Guide](MONITORING.md) - Performance monitoring