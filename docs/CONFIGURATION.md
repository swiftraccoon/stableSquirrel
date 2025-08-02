# Configuration Reference

Complete reference for `config.yaml` settings in Stable Squirrel.

## Configuration File Structure

```yaml
# Database connection settings
database:
  host: "localhost"
  port: 5432
  database: "stable_squirrel"
  username: "stable_squirrel"
  password: "changeme"
  
  # Connection pooling for high throughput
  min_pool_size: 5
  max_pool_size: 20
  
  # Schema management
  create_tables: true
  enable_timescale: true

# Audio ingestion settings
ingestion:
  # Legacy single API key (deprecated)
  api_key: "your-api-key-here"
  
  # Enhanced multi-key system (recommended)
  api_keys:
    - key: "station-alpha-secure-key-2024"
      description: "Main SDR station with static IP"
      allowed_ips: ["192.168.1.100", "10.0.0.50"]
      allowed_systems: ["123", "456"]
    - key: "mobile-unit-beta-key"
      description: "Mobile SDR setup"
      # No IP restrictions for mobile units
  
  # Security policies
  track_upload_sources: true
  require_system_id: true
  enable_file_validation: true
  max_file_size_mb: 100
  max_uploads_per_minute: 60
  max_uploads_per_hour: 1000

# Transcription service settings
transcription:
  # WhisperX model configuration
  model_name: "large-v2"     # Options: tiny, base, small, medium, large, large-v2, large-v3
  device: "auto"             # Options: auto, cpu, cuda
  batch_size: 16
  enable_diarization: true
  language: null             # Auto-detect, or specify: "en", "es", "fr", etc.
  
  # Performance optimization
  queue_size: 10000          # Maximum transcription queue size
  num_workers: 4             # Number of background workers
  max_file_size_mb: 100      # Maximum audio file size
  cleanup_interval_minutes: 5
  
  # Advanced model settings
  compute_type: "auto"       # float16 for GPU, int8 for CPU
  chunk_length: 30           # Audio chunk length for processing
  use_pipeline_cache: true

# Web interface settings
web:
  cors_origins: ["*"]        # CORS allowed origins
  enable_docs: true          # Enable /docs endpoint

# Alerting configuration
alerting:
  enable_notifications: false
  # Add webhook URLs, email settings, etc.
```

## Environment Variables

You can override any configuration using environment variables with the prefix `STABLE_SQUIRREL_`:

```bash
# Database settings
export STABLE_SQUIRREL_DATABASE_HOST="production-db.example.com"
export STABLE_SQUIRREL_DATABASE_PASSWORD="secure-production-password"

# API key
export STABLE_SQUIRREL_INGESTION_API_KEY="production-api-key"

# Transcription settings  
export STABLE_SQUIRREL_TRANSCRIPTION_MODEL_NAME="base"
export STABLE_SQUIRREL_TRANSCRIPTION_DEVICE="cpu"
```

## Configuration Validation

Stable Squirrel validates configuration on startup and will refuse to start with invalid settings.

### Required Settings

- **Database connection**: `database.host`, `database.database`, `database.username`, `database.password`
- **Either**: `ingestion.api_key` OR `ingestion.api_keys` (can be empty for development)

### Development vs Production

#### Development Example

```yaml
database:
  host: "localhost"
  password: "changeme"
  
ingestion:
  api_key: "dev-key"
  track_upload_sources: false
  
transcription:
  model_name: "base"  # Smaller, faster model
  device: "cpu"
  num_workers: 2
```

#### Production Example

```yaml
database:
  host: "prod-timescaledb.internal"
  password: "${STABLE_SQUIRREL_DATABASE_PASSWORD}"
  max_pool_size: 50
  
ingestion:
  api_keys:
    - key: "${STATION_ALPHA_API_KEY}"
      description: "Primary monitoring station"
      allowed_ips: ["10.0.1.100"]
      allowed_systems: ["100", "101", "102"]
  track_upload_sources: true
  max_uploads_per_minute: 100
  
transcription:
  model_name: "large-v2"  # Best accuracy
  device: "cuda"
  num_workers: 8
  queue_size: 50000
```

## Performance Tuning

### High Volume Scenarios

```yaml
database:
  max_pool_size: 50          # More DB connections
  
ingestion:
  max_uploads_per_minute: 200  # Higher rate limits
  
transcription:
  queue_size: 50000          # Larger queue
  num_workers: 16            # More workers (GPU recommended)
  batch_size: 32             # Larger batches for GPU
```

### Resource Constrained

```yaml
transcription:
  model_name: "base"         # Smaller model
  device: "cpu"
  num_workers: 2             # Fewer workers
  batch_size: 8              # Smaller batches
  queue_size: 1000           # Smaller queue
```

## Security Configuration

### Multi-System Deployment

```yaml
ingestion:
  api_keys:
    # Fire department
    - key: "fd-station-primary-2024"
      allowed_systems: ["100", "101", "102"]
      allowed_ips: ["192.168.1.100"]
    
    # Police department  
    - key: "pd-station-primary-2024"
      allowed_systems: ["200", "201"]
      allowed_ips: ["192.168.2.100"]
    
    # Emergency services mobile
    - key: "mobile-emergency-2024"
      allowed_systems: ["300"]
      # No IP restrictions for mobile
```

### Development/Testing

```yaml
ingestion:
  api_key: "dev-test-key"
  track_upload_sources: false
  enable_file_validation: false
```

## Troubleshooting Configuration

### Common Issues

1. **"Database connection failed"**
   - Check `database.host` and `database.port`
   - Verify TimescaleDB is running
   - Test connection: `psql -h HOST -p PORT -U USERNAME -d DATABASE`

2. **"Invalid API key" from SDRTrunk**
   - Verify `ingestion.api_key` matches SDRTrunk configuration
   - Check `allowed_ips` if using enhanced keys
   - Check `allowed_systems` matches SDRTrunk system ID

3. **"WhisperX model failed to load"**
   - GPU models require CUDA installation
   - Try `device: "cpu"` for CPU-only setups
   - Smaller models (`base`, `small`) require less memory

4. **High memory usage**
   - Reduce `transcription.batch_size`
   - Reduce `transcription.num_workers`
   - Use smaller model (`base` instead of `large-v2`)

### Validation Commands

```bash
# Test database connection
python -c "
import asyncio
from stable_squirrel.config import Config
from stable_squirrel.database import DatabaseManager

async def test():
    config = Config()
    db = DatabaseManager(config.database)
    await db.initialize()
    print('✅ Database connection successful')
    await db.close()

asyncio.run(test())
"

# Test configuration loading
python -c "
from stable_squirrel.config import Config
config = Config()
print('✅ Configuration loaded successfully')
print(f'Database: {config.database.host}:{config.database.port}')
print(f'Model: {config.transcription.model_name}')
"
```
