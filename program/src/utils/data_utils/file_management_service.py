from pathlib import Path
from typing import List, Optional
import threading
import time
import os

from src.utils.log_utils.log_service import info, warning, error
from src.utils.concurrency.thread_pool import get_thread_pool_manager, ThreadPoolType
from src.utils.data_utils.compression_service import CompressionService


class FileMaintenanceService:
    """
    Service for rotating and compressing old data files across multiple directories.
    """

    def __init__(
        self,
        compression_service: Optional[CompressionService],
        compression_threshold_bytes: float,
        max_file_age_seconds: int,
    ):
        self.compression_service = compression_service
        self.threshold = compression_threshold_bytes
        self.max_age = max_file_age_seconds

    def rotate_old_files(self, directories: List[Path]) -> None:
        """Rotate files older than max_age seconds into a compressed subdirectory."""
        # use file IO pool to rename old files in parallel
        try:
            now = time.time()
            pool = get_thread_pool_manager().get_pool(ThreadPoolType.FILE_IO)
            futures = []
            for directory in directories:
                for file_path in directory.glob("*.csv"):
                    age = now - file_path.stat().st_mtime
                    if age > self.max_age:
                        compressed_dir = directory / "compressed"
                        compressed_dir.mkdir(exist_ok=True)
                        timestamp = int(file_path.stat().st_mtime)
                        new_name = f"{file_path.stem}_{timestamp}.csv"
                        target = compressed_dir / new_name
                        # schedule rename and return the target path
                        futures.append(
                            pool.submit_task(
                                lambda p=file_path, t=target: (p, (p.rename(t) or t)),
                                task_id=f"rotate_{file_path.name}",
                            )
                        )
            # wait for renames to complete
            for fut in futures:
                try:
                    src, dst = fut.result()
                    info(f"Rotated old file via pool: {src} -> {dst}")
                except Exception as ex:
                    error(f"Error rotating file in pool: {ex}")
        except Exception as e:
            error(f"Error rotating files: {e}")

    def compress_inactive_files(self, directories: List[Path]) -> None:
        """Compress files exceeding threshold bytes into compressed subdirectory."""
        if not self.compression_service:
            warning("Compression service not available")
            return
        try:
            pool = get_thread_pool_manager().get_pool(ThreadPoolType.FILE_IO)
            futures = []
            for directory in directories:
                for file_path in directory.glob("*.csv"):
                    size = file_path.stat().st_size
                    if size >= self.threshold:
                        # schedule compression in FILE_IO pool
                        futures.append(
                            pool.submit_task(
                                lambda p=file_path: self._compress_file(p),
                                task_id=f"compress_{file_path.name}",
                            )
                        )
            # optionally wait or log errors
            for fut in futures:
                try:
                    fut.result()
                except Exception as ex:
                    error(f"Error compressing file in pool: {ex}")
            now = time.time() + 1
            for directory in directories:
                try:
                    os.utime(directory, (now, now))
                except Exception:
                    pass
        except Exception as e:
            error(f"Error compressing files: {e}")

    def _compress_file(self, file_path: Path) -> None:
        """Helper to compress a single file synchronously."""
        # Ensure compression service is available
        if not self.compression_service:
            warning(f"Compression service not available for {file_path}")
            return
        try:
            compressed_dir = file_path.parent / "compressed"
            compressed_dir.mkdir(exist_ok=True)
            compressed_path = (
                compressed_dir / f"{file_path.stem}_{int(time.time())}.csv.gz"
            )
            self.compression_service.compress_file(str(file_path), str(compressed_path))

            preserve = False
            settings = getattr(self.compression_service, "_compression_settings", None)
            if settings is not None:
                preserve = getattr(settings, "preserve_original", False)

            if not preserve and file_path.exists():
                try:
                    file_path.unlink()
                except Exception:
                    pass

            if preserve:
                info(f"Compressed file {file_path} -> {compressed_path}")
            else:
                info(f"Compressed and removed {file_path} -> {compressed_path}")
        except Exception as e:
            error(f"Failed to compress {file_path}: {e}")

    def compress_directory(
        self,
        directory: Path,
        pattern: str = "*",
        data_type: str = "general",
        recursive: bool = False,
    ) -> Optional[List[Path]]:
        """Compress all files matching pattern in a directory using compression service."""
        if not self.compression_service:
            warning("Compression service not available")
            return None
        try:
            # delegate to underlying compression service
            return self.compression_service.compress_directory(
                directory, pattern=pattern, data_type=data_type, recursive=recursive
            )
        except Exception as e:
            error(f"Failed to compress directory {directory}: {e}")
            return None
