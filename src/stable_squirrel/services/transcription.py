"""Transcription service using WhisperX."""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypedDict

import whisperx

from stable_squirrel.config import TranscriptionConfig
from stable_squirrel.database.models import (
    RadioCallCreate,
    SpeakerSegment,
    TranscriptionCreate,
)
from stable_squirrel.database.operations import DatabaseOperations

if TYPE_CHECKING:
    from stable_squirrel.database import DatabaseManager

logger = logging.getLogger(__name__)

# Type aliases for external WhisperX models that don't have type stubs
WhisperModel = Any  # whisperx.load_model() return type
AlignModel = Any  # whisperx.load_align_model() return type
DiarizeModel = Any  # whisperx.DiarizationPipeline type
WhisperResult = Dict[str, Any]  # WhisperX transcription result


class AudioMetadata(TypedDict):
    """Audio file metadata."""

    duration: float
    format: str
    size_bytes: int
    filename: str


class TranscriptionService:
    """Service for transcribing audio files using WhisperX."""

    def __init__(self, config: TranscriptionConfig, db_manager: "DatabaseManager"):
        self.config = config
        self.db_manager = db_manager
        self.db_ops = DatabaseOperations(db_manager)
        self._model: Optional[WhisperModel] = None
        self._diarize_model: Optional[DiarizeModel] = None
        self._align_model: Optional[AlignModel] = None
        self._metadata: Optional[Dict[str, Any]] = None  # Language metadata from align model
        self._running = False

    async def start(self) -> None:
        """Start the transcription service and task queue."""
        if self._running:
            return

        self._running = True
        logger.info("Starting transcription service...")

        # Load WhisperX model
        await self._load_model()

        # Initialize and start task queue for background processing
        try:
            from stable_squirrel.services.task_queue import initialize_task_queue

            task_queue = initialize_task_queue(
                max_queue_size=getattr(self.config, "queue_size", 10000),
                num_workers=getattr(self.config, "num_workers", 4),
            )
            await task_queue.start(self._process_queued_transcription)
            logger.info("Task queue started for background transcription processing")
        except Exception as e:
            logger.warning(f"Failed to start task queue: {e}")
            logger.info("Continuing with synchronous transcription processing")

    async def stop(self) -> None:
        """Stop the transcription service and task queue."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping transcription service...")

        # Stop task queue
        try:
            from stable_squirrel.services.task_queue import shutdown_task_queue

            await shutdown_task_queue()
            logger.info("Task queue stopped")
        except Exception as e:
            logger.warning(f"Error stopping task queue: {e}")

        # Cleanup model
        self._model = None

    async def _load_model(self) -> None:
        """Load the WhisperX model and supporting models."""
        try:
            logger.info(f"Loading WhisperX model: {self.config.model_name}")

            # Determine device
            device = self.config.device
            if device == "auto":
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"

            # Load main transcription model
            self._model = whisperx.load_model(
                self.config.model_name, device=device, compute_type="float16" if device == "cuda" else "int8"
            )
            logger.info(f"Loaded WhisperX model '{self.config.model_name}' on {device}")

            # Load alignment model if available
            try:
                self._align_model, self._metadata = whisperx.load_align_model(
                    language_code=self.config.language or "en", device=device
                )
                logger.info("Loaded alignment model for precise timestamps")
            except Exception as e:
                logger.warning(f"Could not load alignment model: {e}")
                self._align_model = None
                self._metadata = None

            # Load diarization model if enabled
            if self.config.enable_diarization:
                try:
                    # Try different WhisperX diarization approaches
                    if hasattr(whisperx, "DiarizationPipeline"):
                        self._diarize_model = whisperx.DiarizationPipeline(
                            use_auth_token=None, device=device  # You may need to set this for some models
                        )
                        logger.info("Loaded speaker diarization model")
                    else:
                        # WhisperX version doesn't have DiarizationPipeline - use alternative approach
                        logger.info("WhisperX diarization not available in this version - using basic transcription")
                        self._diarize_model = None
                except Exception as e:
                    logger.warning(f"Could not load diarization model: {e}")
                    logger.info("Continuing with transcription without speaker identification")
                    self._diarize_model = None

            logger.info("WhisperX models loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load WhisperX models: {e}")
            raise

    async def transcribe_file(self, file_path: Path) -> WhisperResult:
        """Transcribe an audio file using WhisperX."""
        if not self._running or not self._model:
            raise RuntimeError("Transcription service not ready")

        try:
            start_time = time.time()
            logger.info(f"Transcribing file: {file_path}")

            # Extract audio file metadata first
            audio_info = await self._extract_audio_metadata(file_path)

            # Load and transcribe audio
            audio = whisperx.load_audio(str(file_path))

            # Initial transcription
            result = self._model.transcribe(audio, batch_size=self.config.batch_size, language=self.config.language)

            # Get detected language
            detected_language = result.get("language", "en")
            logger.info(f"Detected language: {detected_language}")

            # Align transcription for precise timestamps
            if self._align_model and self._metadata:
                result = whisperx.align(
                    result["segments"], self._align_model, self._metadata, audio, device=self._model.device
                )

            # Perform speaker diarization if enabled
            diarize_segments = None
            if self.config.enable_diarization and self._diarize_model:
                diarize_segments = self._diarize_model(audio)
                # Assign speaker labels to segments
                result = whisperx.assign_word_speakers(diarize_segments, result)

            # Process results into our format
            processing_time = time.time() - start_time
            processed_result = await self._process_transcription_result(
                result, file_path, audio_info, detected_language, processing_time
            )

            # Store in database
            await self._store_transcription(processed_result)

            logger.info(
                f"Transcription completed for: {file_path} "
                f"(Duration: {audio_info['duration']:.1f}s, "
                f"Processing: {processing_time:.1f}s)"
            )

            return processed_result

        except Exception as e:
            logger.error(f"Error transcribing file {file_path}: {e}")
            raise

    async def _extract_audio_metadata(self, file_path: Path) -> AudioMetadata:
        """Extract metadata from audio file."""
        try:
            # Use librosa or similar to get audio info
            # For now, basic file info
            import librosa

            # Get duration without loading full audio
            duration = librosa.get_duration(path=str(file_path))

            return {
                "duration": duration,
                "format": file_path.suffix.lower(),
                "size_bytes": file_path.stat().st_size,
                "filename": file_path.name,
            }
        except ImportError:
            # Fallback if librosa not available
            logger.warning("librosa not available, using basic metadata")
            return {
                "duration": 0.0,  # Will be updated during transcription
                "format": file_path.suffix.lower(),
                "size_bytes": file_path.stat().st_size,
                "filename": file_path.name,
            }
        except Exception as e:
            logger.error(f"Error extracting audio metadata: {e}")
            # Return minimal metadata
            return {
                "duration": 0.0,
                "format": file_path.suffix.lower(),
                "size_bytes": file_path.stat().st_size,
                "filename": file_path.name,
            }

    async def _process_transcription_result(
        self,
        whisper_result: WhisperResult,
        file_path: Path,
        audio_info: AudioMetadata,
        detected_language: str,
        processing_time: float,
    ) -> WhisperResult:
        """Process WhisperX result into our standardized format."""

        # Create radio call record first to get call_id
        radio_call = RadioCallCreate(
            timestamp=datetime.now(),  # TODO: Extract from filename or metadata
            frequency=0,  # TODO: Extract from filename
            audio_file_path=str(file_path),
            audio_duration_seconds=audio_info.get("duration", 0.0),
            audio_format=audio_info.get("format", "unknown"),
        )

        # Extract segments
        segments = whisper_result.get("segments", [])

        # Build full transcript
        full_transcript = " ".join(segment.get("text", "").strip() for segment in segments)

        # Process speaker segments
        speaker_segments = []
        speakers = set()

        for segment in segments:
            speaker_id = segment.get("speaker", "SPEAKER_00")
            speakers.add(speaker_id)

            speaker_segment = SpeakerSegment(
                call_id=radio_call.call_id,
                start_time_seconds=segment.get("start", 0.0),
                end_time_seconds=segment.get("end", 0.0),
                speaker_id=speaker_id,
                text=segment.get("text", "").strip(),
                confidence_score=segment.get("confidence"),
            )
            speaker_segments.append(speaker_segment)

        # Create transcription record
        transcription = TranscriptionCreate(
            call_id=radio_call.call_id,
            full_transcript=full_transcript,
            language=detected_language,
            confidence_score=self._calculate_overall_confidence(segments),
            speaker_count=len(speakers),
            speaker_segments=speaker_segments,
            model_name=self.config.model_name,
            processing_time_seconds=processing_time,
        )

        return {
            "radio_call": radio_call,
            "transcription": transcription,
            "speaker_segments": speaker_segments,
            "audio_info": audio_info,
            "processing_time": processing_time,
        }

    def _calculate_overall_confidence(self, segments: List[Dict[str, Any]]) -> Optional[float]:
        """Calculate overall confidence score from segments."""
        if not segments:
            return None

        confidences = [float(seg.get("confidence", 0)) for seg in segments if seg.get("confidence") is not None]

        if not confidences:
            return None

        return sum(confidences) / len(confidences)

    async def transcribe_rdioscanner_call(self, file_path: Path, radio_call: RadioCallCreate) -> WhisperResult:
        """Transcribe an RdioScanner call with provided metadata."""
        if not self._running or not self._model:
            raise RuntimeError("Transcription service not ready")

        try:
            start_time = time.time()
            logger.info(f"Transcribing RdioScanner call: {file_path}")

            # Extract audio file metadata
            audio_info = await self._extract_audio_metadata(file_path)

            # Update radio call with actual duration
            radio_call.audio_duration_seconds = audio_info.get("duration", 0.0)

            # Load and transcribe audio
            audio = whisperx.load_audio(str(file_path))

            # Initial transcription
            result = self._model.transcribe(audio, batch_size=self.config.batch_size, language=self.config.language)

            # Get detected language
            detected_language = result.get("language", "en")
            logger.info(f"Detected language: {detected_language}")

            # Align transcription for precise timestamps
            if self._align_model and self._metadata:
                result = whisperx.align(
                    result["segments"],
                    self._align_model,
                    self._metadata,
                    audio,
                    device=self._model.device,
                )

            # Perform speaker diarization if enabled
            diarize_segments = None
            if self.config.enable_diarization and self._diarize_model:
                diarize_segments = self._diarize_model(audio)
                # Assign speaker labels to segments
                result = whisperx.assign_word_speakers(diarize_segments, result)

            # Process results into our format
            processing_time = time.time() - start_time
            processed_result = await self._process_rdioscanner_result(
                result, radio_call, audio_info, detected_language, processing_time
            )

            # Store in database
            await self._store_transcription(processed_result)

            logger.info(
                f"RdioScanner call transcription completed: {file_path} "
                f"(Duration: {audio_info['duration']:.1f}s, "
                f"Processing: {processing_time:.1f}s)"
            )

            return processed_result

        except Exception as e:
            logger.error(f"Error transcribing RdioScanner call {file_path}: {e}")
            raise

    async def _process_rdioscanner_result(
        self,
        whisper_result: WhisperResult,
        radio_call: RadioCallCreate,
        audio_info: AudioMetadata,
        detected_language: str,
        processing_time: float,
    ) -> WhisperResult:
        """Process WhisperX result for RdioScanner call."""

        # Extract segments
        segments = whisper_result.get("segments", [])

        # Build full transcript
        full_transcript = " ".join(segment.get("text", "").strip() for segment in segments)

        # Process speaker segments
        speaker_segments = []
        speakers = set()

        for segment in segments:
            speaker_id = segment.get("speaker", "SPEAKER_00")
            speakers.add(speaker_id)

            speaker_segment = SpeakerSegment(
                call_id=radio_call.call_id,
                start_time_seconds=segment.get("start", 0.0),
                end_time_seconds=segment.get("end", 0.0),
                speaker_id=speaker_id,
                text=segment.get("text", "").strip(),
                confidence_score=segment.get("confidence"),
            )
            speaker_segments.append(speaker_segment)

        # Use the provided radio_call (already has metadata from RdioScanner)
        # Just update the audio duration
        radio_call.audio_duration_seconds = audio_info.get("duration", 0.0)

        # Create transcription record
        transcription = TranscriptionCreate(
            call_id=radio_call.call_id,
            full_transcript=full_transcript,
            language=detected_language,
            confidence_score=self._calculate_overall_confidence(segments),
            speaker_count=len(speakers),
            speaker_segments=speaker_segments,
            model_name=self.config.model_name,
            processing_time_seconds=processing_time,
        )

        return {
            "radio_call": radio_call,
            "transcription": transcription,
            "speaker_segments": speaker_segments,
            "audio_info": audio_info,
            "processing_time": processing_time,
        }

    async def _store_transcription(self, result: WhisperResult) -> None:
        """Store transcription result in database."""
        try:
            radio_call = result["radio_call"]
            transcription = result["transcription"]
            speaker_segments = result["speaker_segments"]

            logger.info(
                f"Storing transcription for {radio_call.audio_file_path}: " f"{len(speaker_segments)} speaker segments"
            )

            # Store complete transcription atomically
            stored_result = await self.db_ops.store_complete_transcription(radio_call, transcription, speaker_segments)

            logger.info(f"Successfully stored transcription for call " f"{stored_result['radio_call']['call_id']}")

        except Exception as e:
            logger.error(f"Error storing transcription: {e}")
            raise

    async def _process_queued_transcription(self, audio_file_path: Path, call_data: RadioCallCreate) -> None:
        """
        Process a transcription task from the background queue.

        This method is called by task queue workers to process transcriptions
        in the background without blocking upload acceptance.
        """
        try:
            logger.info(f"Processing queued transcription for call {call_data.call_id}")

            # Verify file exists
            if not audio_file_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

            # Process the transcription
            await self.transcribe_rdioscanner_call(audio_file_path, call_data)

            logger.info(f"Queued transcription completed for call {call_data.call_id}")

        except Exception as e:
            logger.error(f"Queued transcription failed for call {call_data.call_id}: {e}")
            raise

        finally:
            # Clean up the temporary audio file
            try:
                if audio_file_path.exists():
                    audio_file_path.unlink()
                    logger.debug(f"Cleaned up audio file: {audio_file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup audio file {audio_file_path}: {e}")
