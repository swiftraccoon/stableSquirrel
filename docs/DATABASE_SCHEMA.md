# Database Schema Reference

This document provides the complete TimescaleDB schema definition, including tables, indexes, and optimization guidelines.

## Why TimescaleDB?

### Scale Requirements

- **Hundreds of millions** of radio calls over system lifetime
- **10+ million calls/year** in busy metropolitan areas  
- **High write throughput** for real-time ingestion from multiple SDRTrunk instances
- **Fast search** across transcript text, metadata, and security events
- **Security audit requirements** for compliance and forensic analysis

### TimescaleDB Advantages

1. **Time-Series Optimized**: Automatic partitioning by time (hypertables) for optimal performance
2. **PostgreSQL Compatible**: Familiar SQL with full-text search, JSON support, and mature ecosystem
3. **High Throughput**: Designed for millions of inserts per second across multiple hypertables
4. **Efficient Queries**: Optimized for time-range queries, keyword searches, and security analysis
5. **Compression**: Automatic compression for historical data to reduce storage costs
6. **Mature Ecosystem**: Production-proven with extensive tooling and monitoring support

### Alternative Comparison

| Database | Pros | Cons | Verdict |
|----------|------|------|---------|
| SQLite | Simple, embedded | No concurrency, size limits, no time-series optimization | ❌ Cannot handle scale or security requirements |
| PostgreSQL | Familiar, reliable, JSON support | Manual partitioning needed, not time-series optimized | ⚠️ Good but requires significant optimization work |
| ClickHouse | Extremely fast analytics | Complex operations, steep learning curve, less mature | ✅ Excellent but overkill for our needs |
| **TimescaleDB** | **Time-series optimized PostgreSQL with all PostgreSQL features** | **Requires PostgreSQL knowledge** | **✅ Perfect fit for our requirements** |

## Enhanced Data Schema

### Primary Tables (Hypertables)

#### 1. Radio Calls (Enhanced with Security Tracking)

```sql
CREATE TABLE radio_calls (
    -- Time-series primary key (hypertable partitioning)
    timestamp TIMESTAMPTZ NOT NULL,
    call_id UUID DEFAULT gen_random_uuid(),
    
    -- Radio metadata (from SDRTrunk/RdioScanner)
    frequency BIGINT NOT NULL,              -- Hz
    talkgroup_id INTEGER,
    source_radio_id INTEGER,
    system_id INTEGER,
    
    -- Labels and aliases (human-readable identifiers)
    system_label TEXT,
    talkgroup_label TEXT,
    talkgroup_group TEXT,
    talker_alias TEXT,
    
    -- Audio file reference and metadata
    audio_file_path TEXT NOT NULL,
    audio_duration_seconds REAL,
    audio_format TEXT DEFAULT 'mp3',
    
    -- Transcription status and timing
    transcription_status TEXT DEFAULT 'pending',
    transcribed_at TIMESTAMPTZ,
    
    -- Security tracking (NEW - Enhanced Security)
    upload_source_ip INET,                 -- Source IP with CIDR support
    upload_source_system TEXT,             -- SDRTrunk system identifier
    upload_api_key_id TEXT,                -- Which API key was used
    upload_user_agent TEXT,                -- Client software identification
    
    PRIMARY KEY (timestamp, call_id)
);

-- Convert to hypertable partitioned by timestamp
SELECT create_hypertable('radio_calls', 'timestamp');
```

#### 2. Security Events (NEW - Comprehensive Security Monitoring)

```sql
CREATE TABLE security_events (
    -- Time-series primary key (hypertable partitioning)
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_id UUID DEFAULT gen_random_uuid(),
    
    -- Event classification
    event_type TEXT NOT NULL,              -- e.g., 'api_key_used', 'upload_blocked', 'rate_limit_exceeded'
    severity TEXT NOT NULL CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    
    -- Source information (for traceability)
    source_ip INET,                        -- Source IP with CIDR support
    source_system TEXT,                    -- SDRTrunk system identifier
    api_key_used TEXT,                     -- API key identifier (partial for security)
    user_agent TEXT,                       -- Client software identification
    
    -- Event details
    description TEXT NOT NULL,             -- Human-readable event description
    metadata JSONB,                        -- Structured event data for analysis
    
    -- Related entities (for correlation)
    related_call_id UUID,                  -- Link to radio_calls if applicable
    related_file_path TEXT,                -- File path if file-related event
    
    PRIMARY KEY (timestamp, event_id)
);

-- Convert to hypertable partitioned by timestamp
SELECT create_hypertable('security_events', 'timestamp');
```

#### 3. Transcriptions (Unchanged)

```sql
CREATE TABLE transcriptions (
    call_id UUID NOT NULL,
    
    -- WhisperX transcription results
    full_transcript TEXT NOT NULL,
    language TEXT,
    confidence_score REAL,
    
    -- Speaker diarization results
    speaker_count INTEGER DEFAULT 1,
    
    -- Processing metadata
    model_name TEXT,
    processing_time_seconds REAL,
    
    PRIMARY KEY (call_id)
);
```

#### 4. Speaker Segments (Unchanged)

```sql
CREATE TABLE speaker_segments (
    call_id UUID NOT NULL,
    segment_id UUID DEFAULT gen_random_uuid(),
    
    -- Timing within the call
    start_time_seconds REAL NOT NULL,
    end_time_seconds REAL NOT NULL,
    
    -- Speaker identification
    speaker_id TEXT NOT NULL,
    
    -- Segment transcription
    text TEXT NOT NULL,
    confidence_score REAL,
    
    PRIMARY KEY (call_id, segment_id)
);
```

## Performance-Optimized Indexes

### Radio Calls Indexes

```sql
-- Time-range queries (most common access pattern)
CREATE INDEX idx_calls_timestamp ON radio_calls (timestamp DESC);

-- Frequency and talkgroup searches
CREATE INDEX idx_calls_frequency ON radio_calls (frequency, timestamp DESC);
CREATE INDEX idx_calls_talkgroup ON radio_calls (talkgroup_id, timestamp DESC);
CREATE INDEX idx_calls_system ON radio_calls (system_id, timestamp DESC);

-- Transcription status queries
CREATE INDEX idx_calls_status ON radio_calls (transcription_status);

-- Security tracking indexes (NEW)
CREATE INDEX idx_calls_upload_source_ip ON radio_calls (upload_source_ip, timestamp DESC);
CREATE INDEX idx_calls_upload_source_system ON radio_calls (upload_source_system, timestamp DESC);
CREATE INDEX idx_calls_upload_api_key ON radio_calls (upload_api_key_id, timestamp DESC);
```

### Security Events Indexes (NEW)

```sql
-- Time-range queries for security monitoring
CREATE INDEX idx_security_events_timestamp ON security_events (timestamp DESC);

-- Event type and severity filtering
CREATE INDEX idx_security_events_type ON security_events (event_type, timestamp DESC);
CREATE INDEX idx_security_events_severity ON security_events (severity, timestamp DESC);

-- Source-based security analysis
CREATE INDEX idx_security_events_source_ip ON security_events (source_ip, timestamp DESC);
CREATE INDEX idx_security_events_source_system ON security_events (source_system, timestamp DESC);
CREATE INDEX idx_security_events_api_key ON security_events (api_key_used, timestamp DESC);

-- Event correlation
CREATE INDEX idx_security_events_related_call ON security_events (related_call_id);

-- JSONB metadata queries (for advanced security analysis)
CREATE INDEX idx_security_events_metadata ON security_events USING GIN (metadata);
```

### Transcription Indexes

```sql
-- Full-text search on transcripts (primary search use case)
CREATE INDEX idx_transcript_text ON transcriptions USING GIN(to_tsvector('english', full_transcript));

-- Language and confidence filtering
CREATE INDEX idx_transcript_language ON transcriptions (language);
CREATE INDEX idx_transcript_confidence ON transcriptions (confidence_score DESC);
```

### Speaker Segment Indexes

```sql
-- Speaker-based searches
CREATE INDEX idx_segments_speaker ON speaker_segments (speaker_id, call_id);

-- Timing-based queries
CREATE INDEX idx_segments_timing ON speaker_segments (call_id, start_time_seconds);
```

## TimescaleDB Optimizations

### Hypertable Configuration

```sql
-- Set chunk time interval to 1 day for optimal query performance
SELECT set_chunk_time_interval('radio_calls', INTERVAL '1 day');
SELECT set_chunk_time_interval('security_events', INTERVAL '1 day');

-- Enable compression for data older than 30 days
ALTER TABLE radio_calls SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'frequency, talkgroup_id'
);

ALTER TABLE security_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'event_type, severity'
);

-- Add compression policies
SELECT add_compression_policy('radio_calls', INTERVAL '30 days');
SELECT add_compression_policy('security_events', INTERVAL '30 days');
```

### Data Retention Policies

```sql
-- Automatically drop radio call data older than 5 years
SELECT add_retention_policy('radio_calls', INTERVAL '5 years');

-- Keep security events for 7 years for compliance
SELECT add_retention_policy('security_events', INTERVAL '7 years');
```

## Query Patterns & Performance

### Common Query Patterns

#### 1. Recent Calls with Security Context
```sql
SELECT 
    rc.call_id,
    rc.timestamp,
    rc.frequency,
    rc.talkgroup_label,
    rc.upload_source_ip,
    rc.upload_source_system,
    t.full_transcript
FROM radio_calls rc
LEFT JOIN transcriptions t ON rc.call_id = t.call_id
WHERE rc.timestamp >= NOW() - INTERVAL '1 hour'
ORDER BY rc.timestamp DESC
LIMIT 100;
```

#### 2. Security Event Analysis
```sql
SELECT 
    event_type,
    severity,
    COUNT(*) as event_count,
    COUNT(DISTINCT source_ip) as unique_ips,
    COUNT(DISTINCT source_system) as unique_systems
FROM security_events 
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY event_type, severity
ORDER BY event_count DESC;
```

#### 3. Upload Source Forensics
```sql
SELECT 
    rc.upload_source_system,
    rc.upload_source_ip,
    COUNT(rc.call_id) as upload_count,
    COUNT(se.event_id) as security_events,
    COUNT(se.event_id) FILTER (WHERE se.severity IN ('high', 'critical')) as violations
FROM radio_calls rc
LEFT JOIN security_events se ON se.source_system = rc.upload_source_system
WHERE rc.timestamp >= NOW() - INTERVAL '7 days'
GROUP BY rc.upload_source_system, rc.upload_source_ip
ORDER BY violations DESC, upload_count DESC;
```

#### 4. Full-Text Search with Security Context
```sql
SELECT 
    rc.call_id,
    rc.timestamp,
    rc.upload_source_system,
    rc.upload_source_ip,
    t.full_transcript,
    ts_rank(to_tsvector('english', t.full_transcript), plainto_tsquery('emergency'))
FROM radio_calls rc
JOIN transcriptions t ON rc.call_id = t.call_id
WHERE to_tsvector('english', t.full_transcript) @@ plainto_tsquery('emergency')
    AND rc.timestamp >= NOW() - INTERVAL '30 days'
ORDER BY rc.timestamp DESC
LIMIT 50;
```

### Performance Characteristics

#### Expected Query Performance (1M+ calls, 100K+ security events)

| Query Type | Expected Response Time | Optimization |
|------------|----------------------|--------------|
| Recent calls (1 hour) | < 50ms | Time-based index |
| Full-text search | < 200ms | GIN index on transcript |
| Security event analysis | < 100ms | Compound indexes |
| Upload source forensics | < 150ms | Source-based indexes |
| Cross-table correlation | < 300ms | Foreign key indexes |

## Storage Estimates

### Capacity Planning

#### Radio Calls Table
- **Base Record**: ~200 bytes per call
- **With Security Fields**: ~300 bytes per call
- **1M calls/year**: ~300MB/year (uncompressed)
- **With 3:1 compression**: ~100MB/year (compressed historical data)

#### Security Events Table
- **Base Record**: ~400 bytes per event
- **High-activity system**: 10K events/day = ~4MB/day = ~1.4GB/year
- **With 4:1 compression**: ~350MB/year (compressed historical data)

#### Transcriptions + Speaker Segments
- **Transcription**: ~500 bytes per call average
- **Speaker Segments**: ~200 bytes per segment, 3 segments/call average
- **Combined**: ~1.1KB per call
- **1M calls/year**: ~1.1GB/year

#### Total Storage (1M calls/year, high security activity)
- **Year 1**: ~2.5GB (uncompressed)
- **Historical (compressed)**: ~1.5GB/year
- **5-year system**: ~8-10GB total

## Backup & Recovery

### Backup Strategy

#### Daily Incremental Backups
```sql
-- Backup recent data (last 24 hours)
pg_dump --format=custom \
        --compress=9 \
        --where="timestamp >= NOW() - INTERVAL '1 day'" \
        --table=radio_calls \
        --table=security_events \
        stable_squirrel
```

#### Weekly Full Backups
```sql
-- Complete database backup
pg_dump --format=custom \
        --compress=9 \
        --jobs=4 \
        stable_squirrel
```

#### Security Event Export (Compliance)
```sql
-- Export security events for compliance archival
COPY (
    SELECT event_id, timestamp, event_type, severity, 
           source_ip, source_system, description, metadata
    FROM security_events 
    WHERE timestamp >= '2024-01-01' AND timestamp < '2025-01-01'
) TO '/backup/security_events_2024.csv' WITH CSV HEADER;
```

## Security Considerations

### Database Security

#### Access Control
- **Application Database User**: Limited to INSERT/SELECT/UPDATE on data tables
- **Admin Database User**: Full access for maintenance and backup operations
- **Read-Only User**: For reporting and analytics (no access to sensitive metadata)

#### Audit Logging
- **PostgreSQL Audit**: Enable `log_statement = 'all'` for complete SQL audit trail
- **Connection Logging**: Log all database connections with source IP
- **Privilege Escalation Detection**: Monitor for unexpected GRANT/REVOKE operations

#### Data Encryption
- **Encryption at Rest**: Enable PostgreSQL transparent data encryption
- **Connection Encryption**: Require SSL/TLS for all database connections
- **Backup Encryption**: Encrypt all backup files with strong encryption

### Data Integrity

#### Immutable Audit Trail
```sql
-- Prevent modification of historical security events
CREATE POLICY security_events_immutable ON security_events
    FOR UPDATE TO application_user
    USING (timestamp >= NOW() - INTERVAL '1 hour');
```

#### Foreign Key Constraints
```sql
-- Ensure referential integrity between tables
ALTER TABLE transcriptions 
    ADD CONSTRAINT fk_transcription_call 
    FOREIGN KEY (call_id) REFERENCES radio_calls(call_id);

ALTER TABLE speaker_segments 
    ADD CONSTRAINT fk_segment_call 
    FOREIGN KEY (call_id) REFERENCES radio_calls(call_id);
```

## Monitoring & Maintenance

### Performance Monitoring

#### Key Metrics to Monitor
- **Insert Rate**: Calls/second and security events/second
- **Query Performance**: 95th percentile response times for common queries
- **Compression Ratio**: Storage efficiency of compressed chunks
- **Index Usage**: Ensure all indexes are being utilized effectively

#### TimescaleDB-Specific Monitoring
```sql
-- Monitor chunk compression status
SELECT 
    chunk_schema, chunk_name, 
    compression_status, 
    before_compression_total_bytes,
    after_compression_total_bytes
FROM timescaledb_information.chunks
ORDER BY before_compression_total_bytes DESC;

-- Monitor hypertable statistics
SELECT 
    hypertable_name,
    num_chunks,
    table_size,
    index_size,
    total_size
FROM timescaledb_information.hypertables;
```

### Maintenance Tasks

#### Daily Maintenance
- Monitor database size and growth rates
- Check for failed compression jobs
- Verify backup completion and integrity

#### Weekly Maintenance
- Analyze query performance and optimize slow queries
- Review security event patterns for anomalies
- Update table statistics for optimal query planning

#### Monthly Maintenance
- Full database integrity check
- Review and adjust retention policies
- Capacity planning based on growth trends

## Summary

The enhanced TimescaleDB schema provides:

- **Scalable Time-Series Storage**: Optimized for millions of radio calls and security events
- **Comprehensive Security Tracking**: Complete audit trail with source attribution
- **High-Performance Queries**: Optimized indexes for all common access patterns
- **Automated Optimization**: Compression and retention policies for cost-effective storage
- **Forensic Capabilities**: Complete traceability for security incident investigation
- **Compliance Ready**: Immutable audit trails with export capabilities

This database design ensures that Stable Squirrel can scale to handle large radio networks while providing enterprise-grade security monitoring and forensic capabilities.