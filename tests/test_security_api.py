"""Tests for security API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from stable_squirrel.config import Config
from stable_squirrel.database.models import SecurityEvent
from stable_squirrel.web.routes.security import router


@pytest.fixture
def app():
    """Create test app with security routes."""
    app = FastAPI()
    app.include_router(router)

    # Mock app state
    config = Config()

    # Mock database manager and operations
    mock_db_manager = MagicMock()
    mock_security_ops = AsyncMock()
    mock_db_ops = MagicMock()
    mock_db_ops.security_events = mock_security_ops

    # Mock database operations constructor to return our mock
    import stable_squirrel.web.routes.security

    original_db_ops = stable_squirrel.web.routes.security.DatabaseOperations
    stable_squirrel.web.routes.security.DatabaseOperations = lambda db_manager: mock_db_ops

    app.state.config = config
    app.state.db_manager = mock_db_manager

    # Store the mock for easy access in tests
    app.state.mock_security_ops = mock_security_ops
    app.state.mock_db_manager = mock_db_manager

    yield app

    # Restore original DatabaseOperations
    stable_squirrel.web.routes.security.DatabaseOperations = original_db_ops


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_security_event():
    """Create a sample security event."""
    from datetime import datetime
    from uuid import uuid4

    return SecurityEvent(
        event_id=uuid4(),
        timestamp=datetime.now(),
        event_type="api_key_used",
        severity="info",
        source_ip="192.168.1.100",
        source_system="test-system",
        api_key_used="test-key",
        user_agent="SDRTrunk/1.0",
        description="Test security event",
        metadata={"test": "data"},
    )


def test_get_security_events(client, app, sample_security_event):
    """Test getting security events."""
    # Configure mock to return sample events
    app.state.mock_security_ops.get_security_events.return_value = [sample_security_event]

    response = client.get("/events")

    assert response.status_code == 200
    data = response.json()

    assert "events" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data

    assert len(data["events"]) == 1
    event = data["events"][0]
    assert event["event_type"] == "api_key_used"
    assert event["severity"] == "info"
    assert event["source_ip"] == "192.168.1.100"
    assert event["source_system"] == "test-system"


def test_get_security_events_with_filters(client, app, sample_security_event):
    """Test getting security events with filters."""
    app.state.mock_security_ops.get_security_events.return_value = [sample_security_event]

    response = client.get("/events?event_type=api_key_used&severity=info&limit=50")

    assert response.status_code == 200

    # Verify the mock was called with correct parameters
    app.state.mock_security_ops.get_security_events.assert_called_once()
    call_args = app.state.mock_security_ops.get_security_events.call_args
    assert call_args.kwargs["event_type"] == "api_key_used"
    assert call_args.kwargs["severity"] == "info"
    assert call_args.kwargs["limit"] == 50


def test_get_upload_source_analysis(client, app, sample_security_event):
    """Test getting upload source analysis."""
    analysis_data = {
        "system_id": "test-system",
        "upload_statistics": {"total_uploads": 10, "unique_ips": 2},
        "security_statistics": {"total_events": 5, "violations": 1},
        "ip_addresses": [{"upload_source_ip": "192.168.1.100", "upload_count": 8}],
        "recent_events": [sample_security_event],
    }

    app.state.mock_security_ops.get_upload_source_analysis.return_value = analysis_data

    response = client.get("/analysis/source/test-system")

    assert response.status_code == 200
    data = response.json()

    assert data["system_id"] == "test-system"
    assert "upload_statistics" in data
    assert "security_statistics" in data
    assert "ip_addresses" in data
    assert "recent_events" in data

    assert len(data["recent_events"]) == 1


def test_get_security_summary(client, app, sample_security_event):
    """Test getting security summary."""
    app.state.mock_security_ops.get_security_events.return_value = [sample_security_event]

    response = client.get("/summary?hours=24")

    assert response.status_code == 200
    data = response.json()

    assert "total_events" in data
    assert "events_by_severity" in data
    assert "recent_violations" in data
    assert "top_source_systems" in data
    assert "top_source_ips" in data


def test_get_upload_sources(client, app):
    """Test getting upload sources list."""
    from datetime import datetime

    # Mock database fetchrow to return sample data
    now = datetime.now()
    sample_row = {
        "upload_source_system": "test-system",
        "upload_source_ip": "192.168.1.100",
        "upload_count": 10,
        "first_seen": now,
        "last_seen": now,
        "unique_api_keys": 1,
    }

    app.state.mock_db_manager.fetch = AsyncMock(return_value=[sample_row])

    response = client.get("/uploads/sources?limit=10")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    if len(data) > 0:
        source = data[0]
        assert "system_id" in source
        assert "ip_address" in source
        assert "upload_count" in source


def test_security_events_error_handling(client, app):
    """Test error handling in security events endpoint."""
    # Configure mock to raise an exception
    app.state.mock_security_ops.get_security_events.side_effect = Exception("Database error")

    response = client.get("/events")

    assert response.status_code == 500
    data = response.json()
    assert "Error retrieving security events" in data["detail"]


def test_upload_source_analysis_error_handling(client, app):
    """Test error handling in upload source analysis endpoint."""
    app.state.mock_security_ops.get_upload_source_analysis.side_effect = Exception("Database error")

    response = client.get("/analysis/source/test-system")

    assert response.status_code == 500
    data = response.json()
    assert "Error retrieving upload source analysis" in data["detail"]
