# Production Deployment Guide

This document covers production deployment scenarios, from single-server setups to high-availability clusters.

## Prerequisites

### TimescaleDB Setup

Stable Squirrel requires **TimescaleDB** (PostgreSQL with time-series extension) for handling high-volume radio call data.

#### Option 1: Local Development (Podman)

```bash
# Use the provided podman-compose setup
podman-compose up -d timescaledb

# Or start all services
podman-compose up -d
```

#### Option 2: Production Installation

```bash
# Ubuntu/Debian
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/timescaledb.list
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
sudo apt update && sudo apt install timescaledb-2-postgresql-15

# Enable TimescaleDB extension
sudo -u postgres psql -c "CREATE DATABASE stable_squirrel;"
sudo -u postgres psql -d stable_squirrel -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

## Direct Execution

Install Python dependencies and run directly:

```bash
# Install uv if not already installed
pip install uv

# Install stable-squirrel
uv pip install -e ".[dev]"

# Create config
cp config.yaml.example config.yaml
# Edit config.yaml with your settings

# Run
python3 -m stable_squirrel --config config.yaml
```

## Systemd Service

For automatic startup on Linux systems:

```bash
# Create system user
sudo useradd --system --create-home --shell /bin/false stable-squirrel

# Install to /opt
sudo mkdir -p /opt/stable-squirrel
sudo chown stable-squirrel:stable-squirrel /opt/stable-squirrel

# Install as stable-squirrel user
sudo -u stable-squirrel bash -c '
  cd /opt/stable-squirrel
  python3 -m venv .venv
  source .venv/bin/activate
  pip install uv
  uv pip install stable-squirrel
'

# Create config directory
sudo mkdir -p /etc/stable-squirrel
sudo cp config.yaml.example /etc/stable-squirrel/config.yaml
sudo chown stable-squirrel:stable-squirrel /etc/stable-squirrel/config.yaml

# Install service file
sudo cp stable-squirrel.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable --now stable-squirrel.service

# Check status
sudo systemctl status stable-squirrel.service
```

## Podman Containers

Run the entire stack in rootless containers:

```bash
# Build image
podman build -t stable-squirrel .

# Run with podman-compose
podman-compose up -d

# Or run directly
podman run -d \
  --name stable-squirrel \
  -p 8000:8000 \
  -v ./config.yaml:/app/config.yaml:ro \
  -v ./recordings:/app/recordings:ro \
  stable-squirrel
```

The podman-compose setup includes:

- Rootless container execution
- Health checks
- Volume mounts for config and data
- Automatic restart policies
