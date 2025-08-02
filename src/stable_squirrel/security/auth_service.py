"""Enhanced authentication and security service."""

import logging
from typing import TYPE_CHECKING, Optional, Tuple
from uuid import UUID

from stable_squirrel.config import IngestionConfig
from stable_squirrel.database.models import SecurityEvent

if TYPE_CHECKING:
    from stable_squirrel.database.operations import SecurityEventOperations

logger = logging.getLogger(__name__)


class SecurityAuthService:
    """Enhanced authentication service with IP validation and audit logging."""

    def __init__(self, config: IngestionConfig, security_ops: Optional["SecurityEventOperations"] = None):
        self.config = config
        self.security_ops = security_ops
        self._security_events = []  # Fallback in-memory storage if no DB operations provided

    async def validate_api_key(
        self,
        api_key: str,
        client_ip: str,
        system_id: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[SecurityEvent]]:
        """
        Validate API key with enhanced security checks.

        Returns:
            (is_valid, api_key_id, security_event)
        """

        # Check legacy single API key first (for backward compatibility)
        if self.config.api_key and api_key == self.config.api_key:
            await self._log_security_event(
                event_type="api_key_used",
                severity="info",
                source_ip=client_ip,
                source_system=system_id,
                api_key_used="legacy",
                user_agent=user_agent,
                description=f"Legacy API key used by system {system_id}"
            )
            return True, "legacy", None

        # Check enhanced API keys
        for key_config in self.config.api_keys:
            if key_config.key == api_key:
                # Validate IP restrictions
                if key_config.allowed_ips and client_ip not in key_config.allowed_ips:
                    event = await self._log_security_event(
                        event_type="api_key_ip_violation",
                        severity="high",
                        source_ip=client_ip,
                        source_system=system_id,
                        api_key_used=key_config.key[:8] + "...",  # Partial key for logging
                        user_agent=user_agent,
                        description=f"API key used from unauthorized IP {client_ip}",
                        metadata={
                            "allowed_ips": key_config.allowed_ips,
                            "actual_ip": client_ip
                        }
                    )
                    return False, None, event

                # Validate system restrictions
                if key_config.allowed_systems and system_id and system_id not in key_config.allowed_systems:
                    event = await self._log_security_event(
                        event_type="api_key_system_violation",
                        severity="high",
                        source_ip=client_ip,
                        source_system=system_id,
                        api_key_used=key_config.key[:8] + "...",
                        user_agent=user_agent,
                        description=f"API key used by unauthorized system {system_id}",
                        metadata={
                            "allowed_systems": key_config.allowed_systems,
                            "actual_system": system_id
                        }
                    )
                    return False, None, event

                # Valid API key usage
                await self._log_security_event(
                    event_type="api_key_used",
                    severity="info",
                    source_ip=client_ip,
                    source_system=system_id,
                    api_key_used=key_config.key[:8] + "...",
                    user_agent=user_agent,
                    description=f"Valid API key used by system {system_id}",
                    metadata={"key_description": key_config.description}
                )
                return True, key_config.key[:8], None

        # No valid API key found
        event = await self._log_security_event(
            event_type="invalid_api_key",
            severity="medium",
            source_ip=client_ip,
            source_system=system_id,
            api_key_used=api_key[:8] + "..." if api_key else None,
            user_agent=user_agent,
            description=f"Invalid API key attempted by system {system_id}"
        )
        return False, None, event

    async def log_upload_attempt(
        self,
        client_ip: str,
        system_id: Optional[str],
        api_key_id: Optional[str],
        user_agent: Optional[str],
        file_name: Optional[str],
        success: bool,
        reason: Optional[str] = None
    ) -> None:
        """Log file upload attempt for audit trail."""

        event_type = "upload_success" if success else "upload_blocked"
        severity = "info" if success else "medium"
        description = f"File upload {'succeeded' if success else 'blocked'}"
        if reason:
            description += f": {reason}"

        await self._log_security_event(
            event_type=event_type,
            severity=severity,
            source_ip=client_ip,
            source_system=system_id,
            api_key_used=api_key_id,
            user_agent=user_agent,
            description=description,
            metadata={
                "file_name": file_name,
                "reason": reason
            }
        )

    async def log_rate_limit_violation(
        self,
        client_ip: str,
        system_id: Optional[str],
        limit_type: str,
        current_count: int,
        limit: int
    ) -> None:
        """Log rate limit violations."""

        await self._log_security_event(
            event_type="rate_limit_exceeded",
            severity="medium",
            source_ip=client_ip,
            source_system=system_id,
            description=f"Rate limit exceeded: {limit_type}",
            metadata={
                "limit_type": limit_type,
                "current_count": current_count,
                "limit": limit
            }
        )

    async def _log_security_event(
        self,
        event_type: str,
        severity: str,
        source_ip: Optional[str] = None,
        source_system: Optional[str] = None,
        api_key_used: Optional[str] = None,
        user_agent: Optional[str] = None,
        description: str = "",
        metadata: Optional[dict] = None,
        related_call_id: Optional[str] = None,
        related_file_path: Optional[str] = None
    ) -> SecurityEvent:
        """Create and store a security event."""

        # Convert related_call_id from string to UUID if provided
        call_id_uuid = None
        if related_call_id:
            try:
                call_id_uuid = UUID(related_call_id)
            except ValueError:
                logger.warning(f"Invalid UUID format for related_call_id: {related_call_id}")

        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            source_ip=source_ip,
            source_system=source_system,
            api_key_used=api_key_used,
            user_agent=user_agent,
            description=description,
            metadata=metadata,
            related_call_id=call_id_uuid,
            related_file_path=related_file_path
        )

        # Store in database if available, otherwise fall back to memory
        if self.security_ops:
            try:
                await self.security_ops.create_security_event(event)
            except Exception as e:
                logger.warning(f"Failed to store security event in database: {e}")
                self._security_events.append(event)
        else:
            self._security_events.append(event)

        # Log to application logger based on severity
        log_level = {
            "info": logger.info,
            "low": logger.info,
            "medium": logger.warning,
            "high": logger.error,
            "critical": logger.critical
        }.get(severity, logger.info)

        log_level(f"Security Event [{event_type}]: {description} "
                 f"(IP: {source_ip}, System: {source_system})")

        return event

    async def get_security_events(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        severity: Optional[str] = None
    ) -> list[SecurityEvent]:
        """Retrieve security events for analysis."""

        # Use database if available, otherwise fall back to memory
        if self.security_ops:
            try:
                return await self.security_ops.get_security_events(
                    limit=limit,
                    event_type=event_type,
                    severity=severity
                )
            except Exception as e:
                logger.warning(f"Failed to retrieve security events from database: {e}")

        # Fallback to in-memory events
        events = self._security_events

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if severity:
            events = [e for e in events if e.severity == severity]

        # Return most recent events first
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def get_upload_source_analysis(self, system_id: str) -> dict:
        """Analyze upload patterns for a specific source system."""

        # Use database if available, otherwise fall back to memory
        if self.security_ops:
            try:
                return await self.security_ops.get_upload_source_analysis(system_id)
            except Exception as e:
                logger.warning(f"Failed to retrieve upload analysis from database: {e}")

        # Fallback to in-memory analysis
        system_events = [
            e for e in self._security_events
            if e.source_system == system_id
        ]

        return {
            "system_id": system_id,
            "total_events": len(system_events),
            "upload_attempts": len([e for e in system_events if "upload" in e.event_type]),
            "security_violations": len([
                e for e in system_events
                if e.severity in ["high", "critical"]
            ]),
            "last_seen": max([e.timestamp for e in system_events]) if system_events else None,
            "unique_ips": len(set([e.source_ip for e in system_events if e.source_ip])),
            "recent_events": system_events[:10]  # Last 10 events
        }
