# CLAUDE.md

**CRITICAL: This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. ALWAYS follow these rules to avoid incorrect assumptions.**

## Project Overview

Stable Squirrel is an SDR audio transcription and security monitoring system that integrates with SDRTrunk via the RdioScanner HTTP API. Built with Python 3.12+, FastAPI, TimescaleDB, and WhisperX.

## Essential Development Commands

### Environment Setup (ALWAYS activate venv first)
```bash
source .venv/bin/activate  # Required before ANY operation
```

### Package Management (use `uv`, NEVER use pip)
```bash
uv add package-name        # Add production dependency
uv add --dev package-name  # Add development dependency
```

### Code Quality (ALWAYS run with --fix)
```bash
make format               # Run black, isort, ruff --fix
make lint                 # Run ruff check and mypy
ruff check --fix src/ tests/  # Quick fix linting issues
```

### Testing
```bash
make test                 # Run all tests
make test-cov            # Run with coverage
python -m pytest tests/test_rdioscanner_api.py tests/test_security_validation.py -v  # Priority tests
```

### Running
```bash
make run                  # Standard run
make run-dev             # Development mode with DEBUG
make db-dev              # Start TimescaleDB container
```

## Architecture Overview

### Layered Enterprise Architecture

1. **API Layer** (`src/stable_squirrel/web/`)
   - FastAPI with router-based organization
   - RdioScanner endpoint: `/api/call-upload` (DO NOT change this path)
   - Separate routers: health, api, security, rdioscanner

2. **Security Layer** (`src/stable_squirrel/security/`)
   - Multi-factor authentication with IP restrictions
   - Malicious content detection and file validation
   - Audit logging and forensics

3. **Service Layer** (`src/stable_squirrel/services/`)
   - Asynchronous WhisperX transcription with task queues
   - Rate limiting with database-backed enforcement
   - Background job processing

4. **Data Layer** (`src/stable_squirrel/database/`)
   - TimescaleDB (PostgreSQL with time-series extensions)
   - Connection pooling for high throughput
   - Pydantic models for type-safe operations

### Key Design Patterns
- Dependency Injection via FastAPI
- Repository Pattern for database operations
- Command Pattern for async task processing
- Configuration via YAML with Pydantic validation

## Critical Development Rules

### NEVER MAKE ASSUMPTIONS
- **ALWAYS check the codebase** when unsure about implementation details
- **NEVER assume** libraries, patterns, or conventions without verification
- **READ existing files** before suggesting changes or additions
- **ASK the user** if you cannot find the answer in the codebase
- **VERIFY configuration** by checking config.yaml.example and actual code

### Before ANY Code Changes
1. **Check existing patterns** in neighboring files
2. **Verify imports** and available libraries in package files
3. **Read configuration** to understand what's actually implemented
4. **Test your assumptions** by searching the codebase
5. **ASK if uncertain** rather than guessing

### Audio Processing
- **ONLY accept MP3 files** - SDRTrunk only sends MP3
- Do NOT add support for WAV, M4A, FLAC, OGG, AAC, etc.
- Maintain conservative file validation

### API Standards
- RdioScanner endpoint MUST remain `/api/call-upload`
- Maintain SDRTrunk compatibility
- Return appropriate HTTP status codes (401, 400, 422)

### Security Requirements
- Multi-layered file validation is mandatory
- Reject questionable files rather than allow
- Maintain complete audit trails
- All security tests MUST pass before changes

### Database
- Use TimescaleDB for all time-series data
- Do NOT suggest SQLite for production
- Maintain Pydantic model validation

## Testing Priorities

1. **RdioScanner API tests** - Core functionality
2. **Security validation tests** - File validation, auth
3. **Transcription tests** - WhisperX processing
4. **Database tests** - TimescaleDB operations

## Configuration

### IMPORTANT: Configuration Approach
- **ALWAYS use YAML configuration files** (NOT environment variables)
- **NEVER use `os.getenv()`** - this project uses YAML exclusively
- **CHECK `config.py`** for actual supported configuration fields
- **VERIFY in `config.yaml.example`** for configuration structure

Main config file: `config.yaml` (see `config.yaml.example`)
- Database settings (TimescaleDB required)
- WhisperX model configuration
- Security settings (API keys, rate limits)
- Transcription settings

## Common Tasks

### Before Starting ANY Task
1. **SEARCH the codebase** for existing implementations
2. **READ relevant files** to understand current patterns
3. **CHECK dependencies** in pyproject.toml before importing
4. **ASK the user** if implementation approach is unclear

### Adding a new API endpoint
1. **FIRST check existing routers** for patterns and conventions
2. Create router in `src/stable_squirrel/web/`
3. Add to `create_app()` in `src/stable_squirrel/web/app.py`
4. Add tests in `tests/`
5. Update API documentation

### Modifying security rules
1. Update validation in `src/stable_squirrel/security/`
2. Add tests
3. Update security documentation
4. Ensure all existing security tests pass

### Database schema changes
1. Update models in `src/stable_squirrel/database/models.py`
2. Update table creation in `src/stable_squirrel/database/setup.py`
3. Consider TimescaleDB hypertables for time-series data
4. Test with production-scale data

## Documentation Structure

- `docs/SYSTEM_DESIGN_SPEC.md` - Complete architectural specification
- `docs/SECURITY.md` - Security features and procedures
- `docs/RDIOSCANNER_API.md` - SDRTrunk integration details
- `docs/DATABASE_DESIGN.md` - TimescaleDB schema
- `docs/DEPLOYMENT.md` - Production deployment guide

## Final Reminders

### ALWAYS REMEMBER
1. **NEVER assume** - Always verify in the codebase
2. **READ before writing** - Check existing implementations first
3. **ASK when uncertain** - Better to ask than guess wrong
4. **CHECK configuration approach** - YAML files, not environment variables
5. **VERIFY libraries exist** - Check pyproject.toml before importing
6. **FOLLOW existing patterns** - Maintain consistency with current code

### When In Doubt
- Search the codebase with grep/rg
- Read related files thoroughly
- Check test files for usage examples
- Ask the user for clarification

**Your assumptions can break the system. Always verify!**