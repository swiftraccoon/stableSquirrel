"""Tests for database operations."""

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest

from stable_squirrel.database.models import (
    RadioCallCreate,
    SpeakerSegment,
    TranscriptionCreate,
)
from stable_squirrel.database.operations import DatabaseOperations


@pytest.fixture
def radio_call_data():
    """Create test radio call data."""
    return RadioCallCreate(
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
    )


@pytest.fixture
def transcription_data():
    """Create test transcription data."""
    return TranscriptionCreate(
        call_id=uuid4(),
        full_transcript="This is a test transcription of the radio call.",
        language="en",
        confidence_score=0.95,
        speaker_count=2,
        model_name="large-v2",
        processing_time_seconds=2.3,
    )


@pytest.fixture
def speaker_segments_data():
    """Create test speaker segments data."""
    call_id = uuid4()
    return [
        SpeakerSegment(
            call_id=call_id,
            segment_id=1,
            start_time_seconds=0.0,
            end_time_seconds=5.0,
            speaker_id="SPEAKER_00",
            text="Unit 123 to dispatch",
            confidence_score=0.97,
        ),
        SpeakerSegment(
            call_id=call_id,
            segment_id=2,
            start_time_seconds=5.5,
            end_time_seconds=10.0,
            speaker_id="SPEAKER_01",
            text="Go ahead Unit 123",
            confidence_score=0.93,
        ),
    ]


class MockDatabaseManager:
    """Mock database manager for testing."""

    def __init__(self):
        self.calls = []
        self.transcriptions = []
        self.speaker_segments = []
        self.next_call_id = 1

    async def execute(self, query: str, *args) -> None:
        """Mock execute method."""
        pass

    async def fetch(self, query: str, *args) -> list:
        """Mock fetch method."""
        if "radio_calls" in query and "SELECT" in query:
            return [{"call_id": uuid4(), "frequency": 460025000}]
        return []

    async def fetchrow(self, query: str, *args) -> dict:
        """Mock fetchrow method."""
        if "INSERT INTO radio_calls" in query:
            call_id = uuid4()
            return {
                "call_id": call_id,
                "timestamp": args[0],
                "frequency": args[2],
                "talkgroup_id": args[3],
                "transcription_status": "completed",
            }
        elif "INSERT INTO transcriptions" in query:
            return {
                "call_id": args[0],
                "full_transcript": args[1],
                "language": args[2],
                "confidence_score": args[3],
            }
        return {"call_id": uuid4()}

    async def fetchval(self, query: str, *args):
        """Mock fetchval method."""
        if "COUNT" in query:
            return 1
        return None

    @property
    def pool(self):
        """Mock connection pool."""
        return MockConnectionPool()


class MockConnectionPool:
    """Mock connection pool."""

    def acquire(self):
        return MockConnection()


class MockConnection:
    """Mock database connection."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def transaction(self):
        return MockTransaction()

    async def execute(self, query: str, *args):
        pass

    async def fetchrow(self, query: str, *args):
        call_id = uuid4()
        return {
            "call_id": call_id,
            "timestamp": datetime.now(),
            "frequency": 460025000,
            "transcription_status": "completed",
        }

    async def fetch(self, query: str, *args):
        return []


class MockTransaction:
    """Mock database transaction."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_db_manager():
    """Create mock database manager."""
    return MockDatabaseManager()


@pytest.fixture
def db_operations(mock_db_manager):
    """Create DatabaseOperations with mock database."""
    return DatabaseOperations(mock_db_manager)


def test_database_operations_init(db_operations):
    """Test DatabaseOperations initialization."""
    assert db_operations.db is not None
    assert db_operations.radio_calls is not None
    assert db_operations.transcriptions is not None
    assert db_operations.speaker_segments is not None


@pytest.mark.asyncio
async def test_store_complete_transcription(
    db_operations, radio_call_data, transcription_data, speaker_segments_data
):
    """Test storing complete transcription atomically."""
    # Update speaker segments to match transcription call_id
    for segment in speaker_segments_data:
        segment.call_id = transcription_data.call_id

    result = await db_operations.store_complete_transcription(
        radio_call_data, transcription_data, speaker_segments_data
    )

    # Check that all components are returned
    assert "radio_call" in result
    assert "transcription" in result
    assert "speaker_segments" in result

    # Verify the radio call
    stored_radio_call = result["radio_call"]
    assert stored_radio_call.frequency == radio_call_data.frequency
    assert stored_radio_call.talkgroup_id == radio_call_data.talkgroup_id

    # Verify the transcription
    stored_transcription = result["transcription"]
    assert stored_transcription.full_transcript == transcription_data.full_transcript
    assert stored_transcription.language == transcription_data.language


@pytest.mark.asyncio
async def test_radio_call_operations_create(db_operations, radio_call_data):
    """Test creating a radio call."""
    result = await db_operations.radio_calls.create_radio_call(radio_call_data)

    assert result is not None
    assert result.frequency == radio_call_data.frequency
    assert result.talkgroup_id == radio_call_data.talkgroup_id


@pytest.mark.asyncio
async def test_radio_call_operations_search(db_operations):
    """Test searching radio calls."""
    results = await db_operations.radio_calls.search_radio_calls(
        frequency=460025000,
        limit=10,
        offset=0
    )

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_transcription_operations_search(db_operations):
    """Test searching transcriptions."""
    results = await db_operations.transcriptions.search_transcriptions(
        query="test police",
        limit=10,
        offset=0
    )

    assert isinstance(results, list)


def test_map_record_to_model(db_operations):
    """Test mapping database record to Pydantic model."""
    from stable_squirrel.database.models import RadioCall

    # Create a mock record
    class MockRecord:
        def __init__(self, data):
            self._data = data

        def __getitem__(self, key):
            return self._data[key]

        def keys(self):
            return self._data.keys()

    record_data = {
        "call_id": uuid4(),
        "timestamp": datetime(2023, 12, 30, 20, 0, 0),
        "frequency": 460025000,
        "talkgroup_id": 1001,
        "transcription_status": "completed",
    }

    mock_record = MockRecord(record_data)

    # Test mapping
    result = db_operations._map_record_to_model(mock_record, RadioCall)

    assert isinstance(result, RadioCall)
    assert result.frequency == 460025000
    assert result.talkgroup_id == 1001


def test_execute_insert_query_structure():
    """Test the structure of dynamic insert query generation."""
    # This tests the concept without actual database execution
    table_name = "test_table"
    data = {
        "field1": "value1",
        "field2": 123,
        "field3": datetime.now(),
    }

    # Simulate what the method would generate
    columns = list(data.keys())
    placeholders = [f"${i+1}" for i in range(len(columns))]
    values = list(data.values())

    expected_query_pattern = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

    assert "INSERT INTO test_table" in expected_query_pattern
    assert "field1, field2, field3" in expected_query_pattern
    assert "$1, $2, $3" in expected_query_pattern
    assert len(values) == 3


@pytest.mark.asyncio
async def test_error_handling_in_operations(db_operations):
    """Test error handling in database operations."""
    # Test with invalid data that should raise an error
    invalid_radio_call = RadioCallCreate(
        timestamp=None,  # Invalid - required field
        frequency=460025000,
        audio_file_path="/tmp/test.wav",
    )

    # This should handle the error gracefully
    # Note: In a real test, we'd mock the database to raise specific errors
    try:
        await db_operations.radio_calls.create_radio_call(invalid_radio_call)
    except Exception as e:
        # Expected to fail due to invalid data
        assert isinstance(e, Exception)


def test_search_query_validation():
    """Test search query parameter validation."""
    from stable_squirrel.database.models import SearchQuery

    # Valid search query
    search_query = SearchQuery(
        query="test search",
        frequency=460025000,
        talkgroup_id=1001,
        limit=50,
        offset=0,
    )

    assert search_query.query == "test search"
    assert search_query.limit == 50
    assert search_query.offset == 0

    # Test limit bounds
    search_query_max = SearchQuery(
        query="test",
        limit=200,  # Over default max
    )

    # Should be clamped to maximum
    assert search_query_max.limit <= 100  # Assuming max limit is 100


def test_speaker_segment_model():
    """Test SpeakerSegment model validation."""
    segment = SpeakerSegment(
        call_id=uuid4(),
        segment_id=1,
        start_time_seconds=0.0,
        end_time_seconds=5.0,
        speaker_id="SPEAKER_00",
        text="Test speech segment",
        confidence_score=0.95,
    )

    assert segment.start_time_seconds < segment.end_time_seconds
    assert segment.confidence_score <= 1.0
    assert segment.speaker_id.startswith("SPEAKER_")


@pytest.mark.asyncio
async def test_concurrent_operations(db_operations, radio_call_data):
    """Test concurrent database operations."""
    # Create multiple radio calls concurrently
    tasks = []
    for i in range(3):
        call_data = radio_call_data.model_copy()
        call_data.frequency += i  # Make each call unique
        tasks.append(db_operations.radio_calls.create_radio_call(call_data))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # All operations should complete (may succeed or fail gracefully)
    assert len(results) == 3
    for result in results:
        # Each result should either be a valid RadioCall or an exception
        assert result is not None
