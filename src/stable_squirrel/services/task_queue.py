"""Background task queue for transcription processing.

This module implements a high-throughput task queue system that separates
upload acceptance from transcription processing, allowing unlimited concurrent uploads.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, TypedDict, Union
from uuid import UUID, uuid4

from stable_squirrel.database.models import RadioCallCreate

logger = logging.getLogger(__name__)


class TaskDict(TypedDict):
    """TypedDict for serialized task data."""

    task_id: str
    call_data: Optional[dict[str, Union[str, int, float, None]]]
    audio_file_path: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    status: str
    retry_count: int
    max_retries: int
    error_message: Optional[str]
    worker_id: Optional[str]


class QueueStats(TypedDict):
    """TypedDict for queue statistics."""

    total_enqueued: int
    total_processed: int
    total_failed: int
    total_retries: int
    average_processing_time: float
    queue_full_rejections: int
    queue_size: int
    retry_queue_size: int
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    workers_running: int
    is_running: bool


class TaskStatus(Enum):
    """Task processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class TranscriptionTask:
    """A transcription task in the queue."""

    task_id: UUID = field(default_factory=uuid4)
    call_data: Optional[RadioCallCreate] = None
    audio_file_path: Optional[Path] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    worker_id: Optional[str] = None

    def to_dict(self) -> TaskDict:
        """Convert task to dictionary for serialization."""
        return {
            "task_id": str(self.task_id),
            "call_data": self.call_data.model_dump() if self.call_data else None,
            "audio_file_path": str(self.audio_file_path) if self.audio_file_path else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
            "worker_id": self.worker_id,
        }


class TranscriptionTaskQueue:
    """High-throughput task queue for transcription processing."""

    def __init__(self, max_queue_size: int = 10000, num_workers: int = 4):
        self.max_queue_size = max_queue_size
        self.num_workers = num_workers

        # Core queue and workers
        self.task_queue: asyncio.Queue[TranscriptionTask] = asyncio.Queue(maxsize=max_queue_size)
        self.retry_queue: asyncio.Queue[TranscriptionTask] = asyncio.Queue(maxsize=max_queue_size // 2)
        self.workers: List[asyncio.Task[None]] = []
        self.running = False

        # Task tracking
        self.active_tasks: Dict[UUID, TranscriptionTask] = {}
        self.completed_tasks: Dict[UUID, TranscriptionTask] = {}
        self.failed_tasks: Dict[UUID, TranscriptionTask] = {}

        # Statistics
        self.stats = {
            "total_enqueued": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_retries": 0,
            "average_processing_time": 0.0,
            "queue_full_rejections": 0,
        }

        # Callbacks
        self.transcription_processor: Optional[Callable[[Path, RadioCallCreate], Awaitable[None]]] = None
        self.progress_callback: Optional[Callable[[TranscriptionTask], None]] = None

    async def start(self, transcription_processor: Callable[[Path, RadioCallCreate], Awaitable[None]]) -> None:
        """Start the task queue and workers."""
        if self.running:
            logger.warning("Task queue is already running")
            return

        self.transcription_processor = transcription_processor
        self.running = True

        # Start worker tasks
        logger.info(f"Starting {self.num_workers} transcription workers")
        for i in range(self.num_workers):
            worker_task = asyncio.create_task(self._worker(f"worker-{i+1}"), name=f"transcription-worker-{i+1}")
            self.workers.append(worker_task)

        # Start retry processor
        retry_task = asyncio.create_task(self._retry_processor(), name="retry-processor")
        self.workers.append(retry_task)

        logger.info("Transcription task queue started successfully")

    async def stop(self) -> None:
        """Stop the task queue and workers."""
        if not self.running:
            return

        logger.info("Stopping transcription task queue...")
        self.running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)

        self.workers.clear()
        logger.info("Transcription task queue stopped")

    async def enqueue_task(self, call_data: RadioCallCreate, audio_file_path: Path) -> UUID:
        """
        Enqueue a transcription task for background processing.

        Returns:
            Task ID for tracking

        Raises:
            ValueError: If queue is full
        """
        task = TranscriptionTask(call_data=call_data, audio_file_path=audio_file_path)

        try:
            # Non-blocking enqueue with immediate response
            self.task_queue.put_nowait(task)

            # Track the task
            self.active_tasks[task.task_id] = task
            self.stats["total_enqueued"] += 1

            logger.info(f"Enqueued transcription task {task.task_id} for call {call_data.call_id}")

            return task.task_id

        except asyncio.QueueFull:
            self.stats["queue_full_rejections"] += 1
            raise ValueError(
                f"Transcription queue is full ({self.max_queue_size} tasks). " "Try again later or increase queue size."
            )

    async def get_task_status(self, task_id: UUID) -> Optional[TranscriptionTask]:
        """Get the status of a specific task."""
        # Check active tasks first
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]

        # Check completed tasks
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]

        # Check failed tasks
        if task_id in self.failed_tasks:
            return self.failed_tasks[task_id]

        return None

    def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics."""
        return QueueStats(
            total_enqueued=int(self.stats["total_enqueued"]),
            total_processed=int(self.stats["total_processed"]),
            total_failed=int(self.stats["total_failed"]),
            total_retries=int(self.stats["total_retries"]),
            average_processing_time=self.stats["average_processing_time"],
            queue_full_rejections=int(self.stats["queue_full_rejections"]),
            queue_size=self.task_queue.qsize(),
            retry_queue_size=self.retry_queue.qsize(),
            active_tasks=len(self.active_tasks),
            completed_tasks=len(self.completed_tasks),
            failed_tasks=len(self.failed_tasks),
            workers_running=len(self.workers),
            is_running=self.running,
        )

    async def _worker(self, worker_id: str) -> None:
        """Background worker that processes transcription tasks."""
        logger.info(f"Transcription worker {worker_id} started")

        while self.running:
            try:
                # Get task from queue with timeout
                try:
                    task = await asyncio.wait_for(
                        self.task_queue.get(), timeout=1.0  # Check running status every second
                    )
                except asyncio.TimeoutError:
                    continue

                # Process the task
                await self._process_task(task, worker_id)

                # Mark task as done
                self.task_queue.task_done()

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                # Continue processing other tasks
                continue

        logger.info(f"Transcription worker {worker_id} stopped")

    async def _process_task(self, task: TranscriptionTask, worker_id: str) -> None:
        """Process a single transcription task."""
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.now()
        task.worker_id = worker_id

        start_time = time.time()

        try:
            logger.info(f"Worker {worker_id} processing task {task.task_id}")

            # Call the transcription processor
            if self.transcription_processor and task.audio_file_path and task.call_data:
                await self.transcription_processor(task.audio_file_path, task.call_data)

            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

            # Update statistics
            processing_time = time.time() - start_time
            self.stats["total_processed"] += 1

            # Update average processing time
            if self.stats["average_processing_time"] == 0:
                self.stats["average_processing_time"] = processing_time
            else:
                # Moving average
                self.stats["average_processing_time"] = (
                    self.stats["average_processing_time"] * 0.9 + processing_time * 0.1
                )

            # Move to completed tasks
            self.completed_tasks[task.task_id] = task
            del self.active_tasks[task.task_id]

            logger.info(f"Task {task.task_id} completed in {processing_time:.2f}s")

            # Call progress callback if set
            if self.progress_callback:
                try:
                    self.progress_callback(task)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")

            task.error_message = str(e)
            task.retry_count += 1

            if task.retry_count <= task.max_retries:
                # Retry the task
                task.status = TaskStatus.RETRYING
                self.stats["total_retries"] += 1

                try:
                    # Add to retry queue with delay
                    await asyncio.sleep(min(task.retry_count * 5, 30))  # Exponential backoff
                    self.retry_queue.put_nowait(task)
                    logger.info(f"Task {task.task_id} queued for retry {task.retry_count}/{task.max_retries}")
                except asyncio.QueueFull:
                    logger.error(f"Retry queue full, task {task.task_id} marked as failed")
                    self._mark_task_failed(task)
            else:
                # Max retries exceeded
                self._mark_task_failed(task)

    def _mark_task_failed(self, task: TranscriptionTask) -> None:
        """Mark a task as permanently failed."""
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()

        self.stats["total_failed"] += 1

        # Move to failed tasks
        self.failed_tasks[task.task_id] = task
        if task.task_id in self.active_tasks:
            del self.active_tasks[task.task_id]

        logger.error(f"Task {task.task_id} permanently failed after {task.retry_count} retries")

    async def _retry_processor(self) -> None:
        """Process retry queue."""
        logger.info("Retry processor started")

        while self.running:
            try:
                # Get task from retry queue
                try:
                    task = await asyncio.wait_for(self.retry_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Put back in main queue
                try:
                    await self.task_queue.put(task)
                    self.retry_queue.task_done()
                except asyncio.QueueFull:
                    # Main queue is full, put back in retry queue
                    await asyncio.sleep(5)
                    try:
                        self.retry_queue.put_nowait(task)
                    except asyncio.QueueFull:
                        self._mark_task_failed(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry processor error: {e}")

        logger.info("Retry processor stopped")

    async def cleanup_old_tasks(self, max_age_hours: int = 24) -> None:
        """Clean up old completed and failed tasks to prevent memory leaks."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        # Clean completed tasks
        old_completed = [
            task_id
            for task_id, task in self.completed_tasks.items()
            if task.completed_at and task.completed_at.timestamp() < cutoff_time
        ]

        for task_id in old_completed:
            del self.completed_tasks[task_id]

        # Clean failed tasks
        old_failed = [
            task_id
            for task_id, task in self.failed_tasks.items()
            if task.completed_at and task.completed_at.timestamp() < cutoff_time
        ]

        for task_id in old_failed:
            del self.failed_tasks[task_id]

        if old_completed or old_failed:
            logger.info(f"Cleaned up {len(old_completed)} completed and {len(old_failed)} failed tasks")


# Global task queue instance
_task_queue: Optional[TranscriptionTaskQueue] = None


def get_task_queue() -> TranscriptionTaskQueue:
    """Get the global task queue instance."""
    global _task_queue
    if _task_queue is None:
        raise RuntimeError("Task queue not initialized. Call initialize_task_queue() first.")
    return _task_queue


def initialize_task_queue(max_queue_size: int = 10000, num_workers: int = 4) -> TranscriptionTaskQueue:
    """Initialize the global task queue."""
    global _task_queue
    if _task_queue is not None:
        logger.warning("Task queue already initialized")
        return _task_queue

    _task_queue = TranscriptionTaskQueue(max_queue_size=max_queue_size, num_workers=num_workers)
    return _task_queue


async def shutdown_task_queue() -> None:
    """Shutdown the global task queue."""
    global _task_queue
    if _task_queue is not None:
        await _task_queue.stop()
        _task_queue = None
