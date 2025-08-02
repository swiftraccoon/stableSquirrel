#!/usr/bin/env python3
"""Entry point for stable-squirrel."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from stable_squirrel.config import load_config
from stable_squirrel.database import (
    DatabaseManager,
    create_schema,
    ensure_timescale_setup,
)
from stable_squirrel.services.transcription import TranscriptionService
from stable_squirrel.web.app import create_app

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("stable_squirrel.log"),
        ],
    )


async def main() -> None:
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Stable Squirrel SDR Transcription System")
    parser.add_argument(
        "--config",
        type=Path,
        default="config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind web server to (overrides config)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind web server to (overrides config)",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    logger.info("Starting Stable Squirrel...")

    # Load configuration
    config = load_config(args.config)

    # Initialize database
    db_manager = DatabaseManager(config.database)
    await db_manager.initialize()

    # Create database schema if needed
    if config.database.create_tables:
        await create_schema(db_manager)

        if config.database.enable_timescale:
            await ensure_timescale_setup(db_manager)

    # Initialize services
    transcription_service = TranscriptionService(config.transcription, db_manager)

    # Create web application (includes RdioScanner API endpoint)
    app = create_app(config, transcription_service, db_manager)

    # Start transcription service
    try:
        await transcription_service.start()

        # Use config values or command line overrides
        host = args.host or config.web.host
        port = args.port or config.web.port

        logger.info(f"Starting web server on {host}:{port}")
        logger.info(f"RdioScanner API available at: http://{host}:{port}/api/call-upload")

        # Start web server with Hypercorn for HTTP/2 support
        from hypercorn.asyncio import serve
        from hypercorn.config import Config as HypercornConfig

        hypercorn_config = HypercornConfig()
        hypercorn_config.application_path = "app"
        hypercorn_config.bind = [f"{host}:{port}"]
        hypercorn_config.use_reloader = False
        hypercorn_config.debug = False
        hypercorn_config.access_log_format = "%(h)s %(r)s %(s)s %(b)s %(D)s"

        await serve(app, hypercorn_config)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await asyncio.gather(
            transcription_service.stop(),
            db_manager.close(),
        )


if __name__ == "__main__":
    asyncio.run(main())
