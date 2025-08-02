# RdioScanner API Performance Optimization Guide

## 🔍 Identified Performance Issues

### **1. Database Connection Management**

**Problem**: Connection pool exhaustion under high load

- Current pool size limits aren't enforced properly
- Missing connection lifecycle management
- No circuit breaker for database failures

**Solutions**:

```python
# In config.py - add connection pool monitoring
@dataclass
class DatabaseConfig:
    max_pool_size: int = 20
    min_pool_size: int = 5
    pool_timeout: float = 30.0
    connection_retry_attempts: int = 3
    circuit_breaker_threshold: int = 10  # failures before opening circuit
```

### **2. Memory Management Issues**

**Problem**: Memory leaks from temp files and audio processing

- Temp files not always cleaned up
- Full audio files loaded into memory
- No memory usage monitoring

**Solutions**:

```python
# Stream-based audio processing
async def process_audio_stream(audio_file, chunk_size=8192):
    """Process audio in chunks to reduce memory usage."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        try:
            async for chunk in audio_file.stream():
                temp_file.write(chunk)
            temp_file.flush()
            yield temp_file.name
        finally:
            os.unlink(temp_file.name)
```

### **3. Synchronous Bottlenecks**

**Problem**: Blocking operations in async context

- File I/O operations block event loop
- Database operations can block under load
- No async queue for transcription processing

**Solutions**:

```python
# Async file operations
import aiofiles

async def save_audio_file_async(audio_content: bytes, file_path: Path):
    """Save audio file asynchronously."""
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(audio_content)
```

## 🚀 Recommended Performance Improvements

### **1. Implement Request Queuing**

```python
# Queue-based processing for high-throughput scenarios
import asyncio
from asyncio import Queue

class UploadQueue:
    def __init__(self, max_size: int = 1000, workers: int = 10):
        self.queue = Queue(maxsize=max_size)
        self.workers = workers
        self.running = False
    
    async def start_workers(self):
        """Start background worker tasks."""
        self.running = True
        for i in range(self.workers):
            asyncio.create_task(self._worker(f"worker-{i}"))
    
    async def _worker(self, name: str):
        """Background worker to process uploads."""
        while self.running:
            try:
                upload_data = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
                await self._process_upload(upload_data)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {name} error: {e}")
```

### **2. Enhanced Rate Limiting**

```python
# Distributed rate limiting with Redis
class DistributedRateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Check if request is within rate limit."""
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, window)
        return current <= limit
```

### **3. Connection Pool Optimization**

```python
# Enhanced database configuration
DATABASE_CONFIG = {
    "min_pool_size": 5,
    "max_pool_size": 20,
    "max_queries": 50000,  # Queries per connection before refresh
    "max_inactive_connection_lifetime": 300,  # 5 minutes
    "pool_pre_ping": True,  # Test connections before use
    "pool_recycle": 3600,  # Recycle connections every hour
}
```

### **4. Background Task Processing**

```python
# Celery-style background processing
import asyncio
from typing import Callable

class BackgroundTaskManager:
    def __init__(self):
        self.task_queue = asyncio.Queue()
        self.workers = []
    
    async def enqueue_transcription(self, audio_path: Path, call_data: dict):
        """Queue transcription for background processing."""
        await self.task_queue.put({
            'type': 'transcription',
            'audio_path': audio_path,
            'call_data': call_data
        })
    
    async def start_workers(self, num_workers: int = 4):
        """Start background workers."""
        for i in range(num_workers):
            worker = asyncio.create_task(self._background_worker(i))
            self.workers.append(worker)
```

## 🎯 Stress Test Integration

### **Usage Instructions**

```bash
# Basic stress test
source .venv/bin/activate
python tests/stress_test_rdioscanner.py --max-concurrent 25 --duration 60

# High-load test
python tests/stress_test_rdioscanner.py --max-concurrent 100 --duration 300 --url http://localhost:8000

# Development testing
python tests/stress_test_rdioscanner.py --max-concurrent 10 --duration 30 --api-key "your-dev-key"
```

### **Interpreting Results**

- **Success Rate > 95%**: API handling load well
- **Success Rate 90-95%**: Monitor for improvements needed
- **Success Rate < 90%**: Performance issues require attention

**Key Metrics to Monitor**:

- Average response time (should be < 1s for upload acceptance)
- 95th percentile response time (should be < 3s)
- Memory usage (should stabilize, not grow continuously)
- Error patterns (timeouts vs HTTP errors vs connection failures)

## 🔧 Implementation Priority

### **Phase 1: Critical Fixes (Immediate)**

1. Fix database connection pool management
2. Implement proper temp file cleanup
3. Add transaction rollback for failed operations

### **Phase 2: Performance Improvements (1-2 weeks)**

1. Stream-based audio processing
2. Background task queue implementation
3. Enhanced rate limiting

### **Phase 3: Advanced Optimizations (1-2 months)**

1. Connection pooling optimization
2. Distributed caching
3. Advanced monitoring and alerting

## 🔍 Monitoring & Alerting

### **Key Performance Indicators**

```python
# Metrics to track
PERFORMANCE_METRICS = {
    "upload_rate": "uploads per second",
    "avg_response_time": "average API response time",
    "db_connection_pool_usage": "% of connections in use",
    "memory_usage": "RSS memory usage",
    "transcription_queue_depth": "pending transcriptions",
    "error_rate": "% of failed requests",
    "disk_usage": "storage space for audio files"
}
```

### **Alert Thresholds**

- **High**: Error rate > 5%, Response time > 2s, Memory growth > 10MB/hour
- **Critical**: Error rate > 15%, Response time > 5s, Disk space < 1GB

This optimization guide should be implemented alongside regular stress testing to ensure the API can handle production loads reliably.
