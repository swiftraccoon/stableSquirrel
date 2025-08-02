"""Health check endpoints."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@router.get("/ready", response_model=HealthResponse)
async def readiness_check(request: Request) -> HealthResponse:
    """Readiness check endpoint."""
    try:
        # Check if database is accessible
        db_manager = request.app.state.db_manager
        await db_manager.fetchval("SELECT 1")

        # Check if transcription service is running
        transcription_service = request.app.state.transcription_service
        if not transcription_service._running:
            return HealthResponse(status="not_ready", version="0.1.0")

        return HealthResponse(status="ready", version="0.1.0")

    except Exception:
        return HealthResponse(status="not_ready", version="0.1.0")
