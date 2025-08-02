"""Database schema creation and TimescaleDB setup."""

import logging

from .connection import DatabaseManager

logger = logging.getLogger(__name__)


async def create_schema(db_manager: DatabaseManager) -> None:
    """Create all database tables and indexes."""

    logger.info("Creating database schema...")

    # SQL for creating radio_calls table
    radio_calls_sql = """
    CREATE TABLE IF NOT EXISTS radio_calls (
        -- Time-series primary key
        timestamp TIMESTAMPTZ NOT NULL,
        call_id UUID DEFAULT gen_random_uuid(),

        -- Radio metadata (from SDRTrunk/RdioScanner)
        frequency BIGINT NOT NULL,
        talkgroup_id INTEGER,
        source_radio_id INTEGER,
        system_id INTEGER,

        -- Labels and aliases
        system_label TEXT,
        talkgroup_label TEXT,
        talkgroup_group TEXT,
        talker_alias TEXT,

        -- Audio file reference
        audio_file_path TEXT NOT NULL,
        audio_duration_seconds REAL,
        audio_format TEXT DEFAULT 'wav',

        -- Transcription status
        transcription_status TEXT DEFAULT 'pending',
        transcribed_at TIMESTAMPTZ,

        -- Security tracking (enhanced security)
        upload_source_ip INET,
        upload_source_system TEXT,
        upload_api_key_id TEXT,
        upload_user_agent TEXT,

        PRIMARY KEY (timestamp, call_id)
    );
    """

    # SQL for creating transcriptions table
    transcriptions_sql = """
    CREATE TABLE IF NOT EXISTS transcriptions (
        call_id UUID NOT NULL,

        -- WhisperX results
        full_transcript TEXT NOT NULL,
        language TEXT,
        confidence_score REAL,

        -- Speaker diarization
        speaker_count INTEGER DEFAULT 1,

        -- Processing metadata
        model_name TEXT,
        processing_time_seconds REAL,

        PRIMARY KEY (call_id)
    );
    """

    # SQL for creating speaker_segments table
    speaker_segments_sql = """
    CREATE TABLE IF NOT EXISTS speaker_segments (
        call_id UUID NOT NULL,
        segment_id UUID DEFAULT gen_random_uuid(),

        -- Timing within the call
        start_time_seconds REAL NOT NULL,
        end_time_seconds REAL NOT NULL,

        -- Speaker identification
        speaker_id TEXT NOT NULL,

        -- Segment transcript
        text TEXT NOT NULL,
        confidence_score REAL,

        PRIMARY KEY (call_id, segment_id)
    );
    """

    # SQL for creating security_events table
    security_events_sql = """
    CREATE TABLE IF NOT EXISTS security_events (
        -- Time-series primary key
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        event_id UUID DEFAULT gen_random_uuid(),

        -- Event classification
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),

        -- Source information
        source_ip INET,
        source_system TEXT,
        api_key_used TEXT,
        user_agent TEXT,

        -- Event details
        description TEXT NOT NULL,
        metadata JSONB,

        -- Related entities
        related_call_id UUID,
        related_file_path TEXT,

        PRIMARY KEY (timestamp, event_id)
    );
    """

    # Create indexes for optimal query performance
    indexes_sql = [
        # Time-range queries (most common)
        (
            "CREATE INDEX IF NOT EXISTS idx_calls_timestamp "
            "ON radio_calls (timestamp DESC);"
        ),
        # Frequency and talkgroup searches
        (
            "CREATE INDEX IF NOT EXISTS idx_calls_frequency "
            "ON radio_calls (frequency, timestamp DESC);"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_calls_talkgroup "
            "ON radio_calls (talkgroup_id, timestamp DESC);"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_calls_system "
            "ON radio_calls (system_id, timestamp DESC);"
        ),
        # Transcription status
        (
            "CREATE INDEX IF NOT EXISTS idx_calls_status "
            "ON radio_calls (transcription_status);"
        ),
        # Full-text search on transcripts
        (
            "CREATE INDEX IF NOT EXISTS idx_transcript_text "
            "ON transcriptions USING GIN(to_tsvector('english', full_transcript));"
        ),
        # Speaker segment searches
        (
            "CREATE INDEX IF NOT EXISTS idx_segments_speaker "
            "ON speaker_segments (speaker_id, call_id);"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_segments_timing "
            "ON speaker_segments (call_id, start_time_seconds);"
        ),
        # Security event indexes
        (
            "CREATE INDEX IF NOT EXISTS idx_security_events_timestamp "
            "ON security_events (timestamp DESC);"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_security_events_type "
            "ON security_events (event_type, timestamp DESC);"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_security_events_severity "
            "ON security_events (severity, timestamp DESC);"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_security_events_source_ip "
            "ON security_events (source_ip, timestamp DESC);"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_security_events_source_system "
            "ON security_events (source_system, timestamp DESC);"
        ),
        # Security tracking indexes on radio_calls
        (
            "CREATE INDEX IF NOT EXISTS idx_calls_upload_source_ip "
            "ON radio_calls (upload_source_ip, timestamp DESC);"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_calls_upload_source_system "
            "ON radio_calls (upload_source_system, timestamp DESC);"
        ),
    ]

    try:
        # Create tables
        await db_manager.execute(radio_calls_sql)
        await db_manager.execute(transcriptions_sql)
        await db_manager.execute(speaker_segments_sql)
        await db_manager.execute(security_events_sql)

        # Create indexes
        for index_sql in indexes_sql:
            await db_manager.execute(index_sql)

        logger.info("Database schema created successfully")

    except Exception as e:
        logger.error(f"Failed to create database schema: {e}")
        raise


async def ensure_timescale_setup(db_manager: DatabaseManager) -> None:
    """Set up TimescaleDB hypertables and policies."""

    logger.info("Setting up TimescaleDB optimizations...")

    try:
        # Check if TimescaleDB is available
        ts_check = await db_manager.fetchval(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'"
        )

        if not ts_check:
            logger.warning(
                "TimescaleDB extension not found - run: CREATE EXTENSION timescaledb;"
            )
            return

        # Check if radio_calls is already a hypertable
        hypertable_check = await db_manager.fetchval(
            (
                "SELECT COUNT(*) FROM timescaledb_information.hypertables "
                "WHERE hypertable_name = 'radio_calls'"
            )
        )

        if not hypertable_check:
            # Convert radio_calls to hypertable (partitioned by time)
            await db_manager.execute(
                (
                    "SELECT create_hypertable('radio_calls', 'timestamp', "
                    "if_not_exists => TRUE)"
                )
            )
            logger.info("Created radio_calls hypertable")

        # Check if security_events is already a hypertable
        security_hypertable_check = await db_manager.fetchval(
            (
                "SELECT COUNT(*) FROM timescaledb_information.hypertables "
                "WHERE hypertable_name = 'security_events'"
            )
        )

        if not security_hypertable_check:
            # Convert security_events to hypertable (partitioned by time)
            await db_manager.execute(
                (
                    "SELECT create_hypertable('security_events', 'timestamp', "
                    "if_not_exists => TRUE)"
                )
            )
            logger.info("Created security_events hypertable")

        # Set chunk time interval to 1 day (optimize for our query patterns)
        await db_manager.execute(
            "SELECT set_chunk_time_interval('radio_calls', INTERVAL '1 day')"
        )

        # Enable compression for older data (saves storage)
        await db_manager.execute(
            """
            ALTER TABLE radio_calls SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'frequency, talkgroup_id'
            )
        """
        )

        # Auto-compress data older than 30 days
        compression_policy_check = await db_manager.fetchval(
            (
                "SELECT COUNT(*) FROM timescaledb_information.jobs "
                "WHERE proc_name = 'policy_compression'"
            )
        )

        if not compression_policy_check:
            await db_manager.execute(
                "SELECT add_compression_policy('radio_calls', INTERVAL '30 days')"
            )
            logger.info("Added compression policy for old data")

        logger.info("TimescaleDB setup completed")

    except Exception as e:
        logger.error(f"Failed to set up TimescaleDB optimizations: {e}")
        # Don't raise - the system can work without these optimizations
