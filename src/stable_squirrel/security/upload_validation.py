"""Upload validation and security for audio files."""

import logging
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class SecurityConfig(BaseModel):
    """Configuration for upload security validation."""

    # File size limits (bytes)
    max_file_size: int = Field(default=100 * 1024 * 1024, description="Maximum file size in bytes (100MB)")
    min_file_size: int = Field(default=1024, description="Minimum file size in bytes (1KB)")

    # Allowed file types
    allowed_mime_types: Set[str] = Field(
        default={"audio/mpeg", "audio/mp3"},
        description="Allowed MIME types for SDR audio files (MP3 only - SDRTrunk standard)",
    )

    allowed_extensions: Set[str] = Field(
        default={".mp3"}, description="Allowed file extensions for SDR audio files (MP3 only - SDRTrunk standard)"
    )

    # Content validation
    require_valid_audio_header: bool = Field(default=True, description="Require valid audio file headers")
    scan_for_malicious_content: bool = Field(default=True, description="Scan for potentially malicious content")

    # Rate limiting (per IP)
    max_uploads_per_minute: int = Field(default=10, description="Maximum uploads per IP per minute")
    max_uploads_per_hour: int = Field(default=100, description="Maximum uploads per IP per hour")


class AudioFileValidator:
    """Validates audio file uploads for security."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self._upload_tracking: Dict[str, List[float]] = {}  # IP -> list of timestamps

    async def validate_upload_file(self, file: UploadFile, client_ip: str) -> None:
        """
        Comprehensive validation of uploaded audio file.

        Args:
            file: The uploaded file to validate
            client_ip: Client IP address for rate limiting

        Raises:
            ValidationError: If validation fails
        """
        # Rate limiting check
        self._check_rate_limits(client_ip)

        # Basic file validation
        await self._validate_file_basics(file)

        # Content type validation
        self._validate_content_type(file)

        # File size validation
        await self._validate_file_size(file)

        # Content validation (requires reading file)
        if self.config.require_valid_audio_header or self.config.scan_for_malicious_content:
            await self._validate_file_content(file)

        # Record successful upload for rate limiting
        self._record_upload(client_ip)

        logger.info(f"File validation passed: {file.filename} from {client_ip}")

    def _check_rate_limits(self, client_ip: str) -> None:
        """Check if client has exceeded rate limits."""
        import time

        current_time = time.time()

        # Clean old entries and get current uploads
        if client_ip in self._upload_tracking:
            # Remove uploads older than 1 hour
            self._upload_tracking[client_ip] = [
                ts for ts in self._upload_tracking[client_ip] if current_time - ts < 3600
            ]
        else:
            self._upload_tracking[client_ip] = []

        uploads = self._upload_tracking[client_ip]

        # Check hourly limit
        if len(uploads) >= self.config.max_uploads_per_hour:
            raise ValidationError(f"Rate limit exceeded: maximum {self.config.max_uploads_per_hour} uploads per hour")

        # Check per-minute limit
        recent_uploads = [ts for ts in uploads if current_time - ts < 60]
        if len(recent_uploads) >= self.config.max_uploads_per_minute:
            raise ValidationError(
                f"Rate limit exceeded: maximum {self.config.max_uploads_per_minute} uploads per minute"
            )

    def _record_upload(self, client_ip: str) -> None:
        """Record a successful upload for rate limiting."""
        import time

        if client_ip not in self._upload_tracking:
            self._upload_tracking[client_ip] = []

        self._upload_tracking[client_ip].append(time.time())

    async def _validate_file_basics(self, file: UploadFile) -> None:
        """Basic file validation."""
        if not file:
            raise ValidationError("No file provided")

        if not file.filename:
            raise ValidationError("File must have a filename")

        # Check filename for suspicious patterns
        filename = file.filename.lower()

        # Block potentially dangerous filenames
        dangerous_patterns = [
            "..",
            "/",
            "\\",
            ":",
            "*",
            "?",
            '"',
            "<",
            ">",
            "|",
            ".exe",
            ".bat",
            ".cmd",
            ".scr",
            ".pif",
            ".com",
        ]

        for pattern in dangerous_patterns:
            if pattern in filename:
                raise ValidationError(f"Invalid filename: contains dangerous pattern '{pattern}'")

        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.config.allowed_extensions:
            raise ValidationError(
                f"Invalid file extension '{file_ext}'. " f"Allowed: {', '.join(sorted(self.config.allowed_extensions))}"
            )

    def _validate_content_type(self, file: UploadFile) -> None:
        """Validate MIME type."""
        # Check declared content type
        if file.content_type and file.content_type not in self.config.allowed_mime_types:
            # Try to guess content type from filename
            if file.filename:
                guessed_type, _ = mimetypes.guess_type(file.filename)
                if guessed_type and guessed_type in self.config.allowed_mime_types:
                    return  # Guessed type is valid
            raise ValidationError(
                f"Invalid content type '{file.content_type}'. "
                f"Allowed: {', '.join(sorted(self.config.allowed_mime_types))}"
            )

    async def _validate_file_size(self, file: UploadFile) -> None:
        """Validate file size."""
        # Get file size
        file_size = 0
        if hasattr(file, "size") and file.size:
            file_size = file.size
        else:
            # Read file to get size (will reset position after)
            initial_position = file.file.tell()
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(initial_position)  # Reset position

        if file_size < self.config.min_file_size:
            raise ValidationError(f"File too small: {file_size} bytes " f"(minimum: {self.config.min_file_size} bytes)")

        if file_size > self.config.max_file_size:
            raise ValidationError(f"File too large: {file_size} bytes " f"(maximum: {self.config.max_file_size} bytes)")

    async def _validate_file_content(self, file: UploadFile) -> None:
        """Validate file content for security."""
        # Read file content for validation
        file_content = await file.read()

        try:
            # Reset file position for later use
            await file.seek(0)
        except Exception:
            # Some UploadFile implementations don't support seek
            pass

        if not file_content:
            raise ValidationError("Empty file content")

        # Scan for malicious content first (security priority)
        if self.config.scan_for_malicious_content:
            self._scan_malicious_content(file_content)

        # Check for valid audio headers after malicious content check
        if self.config.require_valid_audio_header:
            self._check_audio_headers(file_content, file.filename or "unknown")

    def _check_audio_headers(self, content: bytes, filename: str) -> None:
        """Check for valid MP3 file headers (SDRTrunk only sends MP3)."""
        if len(content) < 12:
            raise ValidationError("File too small to contain valid audio header")

        file_ext = Path(filename).suffix.lower()

        # MP3 file validation (SDRTrunk standard)
        if file_ext == ".mp3":
            # Check for ID3 tag or MP3 frame header
            if not (
                content.startswith(b"ID3")
                or content.startswith(b"\xff\xfb")  # MP3 frame sync
                or content.startswith(b"\xff\xfa")
            ):
                raise ValidationError("Invalid MP3 file header")
        else:
            # Only MP3 files are allowed
            raise ValidationError(f"Unsupported audio format: {file_ext}. Only MP3 files are accepted.")

    def _scan_malicious_content(self, content: bytes) -> None:
        """Scan for potentially malicious content patterns."""
        # For audio files, be extremely conservative - MP3 compressed data can contain
        # ANY byte pattern naturally. Only check for executable headers at file start.
        if len(content) < 16:
            return  # Too small to contain meaningful headers

        # Only check for executable file headers at the very beginning
        # These should NEVER appear at the start of legitimate audio files
        if content.startswith(b"\x7fELF"):
            raise ValidationError("Executable file detected")
        if content.startswith(b"\xca\xfe\xba\xbe"):
            raise ValidationError("Java class file detected")
        if content.startswith(b"%PDF"):
            raise ValidationError("PDF file detected")

        # Check for HTML/script content only in first 64 bytes (metadata area)
        header_check = content[:64].lower()
        if b"<script" in header_check or b"javascript:" in header_check:
            raise ValidationError("Script content detected in file header")


# Global validator instance (will be configured in main app)
_global_validator: Optional[AudioFileValidator] = None


def configure_validator(config: SecurityConfig) -> None:
    """Configure the global validator instance."""
    global _global_validator
    _global_validator = AudioFileValidator(config)


def get_validator() -> AudioFileValidator:
    """Get the global validator instance."""
    if _global_validator is None:
        # Use default config if not configured
        configure_validator(SecurityConfig())
    assert _global_validator is not None  # Should be set after configure_validator
    return _global_validator


async def validate_audio_file(file: UploadFile, client_ip: str) -> None:
    """
    Convenience function to validate an audio file upload.

    Args:
        file: The uploaded file to validate
        client_ip: Client IP address for rate limiting

    Raises:
        ValidationError: If validation fails
    """
    validator = get_validator()
    await validator.validate_upload_file(file, client_ip)
