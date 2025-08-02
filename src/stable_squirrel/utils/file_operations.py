"""
Async file operations for high-throughput scenarios.

This module provides stream-based file processing to minimize memory usage
and prevent blocking the event loop during large file operations.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional

try:
    import aiofiles
    import aiofiles.os
except ImportError:
    aiofiles = None

logger = logging.getLogger(__name__)


class AsyncFileManager:
    """Manages async file operations with automatic cleanup."""

    def __init__(self):
        self._temp_files = set()

    async def save_upload_stream(
        self,
        content_stream: AsyncIterator[bytes],
        filename: str,
        max_size: int = 100 * 1024 * 1024  # 100MB default
    ) -> Path:
        """
        Save a stream of data to a temporary file asynchronously.

        Args:
            content_stream: Async iterator of bytes
            filename: Original filename for extension detection
            max_size: Maximum file size in bytes

        Returns:
            Path to the saved temporary file

        Raises:
            ValueError: If file is too large
        """
        # Create temp file
        suffix = Path(filename).suffix or ".tmp"
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=suffix, prefix="stream_")
        temp_path = Path(temp_path_str)

        # Close the file descriptor since we'll use aiofiles
        os.close(temp_fd)

        # Track temp file for cleanup
        self._temp_files.add(temp_path)

        try:
            total_size = 0

            if aiofiles:
                async with aiofiles.open(temp_path, 'wb') as f:
                    async for chunk in content_stream:
                        total_size += len(chunk)

                        if total_size > max_size:
                            raise ValueError(f"File size exceeds maximum of {max_size} bytes")

                        await f.write(chunk)
            else:
                with open(temp_path, 'wb') as f:
                    async for chunk in content_stream:
                        total_size += len(chunk)

                        if total_size > max_size:
                            raise ValueError(f"File size exceeds maximum of {max_size} bytes")

                        f.write(chunk)

            logger.debug(f"Saved {total_size} bytes to {temp_path}")
            return temp_path

        except Exception:
            # Clean up on error
            await self.cleanup_file(temp_path)
            raise

    async def copy_file_async(self, source: Path, dest: Path, chunk_size: int = 64*1024) -> None:
        """
        Copy a file asynchronously in chunks.

        Args:
            source: Source file path
            dest: Destination file path
            chunk_size: Size of chunks to read/write
        """
        if aiofiles:
            async with aiofiles.open(source, 'rb') as src:
                async with aiofiles.open(dest, 'wb') as dst:
                    while True:
                        chunk = await src.read(chunk_size)
                        if not chunk:
                            break
                        await dst.write(chunk)
        else:
            # Fallback to sync operations
            with open(source, 'rb') as src:
                with open(dest, 'wb') as dst:
                    while True:
                        chunk = src.read(chunk_size)
                        if not chunk:
                            break
                        dst.write(chunk)

    async def read_file_chunks(
        self,
        file_path: Path,
        chunk_size: int = 64*1024
    ) -> AsyncIterator[bytes]:
        """
        Read a file in chunks asynchronously.

        Args:
            file_path: Path to file to read
            chunk_size: Size of chunks to read

        Yields:
            Chunks of file data
        """
        if aiofiles:
            async with aiofiles.open(file_path, 'rb') as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        else:
            # Fallback to sync file reading in chunks
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

    async def get_file_size(self, file_path: Path) -> int:
        """Get file size asynchronously."""
        if aiofiles:
            stat = await aiofiles.os.stat(file_path)
            return stat.st_size
        else:
            return file_path.stat().st_size

    async def file_exists(self, file_path: Path) -> bool:
        """Check if file exists asynchronously."""
        if aiofiles:
            try:
                await aiofiles.os.stat(file_path)
                return True
            except FileNotFoundError:
                return False
        else:
            return file_path.exists()

    async def cleanup_file(self, file_path: Path) -> bool:
        """
        Clean up a temporary file.

        Returns:
            True if file was deleted, False otherwise
        """
        try:
            if await self.file_exists(file_path):
                if aiofiles:
                    await aiofiles.os.unlink(file_path)
                else:
                    file_path.unlink()
                logger.debug(f"Cleaned up temp file: {file_path}")

            self._temp_files.discard(file_path)
            return True

        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_path}: {e}")
            return False

    async def cleanup_all(self) -> int:
        """
        Clean up all tracked temporary files.

        Returns:
            Number of files cleaned up
        """
        cleaned_count = 0

        for file_path in list(self._temp_files):
            if await self.cleanup_file(file_path):
                cleaned_count += 1

        return cleaned_count


class StreamingUploadProcessor:
    """Process uploads using streaming to minimize memory usage."""

    def __init__(self, max_file_size: int = 100 * 1024 * 1024):
        self.max_file_size = max_file_size
        self.file_manager = AsyncFileManager()

    async def process_upload_content(self, audio_content: bytes, filename: str) -> Path:
        """
        Process upload content with memory optimization.

        Args:
            audio_content: Raw audio data
            filename: Original filename

        Returns:
            Path to processed file
        """
        if len(audio_content) > self.max_file_size:
            raise ValueError(f"File size {len(audio_content)} exceeds maximum {self.max_file_size}")

        # For now, save directly since we already have the content
        # In a real streaming scenario, this would process chunks
        suffix = Path(filename).suffix or ".mp3"
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=suffix, prefix="upload_")
        temp_path = Path(temp_path_str)

        # Close the file descriptor and use aiofiles
        os.close(temp_fd)

        if aiofiles:
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(audio_content)
        else:
            with open(temp_path, 'wb') as f:
                f.write(audio_content)

        return temp_path

    async def validate_audio_stream(
        self,
        file_path: Path,
        allowed_formats: set = {".mp3"}
    ) -> bool:
        """
        Validate audio file format by checking headers.

        Args:
            file_path: Path to file to validate
            allowed_formats: Set of allowed file extensions

        Returns:
            True if valid, False otherwise
        """
        # Check extension
        if file_path.suffix.lower() not in allowed_formats:
            return False

        # Check file header for MP3 files
        if file_path.suffix.lower() == ".mp3":
            if aiofiles:
                async with aiofiles.open(file_path, 'rb') as f:
                    header = await f.read(10)
            else:
                with open(file_path, 'rb') as f:
                    header = f.read(10)

            # Check for ID3 tag or MP3 frame sync
            if header.startswith(b'ID3') or header.startswith(b'\xff\xfb'):
                return True

            return False

        return True

    async def cleanup(self):
        """Clean up all temporary files."""
        return await self.file_manager.cleanup_all()


# Global instances
_file_manager: Optional[AsyncFileManager] = None
_upload_processor: Optional[StreamingUploadProcessor] = None


def get_file_manager() -> AsyncFileManager:
    """Get global file manager instance."""
    global _file_manager
    if _file_manager is None:
        _file_manager = AsyncFileManager()
    return _file_manager


def get_upload_processor() -> StreamingUploadProcessor:
    """Get global upload processor instance."""
    global _upload_processor
    if _upload_processor is None:
        _upload_processor = StreamingUploadProcessor()
    return _upload_processor


async def cleanup_temp_files():
    """Clean up all temporary files from global instances."""
    file_manager = get_file_manager()
    upload_processor = get_upload_processor()

    count1 = await file_manager.cleanup_all()
    count2 = await upload_processor.cleanup()

    total_cleaned = count1 + count2
    if total_cleaned > 0:
        logger.info(f"Cleaned up {total_cleaned} temporary files")

    return total_cleaned
