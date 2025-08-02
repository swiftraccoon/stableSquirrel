"""Security monitoring and analysis API endpoints."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from stable_squirrel.database.operations import DatabaseOperations

logger = logging.getLogger(__name__)

router = APIRouter()


class SecurityEventResponse(BaseModel):
    """Response model for security events."""

    event_id: str
    timestamp: str
    event_type: str
    severity: str
    source_ip: Optional[str] = None
    source_system: Optional[str] = None
    api_key_used: Optional[str] = None
    user_agent: Optional[str] = None
    description: str
    metadata: Optional[Dict] = None
    related_call_id: Optional[str] = None
    related_file_path: Optional[str] = None


class SecurityEventsResponse(BaseModel):
    """Paginated response for security events."""

    events: List[SecurityEventResponse]
    total: int
    limit: int
    offset: int


class UploadSourceAnalysis(BaseModel):
    """Upload source analysis response."""

    system_id: str
    upload_statistics: Dict
    security_statistics: Dict
    ip_addresses: List[Dict]
    recent_events: List[SecurityEventResponse]


class SecuritySummary(BaseModel):
    """Security summary response."""

    total_events: int
    events_by_severity: Dict[str, int]
    recent_violations: List[SecurityEventResponse]
    top_source_systems: List[Dict]
    top_source_ips: List[Dict]


@router.get("/events", response_model=SecurityEventsResponse)
async def get_security_events(
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    source_ip: Optional[str] = Query(None, description="Filter by source IP"),
    source_system: Optional[str] = Query(None, description="Filter by source system"),
    start_time: Optional[datetime] = Query(None, description="Filter events after this time"),
    end_time: Optional[datetime] = Query(None, description="Filter events before this time"),
) -> SecurityEventsResponse:
    """Get security events with filtering and pagination."""

    try:
        # Get database operations from app state
        db_manager = request.app.state.db_manager
        db_ops = DatabaseOperations(db_manager)

        # Get filtered security events
        events = await db_ops.security_events.get_security_events(
            limit=limit,
            offset=offset,
            event_type=event_type,
            severity=severity,
            source_ip=source_ip,
            source_system=source_system,
            start_time=start_time,
            end_time=end_time,
        )

        # Convert to response format
        event_responses = []
        for event in events:
            event_response = SecurityEventResponse(
                event_id=str(event.event_id),
                timestamp=event.timestamp.isoformat(),
                event_type=event.event_type,
                severity=event.severity,
                source_ip=event.source_ip,
                source_system=event.source_system,
                api_key_used=event.api_key_used,
                user_agent=event.user_agent,
                description=event.description,
                metadata=event.metadata,
                related_call_id=str(event.related_call_id) if event.related_call_id else None,
                related_file_path=event.related_file_path,
            )
            event_responses.append(event_response)

        # For now, use the length of results as total (would need separate count query for exact total)
        total_count = len(events) + offset

        return SecurityEventsResponse(
            events=event_responses,
            total=total_count,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(f"Error retrieving security events: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving security events: {str(e)}")


@router.get("/analysis/source/{system_id}", response_model=UploadSourceAnalysis)
async def get_upload_source_analysis(
    request: Request,
    system_id: str,
) -> UploadSourceAnalysis:
    """Get detailed analysis for a specific upload source system."""

    try:
        # Get database operations from app state
        db_manager = request.app.state.db_manager
        db_ops = DatabaseOperations(db_manager)

        # Get upload source analysis
        analysis = await db_ops.security_events.get_upload_source_analysis(system_id)

        # Convert recent events to response format
        recent_events = []
        for event in analysis.get("recent_events", []):
            event_response = SecurityEventResponse(
                event_id=str(event.event_id),
                timestamp=event.timestamp.isoformat(),
                event_type=event.event_type,
                severity=event.severity,
                source_ip=event.source_ip,
                source_system=event.source_system,
                api_key_used=event.api_key_used,
                user_agent=event.user_agent,
                description=event.description,
                metadata=event.metadata,
                related_call_id=str(event.related_call_id) if event.related_call_id else None,
                related_file_path=event.related_file_path,
            )
            recent_events.append(event_response)

        return UploadSourceAnalysis(
            system_id=analysis["system_id"],
            upload_statistics=analysis["upload_statistics"],
            security_statistics=analysis["security_statistics"],
            ip_addresses=analysis["ip_addresses"],
            recent_events=recent_events,
        )

    except Exception as e:
        logger.error(f"Error retrieving upload source analysis for {system_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving upload source analysis: {str(e)}")


@router.get("/summary", response_model=SecuritySummary)
async def get_security_summary(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back for summary"),
) -> SecuritySummary:
    """Get security summary for the specified time period."""

    try:
        # Get database operations from app state
        db_manager = request.app.state.db_manager
        db_ops = DatabaseOperations(db_manager)

        # Calculate time range
        from datetime import timedelta

        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # Get all events in the time range
        all_events = await db_ops.security_events.get_security_events(
            limit=10000,  # Large limit to get all events
            start_time=start_time,
            end_time=end_time,
        )

        # Calculate summary statistics
        total_events = len(all_events)

        # Count events by severity
        events_by_severity = {}
        for event in all_events:
            severity = event.severity
            events_by_severity[severity] = events_by_severity.get(severity, 0) + 1

        # Get recent high-severity violations
        recent_violations = [
            SecurityEventResponse(
                event_id=str(event.event_id),
                timestamp=event.timestamp.isoformat(),
                event_type=event.event_type,
                severity=event.severity,
                source_ip=event.source_ip,
                source_system=event.source_system,
                api_key_used=event.api_key_used,
                user_agent=event.user_agent,
                description=event.description,
                metadata=event.metadata,
                related_call_id=str(event.related_call_id) if event.related_call_id else None,
                related_file_path=event.related_file_path,
            )
            for event in all_events[:10]  # Top 10 recent events
            if event.severity in ["high", "critical"]
        ]

        # Count top source systems
        system_counts = {}
        for event in all_events:
            if event.source_system:
                system_counts[event.source_system] = system_counts.get(event.source_system, 0) + 1

        top_source_systems = [
            {"system_id": system, "event_count": count}
            for system, count in sorted(system_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # Count top source IPs
        ip_counts = {}
        for event in all_events:
            if event.source_ip:
                ip_counts[event.source_ip] = ip_counts.get(event.source_ip, 0) + 1

        top_source_ips = [
            {"ip_address": ip, "event_count": count}
            for ip, count in sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        return SecuritySummary(
            total_events=total_events,
            events_by_severity=events_by_severity,
            recent_violations=recent_violations,
            top_source_systems=top_source_systems,
            top_source_ips=top_source_ips,
        )

    except Exception as e:
        logger.error(f"Error generating security summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating security summary: {str(e)}")


@router.get("/uploads/sources", response_model=List[Dict])
async def get_upload_sources(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Number of sources to return"),
) -> List[Dict]:
    """Get list of all upload sources with basic statistics."""

    try:
        # Get database operations from app state
        db_manager = request.app.state.db_manager

        # Get distinct upload sources with counts
        query = """
            SELECT
                upload_source_system,
                upload_source_ip,
                COUNT(*) as upload_count,
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen,
                COUNT(DISTINCT upload_api_key_id) as unique_api_keys
            FROM radio_calls
            WHERE upload_source_system IS NOT NULL
            GROUP BY upload_source_system, upload_source_ip
            ORDER BY upload_count DESC
            LIMIT $1
        """

        rows = await db_manager.fetch(query, limit)

        sources = []
        for row in rows:
            source = {
                "system_id": row["upload_source_system"],
                "ip_address": row["upload_source_ip"],
                "upload_count": row["upload_count"],
                "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
                "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                "unique_api_keys": row["unique_api_keys"],
            }
            sources.append(source)

        return sources

    except Exception as e:
        logger.error(f"Error retrieving upload sources: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving upload sources: {str(e)}")
