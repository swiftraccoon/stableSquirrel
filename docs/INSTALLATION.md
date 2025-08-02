# Installation Guide

Complete installation instructions for Stable Squirrel across different environments.

## Prerequisites

- **Python 3.12+** with `uv` package manager
- **Podman** for containerized deployment
- **TimescaleDB** (PostgreSQL with time-series extension)

## Installation Methods

### Method 1: Podman Compose (Recommended)

Complete containerized setup with all dependencies:

```bash
# Clone repository
git clone https://github.com/swiftraccoon/stableSquirrel.git
cd stableSquirrel

# Start all services
make podman-compose

# Services will be available at:
# - Stable Squirrel: http://localhost:8000
# - TimescaleDB: localhost:5432
```

This starts both TimescaleDB and Stable Squirrel with proper networking, health checks, and persistence.

### Method 2: Development Setup

For development with external database or live code changes:

```bash
# Install Python dependencies
make install-dev

# Start development database (optional)
make db-dev

# Configure application
cp config.yaml.example config.yaml
# Edit config.yaml with your settings

# Run with hot reload
make run-dev
```

### Method 3: Production Systemd Service

For production deployment on Linux servers:

```bash
# Install system service
make install-systemd

# Configure
sudo mkdir -p /etc/stable-squirrel
sudo cp config.yaml.example /etc/stable-squirrel/config.yaml
sudo nano /etc/stable-squirrel/config.yaml

# Enable and start
sudo systemctl enable --now stable-squirrel.service

# Check status
sudo systemctl status stable-squirrel
```

## Database Setup

### Option 1: Containerized TimescaleDB (Recommended)

The `podman-compose.yaml` includes a pre-configured TimescaleDB instance:

```yaml
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      - POSTGRES_DB=stable_squirrel
      - POSTGRES_USER=stable_squirrel
      - POSTGRES_PASSWORD=changeme
    volumes:
      - timescaledb-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
```

### Option 2: Native TimescaleDB Installation

#### Ubuntu/Debian

```bash
# Add TimescaleDB repository
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/timescaledb.list
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -

# Install TimescaleDB
sudo apt update
sudo apt install timescaledb-2-postgresql-15

# Setup database
sudo -u postgres createdb stable_squirrel
sudo -u postgres psql -d stable_squirrel -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Create user
sudo -u postgres psql -c "CREATE USER stable_squirrel WITH PASSWORD 'your-password-here';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE stable_squirrel TO stable_squirrel;"
```

#### RHEL/CentOS/Fedora

```bash
# Add repository
sudo tee /etc/yum.repos.d/timescaledb.repo <<EOL
[timescaledb]
name=TimescaleDB
baseurl=https://packagecloud.io/timescale/timescaledb/el/7/x86_64
gpgcheck=1
enabled=1
gpgkey=https://packagecloud.io/timescale/timescaledb/gpgkey
EOL

# Install
sudo dnf install timescaledb-2-postgresql-15

# Setup database (same as Ubuntu)
```

### Option 3: Cloud TimescaleDB

For production deployments, consider hosted TimescaleDB:

- **Timescale Cloud**: Fully managed TimescaleDB
- **AWS RDS with TimescaleDB**: Self-managed on AWS
- **Azure Database with TimescaleDB**: Self-managed on Azure

Update `config.yaml` with your cloud database credentials:

```yaml
database:
  host: "your-cloud-db.timescale.com"
  port: 5432
  database: "stable_squirrel"
  username: "your-username"
  password: "${DATABASE_PASSWORD}"  # Use environment variable
  
  # Production settings
  max_pool_size: 50
  min_pool_size: 10
```

## Dependencies

### Python Dependencies

Managed automatically by `uv` and defined in `pyproject.toml`:

**Core Dependencies:**

- `fastapi` - Web framework
- `asyncpg` - PostgreSQL async driver
- `pydantic` - Data validation
- `whisperx` - Speech transcription
- `uvicorn` - ASGI server

**Development Dependencies:**

- `pytest` - Testing framework
- `black` - Code formatting
- `ruff` - Linting
- `mypy` - Type checking

### System Dependencies

**For containerized deployment:** None (handled by Containerfile)

**For native installation:**

```bash
# Ubuntu/Debian
sudo apt install python3.12 python3.12-venv git ffmpeg curl

# RHEL/CentOS/Fedora  
sudo dnf install python3.12 python3.12-venv git ffmpeg curl

# macOS
brew install python@3.12 ffmpeg
```

### GPU Support (Optional)

For GPU-accelerated transcription with CUDA:

```bash
# Install CUDA toolkit (version 11.8+ recommended)
# Follow NVIDIA's installation guide for your OS

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Update config for GPU usage
transcription:
  device: "cuda"
  compute_type: "float16"
  batch_size: 32
```

## Verification

### Quick Health Check

```bash
# Check service status
curl http://localhost:8000/api/system-health

# Expected response:
{
  "status": "healthy",
  "database": {"healthy": true},
  "task_queue": {"status": "healthy"},
  "timestamp": 1704067200
}
```

### Test RdioScanner Endpoint

```bash
# Test API endpoint (should return test message)
curl -X POST http://localhost:8000/api/call-upload \
  -F "key=your-api-key" \
  -F "system=100" \
  -F "test=1"

# Expected: "incomplete call data: no talkgroup"
```

### Database Connection Test

```bash
# Test database connection
psql -h localhost -p 5432 -U stable_squirrel -d stable_squirrel -c "SELECT version();"

# Should show TimescaleDB version info
```

## Troubleshooting

### Common Installation Issues

1. **"uv command not found"**

   ```bash
   pip install uv
   ```

2. **"Permission denied" on systemd install**

   ```bash
   # Requires sudo for system service installation
   sudo make install-systemd
   ```

3. **TimescaleDB extension not found**

   ```bash
   # Enable TimescaleDB extension
   sudo -u postgres psql -d stable_squirrel -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
   ```

4. **Podman permission issues**

   ```bash
   # Enable rootless podman
   sudo usermod -aG podman $USER
   newgrp podman
   ```

5. **Port 5432 already in use**

   ```bash
   # Check what's using the port
   sudo netstat -tulpn | grep 5432
   
   # Stop conflicting PostgreSQL
   sudo systemctl stop postgresql
   ```

### Getting Help

- **Check logs**: `podman-compose logs` or `sudo journalctl -u stable-squirrel`
- **Validate config**: `python -c "from stable_squirrel.config import Config; Config()"`
- **Test components**: Use the monitoring endpoints in [MONITORING.md](MONITORING.md)

## Next Steps

After successful installation:

1. **[Configure SDRTrunk integration](QUICK_START.md#configure-sdrtrunk)**
2. **[Set up security policies](SECURITY_GUIDE.md)**
3. **[Optimize for your workload](PERFORMANCE.md)**
4. **[Set up monitoring](MONITORING.md)**
