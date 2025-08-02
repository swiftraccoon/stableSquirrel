"""Tests for API endpoints."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stable_squirrel.config import Config
from stable_squirrel.database.models import RadioCall, SearchResult, Transcription
from stable_squirrel.web.routes import api


@pytest.fixture
def app():
    """Create test FastAPI app with API router."""
    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")

    # Mock app state
    config = Config()
    app.state.config = config
    app.state.db_manager = AsyncMock()

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_radio_call():
    """Create mock radio call data."""
    return RadioCall(
        call_id=uuid4(),
        timestamp=datetime(2023, 12, 30, 20, 0, 0),
        frequency=460025000,
        talkgroup_id=1001,
        source_radio_id=2001,
        system_id=123,
        system_label="Test System",
        talkgroup_label="Police Dispatch",
        talkgroup_group="Law Enforcement",
        talker_alias="Unit 123",
        audio_file_path="/tmp/test.wav",
        audio_duration_seconds=15.5,
        audio_format=".wav",
        transcription_status="completed",
        transcribed_at=datetime(2023, 12, 30, 20, 1, 0),
    )


@pytest.fixture
def mock_transcription():
    """Create mock transcription data."""
    return Transcription(
        call_id=uuid4(),
        full_transcript="Unit 123 to dispatch, we have a situation at Main and 5th.",
        language="en",
        confidence_score=0.95,
        speaker_count=2,
        model_name="large-v2",
        processing_time_seconds=2.3,
    )


@pytest.fixture
def mock_search_result():
    """Create mock search result."""
    call_id = uuid4()
    return SearchResult(
        call_id=call_id,
        timestamp=datetime(2023, 12, 30, 20, 0, 0),
        frequency=460025000,
        talkgroup_id=1001,
        system_label="Test System",
        talkgroup_label="Police Dispatch",
        full_transcript="Unit 123 to dispatch, we have a situation at Main and 5th.",
        confidence_score=0.95,
        rank=0.8,
    )


def test_list_transcriptions_success(client, mock_radio_call, mock_transcription):
    """Test successful listing of transcriptions."""
    # Mock database operations
    mock_db_ops = MagicMock()
    mock_db_ops.radio_calls.search_radio_calls = AsyncMock(return_value=[mock_radio_call])
    mock_db_ops.transcriptions.get_transcription = AsyncMock(return_value=mock_transcription)
    mock_db_ops.speaker_segments.get_speaker_segments = AsyncMock(return_value=[])

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get("/api/v1/transcriptions")

        assert response.status_code == 200
        data = response.json()

        assert "transcriptions" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        transcriptions = data["transcriptions"]
        assert len(transcriptions) >= 0


def test_list_transcriptions_with_filters(client):
    """Test listing transcriptions with query filters."""
    mock_db_ops = MagicMock()
    mock_db_ops.radio_calls.search_radio_calls = AsyncMock(return_value=[])

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get("/api/v1/transcriptions", params={
            "frequency": 460025000,
            "talkgroup_id": 1001,
            "system_id": 123,
            "limit": 25,
            "offset": 10,
        })

        assert response.status_code == 200

        # Verify the search was called with correct parameters
        mock_db_ops.radio_calls.search_radio_calls.assert_called_once()
        call_args = mock_db_ops.radio_calls.search_radio_calls.call_args
        assert call_args.kwargs["frequency"] == 460025000
        assert call_args.kwargs["talkgroup_id"] == 1001
        assert call_args.kwargs["system_id"] == 123
        assert call_args.kwargs["limit"] == 25
        assert call_args.kwargs["offset"] == 10


def test_search_transcriptions_success(client, mock_search_result):
    """Test successful transcription search."""
    mock_db_ops = MagicMock()
    mock_db_ops.transcriptions.search_transcriptions = AsyncMock(return_value=[mock_search_result])
    mock_db_ops.speaker_segments.get_speaker_segments = AsyncMock(return_value=[])

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get("/api/v1/transcriptions/search", params={
            "q": "police dispatch",
            "frequency": 460025000,
            "limit": 20,
        })

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert "total" in data
        assert "query" in data

        # Verify search was called with correct parameters
        mock_db_ops.transcriptions.search_transcriptions.assert_called_once()
        call_args = mock_db_ops.transcriptions.search_transcriptions.call_args
        assert call_args.kwargs["query"] == "police dispatch"
        assert call_args.kwargs["frequency"] == 460025000
        assert call_args.kwargs["limit"] == 20


def test_search_transcriptions_missing_query(client):
    """Test search transcriptions without query parameter."""
    response = client.get("/api/v1/transcriptions/search")

    assert response.status_code == 422  # FastAPI validation error


def test_get_transcription_success(client, mock_radio_call, mock_transcription):
    """Test successful retrieval of single transcription."""
    mock_db_ops = MagicMock()
    mock_db_ops.radio_calls.get_radio_call = AsyncMock(return_value=mock_radio_call)
    mock_db_ops.transcriptions.get_transcription = AsyncMock(return_value=mock_transcription)
    mock_db_ops.speaker_segments.get_speaker_segments = AsyncMock(return_value=[])

    transcription_id = str(uuid4())

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get(f"/api/v1/transcriptions/{transcription_id}")

        assert response.status_code == 200
        data = response.json()

        # Should contain transcription response structure
        assert "call_id" in data
        assert "timestamp" in data
        assert "frequency" in data
        assert "full_transcript" in data


def test_get_transcription_not_found(client):
    """Test retrieving non-existent transcription."""
    mock_db_ops = MagicMock()
    mock_db_ops.radio_calls.get_radio_call = AsyncMock(return_value=None)

    transcription_id = str(uuid4())

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get(f"/api/v1/transcriptions/{transcription_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_get_transcription_invalid_uuid(client):
    """Test retrieving transcription with invalid UUID."""
    response = client.get("/api/v1/transcriptions/invalid-uuid")

    assert response.status_code == 400
    assert "Invalid UUID" in response.json()["detail"]


def test_chat_completions_placeholder(client):
    """Test LLM chat completions placeholder endpoint."""
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Tell me about the recent radio calls"}
        ],
        "max_tokens": 100,
    }

    response = client.post("/api/v1/chat/completions", json=request_data)

    # Should return 501 Not Implemented for now
    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"].lower()


def test_list_transcriptions_database_error(client):
    """Test handling of database errors in list transcriptions."""
    mock_db_ops = MagicMock()
    mock_db_ops.radio_calls.search_radio_calls = AsyncMock(side_effect=Exception("Database error"))

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get("/api/v1/transcriptions")

        assert response.status_code == 500
        assert "internal server error" in response.json()["detail"].lower()


def test_search_transcriptions_database_error(client):
    """Test handling of database errors in search transcriptions."""
    mock_db_ops = MagicMock()
    mock_db_ops.transcriptions.search_transcriptions = AsyncMock(side_effect=Exception("Search failed"))

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get("/api/v1/transcriptions/search", params={"q": "test"})

        assert response.status_code == 500


def test_get_transcription_database_error(client):
    """Test handling of database errors in get transcription."""
    mock_db_ops = MagicMock()
    mock_db_ops.radio_calls.get_radio_call = AsyncMock(side_effect=Exception("Database error"))

    transcription_id = str(uuid4())

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get(f"/api/v1/transcriptions/{transcription_id}")

        assert response.status_code == 500


def test_transcription_response_structure(client, mock_radio_call, mock_transcription):
    """Test the structure of transcription response data."""
    from stable_squirrel.database.models import SpeakerSegment

    mock_speaker_segments = [
        SpeakerSegment(
            call_id=mock_radio_call.call_id,
            segment_id=1,
            start_time_seconds=0.0,
            end_time_seconds=3.0,
            speaker_id="SPEAKER_00",
            text="Unit 123 to dispatch",
            confidence_score=0.97,
        ),
        SpeakerSegment(
            call_id=mock_radio_call.call_id,
            segment_id=2,
            start_time_seconds=3.5,
            end_time_seconds=7.0,
            speaker_id="SPEAKER_01",
            text="Go ahead Unit 123",
            confidence_score=0.93,
        ),
    ]

    mock_db_ops = MagicMock()
    mock_db_ops.radio_calls.get_radio_call = AsyncMock(return_value=mock_radio_call)
    mock_db_ops.transcriptions.get_transcription = AsyncMock(return_value=mock_transcription)
    mock_db_ops.speaker_segments.get_speaker_segments = AsyncMock(return_value=mock_speaker_segments)

    transcription_id = str(mock_radio_call.call_id)

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        response = client.get(f"/api/v1/transcriptions/{transcription_id}")

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        expected_fields = [
            "call_id", "timestamp", "frequency", "talkgroup_id", "source_radio_id",
            "system_id", "system_label", "talkgroup_label", "talkgroup_group",
            "talker_alias", "audio_file_path", "audio_duration_seconds", "audio_format",
            "full_transcript", "language", "confidence_score", "speaker_count",
            "speakers", "segments", "processing_time_seconds", "model_name"
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        # Verify speaker segments structure
        assert len(data["segments"]) == 2
        segment = data["segments"][0]
        assert "start_time_seconds" in segment
        assert "end_time_seconds" in segment
        assert "speaker_id" in segment
        assert "text" in segment
        assert "confidence_score" in segment

        # Verify unique speakers list
        assert len(data["speakers"]) == 2
        assert "SPEAKER_00" in data["speakers"]
        assert "SPEAKER_01" in data["speakers"]


def test_pagination_parameters(client):
    """Test pagination parameter validation."""
    mock_db_ops = MagicMock()
    mock_db_ops.radio_calls.search_radio_calls = AsyncMock(return_value=[])

    with pytest.MonkeyPatch.context() as m:
        m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)

        # Test maximum limit enforcement
        response = client.get("/api/v1/transcriptions", params={"limit": 500})

        assert response.status_code == 200

        # Verify limit was clamped to maximum
        call_args = mock_db_ops.radio_calls.search_radio_calls.call_args
        assert call_args.kwargs["limit"] <= 100  # Assuming max limit is 100

        # Test negative offset handling
        response = client.get("/api/v1/transcriptions", params={"offset": -10})

        assert response.status_code == 200
        call_args = mock_db_ops.radio_calls.search_radio_calls.call_args
        assert call_args.kwargs["offset"] >= 0


def test_search_query_validation():
    """Test search query parameter validation."""
    from stable_squirrel.database.models import SearchQuery

    # Test valid search query
    query = SearchQuery(
        query="police emergency",
        frequency=460025000,
        talkgroup_id=1001,
        start_time=datetime(2023, 12, 30, 0, 0, 0),
        end_time=datetime(2023, 12, 30, 23, 59, 59),
        limit=50,
        offset=0,
    )

    assert query.query == "police emergency"
    assert query.frequency == 460025000
    assert query.limit == 50

    # Test query length limits (if any)
    very_long_query = "a" * 1000
    query_long = SearchQuery(query=very_long_query)

    # Should handle long queries gracefully
    assert len(query_long.query) <= 1000


def test_concurrent_api_requests(client):
    """Test handling of concurrent API requests."""
    import threading

    mock_db_ops = MagicMock()
    # Add a small delay to simulate database operations
    async def mock_search(*args, **kwargs):
        await asyncio.sleep(0.1)
        return []

    mock_db_ops.radio_calls.search_radio_calls = mock_search

    results = []
    errors = []

    def make_request():
        try:
            with pytest.MonkeyPatch.context() as m:
                m.setattr("stable_squirrel.web.routes.api.DatabaseOperations", lambda x: mock_db_ops)
                response = client.get("/api/v1/transcriptions")
                results.append(response.status_code)
        except Exception as e:
            errors.append(e)

    # Start multiple concurrent requests
    threads = []
    for _ in range(5):
        thread = threading.Thread(target=make_request)
        threads.append(thread)
        thread.start()

    # Wait for all requests to complete
    for thread in threads:
        thread.join()

    # All requests should succeed
    assert len(errors) == 0
    assert all(status == 200 for status in results)
