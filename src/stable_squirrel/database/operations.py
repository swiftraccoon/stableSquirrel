"""Database CRUD operations for radio calls and transcriptions."""

import json
import logging
from datetime import datetime
from typing import Any, List, Optional, TypedDict
from uuid import UUID

from stable_squirrel.database.connection import DatabaseManager
from stable_squirrel.database.models import (
    RadioCall,
    RadioCallCreate,
    SearchQuery,
    SearchResult,
    SecurityEvent,
    SpeakerSegment,
    Transcription,
    TranscriptionCreate,
)


class TranscriptionStoreResult(TypedDict):
    """Result of storing a complete transcription."""

    radio_call: dict[str, Any]
    transcription: dict[str, Any]
    speaker_segments: list[dict[str, Any]]


class UploadSourceAnalysis(TypedDict):
    """Analysis of upload patterns for a source system."""

    system_id: str
    upload_statistics: dict[str, Any]
    security_statistics: dict[str, Any]
    ip_addresses: list[dict[str, Any]]
    recent_events: list[SecurityEvent]


logger = logging.getLogger(__name__)


class RadioCallOperations:
    """Database operations for radio calls."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def create_radio_call(self, radio_call: RadioCallCreate) -> RadioCall:
        """Create a new radio call record."""
        query = """
            INSERT INTO radio_calls (
                timestamp, frequency, talkgroup_id, source_radio_id, system_id,
                system_label, talkgroup_label, talkgroup_group, talker_alias,
                audio_file_path, audio_duration_seconds, audio_format,
                transcription_status, upload_source_ip, upload_source_system,
                upload_api_key_id, upload_user_agent
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            RETURNING call_id, timestamp, frequency, talkgroup_id, source_radio_id,
                     system_id, system_label, talkgroup_label, talkgroup_group,
                     talker_alias, audio_file_path, audio_duration_seconds,
                     audio_format, transcription_status, transcribed_at,
                     upload_source_ip, upload_source_system, upload_api_key_id,
                     upload_user_agent
        """

        row = await self.db.fetchrow(
            query,
            radio_call.timestamp,
            radio_call.frequency,
            radio_call.talkgroup_id,
            radio_call.source_radio_id,
            radio_call.system_id,
            radio_call.system_label,
            radio_call.talkgroup_label,
            radio_call.talkgroup_group,
            radio_call.talker_alias,
            radio_call.audio_file_path,
            radio_call.audio_duration_seconds,
            radio_call.audio_format,
            "pending",  # transcription_status
            radio_call.upload_source_ip,
            radio_call.upload_source_system,
            radio_call.upload_api_key_id,
            radio_call.upload_user_agent,
        )

        if not row:
            raise RuntimeError("Failed to create radio call")

        return RadioCall(**dict(row))

    async def get_radio_call(self, call_id: UUID) -> Optional[RadioCall]:
        """Get a radio call by ID."""
        query = """
            SELECT call_id, timestamp, frequency, talkgroup_id, source_radio_id,
                   system_id, system_label, talkgroup_label, talkgroup_group,
                   talker_alias, audio_file_path, audio_duration_seconds,
                   audio_format, transcription_status, transcribed_at,
                   upload_source_ip, upload_source_system, upload_api_key_id,
                   upload_user_agent
            FROM radio_calls
            WHERE call_id = $1
        """

        row = await self.db.fetchrow(query, call_id)
        return RadioCall(**dict(row)) if row else None

    async def update_transcription_status(
        self, call_id: UUID, status: str, transcribed_at: Optional[datetime] = None
    ) -> None:
        """Update the transcription status of a radio call."""
        query = """
            UPDATE radio_calls
            SET transcription_status = $2, transcribed_at = $3
            WHERE call_id = $1
        """

        await self.db.execute(query, call_id, status, transcribed_at or datetime.now())

    async def search_radio_calls(self, search_query: SearchQuery) -> List[RadioCall]:
        """Search radio calls with filters."""
        conditions = ["1=1"]  # Base condition
        params: list[Any] = []
        param_count = 0

        # Build dynamic WHERE clause
        if search_query.frequency:
            param_count += 1
            conditions.append(f"frequency = ${param_count}")
            params.append(search_query.frequency)

        if search_query.talkgroup_id:
            param_count += 1
            conditions.append(f"talkgroup_id = ${param_count}")
            params.append(search_query.talkgroup_id)

        if search_query.system_id:
            param_count += 1
            conditions.append(f"system_id = ${param_count}")
            params.append(search_query.system_id)

        if search_query.start_time:
            param_count += 1
            conditions.append(f"timestamp >= ${param_count}")
            params.append(search_query.start_time)

        if search_query.end_time:
            param_count += 1
            conditions.append(f"timestamp <= ${param_count}")
            params.append(search_query.end_time)

        # Add LIMIT and OFFSET
        param_count += 1
        limit_param = f"${param_count}"
        params.append(search_query.limit)

        param_count += 1
        offset_param = f"${param_count}"
        params.append(search_query.offset)

        query = f"""
            SELECT call_id, timestamp, frequency, talkgroup_id, source_radio_id,
                   system_id, system_label, talkgroup_label, talkgroup_group,
                   talker_alias, audio_file_path, audio_duration_seconds,
                   audio_format, transcription_status, transcribed_at
            FROM radio_calls
            WHERE {' AND '.join(conditions)}
            ORDER BY timestamp DESC
            LIMIT {limit_param} OFFSET {offset_param}
        """

        rows = await self.db.fetch(query, *params)
        return [RadioCall(**dict(row)) for row in rows]


class TranscriptionOperations:
    """Database operations for transcriptions."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def create_transcription(self, transcription: TranscriptionCreate) -> Transcription:
        """Create a new transcription record."""
        query = """
            INSERT INTO transcriptions (
                call_id, full_transcript, language, confidence_score,
                speaker_count, model_name, processing_time_seconds
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """

        row = await self.db.fetchrow(
            query,
            transcription.call_id,
            transcription.full_transcript,
            transcription.language,
            transcription.confidence_score,
            transcription.speaker_count,
            transcription.model_name,
            transcription.processing_time_seconds,
        )

        if not row:
            raise RuntimeError("Failed to create transcription")

        return Transcription(**dict(row))

    async def get_transcription(self, call_id: UUID) -> Optional[Transcription]:
        """Get a transcription by call ID."""
        query = """
            SELECT call_id, full_transcript, language, confidence_score,
                   speaker_count, model_name, processing_time_seconds
            FROM transcriptions
            WHERE call_id = $1
        """

        row = await self.db.fetchrow(query, call_id)
        return Transcription(**dict(row)) if row else None

    async def search_transcriptions(self, search_query: SearchQuery) -> List[SearchResult]:
        """Search transcriptions with full-text search."""
        conditions = ["rc.call_id = t.call_id"]
        params: list[Any] = []
        param_count = 0

        # Text search using PostgreSQL full-text search
        if search_query.query_text:
            param_count += 1
            conditions.append((f"to_tsvector('english', t.full_transcript) " f"@@ plainto_tsquery(${param_count})"))
            params.append(search_query.query_text)

        # Add radio call filters
        if search_query.frequency:
            param_count += 1
            conditions.append(f"rc.frequency = ${param_count}")
            params.append(search_query.frequency)

        if search_query.talkgroup_id:
            param_count += 1
            conditions.append(f"rc.talkgroup_id = ${param_count}")
            params.append(search_query.talkgroup_id)

        if search_query.system_id:
            param_count += 1
            conditions.append(f"rc.system_id = ${param_count}")
            params.append(search_query.system_id)

        if search_query.start_time:
            param_count += 1
            conditions.append(f"rc.timestamp >= ${param_count}")
            params.append(search_query.start_time)

        if search_query.end_time:
            param_count += 1
            conditions.append(f"rc.timestamp <= ${param_count}")
            params.append(search_query.end_time)

        # Add ranking for text search
        rank_clause = ""
        if search_query.query_text:
            rank_clause = (
                f", ts_rank(to_tsvector('english', t.full_transcript), "
                f"plainto_tsquery(${params.index(search_query.query_text) + 1})) "
                f"as search_rank"
            )
            order_clause = "ORDER BY search_rank DESC, rc.timestamp DESC"
        else:
            rank_clause = ", NULL as search_rank"
            order_clause = "ORDER BY rc.timestamp DESC"

        # Add LIMIT and OFFSET
        param_count += 1
        limit_param = f"${param_count}"
        params.append(search_query.limit)

        param_count += 1
        offset_param = f"${param_count}"
        params.append(search_query.offset)

        query = f"""
            SELECT rc.call_id, rc.timestamp, rc.frequency, rc.talkgroup_id,
                   rc.talkgroup_label, rc.system_label, rc.talker_alias,
                   rc.audio_file_path, rc.audio_duration_seconds,
                   t.full_transcript, t.speaker_count, t.confidence_score
                   {rank_clause}
            FROM radio_calls rc
            JOIN transcriptions t ON rc.call_id = t.call_id
            WHERE {' AND '.join(conditions)}
            {order_clause}
            LIMIT {limit_param} OFFSET {offset_param}
        """

        rows = await self.db.fetch(query, *params)
        return [SearchResult(**dict(row)) for row in rows]


class SpeakerSegmentOperations:
    """Database operations for speaker segments."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def create_speaker_segments(self, segments: List[SpeakerSegment]) -> List[SpeakerSegment]:
        """Create multiple speaker segment records."""
        if not segments:
            return []

        # Build bulk insert query
        value_placeholders = []
        params: list[Any] = []
        param_count = 0

        for segment in segments:
            param_count += 1
            call_id_param = f"${param_count}"
            param_count += 1
            start_param = f"${param_count}"
            param_count += 1
            end_param = f"${param_count}"
            param_count += 1
            speaker_param = f"${param_count}"
            param_count += 1
            text_param = f"${param_count}"
            param_count += 1
            confidence_param = f"${param_count}"

            value_placeholders.append(
                f"({call_id_param}, {start_param}, {end_param}, " f"{speaker_param}, {text_param}, {confidence_param})"
            )

            params.extend(
                [
                    segment.call_id,
                    segment.start_time_seconds,
                    segment.end_time_seconds,
                    segment.speaker_id,
                    segment.text,
                    segment.confidence_score,
                ]
            )

        query = f"""
            INSERT INTO speaker_segments (
                call_id, start_time_seconds, end_time_seconds,
                speaker_id, text, confidence_score
            ) VALUES {', '.join(value_placeholders)}
            RETURNING segment_id, call_id, start_time_seconds, end_time_seconds,
                     speaker_id, text, confidence_score
        """

        rows = await self.db.fetch(query, *params)
        return [SpeakerSegment(**dict(row)) for row in rows]

    async def get_speaker_segments(self, call_id: UUID) -> List[SpeakerSegment]:
        """Get all speaker segments for a call."""
        query = """
            SELECT segment_id, call_id, start_time_seconds, end_time_seconds,
                   speaker_id, text, confidence_score
            FROM speaker_segments
            WHERE call_id = $1
            ORDER BY start_time_seconds
        """

        rows = await self.db.fetch(query, call_id)
        return [SpeakerSegment(**dict(row)) for row in rows]


class DatabaseOperations:
    """Combined database operations interface."""

    def __init__(self, db_manager: DatabaseManager):
        self.radio_calls = RadioCallOperations(db_manager)
        self.transcriptions = TranscriptionOperations(db_manager)
        self.speaker_segments = SpeakerSegmentOperations(db_manager)
        self.security_events = SecurityEventOperations(db_manager)
        self.db = db_manager

    async def store_complete_transcription(
        self,
        radio_call: RadioCallCreate,
        transcription: TranscriptionCreate,
        speaker_segments: List[SpeakerSegment],
    ) -> TranscriptionStoreResult:
        """Store a complete transcription result atomically with proper rollback."""
        async with self.db.transaction() as conn:
            try:
                # Create radio call first
                call_id = radio_call.call_id

                # Insert radio call
                radio_call_sql = """
                    INSERT INTO radio_calls (
                        call_id, timestamp, frequency, talkgroup_id, source_radio_id, system_id,
                        system_label, talkgroup_label, talkgroup_group, talker_alias,
                        audio_file_path, audio_duration_seconds, audio_format,
                        transcription_status, upload_source_ip, upload_source_system,
                        upload_api_key_id, upload_user_agent
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                    RETURNING *
                """
                stored_call_row = await conn.fetchrow(
                    radio_call_sql,
                    call_id,
                    radio_call.timestamp,
                    radio_call.frequency,
                    radio_call.talkgroup_id,
                    radio_call.source_radio_id,
                    radio_call.system_id,
                    radio_call.system_label,
                    radio_call.talkgroup_label,
                    radio_call.talkgroup_group,
                    radio_call.talker_alias,
                    radio_call.audio_file_path,
                    radio_call.audio_duration_seconds,
                    radio_call.audio_format,
                    "processing",
                    radio_call.upload_source_ip,
                    radio_call.upload_source_system,
                    radio_call.upload_api_key_id,
                    radio_call.upload_user_agent,
                )

                # Insert transcription
                transcription_sql = """
                    INSERT INTO transcriptions (
                        call_id, full_transcript, language, confidence_score,
                        speaker_count, model_name, processing_time_seconds
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                """
                stored_transcription_row = await conn.fetchrow(
                    transcription_sql,
                    call_id,
                    transcription.full_transcript,
                    transcription.language,
                    transcription.confidence_score,
                    transcription.speaker_count,
                    transcription.model_name,
                    transcription.processing_time_seconds,
                )

                # Insert speaker segments
                stored_segments = []
                if speaker_segments:
                    segment_sql = """
                        INSERT INTO speaker_segments (
                            call_id, segment_id, start_time_seconds, end_time_seconds,
                            speaker_id, text, confidence_score
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        RETURNING *
                    """
                    for segment in speaker_segments:
                        segment_row = await conn.fetchrow(
                            segment_sql,
                            call_id,
                            segment.segment_id,
                            segment.start_time_seconds,
                            segment.end_time_seconds,
                            segment.speaker_id,
                            segment.text,
                            segment.confidence_score,
                        )
                        stored_segments.append(segment_row)

                # Update radio call status to completed
                await conn.execute(
                    "UPDATE radio_calls SET transcription_status = $1, transcribed_at = NOW() WHERE call_id = $2",
                    "completed",
                    call_id,
                )

                logger.info(f"Stored complete transcription for call {call_id}: " f"{len(stored_segments)} segments")

                return {
                    "radio_call": dict(stored_call_row),
                    "transcription": dict(stored_transcription_row),
                    "speaker_segments": [dict(row) for row in stored_segments],
                }

            except Exception as e:
                logger.error(f"Failed to store transcription for call {call_id}: {e}")
                # Transaction will automatically rollback on exception
                raise


class SecurityEventOperations:
    """Database operations for security events."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def create_security_event(self, event: SecurityEvent) -> SecurityEvent:
        """Create a new security event record."""
        query = """
            INSERT INTO security_events (
                timestamp, event_type, severity, source_ip, source_system,
                api_key_used, user_agent, description, metadata,
                related_call_id, related_file_path
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING event_id, timestamp, event_type, severity, source_ip,
                     source_system, api_key_used, user_agent, description,
                     metadata, related_call_id, related_file_path
        """

        # Convert metadata dict to JSON if provided
        metadata_json = json.dumps(event.metadata) if event.metadata else None

        row = await self.db.fetchrow(
            query,
            event.timestamp,
            event.event_type,
            event.severity,
            event.source_ip,
            event.source_system,
            event.api_key_used,
            event.user_agent,
            event.description,
            metadata_json,
            event.related_call_id,
            event.related_file_path,
        )

        if not row:
            raise RuntimeError("Failed to create security event")

        # Convert row to dict and parse JSON metadata back to dict
        row_dict = dict(row)
        if row_dict.get("metadata") and isinstance(row_dict["metadata"], str):
            row_dict["metadata"] = json.loads(row_dict["metadata"])

        # Convert INET type to string
        if row_dict.get("source_ip"):
            row_dict["source_ip"] = str(row_dict["source_ip"])

        return SecurityEvent(**row_dict)

    async def get_security_events(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        source_ip: Optional[str] = None,
        source_system: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[SecurityEvent]:
        """Get security events with filtering."""
        where_conditions = []
        params: list[Any] = []
        param_index = 1

        if event_type:
            where_conditions.append(f"event_type = ${param_index}")
            params.append(event_type)
            param_index += 1

        if severity:
            where_conditions.append(f"severity = ${param_index}")
            params.append(severity)
            param_index += 1

        if source_ip:
            where_conditions.append(f"source_ip = ${param_index}")
            params.append(source_ip)
            param_index += 1

        if source_system:
            where_conditions.append(f"source_system = ${param_index}")
            params.append(source_system)
            param_index += 1

        if start_time:
            where_conditions.append(f"timestamp >= ${param_index}")
            params.append(start_time)
            param_index += 1

        if end_time:
            where_conditions.append(f"timestamp <= ${param_index}")
            params.append(end_time)
            param_index += 1

        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""

        query = f"""
            SELECT event_id, timestamp, event_type, severity, source_ip,
                   source_system, api_key_used, user_agent, description,
                   metadata, related_call_id, related_file_path
            FROM security_events
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ${param_index} OFFSET ${param_index + 1}
        """

        params.extend([limit, offset])
        rows = await self.db.fetch(query, *params)

        # Convert rows and parse JSON metadata
        results = []
        for row in rows:
            row_dict = dict(row)
            if row_dict.get("metadata") and isinstance(row_dict["metadata"], str):
                row_dict["metadata"] = json.loads(row_dict["metadata"])

            # Convert INET type to string
            if row_dict.get("source_ip"):
                row_dict["source_ip"] = str(row_dict["source_ip"])

            results.append(SecurityEvent(**row_dict))

        return results

    async def get_upload_source_analysis(self, source_system: str) -> UploadSourceAnalysis:
        """Analyze upload patterns for a specific source system."""
        # Get upload statistics
        upload_stats_query = """
            SELECT
                COUNT(*) as total_uploads,
                COUNT(DISTINCT upload_source_ip) as unique_ips,
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen
            FROM radio_calls
            WHERE upload_source_system = $1
        """

        upload_stats = await self.db.fetchrow(upload_stats_query, source_system)

        # Get security events for this system
        security_events_query = """
            SELECT
                COUNT(*) as total_events,
                COUNT(*) FILTER (WHERE severity IN ('high', 'critical')) as violations,
                COUNT(*) FILTER (WHERE event_type LIKE '%upload%') as upload_events
            FROM security_events
            WHERE source_system = $1
        """

        security_stats = await self.db.fetchrow(security_events_query, source_system)

        # Get recent events
        recent_events = await self.get_security_events(limit=10, source_system=source_system)

        # Get IP addresses used by this system
        ips_query = """
            SELECT DISTINCT upload_source_ip, COUNT(*) as upload_count
            FROM radio_calls
            WHERE upload_source_system = $1 AND upload_source_ip IS NOT NULL
            GROUP BY upload_source_ip
            ORDER BY upload_count DESC
        """

        ip_stats = await self.db.fetch(ips_query, source_system)

        return {
            "system_id": source_system,
            "upload_statistics": dict(upload_stats) if upload_stats else {},
            "security_statistics": dict(security_stats) if security_stats else {},
            "ip_addresses": [dict(row) for row in ip_stats],
            "recent_events": recent_events,
        }
