"""RdioScanner API endpoint for receiving calls from SDRTrunk."""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from stable_squirrel.security import (
    SecurityAuthService,
    SecurityConfig,
    ValidationError,
    configure_validator,
    validate_audio_file,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def parse_multipart_manually(content_type: str, body: bytes) -> dict:
    """
    Manually parse multipart form data from raw bytes.
    This handles cases where FastAPI's form parsing fails due to HTTP/2 upgrade issues.
    """
    if not content_type or not content_type.startswith('multipart/form-data'):
        logger.error(f"Invalid content-type: {content_type}")
        return {}

    # Extract boundary from content-type header
    boundary = None
    for part in content_type.split(';'):
        part = part.strip()
        if part.startswith('boundary='):
            boundary = part[9:].strip('"')
            break

    if not boundary:
        logger.error("No boundary found in content-type header")
        return {}

    logger.debug(f"Parsing multipart data with boundary: {boundary}")
    logger.debug(f"Body size: {len(body)} bytes")

    # Parse multipart data manually
    fields = {}
    boundary_bytes = f'--{boundary}'.encode()

    logger.debug(f"Looking for boundary: {boundary_bytes}")

    # Split by boundary
    parts = body.split(boundary_bytes)
    logger.debug(f"Found {len(parts)} parts after splitting by boundary")

    for i, part in enumerate(parts):
        logger.debug(f"Processing part {i}: {len(part)} bytes")
        if i == 0:
            # First part is usually empty or just preamble
            logger.debug(f"Skipping first part (preamble): {part[:50]}...")
            continue

        if part.strip() == b'--' or part.strip() == b'':
            # Last part with closing boundary marker
            logger.debug(f"Skipping closing part: {part}")
            continue

        logger.debug(f"Part {i} content preview: {part[:200]}...")

        # Find the headers/body separator
        headers_section = None
        body_section = None

        if b'\r\n\r\n' in part:
            headers_section, body_section = part.split(b'\r\n\r\n', 1)
            logger.debug("Found \\r\\n\\r\\n separator")
        elif b'\n\n' in part:
            headers_section, body_section = part.split(b'\n\n', 1)
            logger.debug("Found \\n\\n separator")
        else:
            logger.warning(f"No header/body separator found in part {i}")
            continue

        # Parse headers
        headers_text = headers_section.decode('utf-8', errors='ignore').strip()
        logger.debug(f"Headers text: {repr(headers_text)}")

        field_name = None
        filename = None
        content_type_field = None

        for line in headers_text.split('\n'):
            line = line.strip()
            logger.debug(f"Processing header line: {repr(line)}")

            if line.startswith('Content-Disposition:'):
                logger.debug(f"Found Content-Disposition: {line}")
                # Extract name and filename
                for item in line.split(';'):
                    item = item.strip()
                    if item.startswith('name="'):
                        field_name = item[6:-1]
                        logger.debug(f"Extracted field name: {field_name}")
                    elif item.startswith('filename="'):
                        filename = item[10:-1]
                        logger.debug(f"Extracted filename: {filename}")
            elif line.startswith('Content-Type:'):
                content_type_field = line[13:].strip()
                logger.debug(f"Extracted content-type: {content_type_field}")

        if field_name:
            # Clean up body section (remove leading/trailing whitespace)
            body_section = body_section.rstrip(b'\r\n').rstrip(b'\n')

            if filename:
                # This is a file field
                # Default content-type if not provided
                if not content_type_field:
                    content_type_field = "application/octet-stream"

                logger.debug(
                    f"Found file field '{field_name}': {filename} "
                    f"({content_type_field}, {len(body_section)} bytes)"
                )
                # Create a simple file-like object
                class SimpleUploadFile:
                    def __init__(self, filename, content_type, content):
                        self.filename = filename
                        self.content_type = content_type
                        self.content = content
                        self.size = len(content)

                    async def read(self):
                        return self.content

                fields[field_name] = SimpleUploadFile(filename, content_type_field, body_section)
            else:
                # This is a regular field
                value = body_section.decode('utf-8', errors='ignore').strip()
                logger.debug(f"Found field '{field_name}': {value}")
                fields[field_name] = value
        else:
            logger.warning(f"No field name found in part {i}")

    logger.debug(f"Parsed {len(fields)} fields total")
    return fields


class RdioScannerUpload(BaseModel):
    """Model for RdioScanner call upload data."""
    # Required fields
    key: str
    system: str
    dateTime: int  # Unix timestamp in seconds

    # Audio file info (from UploadFile)
    audio_filename: str
    audio_content_type: str
    audio_size: int

    # Radio metadata (optional)
    frequency: Optional[int] = None
    talkgroup: Optional[int] = None
    source: Optional[int] = None  # Source radio ID

    # Labels and descriptions (optional)
    systemLabel: Optional[str] = None
    talkgroupLabel: Optional[str] = None
    talkgroupGroup: Optional[str] = None
    talkerAlias: Optional[str] = None
    patches: Optional[str] = None

    # Additional fields that might be sent
    frequencies: Optional[str] = None
    sources: Optional[str] = None
    talkgroupTag: Optional[str] = None


def get_client_info(request: Request) -> tuple[str, str]:
    """Extract client IP and user agent from request."""
    # Try to get real IP from X-Forwarded-For header (for proxy/load balancer setups)
    client_ip = request.headers.get("x-forwarded-for")
    if client_ip:
        # Take the first IP if there are multiple (original client)
        client_ip = client_ip.split(",")[0].strip()
    else:
        # Fall back to direct connection IP
        client_ip = request.client.host if request.client else "unknown"

    user_agent = request.headers.get("user-agent", "unknown")
    return client_ip, user_agent


async def validate_api_key_and_permissions(
    request: Request,
    key: str,
    system: str,
    client_ip: str,
    user_agent: str
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validate API key with enhanced security checks.

    Returns:
        (is_valid, api_key_id, error_message)
    """
    config = request.app.state.config
    db_manager = request.app.state.db_manager

    # Get database operations for security events
    from stable_squirrel.database.operations import DatabaseOperations
    db_ops = DatabaseOperations(db_manager)

    auth_service = SecurityAuthService(config.ingestion, db_ops.security_events)

    is_valid, api_key_id, security_event = await auth_service.validate_api_key(
        key, client_ip, system, user_agent
    )

    if not is_valid:
        error_msg = "Invalid or unauthorized API key"
        if security_event:
            if "ip" in security_event.event_type:
                error_msg = f"API key not authorized for IP {client_ip}"
            elif "system" in security_event.event_type:
                error_msg = f"API key not authorized for system {system}"

        return False, None, error_msg

    return True, api_key_id, None


async def validate_request_data(
    request: Request,
    form_data: dict,
    test: Optional[int],
    client_ip: str,
    user_agent: str
) -> tuple[bool, Optional[str]]:
    """
    Validate required request data and business rules.

    Returns:
        (is_valid, error_message)
    """
    config = request.app.state.config

    # Get fields from form data
    system = form_data.get("system")
    dateTime = form_data.get("dateTime")
    audio = form_data.get("audio")

    # Validate required fields for non-test requests
    if test is None:  # Not a test request
        if not audio:
            return False, "Audio file is required for non-test requests"
        if not system:
            return False, "System ID is required"
        if not dateTime:
            return False, "DateTime is required"

        # Enhanced validation: require system ID if configured
        if config.ingestion.require_system_id and not system:
            return False, "System ID is required by security policy"

    return True, None


async def perform_file_security_validation(
    request: Request,
    audio,
    client_ip: str,
    api_key_id: Optional[str],
    system: Optional[str],
    user_agent: str
) -> tuple[bool, Optional[str]]:
    """
    Perform comprehensive file security validation.

    Returns:
        (is_valid, error_message)
    """
    config = request.app.state.config

    if not audio or not config.ingestion.enable_file_validation:
        return True, None

    try:
        # Configure security validator based on config
        security_config = SecurityConfig(
            max_file_size=config.ingestion.max_file_size_mb * 1024 * 1024,
            max_uploads_per_minute=config.ingestion.max_uploads_per_minute,
            max_uploads_per_hour=config.ingestion.max_uploads_per_hour,
        )
        configure_validator(security_config)

        # Validate the uploaded file
        await validate_audio_file(audio, client_ip)

        # Log successful validation
        if config.ingestion.track_upload_sources:
            db_manager = request.app.state.db_manager
            from stable_squirrel.database.operations import DatabaseOperations
            db_ops = DatabaseOperations(db_manager)

            auth_service = SecurityAuthService(config.ingestion, db_ops.security_events)
            await auth_service.log_upload_attempt(
                client_ip=client_ip,
                system_id=system,
                api_key_id=api_key_id,
                user_agent=user_agent,
                file_name=getattr(audio, 'filename', None),
                success=True
            )

        return True, None

    except ValidationError as e:
        # Log failed validation
        if config.ingestion.track_upload_sources:
            db_manager = request.app.state.db_manager
            from stable_squirrel.database.operations import DatabaseOperations
            db_ops = DatabaseOperations(db_manager)

            auth_service = SecurityAuthService(config.ingestion, db_ops.security_events)
            await auth_service.log_upload_attempt(
                client_ip=client_ip,
                system_id=system,
                api_key_id=api_key_id,
                user_agent=user_agent,
                file_name=getattr(audio, 'filename', None),
                success=False,
                reason=str(e)
            )

        return False, f"File validation failed: {str(e)}"


def create_upload_data_model(
    form_data: dict, client_ip: str, api_key_id: Optional[str], user_agent: str
) -> RdioScannerUpload:
    """Create RdioScannerUpload model from form data with security tracking."""

    # Extract form data
    key = form_data.get("key")
    system = form_data.get("system")
    dateTime_str = form_data.get("dateTime")
    dateTime = int(dateTime_str) if dateTime_str else None
    audio = form_data.get("audio")
    audioName = form_data.get("audioName")
    audioType = form_data.get("audioType")

    # Radio metadata
    frequency_str = form_data.get("frequency")
    frequency = int(frequency_str) if frequency_str else None
    talkgroup_str = form_data.get("talkgroup")
    talkgroup = int(talkgroup_str) if talkgroup_str else None
    source_str = form_data.get("source")
    source = int(source_str) if source_str else None

    # Labels
    systemLabel = form_data.get("systemLabel")
    talkgroupLabel = form_data.get("talkgroupLabel")
    talkgroupGroup = form_data.get("talkgroupGroup")
    talkerAlias = form_data.get("talkerAlias")
    patches = form_data.get("patches")

    # Additional fields
    frequencies = form_data.get("frequencies")
    sources = form_data.get("sources")
    talkgroupTag = form_data.get("talkgroupTag")

    return RdioScannerUpload(
        key=key or "debug-key",
        system=system or "debug-system",
        dateTime=dateTime or 1703980800,  # Fallback timestamp
        audio_filename=audioName or (
            audio.filename if hasattr(audio, 'filename') and audio else "debug-mode.wav"
        ),
        audio_content_type=audioType or (
            audio.content_type if hasattr(audio, 'content_type') and audio else "application/octet-stream"
        ),
        audio_size=audio.size if hasattr(audio, 'size') and audio else 0,
        frequency=frequency,
        talkgroup=talkgroup,
        source=source,
        systemLabel=systemLabel,
        talkgroupLabel=talkgroupLabel,
        talkgroupGroup=talkgroupGroup,
        talkerAlias=talkerAlias,
        patches=patches,
        frequencies=frequencies,
        sources=sources,
        talkgroupTag=talkgroupTag,
    )


def determine_response_format(request: Request) -> bool:
    """Determine if client wants JSON response based on headers."""
    accept_header = request.headers.get("accept", "")
    user_agent = request.headers.get("user-agent", "").lower()
    return "application/json" in accept_header or "test" in user_agent


@router.post("/api/call-upload")
async def upload_call(request: Request) -> Response:
    """
    RdioScanner API endpoint for receiving calls from SDRTrunk.
    Enhanced with security tracking and IP-based API key validation.
    """
    temp_file_path = None

    try:
        # Extract client information
        client_ip, user_agent = get_client_info(request)

        logger.info("=== RdioScanner API Call Received ===")
        logger.info(f"Client IP: {client_ip}")
        logger.info(f"User Agent: {user_agent}")
        logger.info(f"Method: {request.method}")
        logger.info(f"URL: {request.url}")

        # Parse request data
        raw_body = await request.body()
        logger.debug(f"Raw body size: {len(raw_body)} bytes")

        # Handle different content types
        is_http2_upgrade = 'upgrade' in request.headers and request.headers['upgrade'] == 'h2c'
        content_type = request.headers.get('content-type', '')
        
        logger.info(f"Content-Type: {content_type}")
        logger.info(f"HTTP2 upgrade: {is_http2_upgrade}")
        logger.info(f"Request headers: {dict(request.headers)}")

        if 'multipart/form-data' in content_type and not is_http2_upgrade:
            logger.info("Using manual multipart parsing")
            form_data = parse_multipart_manually(content_type, raw_body)
        else:
            logger.info("Using FastAPI form parsing")
            fastapi_form = await request.form()
            form_data = dict(fastapi_form)

        # Extract core fields
        key = form_data.get("key")
        system = form_data.get("system")
        test_str = form_data.get("test")
        test = int(test_str) if test_str else None
        audio = form_data.get("audio")

        logger.info(f"Parsed form fields: {list(form_data.keys())}")
        logger.info(f"Key: {key}, System: {system}, Test: {test}")

        # Handle test requests first
        if test is not None:
            logger.info(f"Test request received from system {system}")
            wants_json = determine_response_format(request)
            test_message = "incomplete call data: no talkgroup"

            if wants_json:
                return {"status": "ok", "message": test_message, "callId": "test"}
            else:
                return Response(content=test_message, media_type="text/plain")

        # Enhanced API key validation with IP restrictions
        config = request.app.state.config

        # Check if any authentication is required
        has_legacy_key = bool(config.ingestion.api_key)
        has_enhanced_keys = bool(config.ingestion.api_keys)

        if has_legacy_key or has_enhanced_keys:
            # Authentication is required
            if has_legacy_key and not has_enhanced_keys:
                # Legacy API key only
                if key != config.ingestion.api_key:
                    logger.warning(f"Invalid legacy API key from system {system}")
                    raise HTTPException(status_code=401, detail="Invalid API key")
                api_key_id = "legacy"
            else:
                # Use enhanced API key validation
                if key and system:
                    is_valid, api_key_id, error_msg = await validate_api_key_and_permissions(
                        request, key, system, client_ip, user_agent
                    )
                else:
                    is_valid, api_key_id, error_msg = False, None, "Missing API key or system ID"
                if not is_valid:
                    logger.warning(f"API key validation failed: {error_msg}")
                    raise HTTPException(status_code=401, detail=error_msg)
        else:
            # No authentication required
            api_key_id = None
            logger.info(f"No API authentication configured - accepting upload from system {system}")

        # Validate request data
        is_valid, error_msg = await validate_request_data(
            request, form_data, test, client_ip, user_agent
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Perform file security validation
        is_valid, error_msg = await perform_file_security_validation(
            request, audio, client_ip, api_key_id, system, user_agent
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Create upload data model with security tracking
        upload_data = create_upload_data_model(form_data, client_ip, api_key_id, user_agent)

        # Log the incoming call
        logger.info(
            f"Received call: system={upload_data.system}, talkgroup={upload_data.talkgroup}, "
            f"frequency={upload_data.frequency}, source={upload_data.source}, "
            f"file={upload_data.audio_filename}"
        )

        # Process audio file if provided
        if audio and hasattr(audio, 'read'):
            audio_content = await audio.read()
            if not audio_content:
                raise HTTPException(status_code=400, detail="Empty audio file")

            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(
                suffix=Path(upload_data.audio_filename).suffix or ".wav",
                delete=False
            ) as temp_file:
                temp_file.write(audio_content)
                temp_file_path = Path(temp_file.name)

            # Process with transcription service
            transcription_service = request.app.state.transcription_service
            await process_rdioscanner_call(
                upload_data, temp_file_path, transcription_service,
                client_ip, api_key_id, user_agent  # Pass security context
            )

            logger.info(f"Successfully queued call for transcription: {upload_data.audio_filename}")

        # Return appropriate response format
        wants_json = determine_response_format(request)

        if wants_json:
            return {
                "status": "ok",
                "message": "Call received and queued for transcription",
                "callId": upload_data.audio_filename or "unknown"
            }
        else:
            return Response(content="Call imported successfully.", media_type="text/plain")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing RdioScanner upload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        # Clean up temporary file
        if temp_file_path:
            try:
                temp_file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")


async def process_rdioscanner_call(
    upload_data: RdioScannerUpload,
    audio_file_path: Path,
    transcription_service,
    client_ip: str,
    api_key_id: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Process an RdioScanner call upload."""
    try:
        # Convert upload data to RadioCallCreate format
        from stable_squirrel.database.models import RadioCallCreate

        # Convert Unix timestamp to datetime
        call_timestamp = datetime.fromtimestamp(upload_data.dateTime)

        # Create RadioCallCreate object with metadata from RdioScanner and security tracking
        radio_call = RadioCallCreate(
            timestamp=call_timestamp,
            frequency=upload_data.frequency or 0,
            talkgroup_id=upload_data.talkgroup,
            source_radio_id=upload_data.source,
            system_id=int(upload_data.system) if upload_data.system.isdigit() else None,
            system_label=upload_data.systemLabel,
            talkgroup_label=upload_data.talkgroupLabel,
            talkgroup_group=upload_data.talkgroupGroup,
            talker_alias=upload_data.talkerAlias,
            audio_file_path=str(audio_file_path),
            audio_format=Path(upload_data.audio_filename).suffix.lower() or ".wav",
            # Enhanced security tracking
            upload_source_ip=client_ip,
            upload_source_system=upload_data.system,
            upload_api_key_id=api_key_id,
            upload_user_agent=user_agent,
        )

        # Queue for background transcription processing
        try:
            from stable_squirrel.services.task_queue import get_task_queue
            task_queue = get_task_queue()
            task_id = await task_queue.enqueue_task(radio_call, audio_file_path)

            logger.info(
                f"RdioScanner call queued for transcription: {upload_data.audio_filename} "
                f"(Task ID: {task_id})"
            )

        except ValueError as e:
            # Queue is full - fall back to immediate processing
            logger.warning(f"Task queue full, processing immediately: {e}")
            await transcription_service.transcribe_rdioscanner_call(
                audio_file_path, radio_call
            )

        logger.info(
            f"RdioScanner call processed successfully: {upload_data.audio_filename}"
        )

    except Exception as e:
        logger.error(
            f"Error processing RdioScanner call {upload_data.audio_filename}: {e}"
        )
        raise
