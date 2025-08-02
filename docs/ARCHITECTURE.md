# Architecture Overview

This document describes the high-level architecture of Stable Squirrel, focusing on component interaction and design decisions.

## Goals

- **Low latency** – process and stream audio with minimal delay from SDRTrunk
- **Enterprise Security** – comprehensive audit trails, source tracking, and threat detection
- **Simplicity** – non-technical users can set up and operate the system
- **Extensibility** – contributors can add features safely via thorough testing
- **Production Ready** – robust monitoring, alerting, and forensic capabilities

## System Architecture

### RdioScanner API Integration

**Primary Ingestion Method** - Direct integration with SDRTrunk:

- **Endpoint**: `POST /api/call-upload` (RdioScanner standard)
- **Real-time Processing**: Audio calls streamed directly from SDRTrunk
- **Enhanced Security**: Multi-layered validation with source tracking
- **No File Watching**: Eliminates legacy directory monitoring complexity

#### Security Architecture

- **Multi-Factor API Keys**: Enhanced key system with IP restrictions and system allowlists
- **Upload Source Tracking**: Every call linked to source IP, system ID, API key, and user agent
- **Comprehensive Audit Logging**: All security events stored in TimescaleDB for forensic analysis
- **Real-time Threat Detection**: Malicious content detection with immediate source identification

### Transcription Service

- **WhisperX Integration**: Advanced speech-to-text with speaker diarization
- **Asynchronous Processing**: Non-blocking audio processing pipeline
- **Quality Metrics**: Confidence scoring and speaker identification
- **TimescaleDB Storage**: Time-series optimized storage for millions of calls

### Security Monitoring System

#### Security Event Tracking
- **Database-Backed Logging**: Persistent security event storage in TimescaleDB
- **Threat Classification**: Events categorized by type and severity (info/low/medium/high/critical)
- **Source Attribution**: Full traceability from security event to upload source
- **Rate Limiting**: Database-backed rate limiting with violation tracking

#### Security APIs
- **`GET /api/v1/security/events`** - Security event listing and filtering
- **`GET /api/v1/security/analysis/source/{system_id}`** - Upload source analysis
- **`GET /api/v1/security/summary`** - Real-time security dashboard data
- **`GET /api/v1/security/uploads/sources`** - Upload source monitoring

### Web Interface & APIs

#### Core APIs
- **Search API**: Full-text search across transcriptions with metadata filtering
- **Transcription API**: Retrieve calls with speaker segments and timing
- **Health API**: System status and readiness checks

#### LLM Integration
- **OpenAI API Compatible**: Forward user prompts to local or remote models
- **Context-Aware**: Include transcription data in LLM prompts
- **Conversation Memory**: Maintain chat context across requests

#### Alert System
- **Keyword Monitoring**: Real-time alerting on specified terms
- **Multi-Channel Notifications**: Email, SMS, webhook integrations
- **Security Alerts**: Automatic notifications for high-severity security events

## Database Architecture

### TimescaleDB (Time-Series PostgreSQL)

**Why TimescaleDB?**
- **Scale**: Handle hundreds of millions of radio calls
- **Performance**: Optimized for time-range queries and full-text search
- **Mature**: Production-proven PostgreSQL ecosystem
- **Security**: ACID compliance for audit trail integrity

#### Core Tables

##### Radio Calls (Hypertable)
```sql
CREATE TABLE radio_calls (
    -- Time-series optimized
    timestamp TIMESTAMPTZ NOT NULL,
    call_id UUID DEFAULT gen_random_uuid(),
    
    -- Radio metadata
    frequency BIGINT NOT NULL,
    talkgroup_id INTEGER,
    source_radio_id INTEGER,
    system_id INTEGER,
    
    -- Audio and transcription
    audio_file_path TEXT NOT NULL,
    audio_duration_seconds REAL,
    transcription_status TEXT DEFAULT 'pending',
    
    -- Security tracking (NEW)
    upload_source_ip INET,
    upload_source_system TEXT,
    upload_api_key_id TEXT,
    upload_user_agent TEXT,
    
    PRIMARY KEY (timestamp, call_id)
);
```

##### Security Events (Hypertable)
```sql
CREATE TABLE security_events (
    -- Time-series optimized
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_id UUID DEFAULT gen_random_uuid(),
    
    -- Event classification
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    
    -- Source tracking
    source_ip INET,
    source_system TEXT,
    api_key_used TEXT,
    user_agent TEXT,
    
    -- Event data
    description TEXT NOT NULL,
    metadata JSONB,
    related_call_id UUID,
    related_file_path TEXT,
    
    PRIMARY KEY (timestamp, event_id)
);
```

## Security Model

### Multi-Layered File Validation

1. **File Type Validation**: MP3 only (SDRTrunk standard)
2. **Content Inspection**: Audio header validation and malicious content detection
3. **Size Limits**: Configurable min/max file sizes
4. **Rate Limiting**: Per-IP limits with database tracking

### Enhanced API Key System

```yaml
# Enhanced API key configuration
api_keys:
  - key: "station-alpha-secure-key"
    description: "Main SDR station"
    allowed_ips: ["192.168.1.100"]
    allowed_systems: ["123"]
  - key: "mobile-unit-beta-key"
    description: "Mobile monitoring"
    # No IP restrictions for mobile units
```

### Audit Trail & Forensics

**Complete Traceability**: When malicious content is detected:
1. **Source Identification**: IP address, system ID, API key used
2. **Historical Analysis**: All uploads from that source
3. **Security Event Timeline**: Chronological threat progression
4. **Automated Response**: Rate limiting, alerting, and blocking capabilities

## Deployment Options

### Direct Execution
```bash
# Install dependencies with uv
source .venv/bin/activate
uv add stable-squirrel

# Configure security
cp config.yaml.example config.yaml
# Edit API keys and security settings

# Run application
python -m stable_squirrel --config config.yaml
```

### Systemd Service
```bash
# Production deployment
sudo cp stable-squirrel.service /etc/systemd/system/
sudo systemctl enable --now stable-squirrel.service
```

### Container Deployment
```bash
# Rootless containers with Podman
podman-compose up -d
```

## Performance Optimizations

### Application Layer
- **Asynchronous I/O**: FastAPI with async/await throughout
- **Connection Pooling**: Persistent database connections via asyncpg
- **Model Caching**: WhisperX models kept warm between requests

### Database Layer
- **Hypertables**: Automatic time-based partitioning
- **Optimized Indexes**: Time-range, full-text, and security-focused indexes
- **Compression**: Automatic compression for historical data (30+ days)

### Security Performance
- **Efficient Validation**: Optimized MP3 header parsing
- **Database-Backed Rate Limiting**: Persistent tracking without memory bloat
- **Index-Optimized Queries**: Fast security event retrieval and analysis

## Development Workflow

### Code Quality Standards
| Category | Tool | Configuration |
|----------|------|---------------|
| Formatting | Black + isort | 120 character line length |
| Linting | Ruff | Comprehensive rule set with --fix |
| Type Checking | mypy | Strict type checking |
| Testing | pytest | Comprehensive unit and integration tests |

### Security-First Development
- **Multi-layered Validation**: Conservative "reject first" approach
- **Comprehensive Testing**: Security scenarios included in test suite
- **Audit Logging**: All security events logged for analysis
- **Regular Security Reviews**: Code review focused on security implications

## Testing Strategy

### Core Test Coverage
- **API Integration Tests**: RdioScanner endpoint with real SDRTrunk data
- **Security Validation Tests**: Malicious file detection and rate limiting
- **Database Tests**: TimescaleDB operations and schema integrity
- **End-to-End Tests**: Full ingestion → transcription → API flow

### Security Testing
- **Upload Validation**: Malicious file rejection testing
- **Rate Limiting**: Burst and sustained load testing
- **API Key Security**: IP restriction and system validation testing
- **Audit Trail**: Security event logging and retrieval testing

## Monitoring & Operations

### Health Monitoring
- **`/health/ready`**: Application readiness checks
- **`/health/live`**: Liveness probe for container orchestration
- **Database Connectivity**: TimescaleDB connection health

### Security Monitoring
- **Real-time Dashboards**: Security event visualization
- **Automated Alerting**: High-severity event notifications
- **Forensic Analysis**: Historical pattern analysis and threat hunting
- **Compliance Reporting**: Audit trail export and analysis

## Summary

Stable Squirrel has evolved into an enterprise-grade radio transcription platform with comprehensive security monitoring. The system now provides:

- **Direct SDRTrunk Integration** via RdioScanner API
- **Enterprise Security** with multi-layered validation and audit trails
- **Real-time Monitoring** with security event dashboards
- **Forensic Capabilities** for threat analysis and compliance
- **Production-Ready Deployment** with container and service options
- **Comprehensive Testing** ensuring stability and security

The architecture prioritizes security, performance, and operational excellence while maintaining the simplicity needed for non-technical users to deploy and operate the system effectively.