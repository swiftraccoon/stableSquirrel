"""FastAPI web application."""

import time
from typing import TYPE_CHECKING, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from stable_squirrel.config import Config
from stable_squirrel.web.routes import api, health, rdioscanner, security

if TYPE_CHECKING:
    from stable_squirrel.database import DatabaseManager
    from stable_squirrel.services.transcription import TranscriptionService


def create_app(
    config: Config,
    transcription_service: "TranscriptionService",
    db_manager: "DatabaseManager",
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Stable Squirrel",
        description="SDR Audio Transcription and Search System",
        version="0.1.0",
        docs_url="/docs" if config.web.enable_docs else None,
        redoc_url="/redoc" if config.web.enable_docs else None,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.web.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store services in app state
    app.state.config = config
    app.state.transcription_service = transcription_service
    app.state.db_manager = db_manager

    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(api.router, prefix="/api/v1", tags=["api"])
    app.include_router(security.router, prefix="/api/v1/security", tags=["security"])
    app.include_router(rdioscanner.router, tags=["rdioscanner"])

    # Add performance monitoring endpoints
    @app.get("/api/system-health")
    async def get_system_health(request: Request) -> Dict:
        """Get comprehensive system health information."""
        try:
            db_manager = request.app.state.db_manager

            # Get database health
            db_healthy = await db_manager.health_check()
            db_stats = db_manager.get_pool_stats()

            # Get task queue health if available
            queue_health = {"status": "unavailable"}
            try:
                from stable_squirrel.services.task_queue import get_task_queue

                task_queue = get_task_queue()
                queue_stats = task_queue.get_queue_stats()

                # Simple health assessment
                if queue_stats["queue_size"] / max(queue_stats.get("max_queue_size", 1), 1) > 0.9:
                    queue_health = {"status": "warning", "reason": "queue nearly full"}
                else:
                    queue_health = {"status": "healthy"}

                queue_health.update(queue_stats)

            except RuntimeError:
                queue_health = {"status": "not_initialized"}

            # Overall system status
            if db_healthy and queue_health["status"] in ["healthy", "not_initialized"]:
                overall_status = "healthy"
            elif db_healthy:
                overall_status = "warning"
            else:
                overall_status = "unhealthy"

            return {
                "status": overall_status,
                "database": {"healthy": db_healthy, "pool_stats": db_stats},
                "task_queue": queue_health,
                "timestamp": time.time(),
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": time.time()}

    @app.get("/api/queue-stats")
    async def get_queue_stats(request: Request) -> Dict:
        """Get detailed task queue statistics."""
        try:
            from stable_squirrel.services.task_queue import get_task_queue

            task_queue = get_task_queue()
            return task_queue.get_queue_stats()
        except RuntimeError:
            return {"error": "Task queue not initialized"}

    # Performance monitoring middleware
    @app.middleware("http")
    async def performance_middleware(request: Request, call_next):
        """Add performance monitoring to all requests."""
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Add performance headers
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        # Log slow requests (> 1 second)
        if process_time > 1.0:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Slow request: {request.method} {request.url.path} " f"took {process_time:.3f}s")

        return response

    return app
