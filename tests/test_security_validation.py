"""Tests for security validation."""

from unittest.mock import MagicMock

import pytest

from stable_squirrel.security import AudioFileValidator, SecurityConfig, ValidationError


def create_async_mock_file(filename, content_type, content):
    """Helper to create a properly mocked async file."""
    mock_file = MagicMock()
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.size = len(content)

    # Make read() async
    async def async_read():
        return content

    mock_file.read = async_read

    async def async_seek(pos):
        return None

    mock_file.seek = async_seek

    return mock_file


@pytest.fixture
def security_config():
    """Create test security configuration."""
    return SecurityConfig(
        max_file_size=1024 * 1024,  # 1MB
        min_file_size=40,  # 40 bytes (smaller for test files)
        max_uploads_per_minute=5,
        max_uploads_per_hour=50,
    )


@pytest.fixture
def validator(security_config):
    """Create test validator."""
    return AudioFileValidator(security_config)


@pytest.fixture
def mock_mp3_file_for_rejection():
    """Create a mock MP3 file for testing WAV rejection (now contains valid MP3 content)."""
    # Create a minimal valid MP3 file with ID3 header
    content = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 1100  # Make it large enough

    mock_file = MagicMock()
    mock_file.filename = "test.wav"  # Keep .wav to test rejection
    mock_file.content_type = "audio/wav"
    mock_file.size = len(content)

    # Make read() async
    async def async_read():
        return content

    mock_file.read = async_read

    async def async_seek(pos):
        return None

    mock_file.seek = async_seek

    return mock_file


@pytest.fixture
def mock_mp3_file():
    """Create a mock MP3 file."""
    # Create a minimal MP3 file with ID3 header
    content = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 100

    mock_file = MagicMock()
    mock_file.filename = "test.mp3"
    mock_file.content_type = "audio/mpeg"
    mock_file.size = len(content)

    # Make read() async
    async def async_read():
        return content

    mock_file.read = async_read

    async def async_seek(pos):
        return None

    mock_file.seek = async_seek

    return mock_file


@pytest.mark.asyncio
async def test_wav_file_rejection(validator, mock_mp3_file_for_rejection):
    """Test that WAV files are rejected (MP3-only policy for SDRTrunk)."""
    with pytest.raises(ValidationError, match="Invalid file extension '.wav'"):
        await validator.validate_upload_file(mock_mp3_file_for_rejection, "192.168.1.1")


@pytest.mark.asyncio
async def test_valid_mp3_file(validator, mock_mp3_file):
    """Test validation of valid MP3 file."""
    await validator.validate_upload_file(mock_mp3_file, "192.168.1.1")
    # Should not raise any exceptions


@pytest.mark.asyncio
async def test_file_too_large(validator):
    """Test validation fails for files that are too large."""
    mock_file = MagicMock()
    mock_file.filename = "large.mp3"
    mock_file.content_type = "audio/wav"
    mock_file.size = 2 * 1024 * 1024  # 2MB (exceeds 1MB limit)

    with pytest.raises(ValidationError, match="File too large"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_file_too_small(validator):
    """Test validation fails for files that are too small."""
    content = b"small"  # Only 5 bytes - well below 1024 byte minimum
    mock_file = create_async_mock_file("small.mp3", "audio/mpeg", content)

    with pytest.raises(ValidationError, match="File too small"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_invalid_file_extension(validator):
    """Test validation fails for invalid file extensions."""
    mock_file = MagicMock()
    mock_file.filename = "malicious.exe"
    mock_file.content_type = "application/octet-stream"
    mock_file.size = 1000

    with pytest.raises(ValidationError, match="dangerous pattern"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_invalid_file_extension_and_content_type(validator):
    """Test validation fails for invalid file extensions and content types."""
    content = b"RIFF\x24\x00\x00\x00WAVE" + b"\x00" * 1100
    mock_file = create_async_mock_file("test.doc", "application/msword", content)  # Wrong extension and type

    with pytest.raises(ValidationError, match="Invalid file extension"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_dangerous_filename_patterns(validator):
    """Test validation fails for dangerous filename patterns."""
    dangerous_names = [
        "../etc/passwd",
        "file\\with\\backslash",
        "file:with:colon",
        "file<with>brackets",
        "file.exe.mp3",
    ]

    for filename in dangerous_names:
        mock_file = MagicMock()
        mock_file.filename = filename
        mock_file.content_type = "audio/mpeg"
        mock_file.size = 1000

        with pytest.raises(ValidationError, match="Invalid filename"):
            await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_invalid_mp3_header(validator):
    """Test validation fails for invalid MP3 headers."""
    # Create file with wrong MP3 header
    content = b"FAKE\x24\x00\x00\x00FAKE" + b"\x00" * 1100  # Make it big enough

    mock_file = create_async_mock_file("fake.mp3", "audio/mpeg", content)

    with pytest.raises(ValidationError, match="Invalid MP3 file header"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_malicious_content_detection(validator):
    """Test detection of malicious content patterns."""
    # Create file with valid WAV header but Linux executable signature at start
    content = b"\x7fELF" + b"\x00" * 1100  # Linux executable header at start

    mock_file = create_async_mock_file("malicious.mp3", "audio/mpeg", content)  # Use MP3 to avoid header validation

    with pytest.raises(ValidationError, match="Executable file detected"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_empty_file_content(validator):
    """Test validation fails for empty files."""
    content = b""  # Empty content
    mock_file = create_async_mock_file("empty.mp3", "audio/mpeg", content)
    # Override size to be large enough to pass size check but have empty content
    mock_file.size = 2000

    with pytest.raises(ValidationError, match="Empty file content"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_rate_limiting_per_minute(validator):
    """Test per-minute rate limiting."""
    content = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 1100  # Valid MP3 header
    mock_file = create_async_mock_file("test.mp3", "audio/mpeg", content)

    client_ip = "192.168.1.100"

    # Upload 5 files (should succeed)
    for i in range(5):
        await validator.validate_upload_file(mock_file, client_ip)

    # 6th upload should fail
    with pytest.raises(ValidationError, match="Rate limit exceeded.*per minute"):
        await validator.validate_upload_file(mock_file, client_ip)


@pytest.mark.asyncio
async def test_rate_limiting_different_ips(validator):
    """Test that rate limiting is per-IP."""
    content = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 1100  # Valid MP3 header
    mock_file = create_async_mock_file("test.mp3", "audio/mpeg", content)

    # Upload 5 files from first IP
    for i in range(5):
        await validator.validate_upload_file(mock_file, "192.168.1.1")

    # Upload from second IP should still work
    await validator.validate_upload_file(mock_file, "192.168.1.2")


@pytest.mark.asyncio
async def test_no_filename(validator):
    """Test validation fails when file has no filename."""
    mock_file = MagicMock()
    mock_file.filename = None
    mock_file.content_type = "audio/wav"
    mock_file.size = 1000

    with pytest.raises(ValidationError, match="File must have a filename"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_pdf_file_detection(validator):
    """Test detection of PDF files disguised as audio."""
    # Create content with PDF signature at start
    content = b"%PDF-1.4" + b"\x00" * 1100  # PDF header

    mock_file = create_async_mock_file("fake.mp3", "audio/mpeg", content)  # Use MP3 to avoid header validation

    with pytest.raises(ValidationError, match="PDF file detected"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


def test_security_config_defaults():
    """Test default security configuration values."""
    config = SecurityConfig()

    assert config.max_file_size == 100 * 1024 * 1024  # 100MB
    assert config.min_file_size == 1024  # 1KB
    assert "audio/mpeg" in config.allowed_mime_types
    assert ".mp3" in config.allowed_extensions
    assert config.require_valid_audio_header is True
    assert config.scan_for_malicious_content is True


def test_security_config_custom():
    """Test custom security configuration."""
    config = SecurityConfig(
        max_file_size=50 * 1024 * 1024,  # 50MB
        max_uploads_per_minute=20,
        require_valid_audio_header=False,
    )

    assert config.max_file_size == 50 * 1024 * 1024
    assert config.max_uploads_per_minute == 20
    assert config.require_valid_audio_header is False


@pytest.mark.asyncio
async def test_validation_disabled_header_check(validator):
    """Test validation with header checking disabled."""
    # Create validator with header checking disabled and smaller min size
    config = SecurityConfig(require_valid_audio_header=False, min_file_size=50)
    validator = AudioFileValidator(config)

    # File with invalid header should still pass
    content = b"FAKE\x24\x00\x00\x00WAVE" + b"\x00" * 100

    mock_file = create_async_mock_file("fake.mp3", "audio/mpeg", content)

    # Should not raise exception since header checking is disabled
    await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_m4a_file_rejection(validator):
    """Test that M4A files are now rejected (MP3/WAV only policy)."""
    # Create M4A file with valid ftyp box
    content = b"\x00\x00\x00\x20ftyp" + b"M4A " + b"\x00" * 1100  # Make it big enough

    mock_file = create_async_mock_file("test.m4a", "audio/mp4", content)

    with pytest.raises(ValidationError, match="Invalid file extension '.m4a'"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_flac_file_rejection(validator):
    """Test that FLAC files are now rejected (MP3/WAV only policy)."""
    # Create FLAC file with valid header
    content = b"fLaC" + b"\x00" * 1100  # Make it big enough

    mock_file = create_async_mock_file("test.flac", "audio/flac", content)

    with pytest.raises(ValidationError, match="Invalid file extension '.flac'"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")


@pytest.mark.asyncio
async def test_ogg_file_rejection(validator):
    """Test that OGG files are now rejected (MP3/WAV only policy)."""
    # Create OGG file with valid header
    content = b"OggS" + b"\x00" * 1100  # Make it big enough

    mock_file = create_async_mock_file("test.ogg", "audio/ogg", content)

    with pytest.raises(ValidationError, match="Invalid file extension '.ogg'"):
        await validator.validate_upload_file(mock_file, "192.168.1.1")
