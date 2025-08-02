"""Database package for TimescaleDB integration."""

from .connection import DatabaseManager
from .models import RadioCall, SearchQuery, SearchResult, SpeakerSegment, Transcription
from .operations import DatabaseOperations
from .schema import create_schema, ensure_timescale_setup

__all__ = [
    "DatabaseManager",
    "DatabaseOperations",
    "RadioCall",
    "Transcription",
    "SpeakerSegment",
    "SearchQuery",
    "SearchResult",
    "create_schema",
    "ensure_timescale_setup",
]
