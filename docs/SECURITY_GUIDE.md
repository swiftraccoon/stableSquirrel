# Security Guide

This document covers authentication, validation, monitoring, and security best practices for Stable Squirrel deployments.

## Security Architecture

### Enhanced API Key System

#### Multi-Factor Authentication
- **Enhanced API Keys**: Support for multiple keys with granular permissions
- **IP-Based Restrictions**: Optional IP allowlists for static-IP deployments
- **System-Based Restrictions**: API keys can be restricted to specific SDRTrunk system IDs
- **Legacy Compatibility**: Backward compatibility with single API key deployments

#### Configuration Example
```yaml
ingestion:
  # Enhanced API key configuration
  api_keys:
    - key: "station-alpha-secure-key-2024"
      description: "Main SDR station with static IP"
      allowed_ips: ["192.168.1.100", "10.0.0.50"]
      allowed_systems: ["123", "456"]
    - key: "mobile-unit-beta-key-2024"
      description: "Mobile SDR setup"
      # No IP restrictions for mobile units
    - key: "backup-station-gamma-key"
      description: "Backup monitoring station"
      allowed_ips: ["192.168.1.101"]
  
  # Security policies
  track_upload_sources: true
  require_system_id: true
```

### Upload Source Tracking

#### Complete Traceability
Every upload is now linked to its source with comprehensive metadata:

- **Source IP Address**: Including X-Forwarded-For header support for proxied environments
- **System ID**: SDRTrunk instance identifier for multi-system deployments
- **API Key ID**: Which specific API key was used for authentication
- **User Agent**: Client software identification and version
- **Timestamp**: Precise upload timing with timezone information

#### Forensic Capabilities
When malicious content is detected, administrators can:

1. **Identify Source**: Immediately trace back to the exact SDRTrunk instance
2. **Analyze Patterns**: Review all historical uploads from that source
3. **Security Timeline**: Examine the complete security event history
4. **Automated Response**: Implement targeted blocking or rate limiting

## File Upload Security

### Strict File Type Enforcement

**ONLY MP3 files are accepted** for maximum security:

#### Reasons for MP3-Only Policy
1. **SDRTrunk Compatibility**: SDRTrunk exclusively sends MP3 files
2. **Attack Surface Reduction**: Single format eliminates complex parser vulnerabilities
3. **Parsing Simplicity**: MP3 has well-understood, validated header structure
4. **Performance**: Fastest validation with single-format checking
5. **Security Focus**: Concentrated security effort on one format

#### Rejected Formats (Security Reasons)
- **WAV**: Uncompressed format not used by SDRTrunk, unnecessary attack surface
- **M4A, AAC**: Complex container formats with metadata injection vulnerabilities
- **FLAC, OGG**: Unused by SDRTrunk, additional parser complexity
- **WebM, MP4**: Video containers inappropriate for radio, significant attack surface
- **Any Other**: Conservative "deny by default" approach

### Multi-Layered Validation Pipeline

#### Layer 1: Basic File Validation
- **File Extension Check**: Must be `.mp3` only (case-insensitive)
- **MIME Type Validation**: Must be `audio/mpeg` or `audio/mp3`
- **Filename Sanitization**: Blocks path traversal and dangerous characters
- **Size Limits**: 1KB minimum, 100MB maximum (configurable per deployment)

#### Layer 2: Content Validation
- **MP3 Header Validation**: Verifies legitimate MP3 file structure and metadata
- **Malicious Content Scanning**: Detects executable signatures, script injection attempts
- **Metadata Inspection**: Validates ID3 tags and embedded content
- **Conservative Rejection**: When validation is uncertain, the file is rejected

#### Layer 3: Advanced Security Scanning
- **Pattern Detection**: Scans for known malicious patterns and signatures
- **Size Anomaly Detection**: Flags unusually large or small files for manual review
- **Rate-Based Analysis**: Detects rapid-fire upload attempts indicating automation
- **Source Behavior Analysis**: Identifies suspicious patterns from specific sources

## Security Event Monitoring

### Database-Backed Security Logging

#### Persistent Event Storage
- **TimescaleDB Integration**: All security events stored in time-series optimized database
- **Event Classification**: Events categorized by type and severity level
- **Structured Metadata**: JSON metadata for detailed event context
- **Performance Optimized**: Indexed for fast querying and analysis

#### Event Severity Levels
- **`info`**: Normal operations (successful uploads, valid API key usage)
- **`low`**: Minor issues (deprecated API key usage warnings)
- **`medium`**: Security concerns (rate limits exceeded, validation failures)
- **`high`**: Security violations (invalid API key, IP restrictions violated)
- **`critical`**: Security breaches (malicious content detected, attack patterns)

### Security Event Types

#### Authentication Events
- **`api_key_used`**: Successful API key authentication
- **`invalid_api_key`**: Failed authentication attempts
- **`api_key_ip_violation`**: API key used from unauthorized IP
- **`api_key_system_violation`**: API key used by unauthorized system

#### Upload Events
- **`upload_success`**: Successful file upload and validation
- **`upload_blocked`**: File upload rejected due to validation failure
- **`malicious_content_detected`**: Potentially dangerous content identified

#### Rate Limiting Events
- **`rate_limit_exceeded`**: Upload rate limits exceeded
- **`suspicious_activity`**: Unusual upload patterns detected

### Real-Time Security Monitoring

#### Security Dashboard APIs
- **`GET /api/v1/security/events`**: List and filter security events
- **`GET /api/v1/security/summary`**: Real-time security overview
- **`GET /api/v1/security/analysis/source/{system_id}`**: Deep-dive source analysis
- **`GET /api/v1/security/uploads/sources`**: Monitor all upload sources

#### Example Security Analysis
```json
{
  "system_id": "station-alpha-123",
  "upload_statistics": {
    "total_uploads": 1284,
    "unique_ips": 2,
    "first_seen": "2024-01-15T08:30:00Z",
    "last_seen": "2024-01-20T16:45:00Z"
  },
  "security_statistics": {
    "total_events": 45,
    "violations": 3,
    "upload_events": 42
  },
  "ip_addresses": [
    {"upload_source_ip": "192.168.1.100", "upload_count": 1200},
    {"upload_source_ip": "192.168.1.101", "upload_count": 84}
  ],
  "recent_events": [...]
}
```

## Rate Limiting & Abuse Prevention

### Database-Backed Rate Limiting

#### Multi-Tier Limits
- **Per-IP Limits**: 10 uploads per minute, 100 per hour (configurable)
- **Per-System Limits**: Configurable per SDRTrunk system ID
- **Global Limits**: Overall system capacity protection
- **Burst Allowances**: Temporary spikes handled gracefully

#### Persistent Tracking
- **Database Storage**: Rate limit counters stored in TimescaleDB
- **Cross-Restart Persistence**: Limits maintained across application restarts
- **Historical Analysis**: Rate limiting patterns available for security analysis
- **Automated Enforcement**: Progressive enforcement from warnings to blocks

### Abuse Detection

#### Behavioral Analysis
- **Upload Pattern Analysis**: Detects automated or suspicious upload behaviors
- **Source Correlation**: Identifies coordinated attacks from multiple sources
- **Temporal Analysis**: Recognizes time-based attack patterns
- **Volume Analysis**: Flags unusual upload volumes or frequencies

#### Automated Response
- **Progressive Enforcement**: Warnings → temporary blocks → permanent blocks
- **Source-Specific Limits**: Targeted rate limiting for problematic sources
- **Alert Generation**: Automatic notifications for security violations
- **Audit Trail**: Complete record of all enforcement actions

## Forensic Capabilities

### Malicious Content Response

When malicious content is detected, the system provides:

#### Immediate Response
1. **Block Upload**: Immediate rejection with detailed logging
2. **Source Identification**: Complete source metadata capture
3. **Alert Generation**: Real-time notifications to administrators
4. **Pattern Recording**: Malicious pattern storage for future detection

#### Investigation Support
1. **Historical Analysis**: All uploads from the identified source
2. **Timeline Reconstruction**: Chronological security event sequence
3. **Cross-Reference Analysis**: Related security events from other sources
4. **Evidence Preservation**: Immutable audit trail for compliance

#### Example Forensic Query Flow
```bash
# 1. Malicious content detected in call_id abc-123
# 2. Find the source system
GET /api/v1/transcriptions/abc-123
# Returns: upload_source_system="station-alpha-123"

# 3. Analyze all activity from this source
GET /api/v1/security/analysis/source/station-alpha-123
# Returns: Complete upload and security history

# 4. Check for related incidents
GET /api/v1/security/events?severity=high&source_system=station-alpha-123
# Returns: All high-severity events from this source

# 5. System-wide threat analysis
GET /api/v1/security/summary?hours=168
# Returns: Week-long security overview for pattern detection
```

## Security Configuration

### Production Security Checklist

#### Essential Configuration
- [ ] **API Keys Configured**: At least one strong API key set
- [ ] **IP Restrictions**: Enable for static-IP deployments
- [ ] **System ID Requirements**: Enable `require_system_id: true`
- [ ] **Upload Source Tracking**: Enable `track_upload_sources: true`
- [ ] **File Size Limits**: Set appropriate `max_file_size_mb`
- [ ] **Rate Limits**: Configure `max_uploads_per_minute/hour`

#### Recommended Settings
```yaml
ingestion:
  # Security policies
  enable_file_validation: true
  max_file_size_mb: 50
  max_uploads_per_minute: 5
  max_uploads_per_hour: 50
  track_upload_sources: true
  require_system_id: true
  
  # Enhanced API keys with restrictions
  api_keys:
    - key: "your-secure-32-char-api-key-here"
      description: "Production SDR Station"
      allowed_ips: ["your.static.ip.here"]
      allowed_systems: ["your-system-id"]
```

#### Monitoring Setup
- **Log Monitoring**: Monitor application logs for security events
- **Database Monitoring**: Set up alerts for high-severity security events
- **API Monitoring**: Regular checks of security API endpoints
- **Audit Schedule**: Regular review of security event summaries

## Compliance & Audit

### Audit Trail Features

#### Complete Event Logging
- **Immutable Records**: Security events cannot be modified after creation
- **Detailed Metadata**: Full context for every security-related action
- **Time-Series Storage**: Optimized for historical analysis and reporting
- **Export Capabilities**: Security data export for compliance reporting

#### Compliance Support
- **Data Retention**: Configurable retention policies for audit data
- **Access Logging**: Complete record of who accessed what security information
- **Integrity Verification**: Database-level integrity checks for audit data
- **Reporting APIs**: Structured data export for compliance systems

### Security Monitoring Best Practices

#### Regular Security Reviews
1. **Daily**: Monitor security event dashboard for anomalies
2. **Weekly**: Review upload source analysis for unusual patterns
3. **Monthly**: Comprehensive security summary analysis
4. **Quarterly**: Full audit trail review and compliance reporting

#### Incident Response
1. **Detection**: Automated alerts for high-severity events
2. **Analysis**: Use forensic APIs to understand scope and impact
3. **Response**: Implement targeted rate limiting or blocking
4. **Documentation**: Complete incident record in audit trail
5. **Improvement**: Update security policies based on lessons learned

## Summary

Stable Squirrel's security architecture provides enterprise-grade protection through:

- **Multi-layered Validation**: Conservative file validation with multiple security checks
- **Enhanced Authentication**: IP and system-restricted API keys with complete audit trails
- **Real-time Monitoring**: Comprehensive security event tracking and analysis
- **Forensic Capabilities**: Complete traceability from threat detection to source identification
- **Automated Protection**: Database-backed rate limiting and abuse prevention
- **Compliance Ready**: Immutable audit trails and comprehensive reporting capabilities

This security model ensures that any malicious content can be immediately traced back to its source, providing both real-time protection and forensic analysis capabilities for maintaining system integrity.