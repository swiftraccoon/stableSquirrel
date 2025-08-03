"""Pydantic models for radio call data."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RadioCallCreate(BaseModel):
    """Model for creating a new radio call record."""

    call_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    frequency: int  # Hz
    talkgroup_id: Optional[int] = None
    source_radio_id: Optional[int] = None
    system_id: Optional[int] = None

    # Labels and aliases
    system_label: Optional[str] = None
    talkgroup_label: Optional[str] = None
    talkgroup_group: Optional[str] = None
    talker_alias: Optional[str] = None

    # Audio file info
    audio_file_path: str
    audio_duration_seconds: Optional[float] = None
    audio_format: str = "wav"

    # Security tracking (enhanced security)
    upload_source_ip: Optional[str] = None
    upload_source_system: Optional[str] = None  # System ID that uploaded this
    upload_api_key_id: Optional[str] = None  # Which API key was used
    upload_user_agent: Optional[str] = None


class RadioCall(RadioCallCreate):
    """Complete radio call record with database fields."""

    call_id: UUID = Field(default_factory=uuid4)
    transcription_status: str = "pending"  # pending, processing, completed, failed
    transcribed_at: Optional[datetime] = None


class SpeakerSegment(BaseModel):
    """Individual speaker segment from diarization."""

    call_id: UUID
    segment_id: UUID = Field(default_factory=uuid4)

    # Timing within the call
    start_time_seconds: float
    end_time_seconds: float

    # Speaker identification
    speaker_id: str  # Speaker label from diarization

    # Segment content
    text: str
    confidence_score: Optional[float] = None


class TranscriptionCreate(BaseModel):
    """Model for creating transcription results."""

    call_id: UUID

    # WhisperX results
    full_transcript: str
    language: Optional[str] = None
    confidence_score: Optional[float] = None

    # Speaker diarization
    speaker_count: int = 1
    speaker_segments: List[SpeakerSegment] = Field(default_factory=list)

    # Processing metadata
    model_name: Optional[str] = None
    processing_time_seconds: Optional[float] = None


class Transcription(TranscriptionCreate):
    """Complete transcription record."""

    pass


class SearchQuery(BaseModel):
    """Search query parameters."""

    query_text: Optional[str] = None
    frequency: Optional[int] = None
    talkgroup_id: Optional[int] = None
    system_id: Optional[int] = None

    # Time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Pagination
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class SearchResult(BaseModel):
    """Search result with call and transcription data."""

    # Radio call data
    call_id: UUID
    timestamp: datetime
    frequency: int
    talkgroup_id: Optional[int] = None
    talkgroup_label: Optional[str] = None
    system_label: Optional[str] = None
    talker_alias: Optional[str] = None
    audio_file_path: str
    audio_duration_seconds: Optional[float] = None

    # Transcription data
    full_transcript: Optional[str] = None
    speaker_count: Optional[int] = None
    confidence_score: Optional[float] = None

    # Search relevance
    search_rank: Optional[float] = None


class TranscriptionResponse(BaseModel):
    """Response model for transcription queries."""

    id: str
    file_path: str
    transcript: str
    timestamp: str
    duration: float
    speakers: List[str]


class PaginatedTranscriptionResponse(BaseModel):
    """Paginated response for transcription listings."""

    transcriptions: List[TranscriptionResponse]
    total: int
    limit: int
    offset: int


class PaginatedSearchResponse(BaseModel):
    """Paginated response for transcription search results."""

    results: List[SearchResult]
    total: int
    limit: int
    offset: int
    query: str


class SecurityEvent(BaseModel):
    """Security audit log entry."""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str  # "upload_blocked", "invalid_api_key", "rate_limit_exceeded", etc.
    severity: str = "info"  # "low", "medium", "high", "critical"

    # Source information
    source_ip: Optional[str] = None
    source_system: Optional[str] = None
    api_key_used: Optional[str] = None
    user_agent: Optional[str] = None

    # Event details
    description: str
    metadata: Optional[dict[str, Any]] = None  # Additional context

    # Related entities
    related_call_id: Optional[UUID] = None
    related_file_path: Optional[str] = None
