"""FastAPI web application."""

import time
from typing import TYPE_CHECKING, Awaitable, Callable, TypedDict, Union

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from stable_squirrel.config import Config
from stable_squirrel.web.routes import api, health, rdioscanner, security

if TYPE_CHECKING:
    from stable_squirrel.database import DatabaseManager
    from stable_squirrel.services.transcription import TranscriptionService


class SystemHealth(TypedDict):
    """TypedDict for system health information."""
    status: str
    database: dict[str, Union[str, int, bool]]
    task_queue: dict[str, Union[str, int, bool, float]]
    memory: dict[str, float]
    uptime_seconds: float


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
    app.state.startup_time = time.time()

    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(api.router, prefix="/api/v1", tags=["api"])
    app.include_router(security.router, prefix="/api/v1/security", tags=["security"])
    app.include_router(rdioscanner.router, tags=["rdioscanner"])

    # Add performance monitoring endpoints
    @app.get("/api/system-health")
    async def get_system_health(request: Request) -> SystemHealth:
        """Get comprehensive system health information."""
        try:
            db_manager = request.app.state.db_manager

            # Get database health
            db_healthy = await db_manager.health_check()
            db_stats = db_manager.get_pool_stats()

            # Get task queue health if available
            queue_health: dict[str, Union[str, int, bool, float]]
            try:
                from stable_squirrel.services.task_queue import get_task_queue

                task_queue = get_task_queue()
                queue_stats = task_queue.get_queue_stats()

                # Simple health assessment
                # We don't have max_queue_size in QueueStats, so use a reasonable default
                max_queue_size = 10000  # Default from TranscriptionTaskQueue

                # Determine status
                status = "warning" if queue_stats["queue_size"] / max_queue_size > 0.9 else "healthy"

                # Convert QueueStats to dict and merge
                queue_health = {
                    "status": status,
                    "total_enqueued": queue_stats["total_enqueued"],
                    "total_processed": queue_stats["total_processed"],
                    "total_failed": queue_stats["total_failed"],
                    "total_retries": queue_stats["total_retries"],
                    "average_processing_time": queue_stats["average_processing_time"],
                    "queue_full_rejections": queue_stats["queue_full_rejections"],
                    "queue_size": queue_stats["queue_size"],
                    "retry_queue_size": queue_stats["retry_queue_size"],
                    "active_tasks": queue_stats["active_tasks"],
                    "completed_tasks": queue_stats["completed_tasks"],
                    "failed_tasks": queue_stats["failed_tasks"],
                    "workers_running": queue_stats["workers_running"],
                    "is_running": queue_stats["is_running"],
                }
                if status == "warning":
                    queue_health["reason"] = "queue nearly full"

            except RuntimeError:
                queue_health = {"status": "not_initialized"}

            # Overall system status
            if db_healthy and queue_health["status"] in ["healthy", "not_initialized"]:
                overall_status = "healthy"
            elif db_healthy:
                overall_status = "warning"
            else:
                overall_status = "unhealthy"

            # Get memory info
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()

            # Get uptime
            uptime = time.time() - request.app.state.startup_time

            return SystemHealth(
                status=overall_status,
                database={"healthy": db_healthy, **db_stats},
                task_queue=queue_health,
                memory={
                    "rss_mb": memory_info.rss / 1024 / 1024,
                    "vms_mb": memory_info.vms / 1024 / 1024,
                },
                uptime_seconds=uptime,
            )

        except Exception as e:
            # Return minimal health info on error
            return SystemHealth(
                status="error",
                database={"healthy": False, "error": str(e)},
                task_queue={"status": "unknown"},
                memory={"rss_mb": 0.0, "vms_mb": 0.0},
                uptime_seconds=0.0,
            )

    @app.get("/api/queue-stats")
    async def get_queue_stats(request: Request) -> dict[str, Union[str, int, float, bool]]:
        """Get detailed task queue statistics."""
        try:
            from stable_squirrel.services.task_queue import get_task_queue

            task_queue = get_task_queue()
            stats = task_queue.get_queue_stats()
            # Convert TypedDict to regular dict by explicit construction
            return {
                "total_enqueued": stats["total_enqueued"],
                "total_processed": stats["total_processed"],
                "total_failed": stats["total_failed"],
                "total_retries": stats["total_retries"],
                "average_processing_time": stats["average_processing_time"],
                "queue_full_rejections": stats["queue_full_rejections"],
                "queue_size": stats["queue_size"],
                "retry_queue_size": stats["retry_queue_size"],
                "active_tasks": stats["active_tasks"],
                "completed_tasks": stats["completed_tasks"],
                "failed_tasks": stats["failed_tasks"],
                "workers_running": stats["workers_running"],
                "is_running": stats["is_running"],
            }
        except RuntimeError:
            return {"error": "Task queue not initialized"}

    # Performance monitoring middleware
    @app.middleware("http")
    async def performance_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
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
