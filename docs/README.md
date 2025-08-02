# Stable Squirrel Documentation

## Overview

Stable Squirrel is a high-performance SDR audio ingestion and transcription system that integrates with SDRTrunk via the RdioScanner API. It processes radio calls in real-time with WhisperX transcription, speaker diarization, and comprehensive security monitoring.

## Key Features

- **High-throughput ingestion** - Handles unlimited concurrent uploads from SDRTrunk
- **Background transcription** - Queue-based processing with WhisperX and speaker diarization  
- **Enterprise security** - Multi-layered validation, source tracking, and audit trails
- **TimescaleDB storage** - Optimized for millions of radio calls with time-series queries
- **Real-time monitoring** - Performance metrics and health monitoring

## Documentation Structure

### Getting Started

- **[Quick Start Guide](QUICK_START.md)** - Get up and running in 15 minutes
- **[Installation Guide](INSTALLATION.md)** - Detailed setup instructions for all deployment methods
- **[Configuration Reference](CONFIGURATION.md)** - Complete config.yaml documentation

### Core Components  

- **[API Reference](API_REFERENCE.md)** - Complete API documentation including RdioScanner endpoint
- **[Database Schema](DATABASE_SCHEMA.md)** - TimescaleDB tables, indexes, and optimization
- **[Security Guide](SECURITY_GUIDE.md)** - Authentication, validation, and monitoring

### Operations

- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment options
- **[Performance Tuning](PERFORMANCE.md)** - Optimization for high-volume scenarios
- **[Monitoring & Troubleshooting](MONITORING.md)** - Health checks, metrics, and debugging

### Development

- **[Architecture Overview](ARCHITECTURE.md)** - System design and component interaction
- **[Contributing Guide](CONTRIBUTING.md)** - Development setup and guidelines

## Quick Links

- **SDRTrunk Integration**: See [API Reference - RdioScanner Endpoint](API_REFERENCE.md#rdioscanner-endpoint)
- **Security Configuration**: See [Security Guide - API Keys](SECURITY_GUIDE.md#api-key-configuration)
- **Performance Tuning**: See [Performance Guide - High Volume](PERFORMANCE.md#high-volume-optimization)
- **Troubleshooting**: See [Monitoring Guide - Common Issues](MONITORING.md#common-issues)

## Support

- **Issues**: [GitHub Issues](https://github.com/swiftraccoon/stableSquirrel/issues)
- **Discussions**: [GitHub Discussions](https://github.com/swiftraccoon/stableSquirrel/discussions)
- **Security**: Report security issues privately via [GitHub Security Advisories](https://github.com/swiftraccoon/stableSquirrel/security/advisories)
