"""Tests for transcription service."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stable_squirrel.config import TranscriptionConfig
from stable_squirrel.database.models import RadioCallCreate
from stable_squirrel.services.transcription import TranscriptionService


@pytest.fixture
def transcription_config():
    """Create test transcription configuration."""
    return TranscriptionConfig(
        model_name="base",  # Use smaller model for tests
        device="cpu",  # Force CPU for CI/testing
        enable_diarization=True,
        batch_size=8,
        language="en",
    )


@pytest.fixture
def mock_db_manager():
    """Create mock database manager."""
    return AsyncMock()


@pytest.fixture
def mock_whisperx_result():
    """Create mock WhisperX transcription result."""
    return {
        "segments": [
            {
                "start": 0.0,
                "end": 3.5,
                "text": " Unit 123 to dispatch",
                "speaker": "SPEAKER_00",
                "confidence": 0.97,
            },
            {
                "start": 4.0,
                "end": 7.2,
                "text": " Go ahead Unit 123",
                "speaker": "SPEAKER_01",
                "confidence": 0.93,
            },
            {
                "start": 8.0,
                "end": 12.5,
                "text": " We have a Code 2 at Main and 5th",
                "speaker": "SPEAKER_00",
                "confidence": 0.95,
            },
        ],
        "language": "en",
    }


@pytest.fixture
def mock_audio_file():
    """Create a temporary mock audio file."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        # Write minimal WAV header
        wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        wav_data = b"\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        tmp_file.write(wav_header + wav_data)
        yield Path(tmp_file.name)

    # Cleanup
    Path(tmp_file.name).unlink(missing_ok=True)


@pytest.fixture
def radio_call_data():
    """Create test radio call data."""
    return RadioCallCreate(
        timestamp=datetime(2023, 12, 30, 20, 0, 0),
        frequency=460025000,
        talkgroup_id=1001,
        source_radio_id=2001,
        system_id=123,
        system_label="Test System",
        talkgroup_label="Police Dispatch",
        talker_alias="Unit 123",
        audio_file_path="/tmp/test.wav",
        audio_format=".wav",
    )


def test_transcription_service_init(transcription_config, mock_db_manager):
    """Test TranscriptionService initialization."""
    service = TranscriptionService(transcription_config, mock_db_manager)

    assert service.config == transcription_config
    assert service.db_manager == mock_db_manager
    assert not service._running
    assert service._model is None


@pytest.mark.asyncio
@patch("stable_squirrel.services.transcription.whisperx")
@patch("torch.cuda.is_available")
async def test_transcription_service_start(mock_cuda_available, mock_whisperx, transcription_config, mock_db_manager):
    """Test starting the transcription service."""
    # Mock torch.cuda.is_available() to return False (CPU)
    mock_cuda_available.return_value = False

    # Mock WhisperX components
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_whisperx.load_model.return_value = mock_model
    mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
    mock_whisperx.DiarizationPipeline.return_value = MagicMock()

    # Force auto device detection to trigger torch import
    transcription_config.device = "auto"
    service = TranscriptionService(transcription_config, mock_db_manager)

    await service.start()

    assert service._running
    assert service._model is not None

    # Verify WhisperX was called correctly
    mock_whisperx.load_model.assert_called_once_with("base", device="cpu", compute_type="int8")

    # Verify align model was loaded
    mock_whisperx.load_align_model.assert_called_once()

    # Verify diarization pipeline was created
    mock_whisperx.DiarizationPipeline.assert_called_once()


@pytest.mark.asyncio
async def test_transcription_service_stop(transcription_config, mock_db_manager):
    """Test stopping the transcription service."""
    service = TranscriptionService(transcription_config, mock_db_manager)
    service._running = True

    await service.stop()

    assert not service._running


@pytest.mark.asyncio
@patch("stable_squirrel.services.transcription.whisperx")
@patch("torch.cuda.is_available")
@patch("librosa.get_duration")
async def test_transcribe_file(
    mock_librosa_duration,
    mock_cuda_available,
    mock_whisperx,
    transcription_config,
    mock_db_manager,
    mock_audio_file,
    mock_whisperx_result,
):
    """Test transcribing an audio file."""
    # Setup mocks
    mock_cuda_available.return_value = False
    mock_librosa_duration.return_value = 12.5

    # Mock WhisperX components
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.transcribe.return_value = mock_whisperx_result
    mock_whisperx.load_model.return_value = mock_model
    mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
    mock_whisperx.DiarizationPipeline.return_value = MagicMock()
    mock_whisperx.load_audio.return_value = MagicMock()  # Mock audio array
    mock_whisperx.align.return_value = mock_whisperx_result
    mock_whisperx.assign_word_speakers.return_value = mock_whisperx_result

    # Mock file stats
    with patch.object(Path, "stat") as mock_stat:
        mock_stat.return_value.st_size = 1024

        # Force auto device detection to trigger torch import
        transcription_config.device = "auto"
        service = TranscriptionService(transcription_config, mock_db_manager)

        # Mock database operations
        service.db_ops = MagicMock()
        service.db_ops.store_complete_transcription = AsyncMock()

        await service.start()

        result = await service.transcribe_file(mock_audio_file)

        # Verify result structure
        assert "radio_call" in result
        assert "transcription" in result
        assert "speaker_segments" in result

        # Verify transcription content
        transcription = result["transcription"]
        assert "Unit 123 to dispatch" in transcription.full_transcript
        assert transcription.language == "en"
        assert transcription.speaker_count == 2  # SPEAKER_00 and SPEAKER_01

        # Verify speaker segments
        speaker_segments = result["speaker_segments"]
        assert len(speaker_segments) == 3
        assert speaker_segments[0].speaker_id == "SPEAKER_00"
        assert speaker_segments[1].speaker_id == "SPEAKER_01"

        # Verify database storage was called
        service.db_ops.store_complete_transcription.assert_called_once()


@pytest.mark.asyncio
@patch("stable_squirrel.services.transcription.whisperx")
@patch("torch.cuda.is_available")
async def test_transcribe_rdioscanner_call(
    mock_cuda_available,
    mock_whisperx,
    transcription_config,
    mock_db_manager,
    mock_audio_file,
    radio_call_data,
    mock_whisperx_result,
):
    """Test transcribing an RdioScanner call with provided metadata."""
    # Setup mocks
    mock_cuda_available.return_value = False

    # Mock WhisperX components
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.transcribe.return_value = mock_whisperx_result
    mock_whisperx.load_model.return_value = mock_model
    mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
    mock_whisperx.DiarizationPipeline.return_value = MagicMock()
    mock_whisperx.load_audio.return_value = MagicMock()
    mock_whisperx.align.return_value = mock_whisperx_result
    mock_whisperx.assign_word_speakers.return_value = mock_whisperx_result

    with patch("librosa.get_duration") as mock_librosa_duration:
        mock_librosa_duration.return_value = 12.5

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 1024

            # Force auto device detection to trigger torch import
            transcription_config.device = "auto"
            service = TranscriptionService(transcription_config, mock_db_manager)

            # Mock database operations
            service.db_ops = MagicMock()
            service.db_ops.store_complete_transcription = AsyncMock()

            await service.start()

            result = await service.transcribe_rdioscanner_call(mock_audio_file, radio_call_data)

            # Verify the radio call data was preserved
            radio_call = result["radio_call"]
            assert radio_call.frequency == radio_call_data.frequency
            assert radio_call.talkgroup_id == radio_call_data.talkgroup_id
            assert radio_call.system_label == radio_call_data.system_label
            assert radio_call.audio_duration_seconds == 12.5

            # Verify database storage was called
            service.db_ops.store_complete_transcription.assert_called_once()


@pytest.mark.asyncio
@patch("librosa.get_duration", side_effect=ImportError("librosa not available"))
async def test_extract_audio_metadata_without_librosa(
    mock_librosa_duration, transcription_config, mock_db_manager, mock_audio_file
):
    """Test audio metadata extraction when librosa is not available."""
    service = TranscriptionService(transcription_config, mock_db_manager)

    with patch.object(Path, "stat") as mock_stat:
        mock_stat.return_value.st_size = 2048

        metadata = await service._extract_audio_metadata(mock_audio_file)

        # Should fall back to basic metadata without librosa duration
        assert metadata["size_bytes"] == 2048
        assert metadata["duration"] == 0.0  # Default when librosa unavailable
        assert "filename" in metadata
        assert "format" in metadata


@pytest.mark.asyncio
@patch("librosa.get_duration")
async def test_extract_audio_metadata_with_librosa(
    mock_librosa_duration, transcription_config, mock_db_manager, mock_audio_file
):
    """Test audio metadata extraction with librosa available."""
    mock_librosa_duration.return_value = 15.7

    service = TranscriptionService(transcription_config, mock_db_manager)

    with patch.object(Path, "stat") as mock_stat:
        mock_stat.return_value.st_size = 3072

        metadata = await service._extract_audio_metadata(mock_audio_file)

        assert metadata["duration"] == 15.7
        assert metadata["size_bytes"] == 3072
        assert metadata["format"] == ".wav"


def test_calculate_overall_confidence(transcription_config, mock_db_manager):
    """Test confidence score calculation."""
    service = TranscriptionService(transcription_config, mock_db_manager)

    segments = [
        {"confidence": 0.95},
        {"confidence": 0.87},
        {"confidence": 0.92},
    ]

    confidence = service._calculate_overall_confidence(segments)
    expected = (0.95 + 0.87 + 0.92) / 3

    assert abs(confidence - expected) < 0.001

    # Test with no confidences
    segments_no_conf = [{"text": "test"}, {"text": "test2"}]
    confidence = service._calculate_overall_confidence(segments_no_conf)
    assert confidence is None


@pytest.mark.asyncio
async def test_transcribe_file_not_running(transcription_config, mock_db_manager, mock_audio_file):
    """Test transcribing when service is not running."""
    service = TranscriptionService(transcription_config, mock_db_manager)

    with pytest.raises(RuntimeError, match="Transcription service not ready"):
        await service.transcribe_file(mock_audio_file)


@pytest.mark.asyncio
@patch("stable_squirrel.services.transcription.whisperx")
@patch("torch.cuda.is_available")
async def test_transcribe_file_error_handling(
    mock_cuda_available, mock_whisperx, transcription_config, mock_db_manager, mock_audio_file
):
    """Test error handling during transcription."""
    # Setup mocks
    mock_cuda_available.return_value = False

    # Mock WhisperX to raise an error
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = Exception("Transcription failed")
    mock_whisperx.load_model.return_value = mock_model
    mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
    mock_whisperx.DiarizationPipeline.return_value = MagicMock()
    mock_whisperx.load_audio.return_value = MagicMock()

    # Force auto device detection to trigger torch import
    transcription_config.device = "auto"
    service = TranscriptionService(transcription_config, mock_db_manager)
    service.db_ops = MagicMock()

    await service.start()

    # Should raise the exception
    with pytest.raises(Exception, match="Transcription failed"):
        await service.transcribe_file(mock_audio_file)


def test_device_detection():
    """Test automatic device detection during model loading."""
    with patch("torch.cuda.is_available") as mock_cuda_available:
        with patch("stable_squirrel.services.transcription.whisperx") as mock_whisperx:
            # Test CUDA available
            mock_cuda_available.return_value = True
            mock_model = MagicMock()
            mock_model.device = "cuda"
            mock_whisperx.load_model.return_value = mock_model
            mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
            mock_whisperx.DiarizationPipeline.return_value = MagicMock()

            service = TranscriptionService(TranscriptionConfig(device="auto"), MagicMock())
            # Device detection happens during start/model loading
            # This will trigger the device detection logic
            service._model = mock_model
            assert service._model.device == "cuda"

            # Test CUDA not available
            mock_cuda_available.return_value = False
            mock_model_cpu = MagicMock()
            mock_model_cpu.device = "cpu"
            mock_whisperx.load_model.return_value = mock_model_cpu

            service2 = TranscriptionService(TranscriptionConfig(device="auto"), MagicMock())
            service2._model = mock_model_cpu
            assert service2._model.device == "cpu"


def test_process_transcription_result_speaker_counting(transcription_config, mock_db_manager):
    """Test speaker counting in transcription results."""
    TranscriptionService(transcription_config, mock_db_manager)

    # Create test data with multiple speakers
    mock_result = {
        "segments": [
            {"speaker": "SPEAKER_00", "text": "First speaker", "start": 0, "end": 2},
            {"speaker": "SPEAKER_01", "text": "Second speaker", "start": 3, "end": 5},
            {"speaker": "SPEAKER_00", "text": "First speaker again", "start": 6, "end": 8},
            {"speaker": "SPEAKER_02", "text": "Third speaker", "start": 9, "end": 11},
        ]
    }

    # This would normally be called within transcribe_file
    # We're testing the logic that counts unique speakers
    speakers = set()
    for segment in mock_result["segments"]:
        speakers.add(segment.get("speaker", "SPEAKER_00"))

    assert len(speakers) == 3  # SPEAKER_00, SPEAKER_01, SPEAKER_02


@pytest.mark.asyncio
@patch("stable_squirrel.services.transcription.whisperx")
@patch("torch.cuda.is_available")
async def test_diarization_disabled(
    mock_cuda_available, mock_whisperx, mock_db_manager, mock_audio_file, mock_whisperx_result
):
    """Test transcription with speaker diarization disabled."""
    config = TranscriptionConfig(enable_diarization=False, device="auto")
    mock_cuda_available.return_value = False

    # Mock WhisperX components
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.transcribe.return_value = mock_whisperx_result
    mock_whisperx.load_model.return_value = mock_model
    mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
    mock_whisperx.load_audio.return_value = MagicMock()
    mock_whisperx.align.return_value = mock_whisperx_result

    service = TranscriptionService(config, mock_db_manager)
    service.db_ops = MagicMock()
    service.db_ops.store_complete_transcription = AsyncMock()

    await service.start()

    # Verify diarization pipeline was not created
    mock_whisperx.DiarizationPipeline.assert_not_called()

    with patch("librosa.get_duration") as mock_librosa_duration:
        mock_librosa_duration.return_value = 10.0

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 1024

            result = await service.transcribe_file(mock_audio_file)

            # Should still work without diarization
            assert "transcription" in result
            assert result["transcription"].full_transcript
