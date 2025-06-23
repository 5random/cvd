from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Tuple, List
from concurrent.futures import Future
from src.utils.data_utils.indexing import DataCategory, DirectoryEventHandler
from src.utils.log_service import info, warning, error, debug
from src.utils.concurrency.thread_pool import (
    get_thread_pool_manager,
    ThreadPoolType,
    ManagedThreadPool,
)

if TYPE_CHECKING:
    from .data_manager import DataManager


class MaintenanceManager:
    """Background maintenance and watcher management for DataManager."""

    def __init__(self, manager: "DataManager") -> None:
        self._manager = manager
        self._observer = None
        self._background_tasks: List[Tuple[ManagedThreadPool, Future[Any]]] = []

    def _track(self, pool: ManagedThreadPool, fut: Future[Any]) -> None:
        """Track a background task and remove it from the list when done."""

        self._background_tasks.append((pool, fut))

        def _remove(f: Future[Any]) -> None:
            try:
                self._background_tasks.remove((pool, f))
            except ValueError:  # pragma: no cover - double remove
                pass

        fut.add_done_callback(_remove)

    def start_worker(self) -> None:
        mgr = get_thread_pool_manager()
        pool = mgr.get_pool(ThreadPoolType.FILE_IO)
        fut = pool.submit_task(
            lambda: self._background_worker(), task_id="data_maintenance"
        )
        self._track(pool, fut)

    def shutdown(self) -> None:
        for pool, fut in self._background_tasks:
            if not fut.done():
                fut.cancel()
            try:
                pool_type = getattr(pool, "pool_type", None)
            except Exception as e:
                error(f"Failed to get pool_type: {e}")
                pool_type = None
            if pool_type is not ThreadPoolType.GENERAL:
                pool.shutdown()
        self._background_tasks.clear()
        self._stop_watchers()

    def _background_worker(self) -> None:
        info("Background maintenance worker started")
        mgr = self._manager
        while not mgr._shutdown_event.is_set():
            try:
                mgr.indexer.scan_directories()
                self._cleanup_expired_downloads()
                mgr.compression_mgr.process_compression_queue()
                mgr._maintenance_service.rotate_old_files(
                    [mgr.raw_dir, mgr.processed_dir]
                )
                mgr._maintenance_service.compress_inactive_files(
                    [mgr.raw_dir, mgr.processed_dir]
                )
                mgr._shutdown_event.wait(mgr.index_scan_interval * 60)
            except Exception as e:
                error(f"Error in background maintenance: {e}")
                mgr._shutdown_event.wait(60)
        info("Background maintenance worker stopped")

    def start_watchers(self) -> None:
        if (
            not DirectoryEventHandler
            or getattr(DirectoryEventHandler, "__name__", None) is None
        ):
            return
        from watchdog.observers import Observer  # lazy import

        self._observer = Observer()
        directories = [
            (self._manager.raw_dir, DataCategory.RAW),
            (self._manager.processed_dir, DataCategory.PROCESSED),
            (self._manager.experiments_dir, DataCategory.EXPERIMENTS),
            (self._manager.logs_dir, DataCategory.LOGS),
        ]
        for directory, category in directories:
            if directory.exists():
                handler = DirectoryEventHandler(self._manager, category)
                self._observer.schedule(handler, str(directory), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def _stop_watchers(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def _process_changed_file(self, file_path: Path, category: DataCategory) -> None:
        mgr = self._manager
        idx = mgr._index
        if not idx or not file_path.exists():
            return
        file_key = str(file_path.resolve())
        if mgr.indexer._should_update_file_metadata(file_path, file_key):
            metadata = mgr.indexer._create_file_metadata(file_path, category)
            if metadata:
                idx.files[file_key] = metadata
                idx.dir_mtimes[
                    str(file_path.parent.resolve())
                ] = file_path.parent.stat().st_mtime
                mgr.indexer.save_index()

    def _cleanup_expired_downloads(self) -> None:
        mgr = self._manager
        now = time.time()
        expired_requests = []
        for request_id, request in list(mgr._download_requests.items()):
            if request.expires_at.timestamp() < now:
                expired_requests.append(request_id)
                if request.download_path and request.download_path.exists():
                    try:
                        request.download_path.unlink()
                        debug(f"Removed expired download file: {request.download_path}")
                    except Exception as e:
                        warning(f"Failed to remove expired download file: {e}")
        for request_id in expired_requests:
            mgr._download_requests.pop(request_id, None)
        if expired_requests:
            info(f"Cleaned up {len(expired_requests)} expired download requests")
