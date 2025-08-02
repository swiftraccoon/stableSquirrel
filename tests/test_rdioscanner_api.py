"""Tests for RdioScanner API endpoints."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from stable_squirrel.config import Config
from stable_squirrel.web.routes.rdioscanner import router


@pytest.fixture
def app():
    """Create test app."""
    app = FastAPI()
    app.include_router(router)

    # Mock app state
    config = Config()
    config.ingestion.api_key = "test-api-key"
    config.ingestion.enable_file_validation = False  # Disable for basic API tests

    app.state.config = config
    app.state.transcription_service = AsyncMock()
    app.state.db_manager = AsyncMock()  # Add mock db_manager

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_audio_file():
    """Create a mock audio file for testing."""
    # Create a larger WAV file-like content to pass security validation
    wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    wav_data = b"\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    # Add padding to meet minimum size requirements (1100+ bytes)
    padding = b"\x00" * 1100
    return io.BytesIO(wav_header + wav_data + padding)


def test_upload_call_success(client, mock_audio_file):
    """Test successful call upload."""
    with patch("stable_squirrel.web.routes.rdioscanner.process_rdioscanner_call") as mock_process:
        mock_process.return_value = None

        files = {"audio": ("test.wav", mock_audio_file, "audio/wav")}
        data = {
            "key": "test-api-key",
            "system": "123",
            "dateTime": 1703980800,  # 2023-12-30 20:00:00 UTC
            "frequency": 460025000,
            "talkgroup": 1001,
            "source": 2001,
            "systemLabel": "Test System",
            "talkgroupLabel": "Police Dispatch",
            "talkerAlias": "Unit 123",
        }

        response = client.post("/api/call-upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "ok"
        assert result["message"] == "Call received and queued for transcription"
        assert result["callId"] == "test.wav"

        # Verify process_rdioscanner_call was called
        mock_process.assert_called_once()


def test_upload_call_test_mode(client):
    """Test test mode (no audio file required)."""
    data = {
        "key": "test-api-key",
        "system": "123",
        "dateTime": 1703980800,
        "test": 1,
    }

    response = client.post("/api/call-upload", data=data)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["message"] == "incomplete call data: no talkgroup"
    assert result["callId"] == "test"


def test_upload_call_invalid_api_key(client, mock_audio_file):
    """Test upload with invalid API key."""
    files = {"audio": ("test.wav", mock_audio_file, "audio/wav")}
    data = {
        "key": "wrong-api-key",
        "system": "123",
        "dateTime": 1703980800,
    }

    response = client.post("/api/call-upload", files=files, data=data)

    assert response.status_code == 401


def test_upload_call_no_api_key_required(client, mock_audio_file):
    """Test upload when no API key is configured."""
    # Modify app config to not require API key AND clear enhanced keys
    client.app.state.config.ingestion.api_key = None
    client.app.state.config.ingestion.api_keys = []

    with patch("stable_squirrel.web.routes.rdioscanner.process_rdioscanner_call") as mock_process:
        mock_process.return_value = None

        files = {"audio": ("test.wav", mock_audio_file, "audio/wav")}
        data = {
            "key": "any-key",
            "system": "123",
            "dateTime": 1703980800,
        }

        response = client.post("/api/call-upload", files=files, data=data)

        assert response.status_code == 200


def test_upload_call_missing_audio_file(client):
    """Test upload without audio file."""
    data = {
        "key": "test-api-key",
        "system": "123",
        "dateTime": 1703980800,
    }

    response = client.post("/api/call-upload", data=data)

    assert response.status_code == 400  # Missing audio file for non-test request


def test_upload_call_empty_audio_file(client):
    """Test upload with empty audio file."""
    files = {"audio": ("test.wav", io.BytesIO(b""), "audio/wav")}
    data = {
        "key": "test-api-key",
        "system": "123",
        "dateTime": 1703980800,
    }

    response = client.post("/api/call-upload", files=files, data=data)

    assert response.status_code == 400


def test_upload_call_missing_required_fields(client, mock_audio_file):
    """Test upload with missing required fields."""
    files = {"audio": ("test.wav", mock_audio_file, "audio/wav")}

    # Missing 'key'
    data = {
        "system": "123",
        "dateTime": 1703980800,
    }

    response = client.post("/api/call-upload", files=files, data=data)

    assert response.status_code == 401  # API key validation happens first


def test_upload_call_optional_fields(client, mock_audio_file):
    """Test upload with all optional fields."""
    with patch("stable_squirrel.web.routes.rdioscanner.process_rdioscanner_call") as mock_process:
        mock_process.return_value = None

        files = {"audio": ("test.wav", mock_audio_file, "audio/wav")}
        data = {
            "key": "test-api-key",
            "system": "123",
            "dateTime": 1703980800,
            "audioName": "custom_name.wav",
            "audioType": "audio/wav",
            "frequency": 460025000,
            "talkgroup": 1001,
            "source": 2001,
            "systemLabel": "Test System",
            "talkgroupLabel": "Police Dispatch",
            "talkgroupGroup": "Law Enforcement",
            "talkerAlias": "Unit 123",
            "patches": "patch1,patch2",
            "frequencies": "460.025,460.050",
            "sources": "2001,2002",
            "talkgroupTag": "emergency",
        }

        response = client.post("/api/call-upload", files=files, data=data)

        assert response.status_code == 200


@patch("stable_squirrel.web.routes.rdioscanner.process_rdioscanner_call")
def test_upload_call_processing_error(mock_process, client, mock_audio_file):
    """Test handling of processing errors."""
    mock_process.side_effect = Exception("Processing failed")

    files = {"audio": ("test.wav", mock_audio_file, "audio/wav")}
    data = {
        "key": "test-api-key",
        "system": "123",
        "dateTime": 1703980800,
    }

    response = client.post("/api/call-upload", files=files, data=data)

    assert response.status_code == 500


def test_rdioscanner_upload_model():
    """Test RdioScannerUpload model validation."""
    from stable_squirrel.web.routes.rdioscanner import RdioScannerUpload

    # Test valid data
    upload = RdioScannerUpload(
        key="test-key",
        system="123",
        dateTime=1703980800,
        audio_filename="test.wav",
        audio_content_type="audio/wav",
        audio_size=9,
    )

    assert upload.key == "test-key"
    assert upload.system == "123"
    assert upload.dateTime == 1703980800


def test_process_rdioscanner_call():
    """Test the process_rdioscanner_call function."""
    import tempfile
    from pathlib import Path

    from stable_squirrel.services.task_queue import (
        initialize_task_queue,
        shutdown_task_queue,
    )
    from stable_squirrel.web.routes.rdioscanner import (
        RdioScannerUpload,
        process_rdioscanner_call,
    )

    # Create test data
    upload_data = RdioScannerUpload(
        key="test-key",
        system="123",
        dateTime=1703980800,
        audio_filename="test.wav",
        audio_content_type="audio/wav",
        audio_size=9,
        frequency=460025000,
        talkgroup=1001,
        source=2001,
    )

    # Mock transcription service
    mock_service = AsyncMock()

    # Test the function
    with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:
        import asyncio

        async def run_test():
            # Initialize task queue
            queue = initialize_task_queue()

            # Mock transcription processor
            async def mock_processor(task):
                return {"transcript": "test transcript"}

            await queue.start(mock_processor)

            try:
                # Mock the task queue to be full so it falls back to direct transcription
                with patch("stable_squirrel.services.task_queue.get_task_queue") as mock_get_queue:
                    mock_queue = AsyncMock()
                    mock_queue.enqueue_task.side_effect = ValueError("Queue is full")
                    mock_get_queue.return_value = mock_queue

                    await process_rdioscanner_call(
                        upload_data,
                        Path(temp_file.name),
                        mock_service,
                        "127.0.0.1",  # client_ip
                        "test-key",  # api_key_id
                        "test-agent",  # user_agent
                    )
            finally:
                # Cleanup
                await shutdown_task_queue()

        asyncio.run(run_test())

        # Verify transcription service was called (fallback path)
        mock_service.transcribe_rdioscanner_call.assert_called_once()


def test_datetime_conversion():
    """Test datetime conversion from Unix timestamp."""
    from datetime import datetime

    from stable_squirrel.web.routes.rdioscanner import RdioScannerUpload

    upload = RdioScannerUpload(
        key="test-key",
        system="123",
        dateTime=1703980800,  # 2023-12-30 20:00:00 UTC
        audio_filename="test.wav",
        audio_content_type="audio/wav",
        audio_size=9,
    )

    # Convert to datetime
    call_timestamp = datetime.fromtimestamp(upload.dateTime)
    assert call_timestamp.year == 2023
    assert call_timestamp.month == 12
    assert call_timestamp.day == 30
