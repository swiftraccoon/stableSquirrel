# Stable Squirrel

An enterprise-grade, real-time SDR audio transcription and security monitoring system that integrates with SDRTrunk via the RdioScanner HTTP API. Features advanced speech-to-text processing with WhisperX, comprehensive security monitoring, and forensic-grade audit trails for radio communications analysis.

## 🎯 Features

### Core Capabilities

- **🔗 SDRTrunk Integration**: Native RdioScanner HTTP API endpoint (`/api/call-upload`) for real-time MP3 call ingestion
- **🎙️ Advanced Transcription**: WhisperX with speaker diarization for accurate multi-speaker transcripts
- **🔍 Full-Text Search**: Fast search across millions of calls with metadata filtering
- **🤖 LLM Integration**: OpenAI-compatible API for AI-powered analysis of transcriptions
- **📊 TimescaleDB Storage**: Time-series optimized database for efficient storage and querying

### Enterprise Security Features

- **🛡️ Multi-Layered Security**: Advanced file validation with malicious content detection
- **🔐 Enhanced Authentication**: IP-restricted API keys with system-based permissions
- **📈 Real-Time Monitoring**: Comprehensive security event tracking and analysis
- **🔬 Forensic Capabilities**: Complete upload source tracking for incident investigation
- **🚨 Threat Detection**: Automated detection of suspicious upload patterns
- **📋 Audit Compliance**: Immutable security audit trails for regulatory compliance

### Deployment & Operations

- **🐳 Multiple Deployment Options**: Direct execution, systemd service, or Podman containers
- **📊 Security Dashboard**: Real-time security monitoring and analytics APIs
- **🔧 Production Ready**: Health checks, monitoring endpoints, and operational tooling

## 🚀 Quick Start

### Prerequisites: TimescaleDB

```bash
# Start TimescaleDB for development
make db-dev

# Or install locally (Ubuntu/Debian)
# See docs/deployment.md for full installation instructions
```

### Install and Run

1. **Install Dependencies** (using `uv` for speed):

   ```bash
   # Activate virtual environment
   source .venv/bin/activate
   
   # Install with all dependencies
   uv add stable-squirrel
   ```

2. **Configure Security**:

   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml - pay special attention to security settings
   ```

   **Enhanced Security Configuration Example**:

   ```yaml
   ingestion:
     # Enhanced API key system with IP restrictions
     api_keys:
       - key: "your-secure-32-char-api-key-here"
         description: "Main SDR station"
         allowed_ips: ["192.168.1.100"]  # Optional IP restriction
         allowed_systems: ["station-001"]  # Optional system restriction
       - key: "mobile-unit-key-different"
         description: "Mobile monitoring unit"
         # No IP restrictions for mobile units
     
     # Security policies
     track_upload_sources: true
     require_system_id: true
     max_file_size_mb: 50
     max_uploads_per_minute: 10
   ```

3. **Run Application**:

   ```bash
   python3 -m stable_squirrel --config config.yaml
   ```

4. **Access Interfaces**:
   - **API Documentation**: <http://localhost:8000/docs>
   - **Health Check**: <http://localhost:8000/health>
   - **Security Dashboard**: <http://localhost:8000/docs#/security> (see Security APIs)

## 🔒 Security Architecture

### Upload Source Tracking

Every upload is comprehensively tracked for security and forensic analysis:

- **🌍 Source IP**: Including X-Forwarded-For support for proxied environments
- **🏷️ System ID**: SDRTrunk instance identifier for multi-system deployments  
- **🔑 API Key**: Which specific API key authenticated the upload
- **🖥️ User Agent**: Client software identification and version
- **📅 Timestamp**: Precise upload timing with timezone information

### Enhanced API Key System

```yaml
# Multiple API keys with granular restrictions
api_keys:
  - key: "station-alpha-secure-key-2024"
    description: "Primary monitoring station"
    allowed_ips: ["192.168.1.100", "10.0.0.50"]
    allowed_systems: ["123", "456"]
  - key: "mobile-unit-beta-key"
    description: "Mobile SDR setup"
    # No IP restrictions for mobile units
```

### Malicious Content Response

When threats are detected, full forensic capabilities enable:

1. **🎯 Immediate Source Identification**: Trace to exact SDRTrunk instance
2. **📊 Historical Analysis**: Review all uploads from compromised source
3. **⏱️ Timeline Reconstruction**: Complete security event chronology
4. **🚫 Automated Response**: Rate limiting, blocking, and alerting

## 📡 SDRTrunk Configuration

### Basic Setup

Configure SDRTrunk to stream to Stable Squirrel:

1. **In SDRTrunk, go to View > Streaming**
2. **Add RdioScanner stream**:
   - **Host**: `your-server-ip:8000`
   - **Path**: `/api/call-upload`
   - **API Key**: Your secure API key from `config.yaml`
   - **System ID**: Unique identifier for this SDRTrunk instance

### Enhanced Security Setup

For production deployments with IP restrictions:

```xml
<!-- SDRTrunk streaming configuration -->
<streaming>
  <streamingAction>
    <actionType>STREAM_HTTP</actionType>
    <serverUrl>https://your-secure-server:8000/api/call-upload</serverUrl>
    <apiKey>station-alpha-secure-key-2024</apiKey>
    <systemId>station-alpha-123</systemId>
    <userAgent>SDRTrunk/0.6.0-station-alpha</userAgent>
  </streamingAction>
</streaming>
```

## 🛠️ Development

### Development Environment Setup

```bash
# Clone repository
git clone https://github.com/swiftraccoon/stableSquirrel
cd stableSquirrel

# Activate virtual environment
source .venv/bin/activate

# Install with development dependencies
uv add --dev stable-squirrel

# Setup pre-commit hooks for code quality
pre-commit install

# Run comprehensive test suite
python -m pytest tests/test_rdioscanner_api.py tests/test_security_validation.py -v
```

### Code Quality Standards

This project maintains high code quality with:

- **🎨 Black** for code formatting (120 character line length)
- **📦 isort** for import sorting
- **🔍 Ruff** for comprehensive linting with `--fix`
- **🏷️ mypy** for strict type checking
- **🧪 pytest** for extensive testing including security scenarios

**Quick Quality Check**:

```bash
# Activate environment and run full quality pipeline
source .venv/bin/activate && \
ruff check --fix src/ tests/ && \
black src/ tests/ && \
mypy src/ && \
python -m pytest
```

## 🌐 API Endpoints

### Core APIs

#### Health & Status

- `GET /health/ready` - Application readiness check
- `GET /health/live` - Liveness probe for container orchestration

#### SDRTrunk Integration

- `POST /api/call-upload` - **RdioScanner API endpoint** (primary ingestion)

#### Transcription & Search

- `GET /api/v1/transcriptions` - List recent transcriptions with pagination
- `GET /api/v1/transcriptions/search` - Advanced search with filters
- `GET /api/v1/transcriptions/{id}` - Get specific transcription with speaker segments

#### LLM Integration

- `POST /api/v1/llm/chat/completions` - OpenAI-compatible chat completions

### 🔒 Security Monitoring APIs (NEW)

#### Security Event Analysis

- `GET /api/v1/security/events` - **List security events** with filtering
- `GET /api/v1/security/summary` - **Real-time security dashboard** data
- `GET /api/v1/security/analysis/source/{system_id}` - **Deep source analysis**
- `GET /api/v1/security/uploads/sources` - **Monitor all upload sources**

#### Example Security Queries

```bash
# Monitor recent security events
curl "http://localhost:8000/api/v1/security/events?limit=50"

# Check for high-severity events in last 24 hours
curl "http://localhost:8000/api/v1/security/events?severity=high&hours=24"

# Analyze specific system behavior
curl "http://localhost:8000/api/v1/security/analysis/source/station-alpha-123"

# Security dashboard summary
curl "http://localhost:8000/api/v1/security/summary?hours=24"
```

## 🏗️ Architecture

### System Components

- **🔗 RdioScanner API**: Standards-compliant endpoint for SDRTrunk integration
- **🛡️ Security Layer**: Multi-layered validation with comprehensive audit logging
- **🎙️ Transcription Engine**: WhisperX-based speech-to-text with speaker diarization
- **🔍 Search Engine**: Full-text search across transcriptions with metadata
- **📊 Security Monitor**: Real-time threat detection and forensic analysis
- **🗄️ Database**: TimescaleDB for time-series optimization and scalability

### Security Architecture

```
SDRTrunk → [IP/API Key Auth] → [File Validation] → [Content Scanning] → [Processing]
                ↓                     ↓                    ↓              ↓
          Security Events ←    Security Events ←   Security Events ← Audit Trail
                ↓                     ↓                    ↓              ↓
           [Security APIs] ←    [Dashboard] ←        [Forensics] ← [Compliance]
```

## 📚 Documentation

### Comprehensive Documentation

- **[📋 System Design Specification](docs/SYSTEM_DESIGN_SPEC.md)** - Complete architectural overview
- **[🔒 Security Documentation](docs/SECURITY.md)** - Detailed security features and procedures
- **[🗄️ Database Design](docs/DATABASE_DESIGN.md)** - TimescaleDB schema and optimization
- **[📡 RdioScanner API](docs/RDIOSCANNER_API.md)** - SDRTrunk integration details
- **[🚀 Deployment Guide](docs/deployment.md)** - Production deployment instructions

## 🔧 Production Deployment

### Container Deployment (Recommended)

```bash
# Production deployment with Podman
podman-compose up -d

# Or with systemd service
sudo cp stable-squirrel.service /etc/systemd/system/
sudo systemctl enable --now stable-squirrel.service
```

### Security Configuration Checklist

- [ ] **Strong API Keys**: Use cryptographically secure, unique keys
- [ ] **IP Restrictions**: Configure `allowed_ips` for static IP deployments
- [ ] **System ID Requirements**: Enable `require_system_id: true`
- [ ] **Upload Source Tracking**: Enable `track_upload_sources: true`
- [ ] **Rate Limiting**: Set appropriate upload limits
- [ ] **HTTPS**: Use TLS for all production deployments
- [ ] **Database Security**: Configure TimescaleDB access controls
- [ ] **Monitoring**: Set up security event monitoring and alerting

## 🔬 Forensic Capabilities

### Threat Investigation Workflow

When malicious content is detected:

```bash
# 1. Identify the threat source
GET /api/v1/transcriptions/{suspicious_call_id}
# Returns: upload_source_ip, upload_source_system, upload_api_key_id

# 2. Analyze source system history
GET /api/v1/security/analysis/source/{source_system}
# Returns: Complete upload and security event history

# 3. Look for related incidents
GET /api/v1/security/events?source_ip={suspicious_ip}&severity=high

# 4. System-wide threat analysis
GET /api/v1/security/summary?hours=168
# Returns: Week-long security patterns and trends
```

### Compliance & Audit

- **📋 Immutable Audit Trails**: Complete security event logging with tamper resistance
- **📊 Compliance Reporting**: Structured data export for regulatory requirements
- **🔍 Forensic Analysis**: Complete traceability from threat to source
- **⏱️ Time-Series Analysis**: Historical pattern analysis for threat hunting

## 🤝 Contributing

We welcome contributions! Please see our development workflow:

1. **📋 Follow Code Quality Standards**: Use `ruff --fix`, `black`, and `mypy`
2. **🧪 Add Comprehensive Tests**: Include security scenarios in test coverage
3. **📚 Update Documentation**: Keep docs synchronized with code changes
4. **🔒 Security First**: Consider security implications of all changes

## 📄 License

[Add your license information here]

## 🆘 Support

- **📚 Documentation**: See `docs/` directory for comprehensive guides
- **🐛 Issues**: Report bugs and feature requests via GitHub Issues
- **💬 Discussions**: Join community discussions for help and ideas

---

**Stable Squirrel** - Enterprise-grade radio transcription with forensic-level security monitoring 🐿️🔒
