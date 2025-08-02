"""Main API endpoints."""

from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from stable_squirrel.database.models import (
    PaginatedSearchResponse,
    PaginatedTranscriptionResponse,
    SearchQuery,
    TranscriptionResponse,
)
from stable_squirrel.database.operations import DatabaseOperations

router = APIRouter()


class SearchRequest(BaseModel):
    """Request model for search queries."""

    query: str
    limit: int = 50
    offset: int = 0


@router.get("/transcriptions", response_model=PaginatedTranscriptionResponse)
async def list_transcriptions(
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    frequency: int = Query(None, description="Filter by frequency"),
    talkgroup_id: int = Query(None, description="Filter by talkgroup ID"),
    system_id: int = Query(None, description="Filter by system ID"),
) -> PaginatedTranscriptionResponse:
    """List recent transcriptions with optional filters."""
    try:
        # Get database operations from app state
        db_manager = request.app.state.db_manager
        db_ops = DatabaseOperations(db_manager)

        # Build search query
        search_query = SearchQuery(
            query_text=None,  # No text search for list endpoint
            limit=limit,
            offset=offset,
            frequency=frequency,
            talkgroup_id=talkgroup_id,
            system_id=system_id,
        )

        # Get radio calls and total count
        radio_calls = await db_ops.radio_calls.search_radio_calls(search_query)
        # For now, use the length of results as total (would need separate count query for exact total)
        total_count = len(radio_calls) + offset

        # Convert to response format
        responses = []
        for call in radio_calls:
            # Get transcription if available
            transcription = None
            if call.transcription_status == "completed":
                transcription = await db_ops.transcriptions.get_transcription(call.call_id)

            response = TranscriptionResponse(
                id=str(call.call_id),
                file_path=call.audio_file_path,
                transcript=transcription.full_transcript if transcription else "",
                timestamp=call.timestamp.isoformat(),
                duration=call.audio_duration_seconds or 0.0,
                speakers=[],  # TODO: Get speaker list from segments
            )
            responses.append(response)

        return PaginatedTranscriptionResponse(
            transcriptions=responses,
            total=total_count,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving transcriptions: {str(e)}")


@router.get("/search", response_model=PaginatedSearchResponse)
async def search_transcriptions(
    request: Request,
    q: str = Query(..., description="Search query text"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    frequency: int = Query(None, description="Filter by frequency"),
    talkgroup_id: int = Query(None, description="Filter by talkgroup ID"),
) -> PaginatedSearchResponse:
    """Search transcriptions by text using full-text search."""
    try:
        # Get database operations from app state
        db_manager = request.app.state.db_manager
        db_ops = DatabaseOperations(db_manager)

        # Build search query
        search_query = SearchQuery(
            query_text=q,
            limit=limit,
            offset=offset,
            frequency=frequency,
            talkgroup_id=talkgroup_id,
        )

        # Perform search
        search_results = await db_ops.transcriptions.search_transcriptions(search_query)
        total_count = len(search_results) + offset

        return PaginatedSearchResponse(
            results=search_results,
            total=total_count,
            limit=limit,
            offset=offset,
            query=q,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching transcriptions: {str(e)}")


@router.get("/transcriptions/{transcription_id}")
async def get_transcription(
    request: Request,
    transcription_id: str,
) -> TranscriptionResponse:
    """Get a specific transcription by ID."""
    try:
        # Parse UUID
        try:
            call_id = UUID(transcription_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid transcription ID format")

        # Get database operations from app state
        db_manager = request.app.state.db_manager
        db_ops = DatabaseOperations(db_manager)

        # Get radio call
        radio_call = await db_ops.radio_calls.get_radio_call(call_id)
        if not radio_call:
            raise HTTPException(status_code=404, detail="Transcription not found")

        # Get transcription
        transcription = await db_ops.transcriptions.get_transcription(call_id)

        # Get speaker segments
        speakers = await db_ops.speaker_segments.get_speaker_segments(call_id)
        unique_speakers = list(set(segment.speaker_id for segment in speakers))

        response = TranscriptionResponse(
            id=str(radio_call.call_id),
            file_path=radio_call.audio_file_path,
            transcript=transcription.full_transcript if transcription else "",
            timestamp=radio_call.timestamp.isoformat(),
            duration=radio_call.audio_duration_seconds or 0.0,
            speakers=unique_speakers,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving transcription: {str(e)}")


@router.post("/llm/chat/completions")
async def llm_chat_completions(
    request: Request,
    chat_request: Dict[str, Any],
) -> Dict[str, Any]:
    """OpenAI-compatible chat completions endpoint."""
    # TODO: Implement LLM functionality
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": ("This is a placeholder response. " "LLM functionality not yet implemented."),
                },
                "finish_reason": "stop",
            }
        ],
        "model": "stable-squirrel-v0.1",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
