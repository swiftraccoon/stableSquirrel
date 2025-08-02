# Quick Start Guide

Get Stable Squirrel running with SDRTrunk in 15 minutes.

## Prerequisites

- **Python 3.12+**
- **Docker** (for TimescaleDB)
- **SDRTrunk** configured and running

## 1. Install Stable Squirrel

```bash
# Clone and setup
git clone https://github.com/swiftraccoon/stableSquirrel.git
cd stableSquirrel

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

## 2. Start Services with Podman

```bash
# Start all services (database + application)
make podman-compose

# Or manually
podman-compose up -d
```

## 3. Configure Stable Squirrel

```bash
# Copy example config
cp config.yaml.example config.yaml

# Edit config.yaml - minimal required changes:
```

```yaml
database:
  host: "localhost"
  port: 5432
  database: "stable_squirrel"
  username: "stable_squirrel" 
  password: "changeme"

ingestion:
  # Set API key for SDRTrunk authentication
  api_key: "your-secure-api-key-here"

transcription:
  # Start with CPU-based model for testing
  model_name: "base"
  device: "cpu"
```

## 4. Configure and Start

```bash
# Copy and edit configuration
cp config.yaml.example config.yaml
# Edit config.yaml with your settings (database, API keys, etc.)

# Start all services (TimescaleDB + Stable Squirrel)
podman-compose up -d

# Or for development with live reload
make run-dev

# Service starts on http://localhost:8000
# RdioScanner API endpoint: http://localhost:8000/api/call-upload
```

## 5. Configure SDRTrunk

In SDRTrunk, add a **Call Audio Recorder**:

1. **File → Edit Audio Recorders**
2. **Add → RdioScanner Call Upload**
3. Configure:
   - **Server**: `http://localhost:8000`
   - **API Key**: `your-secure-api-key-here` (from step 3)
   - **System ID**: `100` (any unique number)

4. **Save and Enable** the recorder

## 6. Test the Integration

```bash
# Check system health
curl http://localhost:8000/api/system-health

# Expected response:
{
  "status": "healthy",
  "database": {"healthy": true},
  "task_queue": {"status": "healthy"},
  "timestamp": 1704067200
}
```

## 7. Monitor Activity

```bash
# View performance metrics  
curl http://localhost:8000/api/queue-stats

# Web interface (if enabled)
open http://localhost:8000/docs
```

## 🎯 **Success!**

When SDRTrunk records a call, you should see:

1. **Upload logs** in Stable Squirrel console
2. **Transcription processing** in background queue
3. **Database entries** for calls and transcriptions

## Next Steps

- **[Performance Tuning](PERFORMANCE.md)** - Optimize for high volume
- **[Security Guide](SECURITY_GUIDE.md)** - Enhanced API key setup  
- **[API Reference](API_REFERENCE.md)** - Full API documentation

## Common Issues

### "Connection refused" to database

```bash
# Check if services are running
podman-compose ps

# Check database logs
podman-compose logs timescaledb

# Check application logs
podman-compose logs stable-squirrel
```

### SDRTrunk "Upload failed"

```bash
# Check API key matches
curl -X POST http://localhost:8000/api/call-upload \
  -F "key=your-secure-api-key-here" \
  -F "system=100" \
  -F "test=1"

# Should return: "incomplete call data: no talkgroup"
```

### Transcription not working

```bash
# Check if WhisperX model is loading
# Look for "Loading WhisperX model" in logs
# GPU models require CUDA setup
```
