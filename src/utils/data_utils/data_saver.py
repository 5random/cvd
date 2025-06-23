import csv
from pathlib import Path
from typing import Dict, Tuple, IO, Any, Optional, List
from types import SimpleNamespace
import contextlib
from concurrent.futures import Future
from src.utils.concurrency.thread_pool import get_thread_pool_manager, ThreadPoolType
from src.utils.log_service import info, warning, error
import threading
import time
from src.utils.data_utils.compression_service import get_compression_service
from src.utils.data_utils.file_management_service import FileMaintenanceService
from src.utils.data_utils.id_utils import sanitize_id


class DataSaver:
    """Service for saving sensor readings (raw and processed) to CSV files with efficient compression and rotation."""

    def __init__(
        self,
        base_output_dir: Path,
        storage_paths: Optional[Dict[str, str]] = None,
        compression_threshold_mb: float = 10.0,
        rotation_check_interval: int = 100,
        max_file_age_hours: int = 24,
        enable_background_operations: bool = True,
        flush_interval: int = 10,
    ):
        """
        Initialize DataSaver using either base_output_dir or explicit storage_paths from configuration.
        """
        # Determine raw and processed directories based on storage_paths or base_output_dir
        if storage_paths:
            raw_path = storage_paths.get("raw")
            proc_path = storage_paths.get("processed")
            self.raw_dir = Path(raw_path) if raw_path else base_output_dir / "raw"
            self.proc_dir = (
                Path(proc_path) if proc_path else base_output_dir / "processed"
            )
        else:
            self.raw_dir = base_output_dir / "raw"
            self.proc_dir = base_output_dir / "processed"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.proc_dir.mkdir(parents=True, exist_ok=True)

        # Configuration for performance optimization
        self.compression_threshold_bytes = compression_threshold_mb * 1024 * 1024
        self.rotation_check_interval = rotation_check_interval
        self.max_file_age_seconds = max_file_age_hours * 3600
        self.enable_background_operations = enable_background_operations
        try:
            flush_interval = int(flush_interval)
        except Exception:
            flush_interval = 1
        if flush_interval <= 0:
            flush_interval = 1
        self.flush_interval = flush_interval

        # mapping: category -> sensor_id -> (writer, file, row_count)
        self._writers: Dict[str, Dict[str, Tuple[Any, Optional[IO], int]]] = {
            "raw": {},
            "processed": {},
        }
        # Performance tracking
        self._operation_counts = {"raw": 0, "processed": 0}
        self._last_rotation_check = time.time()

        # Thread safety
        self._writer_lock = threading.Lock()

        # Services - initialize compression service if available
        try:
            self.compression_service = get_compression_service()
            self._compression_available = True
        except Exception as e:
            warning(f"Compression service not available: {e}")
            self.compression_service = None
            self._compression_available = False

        # Shutdown event for background tasks
        self._shutdown_event = threading.Event()
        # Initialize maintenance service
        self._maintenance_service = FileMaintenanceService(
            compression_service=self.compression_service,
            compression_threshold_bytes=self.compression_threshold_bytes,
            max_file_age_seconds=self.max_file_age_seconds,
        )

        # Initialize thread pools
        self._pool = get_thread_pool_manager().get_pool(ThreadPoolType.GENERAL)
        self._file_pool = get_thread_pool_manager().get_pool(ThreadPoolType.FILE_IO)
        # Track submitted background tasks for graceful shutdown
        self._tasks: List[Future] = []
        self._tasks_lock = threading.Lock()
        if self.enable_background_operations:
            fut = self._start_maintenance_thread()
            self._track(fut)

    def _start_maintenance_thread(self) -> Future:
        """Schedule periodic maintenance via ManagedThreadPool."""

        def maintenance_worker():
            while not self._shutdown_event.wait(timeout=60):  # Check every minute
                try:
                    self._perform_maintenance()
                except Exception as e:
                    error(f"Error in maintenance task: {e}")

        # Submit maintenance loop as long-running task
        fut = self._pool.submit_task(
            maintenance_worker, task_id="data_saver_maintenance"
        )
        return fut

    def _perform_maintenance(self) -> None:
        """Perform background maintenance operations."""
        # Delegate maintenance to unified service
        directories = [self.raw_dir, self.proc_dir]
        try:
            self._maintenance_service.rotate_old_files(directories)
            self._maintenance_service.compress_inactive_files(directories)
        except Exception as e:
            error(f"Maintenance error: {e}")

    def _check_compression_if_needed(
        self, file_handle: Optional[IO], sensor_id: str, category: str
    ) -> None:
        """Check if file needs compression based on size threshold."""
        if file_handle is None or not self._compression_available:
            return

        try:
            file_path = Path(file_handle.name)
            if file_path.stat().st_size >= self.compression_threshold_bytes:
                # Thread-safe file handle closing and writer removal
                with self._writer_lock:
                    # Close current file handle before compression
                    file_handle.close()

                    # Remove from writers to trigger recreation
                    if sensor_id in self._writers[category]:
                        del self._writers[category][sensor_id]

                # Compress in background to avoid blocking writes
                if self.enable_background_operations:
                    # schedule async compression via file IO pool
                    fut = self._file_pool.submit_task(
                        self._compress_file_async,
                        file_path,
                        sensor_id,
                        category,
                        task_id=f"compress_async_{sensor_id}_{category}",
                    )
                    self._track(fut)
                else:
                    self._compress_file_sync(file_path)

        except Exception as e:
            error(f"Error checking compression for {sensor_id}: {e}")

    def _compress_file_async(
        self, file_path: Path, sensor_id: str, category: str
    ) -> Optional[Path]:
        """Compress file asynchronously."""
        if not self._compression_available:
            warning(f"Compression not available for {file_path}")
            return
        assert self.compression_service is not None, "Compression service unavailable"
        try:
            compressed_dir = file_path.parent / "compressed"
            compressed_dir.mkdir(exist_ok=True)

            compressed_path = (
                compressed_dir / f"{file_path.stem}_{int(time.time())}.csv.gz"
            )
            result = self.compression_service.compress_file(
                str(file_path), str(compressed_path)
            )

            preserve = getattr(
                self.compression_service,
                "_compression_settings",
                SimpleNamespace(preserve_original=False),
            ).preserve_original

            if not preserve and file_path.exists():
                try:
                    file_path.unlink(missing_ok=True)
                except Exception as e:
                    warning(f"Failed to delete source file {file_path}: {e}")
                if file_path.exists():
                    warning(
                        f"Source file was not deleted after compression: {file_path}"
                    )

            if preserve:
                info(f"Compressed file {file_path} -> {compressed_path}")
            else:
                info(f"Compressed and removed {file_path} -> {compressed_path}")
            return result

        except Exception as e:
            error(f"Failed to compress {file_path}: {e}")

    def _compress_file_sync(self, file_path: Path) -> Optional[Path]:
        """Compress file synchronously."""
        if not self._compression_available:
            warning(f"Compression not available for {file_path}")
            return
        assert self.compression_service is not None, "Compression service unavailable"
        try:
            compressed_dir = file_path.parent / "compressed"
            compressed_dir.mkdir(exist_ok=True)

            compressed_path = (
                compressed_dir / f"{file_path.stem}_{int(time.time())}.csv.gz"
            )
            result = self.compression_service.compress_file(
                str(file_path), str(compressed_path)
            )

            preserve = getattr(
                self.compression_service,
                "_compression_settings",
                SimpleNamespace(preserve_original=False),
            ).preserve_original

            if not preserve and file_path.exists():
                try:
                    file_path.unlink(missing_ok=True)
                except Exception as e:
                    warning(f"Failed to delete source file {file_path}: {e}")
                if file_path.exists():
                    warning(
                        f"Source file was not deleted after compression: {file_path}"
                    )

            if preserve:
                info(f"Compressed file {file_path} -> {compressed_path}")
            else:
                info(f"Compressed and removed {file_path} -> {compressed_path}")
            return result

        except Exception as e:
            error(f"Failed to compress {file_path}: {e}")

    def _check_rotation_if_needed(self, category: str) -> None:
        """Check if rotation is needed based on operation count."""
        # Only check rotation periodically to avoid overhead
        if (
            self._operation_counts[category] % self.rotation_check_interval == 0
            or time.time() - self._last_rotation_check > 300
        ):  # Check every 5 minutes minimum
            self._last_rotation_check = time.time()
            # rotation is handled by FileMaintenanceService; no scheduled rotation needed here
            return

    def _rotate_old_files(self, current_time: float) -> None:
        """Rotate files older than the specified age."""
        try:
            for directory in [self.raw_dir, self.proc_dir]:
                for file_path in directory.glob("*.csv"):
                    file_age = current_time - file_path.stat().st_mtime

                    if file_age > self.max_file_age_seconds:
                        # Move to compressed directory with timestamp
                        compressed_dir = directory / "compressed"
                        compressed_dir.mkdir(exist_ok=True)

                        timestamp = int(file_path.stat().st_mtime)
                        new_name = f"{file_path.stem}_{timestamp}.csv"
                        rotated_path = compressed_dir / new_name

                        file_path.rename(rotated_path)
                        info(f"Rotated old file {file_path} -> {rotated_path}")

        except Exception as e:
            error(f"Error rotating old files: {e}")

    def _compress_inactive_files(self, current_time: float) -> None:
        """Compress files that haven't been accessed recently."""
        try:
            for directory in [self.raw_dir, self.proc_dir]:
                for file_path in directory.glob("*.csv"):
                    # Skip if file is currently being written to
                    file_in_use = any(
                        file_handle is not None and file_handle.name == str(file_path)
                        for writers in self._writers.values()
                        for _, file_handle, _ in writers.values()
                    )

                    if not file_in_use:
                        file_age = current_time - file_path.stat().st_atime
                        file_size = file_path.stat().st_size

                        # Compress if file is large and hasn't been accessed in a while
                        if (
                            file_size > self.compression_threshold_bytes / 2
                            and file_age > 3600
                        ):  # 1 hour since last access
                            self._compress_file_sync(file_path)
        except Exception as e:
            error(f"Error compressing inactive files: {e}")

    def save(self, reading: Any, category: str = "raw") -> None:
        """Save a SensorReading under the given category ('raw' or 'processed') with performance optimizations."""
        if category not in self._writers:
            error(f"Unknown data saver category: {category}")
            return

        output_dir = self.raw_dir if category == "raw" else self.proc_dir
        sensor_id = reading.sensor_id

        with self._writer_lock:
            sensor_map = self._writers[category]
            writer_data = sensor_map.get(sensor_id)

            writer: Any
            f: Optional[IO[Any]]
            row_count: int

            if writer_data is None or writer_data[0] is None:
                safe_id = sanitize_id(sensor_id)
                file_path = output_dir / f"{safe_id}.csv"
                is_new = not file_path.exists() or file_path.stat().st_size == 0
                temp_f = open(file_path, "a", newline="", encoding="utf-8")
                temp_writer = csv.writer(temp_f)
                row_count = 0
                existing = sensor_map.get(sensor_id)
                if existing is None or existing[0] is None:
                    if is_new:
                        try:
                            temp_writer.writerow(["timestamp", "value", "status"])
                            row_count = 1
                        except Exception as e:
                            error(
                                f"Failed to write CSV header ({category}) for {sensor_id}: {e}"
                            )
                            temp_f.close()
                            return
                    sensor_map[sensor_id] = (
                        temp_writer,
                        temp_f,
                        row_count,
                    )
                    writer, f = temp_writer, temp_f
                else:
                    writer, f, row_count = existing
                    temp_f.close()
            else:
                writer, f, row_count = writer_data

            try:
                writer.writerow(
                    [
                        reading.timestamp,
                        reading.value,
                        reading.status.value,
                    ]
                )
                row_count += 1
                if f is not None and row_count % self.flush_interval == 0:
                    f.flush()

                sensor_map[sensor_id] = (writer, f, row_count)
            except Exception as e:
                error(f"Failed to write {category} data for {sensor_id}: {e}")
                return

        self._operation_counts[category] += 1

        self._check_compression_if_needed(f, sensor_id, category)
        self._check_rotation_if_needed(category)

    def flush_all(self) -> None:
        """Flush all open buffers."""
        for cat_map in self._writers.values():
            for writer, f, row_count in cat_map.values():
                if f:
                    try:
                        f.flush()
                    except Exception as e:
                        warning(f"Failed to flush file buffer: {e}")

    def close(self) -> None:
        """Close all open file handles and cleanup background operations."""
        # Signal shutdown to background loops
        self._shutdown_event.set()
        # Wait for tracked background tasks to finish instead of cancelling
        with self._tasks_lock:
            tasks_snapshot = list(self._tasks)
        for fut in tasks_snapshot:
            try:
                # give the worker some time to finish gracefully
                fut.result(timeout=5)
            except Exception:
                try:
                    fut.cancel()
                except Exception as e:
                    warning(f"Failed to cancel background task: {e}")
            finally:
                with contextlib.suppress(ValueError):
                    with self._tasks_lock:
                        self._tasks.remove(fut)

        # Close all file handles
        for cat_map in self._writers.values():
            for writer, f, row_count in cat_map.values():
                if f:
                    try:
                        f.close()
                    except Exception as e:
                        warning(f"Failed to close file handle: {e}")
        self._writers.clear()

    def __del__(self) -> None:
        """Destructor to ensure files are closed on deletion."""
        try:
            self.close()
        except Exception as e:
            warning(f"Error during DataSaver cleanup: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for monitoring."""
        return {
            "operation_counts": self._operation_counts.copy(),
            "active_writers": {
                category: len(writers) for category, writers in self._writers.items()
            },
            "compression_threshold_mb": self.compression_threshold_bytes
            / (1024 * 1024),
            "rotation_check_interval": self.rotation_check_interval,
            "background_operations_enabled": self.enable_background_operations,
            "compression_available": self._compression_available,
            # maintenance tasks scheduled via thread pool
            "maintenance_tasks_scheduled": self.enable_background_operations,
            "maintenance_thread_active": any(not t.done() for t in self._tasks),
        }

    def _track(self, fut: Future) -> None:
        """Track background Future and remove it from the list once done."""
        with self._tasks_lock:
            self._tasks.append(fut)

        def _remove(f: Future):
            try:
                with self._tasks_lock:
                    self._tasks.remove(f)
            except ValueError:
                # Task was already removed
                pass

        fut.add_done_callback(_remove)
