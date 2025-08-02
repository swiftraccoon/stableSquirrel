# API Reference

This document provides complete API documentation for Stable Squirrel, including the RdioScanner integration endpoint used by SDRTrunk.

## API Endpoint

**`POST /api/call-upload`**

This is the standard RdioScanner API endpoint that SDRTrunk expects. **Do not change this path** - SDRTrunk is configured to use this exact endpoint across the radio monitoring community.

## Enhanced Security Features

### Upload Source Tracking

Every upload is now comprehensively tracked for security and forensic purposes:

- **Source IP Address**: Captured with X-Forwarded-For header support for proxied environments
- **System ID**: SDRTrunk instance identifier for multi-system deployments  
- **API Key Used**: Which specific API key authenticated the upload
- **User Agent**: Client software identification and version information
- **Upload Timestamp**: Precise timing with timezone information

### Enhanced API Key System

The API now supports advanced authentication with granular restrictions:

#### Multi-Key Configuration
```yaml
ingestion:
  api_keys:
    - key: "station-alpha-secure-key-2024"
      description: "Main SDR station with static IP"
      allowed_ips: ["192.168.1.100", "10.0.0.50"]
      allowed_systems: ["123", "456"]
    - key: "mobile-unit-beta-key"
      description: "Mobile SDR setup"
      # No IP restrictions for mobile deployments
```

#### IP-Based Restrictions
- **Static IP Enforcement**: API keys can be restricted to specific IP addresses
- **Proxy Support**: X-Forwarded-For header respected for load balancer deployments
- **CIDR Support**: IP ranges supported for network-based restrictions

#### System-Based Restrictions  
- **System ID Validation**: API keys can be restricted to specific SDRTrunk system IDs
- **Multi-System Support**: Single key can authorize multiple related systems
- **System Tracking**: All uploads linked to originating system for analysis

## Implementation Details

### File Format Requirements

**CRITICAL: MP3 Files Only**

- **Supported Format**: MP3 only (`.mp3` extension, `audio/mpeg` MIME type)
- **Rejected Formats**: WAV, M4A, FLAC, OGG, AAC, WebM are **not supported**
- **Security Reasoning**: 
  - SDRTrunk only sends MP3 files, making this restriction natural
  - Reduced attack surface by supporting only one well-understood format
  - Faster validation and processing with single format checking
  - Concentrated security effort on one format for maximum protection

### Request Format

SDRTrunk sends multipart form data with the following fields:

#### Required Fields (for real calls)
- **`key`**: API key for authentication (now supports enhanced key validation)
- **`system`**: SDR system identifier (now required for security tracking)
- **`dateTime`**: Unix timestamp of the call
- **`audio`**: MP3 audio file (binary data)

#### Optional Fields (Enhanced for Security)
- **`frequency`**: Radio frequency in Hz
- **`talkgroup`**: Talkgroup ID
- **`source`**: Source radio ID
- **`systemLabel`**: Human-readable system name
- **`talkgroupLabel`**: Human-readable talkgroup name
- **`talkgroupGroup`**: Talkgroup category
- **`talkerAlias`**: Radio user identifier
- **`audioName`**: Original filename (logged for security analysis)
- **`audioType`**: Audio MIME type (validated for security)

#### Test Mode (Enhanced)
- **`test=1`**: Enables test mode for connection testing
- **Test Mode Security**: Test requests still validated for API key and IP restrictions
- **No Audio Required**: Test mode bypasses file validation but maintains authentication

### Response Format

#### Success Response (200 OK)
```json
{
  "success": true,
  "message": "Call received and queued for processing",
  "call_id": "abc-123-def-456",
  "timestamp": "2024-01-20T10:30:00Z"
}
```

#### Enhanced Error Responses

##### Authentication Errors (401 Unauthorized)
```json
{
  "error": "Authentication failed",
  "details": "Invalid API key",
  "timestamp": "2024-01-20T10:30:00Z"
}
```

**Specific Authentication Error Types:**
- `"Invalid API key"` - API key not recognized
- `"API key not authorized for IP {ip}"` - IP restriction violation
- `"API key not authorized for system {system_id}"` - System restriction violation
- `"Missing API key"` - No key provided when required

##### Validation Errors (400 Bad Request)
```json
{
  "error": "File validation failed",
  "details": "Only MP3 files are supported",
  "timestamp": "2024-01-20T10:30:00Z"
}
```

**Validation Error Types:**
- `"Only MP3 files are supported"` - Wrong file format
- `"File size exceeds maximum limit"` - File too large
- `"File size below minimum threshold"` - File too small  
- `"Missing required field: {field}"` - Required field not provided
- `"System ID required"` - system field missing when required
- `"Malicious content detected"` - Security validation failure

##### Rate Limiting Errors (429 Too Many Requests)
```json
{
  "error": "Rate limit exceeded",
  "details": "Maximum 10 uploads per minute exceeded",
  "retry_after": 45,
  "timestamp": "2024-01-20T10:30:00Z"
}
```

## Security Validation Pipeline

### Layer 1: Authentication
1. **API Key Validation**: Verify key exists and is valid
2. **IP Restriction Check**: Validate source IP if restrictions configured
3. **System Restriction Check**: Validate system ID if restrictions configured
4. **Security Event Logging**: Log all authentication attempts

### Layer 2: Request Validation  
1. **Required Field Check**: Ensure all mandatory fields present
2. **System ID Validation**: Verify system ID provided if required
3. **Rate Limiting**: Check per-IP and per-system upload limits
4. **Request Size Validation**: Verify overall request size within limits

### Layer 3: File Security Validation
1. **File Extension Check**: Must be `.mp3` only
2. **MIME Type Validation**: Must be `audio/mpeg` or `audio/mp3`
3. **File Size Validation**: Within configured min/max limits
4. **Content Validation**: MP3 header structure validation
5. **Malicious Content Scanning**: Pattern detection for threats
6. **Security Event Logging**: Log all validation attempts and failures

## Security Event Generation

### Event Types Generated

#### Authentication Events
- **`api_key_used`**: Successful API key authentication
- **`invalid_api_key`**: Failed authentication attempt
- **`api_key_ip_violation`**: API key used from unauthorized IP
- **`api_key_system_violation`**: API key used by unauthorized system

#### Upload Events  
- **`upload_success`**: Successful file upload and validation
- **`upload_blocked`**: File upload rejected due to validation failure
- **`malicious_content_detected`**: Potentially dangerous content identified

#### Rate Limiting Events
- **`rate_limit_exceeded`**: Upload rate limits exceeded
- **`suspicious_activity`**: Unusual upload patterns detected

### Event Severity Levels
- **`info`**: Normal successful operations
- **`medium`**: Rate limits exceeded, validation failures
- **`high`**: Security violations (IP/system restrictions)
- **`critical`**: Malicious content detected, attack patterns

## SDRTrunk Configuration

### Basic Configuration

Add to SDRTrunk's `playlist.xml`:

```xml
<streaming>
  <streamingAction>
    <actionType>STREAM_HTTP</actionType>
    <serverUrl>http://your-server:8000/api/call-upload</serverUrl>
    <apiKey>your-api-key-here</apiKey>
    <systemId>your-system-id</systemId>
  </streamingAction>
</streaming>
```

### Enhanced Security Configuration

For deployments using enhanced security features:

```xml
<streaming>
  <streamingAction>
    <actionType>STREAM_HTTP</actionType>
    <serverUrl>https://your-secure-server:8000/api/call-upload</serverUrl>
    <apiKey>station-alpha-secure-key-2024</apiKey>
    <systemId>station-alpha-123</systemId>
    <userAgent>SDRTrunk/0.6.0-alpha-station-alpha</userAgent>
  </streamingAction>
</streaming>
```

### Configuration Best Practices

#### Security Recommendations
1. **Use Unique System IDs**: Each SDRTrunk instance should have a unique system ID
2. **Strong API Keys**: Use cryptographically strong, unique API keys per station
3. **HTTPS Only**: Always use HTTPS for production deployments
4. **IP Restrictions**: Configure IP allowlists for static IP deployments
5. **Custom User Agents**: Use descriptive user agents for easier identification

#### Multi-Station Deployments
```yaml
# Server configuration for multiple stations
ingestion:
  api_keys:
    - key: "main-station-key-2024"
      description: "Primary monitoring station"
      allowed_ips: ["192.168.1.100"]
      allowed_systems: ["main-001"]
    - key: "backup-station-key-2024"
      description: "Backup monitoring station"  
      allowed_ips: ["192.168.1.101"]
      allowed_systems: ["backup-001"]
    - key: "mobile-units-key-2024"
      description: "Mobile monitoring units"
      allowed_systems: ["mobile-001", "mobile-002"]
      # No IP restrictions for mobile units
```

## Monitoring & Analytics

### Security Monitoring APIs

Monitor upload activity and security events using the security APIs:

#### Security Event Monitoring
```bash
# Monitor recent security events
GET /api/v1/security/events?limit=100

# Filter high-severity events
GET /api/v1/security/events?severity=high&hours=24

# Monitor specific system
GET /api/v1/security/events?source_system=station-alpha-123
```

#### Upload Source Analysis
```bash
# Analyze specific system behavior
GET /api/v1/security/analysis/source/station-alpha-123

# List all upload sources
GET /api/v1/security/uploads/sources

# Security dashboard summary
GET /api/v1/security/summary?hours=24
```

### Performance Monitoring

#### Key Metrics to Monitor
- **Upload Success Rate**: Percentage of successful uploads vs. rejections
- **Authentication Failures**: Rate of invalid API key attempts
- **Rate Limiting Events**: Frequency of rate limit violations
- **File Validation Failures**: Types and frequency of validation errors
- **Response Time**: API endpoint response time under load

#### Example Monitoring Queries
```bash
# Upload success rate (last 24 hours)
GET /api/v1/security/events?event_type=upload_success&hours=24
GET /api/v1/security/events?event_type=upload_blocked&hours=24

# Authentication failure rate
GET /api/v1/security/events?event_type=invalid_api_key&hours=24

# System-specific performance
GET /api/v1/security/analysis/source/{system_id}
```

## Troubleshooting

### Common Issues

#### Authentication Problems
**Error**: `"Invalid API key"`
- **Solution**: Verify API key in both SDRTrunk config and server config
- **Check**: Ensure no typos or extra whitespace in API key

**Error**: `"API key not authorized for IP {ip}"`
- **Solution**: Add the SDRTrunk server IP to the `allowed_ips` list
- **Check**: Verify actual source IP (check for NAT/proxy complications)

**Error**: `"API key not authorized for system {system_id}"`
- **Solution**: Add the system ID to the `allowed_systems` list
- **Check**: Verify system ID matches between SDRTrunk and server config

#### File Validation Problems
**Error**: `"Only MP3 files are supported"`
- **Solution**: Configure SDRTrunk to output MP3 format only
- **Check**: Verify audio format settings in SDRTrunk

**Error**: `"File size exceeds maximum limit"`
- **Solution**: Increase `max_file_size_mb` in server config or optimize SDRTrunk encoding
- **Check**: Review typical file sizes and adjust limits appropriately

#### Rate Limiting Issues
**Error**: `"Rate limit exceeded"`
- **Solution**: Increase rate limits or investigate unusual upload patterns
- **Check**: Monitor security events for suspicious activity patterns

### Debug Mode

Enable detailed logging for troubleshooting:

```yaml
# Enhanced logging configuration
logging:
  level: DEBUG
  
ingestion:
  # Enable detailed security logging
  track_upload_sources: true
  log_all_uploads: true
```

### Security Incident Response

When security violations are detected:

1. **Immediate Analysis**: Use security APIs to analyze the incident
2. **Source Investigation**: Review all uploads from the problematic source
3. **Pattern Detection**: Look for similar incidents from other sources
4. **Response Actions**: Implement appropriate blocking or rate limiting
5. **Documentation**: Ensure complete incident documentation in audit trail

## Summary

The enhanced RdioScanner API implementation provides:

- **Standard Compatibility**: Full compatibility with SDRTrunk's expectations
- **Enterprise Security**: Multi-layered authentication and validation
- **Comprehensive Tracking**: Complete source attribution for all uploads
- **Real-time Monitoring**: Security event generation and analysis capabilities
- **Forensic Support**: Complete audit trail for incident investigation
- **Scalable Architecture**: Support for large multi-station deployments

This implementation ensures that SDRTrunk integration remains seamless while providing enterprise-grade security monitoring and forensic capabilities for radio monitoring networks.