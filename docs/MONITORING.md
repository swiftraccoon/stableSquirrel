# Monitoring & Troubleshooting Guide

This guide covers monitoring, health checks, performance metrics, and troubleshooting for Stable Squirrel deployments.

## Health Monitoring

### System Health Endpoint

```bash
# Check overall system health
curl http://localhost:8000/api/system-health

# Example healthy response:
{
  "status": "healthy",
  "database": {
    "healthy": true,
    "pool_stats": {
      "status": "active",
      "size": 5,
      "max_size": 20,
      "idle_connections": 3
    }
  },
  "task_queue": {
    "status": "healthy", 
    "queue_size": 12,
    "workers_running": 4,
    "total_processed": 1543
  },
  "timestamp": 1704067200
}
```

### Performance Metrics

```bash
# Get detailed performance metrics
curl http://localhost:8000/api/queue-stats

# Example response:
{
  "queue_size": 12,
  "retry_queue_size": 0,
  "active_tasks": 4,
  "completed_tasks": 1543,
  "failed_tasks": 7,
  "workers_running": 4,
  "is_running": true,
  "total_enqueued": 1550,
  "total_processed": 1543,
  "success_rate": 0.995,
  "average_processing_time": 23.4,
  "processing_rate": 2.1
}
```

## Application Logs

### Log Levels and Formats

Stable Squirrel uses structured logging with these levels:

- **DEBUG**: Detailed execution flow (development only)
- **INFO**: Normal operation events (uploads, completions)
- **WARNING**: Potential issues (queue full, slow requests)
- **ERROR**: Operation failures (transcription errors)
- **CRITICAL**: System failures (database down, service crash)

### Key Log Messages

#### Normal Operation

```log
INFO - Starting transcription service...
INFO - Task queue started for background transcription processing
INFO - === RdioScanner API Call Received ===
INFO - Received call: system=100, talkgroup=1001, frequency=460250000
INFO - Enqueued transcription task abc-123 for call def-456
INFO - Processing queued transcription for call def-456
INFO - Queued transcription completed for call def-456
```

#### Performance Issues

```log
WARNING - Slow request: POST /api/call-upload took 2.341s
WARNING - Task queue full, processing immediately: Queue is full (10000 tasks)
ERROR - Worker worker-1 error: CUDA out of memory
ERROR - Task abc-123 failed: Audio file not found: /tmp/upload_xyz.mp3
```

#### System Issues

```log
CRITICAL - Failed to initialize database: connection refused
CRITICAL - WhisperX model failed to load: No such file or directory
ERROR - Database health check failed: server closed the connection
```

## Monitoring Dashboards

### Key Metrics to Track

1. **Upload Performance**
   - Requests per second
   - Average response time
   - Success rate (should be >99%)

2. **Transcription Performance**
   - Queue depth (should stay <50% of max)
   - Processing rate (calls/minute)
   - Average processing time
   - Worker utilization

3. **Database Performance**
   - Connection pool usage
   - Query response times
   - Storage growth rate

4. **System Resources**
   - CPU usage (transcription workers)
   - Memory usage (models + queue)
   - Disk usage (audio files + database)
   - GPU utilization (if using CUDA)

### Grafana Dashboard Example

```yaml
# Example Prometheus metrics (if implemented)
# stable_squirrel_uploads_total
# stable_squirrel_uploads_duration_seconds
# stable_squirrel_queue_size
# stable_squirrel_transcription_duration_seconds
# stable_squirrel_database_connections_active
```

## Common Issues & Solutions

### Database Issues

#### "Connection refused"

```bash
# Check if services are running
podman-compose ps

# Check database health
podman-compose exec timescaledb pg_isready -U stable_squirrel

# Check logs
podman-compose logs timescaledb

# For native PostgreSQL
systemctl status postgresql
journalctl -u postgresql

# Test connection manually
psql -h localhost -p 5432 -U stable_squirrel -d stable_squirrel
```

#### "Too many connections"

```bash
# Check current connections
SELECT count(*) FROM pg_stat_activity;

# Increase max_connections in postgresql.conf
# Or reduce max_pool_size in config.yaml
```

#### "Database health check failed"

```bash
# Check database load
SELECT * FROM pg_stat_activity WHERE state = 'active';

# Check for long-running queries
SELECT pid, query_start, query FROM pg_stat_activity 
WHERE query_start < NOW() - INTERVAL '1 minute';
```

### Transcription Issues

#### "WhisperX model failed to load"

```bash
# Check available disk space
df -h

# For GPU models, check CUDA
nvidia-smi

# Try smaller model in config.yaml
transcription:
  model_name: "base"  # Instead of "large-v2"
  device: "cpu"       # Instead of "cuda"
```

#### "CUDA out of memory"

```bash
# Reduce batch size
transcription:
  batch_size: 8       # Instead of 16
  
# Or reduce workers
transcription:
  num_workers: 2      # Instead of 4
```

#### "Task queue full"

```bash
# Increase queue size
transcription:
  queue_size: 20000   # Instead of 10000
  
# Or add more workers
transcription:
  num_workers: 8      # More parallel processing
```

### Upload Issues

#### SDRTrunk "Upload failed"

```bash
# Test API endpoint manually
curl -X POST http://localhost:8000/api/call-upload \
  -F "key=your-api-key" \
  -F "system=100" \
  -F "test=1"

# Should return: "incomplete call data: no talkgroup"

# Check API key configuration
# Check allowed_ips if using enhanced keys
# Check allowed_systems matches SDRTrunk system ID
```

#### "Invalid API key"

```bash
# Verify key in logs
grep "Invalid API key" /var/log/stable-squirrel.log

# Check enhanced key restrictions
# IP address might not be in allowed_ips
# System ID might not be in allowed_systems
```

#### High latency uploads

```bash
# Check response times
curl -w "%{time_total}" http://localhost:8000/api/call-upload ...

# Should be <0.1s typically
# Check for:
# - Database connection issues
# - Full transcription queue  
# - Disk space issues
# - High CPU/memory usage
```

### Performance Issues

#### Slow transcription processing

```bash
# Check worker utilization
curl http://localhost:8000/api/queue-stats | jq '.workers_running'

# Check processing times
# Should be 15-45 seconds per call depending on model/hardware

# Solutions:
# - Add more workers (if CPU/GPU allows)
# - Use faster model (base vs large-v2) 
# - Increase batch_size (GPU only)
```

#### High memory usage

```bash
# Check memory per process
ps aux | grep python | grep stable_squirrel

# Common causes:
# - Too many workers for available RAM
# - Large model (large-v2 uses ~6GB)
# - Memory leaks (temp files not cleaned)

# Solutions:
# - Reduce num_workers
# - Use smaller model  
# - Monitor temp file cleanup
```

#### Database growing too fast

```bash
# Check table sizes
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

# Enable compression for old data (TimescaleDB)
SELECT add_compression_policy('radio_calls', INTERVAL '7 days');
```

## Alerting

### Critical Alerts

1. **Service Down**
   - HTTP health check fails
   - Process not responding

2. **Database Issues**
   - Connection failures
   - High connection usage (>80%)
   - Slow queries (>5 seconds)

3. **Queue Issues**
   - Queue near full (>90%)
   - High failure rate (>5%)
   - Workers not processing

### Warning Alerts

1. **Performance Degradation**
   - Upload latency >1 second
   - Transcription taking >60 seconds
   - Memory usage >80%

2. **Resource Issues**
   - Disk usage >85%
   - CPU usage >90% sustained
   - GPU memory >90%

### Example Alert Configuration

```yaml
# Example Prometheus alerting rules
groups:
- name: stable-squirrel
  rules:
  - alert: StableSquirrelDown
    expr: up{job="stable-squirrel"} == 0
    for: 1m
    
  - alert: TranscriptionQueueFull
    expr: stable_squirrel_queue_size > 9000
    for: 5m
    
  - alert: HighUploadLatency  
    expr: stable_squirrel_upload_duration_p95 > 1
    for: 2m
```

## Debugging Tools

### Debug Mode

```bash
# Enable debug logging
STABLE_SQUIRREL_LOG_LEVEL=DEBUG python -m stable_squirrel

# More verbose output for troubleshooting
```

### Performance Profiling

```bash
# Profile with py-spy (install: pip install py-spy)
py-spy record -o profile.svg -d 60 -p $(pgrep -f stable_squirrel)

# Analyze memory usage
py-spy dump -p $(pgrep -f stable_squirrel)
```

### Database Queries

```sql
-- Check recent uploads
SELECT timestamp, system_label, talkgroup_label, transcription_status 
FROM radio_calls 
ORDER BY timestamp DESC 
LIMIT 10;

-- Check transcription queue status
SELECT transcription_status, COUNT(*) 
FROM radio_calls 
GROUP BY transcription_status;

-- Check security events
SELECT timestamp, event_type, severity, source_ip 
FROM security_events 
ORDER BY timestamp DESC 
LIMIT 10;
```
