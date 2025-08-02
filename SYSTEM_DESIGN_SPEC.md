# Stable Squirrel System Design Spec

This document describes the architecture and deployment options for the "Stable Squirrel" project.  The system processes SDRTrunk recordings with WhisperX, serves transcriptions and audio to a web interface, exposes search and LLM functionality, and allows keyword alerts.

## Goals
- **Low latency** – process and stream audio with minimal delay.
- **Simplicity** – non-technical users can set up and operate the system.
- **Extensibility** – contributors can add features safely via thorough testing.

## Components
### Ingestion Service
- Monitors SDRTrunk recording output directories.
- Converts or normalizes audio if needed (e.g., to WAV).
- Passes audio to the transcription service.

### Transcription Service
- Uses **WhisperX** with speaker diarization enabled.
- Produces timestamps, speaker labels, and text.
- Stores results in a fast local database (e.g., SQLite or Postgres).
- Maintains mapping to original audio files for streaming.

### Web Interface
- Built with a lightweight Python web framework (e.g., FastAPI or Flask).
- Streams live audio and/or shows transcriptions in near real time.
- Search endpoint for querying transcriptions and metadata.
- LLM endpoint implementing the OpenAI API format to forward user prompts to
  either a local or remote model.
- Alert configuration page where users can set keywords and choose email or text
  notifications.

### Deployment Options
- **Direct Execution** – install Python dependencies and run `python3 -m stable_squirrel`.
- **Systemd Service** – include a sample unit file so users can `systemctl enable --now stable-squirrel.service` for automatic startup on Linux.
- **Podman Containers** – provide container images and a `podman-compose` file so the entire stack can run in rootless containers.
- **Dependency Management** – use [`uv`](https://github.com/astral-sh/uv) for installing and caching Python packages.

### Testing Strategy
- Unit tests for each service component, using `pytest`.
- Integration tests for the full ingestion → transcription → web flow.
- Continuous Integration pipeline running on each pull request.
- Example test data and scripted environment to help new contributors reproduce
  failures quickly.

## Development Tooling

The project standardizes on the following tools to keep the codebase consistent and stable:

| Category | Tool(s) | Configuration (examples) |
| --- | --- | --- |
| Formatting | Black + isort | `black --line-length=88`; `isort --profile black` |
| Linting | Ruff | Set `max-complexity`, `ignore` rules |
| Type Checking | Pyright for dev; Mypy for CI | `pyrightconfig.json`; `mypy --strict src/` |
| Docstrings | Google or NumPy style | Use Napolean plugin in Sphinx |
| Pre-commit / CI | pre-commit, GitHub Actions | Automated checks on push and PR |
| Test Framework | pytest | `pip install pytestpytest-cov` |
## Performance Considerations
- Use asynchronous I/O for reading audio and serving web requests.
- Keep WhisperX models warmed and loaded between requests to avoid startup cost.
- Configure a lightweight database with indexes on timestamp and keywords for
  fast search.
- Avoid unnecessary copying of audio data during streaming.

## Summary
Stable Squirrel will ingest SDRTrunk recordings, transcribe them with
WhisperX, and serve results through a simple web interface.  Users can run the
system directly, as a systemd service, or in Podman containers.  Extensive tests
and CI ensure that contributions remain stable while keeping latency low.
