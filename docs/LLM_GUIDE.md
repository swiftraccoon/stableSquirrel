# Stable Squirrel LLM Operations Guide - Actual Commands Used

## Overview
SDR audio transcription system tested with direct execution method. Uses TimescaleDB (via Podman), WhisperX, and FastAPI.

## Actual Commands Executed in Our Session

### Environment Setup
```bash
# Activated virtual environment
source .venv/bin/activate
```

### Database Setup
```bash
# Initialize and start Podman machine (first time only)
podman machine init
podman machine start

# Start TimescaleDB container
make db-dev
# This ran: podman run -d --name timescaledb -p 5432:5432 -e POSTGRES_PASSWORD=changeme -e POSTGRES_USER=stable_squirrel -e POSTGRES_DB=stable_squirrel timescale/timescaledb:latest-pg15
```

### Configuration Changes Made
```yaml
# In config.yaml:
database:
  password: "changeme"  # Changed from "change-this-secure-password-in-production"

ingestion:
  api_keys:
    - key: "station-alpha-secure-32-char-key-2024"
      allowed_ips: ["192.168.88.254", "192.168.1.100", "10.0.0.50"]  # Added 192.168.88.254

web:
  host: "0.0.0.0"  # Added to WebConfig
  port: 8000       # Added to WebConfig
```

### Running the Application
```bash
# Start application
source .venv/bin/activate && python -m stable_squirrel --config config.yaml --log-level INFO

# Start in background
source .venv/bin/activate && python -m stable_squirrel --config config.yaml --log-level INFO &

# Stop application
pkill -f "python -m stable_squirrel"
```

### Testing Commands Used
```bash
# Run tests
source .venv/bin/activate && python -m pytest
source .venv/bin/activate && python -m pytest tests/test_rdioscanner_api.py tests/test_security_validation.py -v

# Linting
source .venv/bin/activate && ruff check --fix src/ tests/
```

### Log Monitoring Commands Used
```bash
# View logs
tail -f stable_squirrel.log
tail -50 stable_squirrel.log
tail -20 stable_squirrel.log

# Search logs
grep "RdioScanner API Call Received" stable_squirrel.log | tail -5
grep -A 10 -B 5 "Parsed form fields" stable_squirrel.log
grep -A 10 -B 2 "Invalid HTTP request received" stable_squirrel.log | tail -15
```

### API Testing Commands Used
```bash
# Health check
curl -s http://localhost:8000/health/ready
curl http://localhost:8000/docs

# Test RdioScanner endpoint
curl -X POST http://localhost:8000/api/call-upload \
  -H "Content-Type: multipart/form-data" \
  -F "key=test-stable-squirrel-2024" \
  -F "system=123" \
  -F "test=1"

# Check transcriptions
curl http://localhost:8000/api/v1/transcriptions?limit=10
```

## Actual Issues Encountered & Fixes Applied

### 1. Database Password Mismatch
**Error**: `password authentication failed for user "stable_squirrel"`
**Fix Applied**: Changed database.password in config.yaml from "change-this-secure-password-in-production" to "changeme"

### 2. Server Binding to Wrong IP
**Error**: Server only listening on 127.0.0.1 despite config saying 0.0.0.0
**Fix Applied**: 
- Modified __main__.py to set argparse defaults to None
- Added host and port to WebConfig class

### 3. API Key Validation Failures
**Error**: "API key validation failed: Missing API key or system ID"
**Fix Applied**: Added SDRTrunk's IP (192.168.88.254) to allowed_ips in config.yaml

### 4. HTTP/2 Multipart Parsing (RESOLVED)
**Error**: Parsed form fields: [] for HTTP/2 upgrade requests with Uvicorn
**Solution**: Replaced Uvicorn with Hypercorn for proper HTTP/2 support
**Result**: Full HTTP/2 multipart parsing now works correctly

### 5. WhisperX Compatibility
**Error**: `module 'whisperx' has no attribute 'DiarizationPipeline'`
**Fix Applied**: Added hasattr check in transcription.py

### 6. Asyncio Event Loop Conflict
**Error**: `RuntimeError: asyncio.run() cannot be called from a running event loop`
**Fix Applied**: Changed to Hypercorn's async serve() method

## Key Project Rules Enforced
- Only MP3 files allowed (not WAV, M4A, FLAC, OGG, AAC)
- Use uv for package management (never pip directly)
- TimescaleDB only (no SQLite)
- RdioScanner endpoint must remain /api/call-upload
- Always run linting with --fix flag