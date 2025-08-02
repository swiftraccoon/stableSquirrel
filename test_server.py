#!/usr/bin/env python3
"""Quick test server for RdioScanner API without database setup."""

import asyncio
import logging
import sys
from unittest.mock import AsyncMock

import uvicorn
from fastapi import FastAPI

from stable_squirrel.config import Config
from stable_squirrel.web.routes.rdioscanner import router

# Setup logging to both console and file
from datetime import datetime
log_filename = f"test_server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create handlers
file_handler = logging.FileHandler(log_filename)
console_handler = logging.StreamHandler(sys.stdout)

# Set format
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler],
)

# Reduce verbosity for specific loggers
logging.getLogger("stable_squirrel.web.routes.rdioscanner").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def create_test_app():
    """Create a minimal FastAPI app for testing RdioScanner API."""
    app = FastAPI(
        title="Stable Squirrel - RdioScanner API Test",
        description="Quick test server for RdioScanner API endpoint",
        version="1.0.0",
    )
    
    # Include just the RdioScanner router
    app.include_router(router, tags=["rdioscanner"])
    
    # Create mock configuration
    config = Config()
    config.ingestion.api_key = "test-stable-squirrel-2024"
    config.ingestion.enable_file_validation = True
    config.ingestion.max_file_size_mb = 50
    config.ingestion.max_uploads_per_minute = 20
    config.ingestion.max_uploads_per_hour = 200
    
    # Mock database and transcription service
    app.state.config = config
    app.state.db_manager = AsyncMock()
    app.state.transcription_service = AsyncMock()
    
    # Mock the process_rdioscanner_call function to simulate successful processing
    async def mock_process_call(upload_data, file_path, transcription_service):
        logger.info(f"MOCK: Processing call from system {upload_data.system}")
        logger.info(f"MOCK: Audio file: {upload_data.audio_filename}")
        logger.info(f"MOCK: Talkgroup: {upload_data.talkgroup}")
        logger.info(f"MOCK: Frequency: {upload_data.frequency}")
        logger.info(f"MOCK: File size: {upload_data.audio_size} bytes")
        
        # Simulate some processing time
        await asyncio.sleep(0.1)
        
        logger.info("MOCK: Call processed successfully!")
    
    # Replace the real function with our mock
    import stable_squirrel.web.routes.rdioscanner
    stable_squirrel.web.routes.rdioscanner.process_rdioscanner_call = mock_process_call
    
    @app.get("/")
    async def root():
        return {
            "message": "Stable Squirrel RdioScanner API Test Server",
            "rdioscanner_endpoint": "/api/call-upload",
            "api_key": config.ingestion.api_key,
            "security_enabled": config.ingestion.enable_file_validation,
        }
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": "testing"}
    
    return app

if __name__ == "__main__":
    app = create_test_app()
    
    logger.info("🚀 Starting Stable Squirrel RdioScanner API Test Server")
    logger.info(f"📋 Logging to file: {log_filename}")
    logger.info("📡 RdioScanner endpoint: http://0.0.0.0:8000/api/call-upload")
    logger.info("🔑 API Key: test-stable-squirrel-2024")
    logger.info("🌐 Server info: http://0.0.0.0:8000/")
    logger.info("❤️  Health check: http://0.0.0.0:8000/health")
    logger.info("")
    logger.info("🔧 Configure SDRTrunk RdioScanner with:")
    logger.info("   URL: http://YOUR_IP:8000/api/call-upload")
    logger.info("   API Key: test-stable-squirrel-2024")
    logger.info("")
    logger.info("Press Ctrl+C to stop")
    
    # Try Hypercorn instead of Uvicorn for better HTTP/2 support
    try:
        import hypercorn.asyncio
        import hypercorn.config
        import asyncio
        
        logger.info("Using Hypercorn server for better HTTP/2 support")
        
        config = hypercorn.config.Config()
        config.bind = ["0.0.0.0:8000"]
        config.application_path = "app"
        
        # Run with Hypercorn
        asyncio.run(hypercorn.asyncio.serve(app, config))
        
    except ImportError:
        logger.info("Hypercorn not available, falling back to Uvicorn with strict HTTP/1.1")
        
        # Fallback to uvicorn with more aggressive HTTP/1.1 enforcement
        import uvicorn
        uvicorn.run(
            app,
            host="0.0.0.0", 
            port=8000,
            log_config=None,
            loop="asyncio",
            http="h11",
            ws="none",  # Disable websockets 
            lifespan="off"  # Disable lifespan events
        )