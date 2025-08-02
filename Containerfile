# Containerfile for Stable Squirrel
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Create non-root user
RUN useradd --create-home --shell /bin/bash stable-squirrel

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ src/
COPY README.md ./

# Install dependencies
RUN uv pip install --system -e .

# Switch to non-root user
USER stable-squirrel

# Create config directory
RUN mkdir -p /home/stable-squirrel/.config/stable-squirrel

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "stable_squirrel", "--host", "0.0.0.0", "--port", "8000"]