"""Facade for data management functionality."""

from __future__ import annotations

import os
import threading
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from types import TracebackType

from src.utils.config_service import get_config_service
from src.utils.concurrency.thread_pool import (
    get_thread_pool_manager,
    ThreadPoolType,
)
from src.utils.data_utils.compression_service import get_compression_service
from src.utils.data_utils.file_management_service import FileMaintenanceService
from src.utils.data_utils.indexing import (
    DataCategory,
    FileStatus,
    FileMetadata,
    DataIndex,
    DownloadRequest,
    Indexer,
    DirectoryEventHandler,
)
from src.utils.data_utils.compression_manager import CompressionManager
from src.utils.data_utils.maintenance import MaintenanceManager
from src.utils.log_service import info, warning, error


class DataManager:
    """High level interface aggregating indexing and maintenance components."""

    def __init__(self, base_output_dir: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()

        self._config_service = get_config_service()
        self._compression_service = get_compression_service()
        self._load_configuration(base_output_dir)

        self._index: Optional[DataIndex] = None
        self._download_requests: Dict[str, DownloadRequest] = {}

        self._create_directories()

        self.indexer = Indexer(self)
        self.indexer.load_index()

        self.compression_mgr = CompressionManager(self)
        self._maintenance_service = FileMaintenanceService(
            compression_service=self._compression_service,
            compression_threshold_bytes=self.compression_threshold_bytes,
            max_file_age_seconds=self.max_file_age_seconds,
        )
        self.maintenance_mgr = MaintenanceManager(self)
        self.maintenance_mgr.start_worker()
        if DirectoryEventHandler and os.getenv("ENABLE_WATCHDOG") == "1":
            try:
                self.maintenance_mgr.start_watchers()
            except Exception as e:  # pragma: no cover - optional
                warning(f"Failed to start directory watchers: {e}")
        info("DataManager initialized")

    # ------------------------------------------------------------------
    # Configuration and directory management
    def _load_configuration(self, base_output_dir: Optional[Path] = None) -> None:
        if self._config_service:
            storage_cfg = (
                self._config_service.get("data_storage.storage_paths", dict, {}) or {}
            )
            compression_cfg = (
                self._config_service.get("data_storage.compression", dict, {}) or {}
            )
            download_cfg = (
                self._config_service.get("data_storage.downloads", dict, {}) or {}
            )
        else:
            storage_cfg = {}
            compression_cfg = {}
            download_cfg = {}
            warning("Configuration service not available, using defaults")
        base_dir = base_output_dir or Path(storage_cfg.get("base", "data"))
        self.raw_dir = Path(storage_cfg.get("raw", str(base_dir / "raw")))
        self.processed_dir = Path(
            storage_cfg.get("processed", str(base_dir / "processed"))
        )
        exp_cfg = storage_cfg.get("experiments", {}) or {}
        self.experiments_dir = Path(exp_cfg.get("base", str(base_dir / "experiments")))
        self.logs_dir = Path(storage_cfg.get("logs", str(base_dir / "logs")))
        self.cache_dir = Path(storage_cfg.get("cache", str(base_dir / "cache")))
        self.index_file = Path(
            storage_cfg.get("index_file", str(base_dir / "data_index.json"))
        )
        self.downloads_dir = Path(
            download_cfg.get("downloads_dir", str(base_dir / "downloads"))
        )
        self.auto_compression = compression_cfg.get("enabled", True)
        self.compression_threshold_bytes = compression_cfg.get(
            "threshold_bytes", 10 * 1024 * 1024
        )
        self.max_file_age_seconds = compression_cfg.get(
            "max_file_age_seconds", 24 * 3600
        )
        self.index_scan_interval = max(1, download_cfg.get("scan_interval_minutes", 30))
        self.download_expiry_hours = max(1, download_cfg.get("expiry_hours", 24))
        self.max_download_size_mb = max(1, download_cfg.get("max_size_mb", 500))

    def _create_directories(self) -> None:
        directories = [
            self.raw_dir,
            self.processed_dir,
            self.experiments_dir,
            self.logs_dir,
            self.cache_dir,
            self.downloads_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API delegating to components
    def scan_directories(self) -> int:
        with self._lock:
            return self.indexer.scan_directories()

    def list_files(
        self,
        category: Optional[DataCategory] = None,
        sensor_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        status: Optional[FileStatus] = None,
        tags: Optional[List[str]] = None,
    ) -> List[FileMetadata]:
        with self._lock:
            return self.indexer.list_files(
                category, sensor_id, experiment_id, status, tags
            )

    def get_data_overview(self) -> Dict[str, Any]:
        with self._lock:
            return self.indexer.get_data_overview()

    def create_download_package(
        self, file_paths: List[str], format: str = "zip"
    ) -> str:
        if format not in ["zip"]:
            raise ValueError(f"Unsupported format: {format}")
        total_size = 0
        valid_paths = []
        with self._lock:
            if not self._index:
                raise ValueError("Data index not available")
            for file_path in file_paths:
                if file_path in self._index.files:
                    metadata = self._index.files[file_path]
                    if metadata.file_path.exists():
                        valid_paths.append(file_path)
                        total_size += metadata.size_bytes
                    else:
                        warning(f"File not found: {file_path}")
                else:
                    warning(f"File not in index: {file_path}")
        if not valid_paths:
            raise ValueError("No valid files found for download")
        if total_size > self.max_download_size_mb * 1024 * 1024:
            raise ValueError(
                f"Package size exceeds limit ({self.max_download_size_mb}MB)"
            )
        request_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=self.download_expiry_hours)
        download_request = DownloadRequest(
            request_id=request_id,
            requested_files=valid_paths,
            format=format,
            status="pending",
            created_at=datetime.now(),
            expires_at=expires_at,
            processed_files=0,
            total_files=len(valid_paths),
        )
        self._download_requests[request_id] = download_request
        mgr = get_thread_pool_manager()
        pool = mgr.get_pool(ThreadPoolType.GENERAL)
        fut = pool.submit_task(
            lambda rid=request_id: self._process_download_request(rid),
            task_id=f"download_{request_id}",
        )
        self.maintenance_mgr._track(pool, fut)
        info(f"Created download request {request_id} for {len(valid_paths)} files")
        return request_id

    def _process_download_request(self, request_id: str) -> None:
        try:
            with self._lock:
                request = self._download_requests.get(request_id)
                if not request:
                    return
                request.status = "processing"
                request.processed_files = 0
            package_path = self.downloads_dir / f"{request_id}.{request.format}"
            if request.format == "zip":
                self._create_zip_package(request.requested_files, package_path, request)
            with self._lock:
                request.download_path = package_path
                request.status = "ready"
            info(f"Download package ready: {request_id}")
        except Exception as e:
            error(f"Error processing download request {request_id}: {e}")
            with self._lock:
                if request_id in self._download_requests:
                    self._download_requests[request_id].status = "error"
                    self._download_requests[request_id].error_message = str(e)

    def _create_zip_package(
        self, file_paths: List[str], output_path: Path, request: DownloadRequest
    ) -> None:
        if not self._index:
            raise ValueError("Data index not available")
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in file_paths:
                if file_path in self._index.files:
                    metadata = self._index.files[file_path]
                    if metadata.file_path.exists():
                        arcname = metadata.file_path.name
                        if metadata.sensor_id:
                            arcname = f"{metadata.category.value}/{metadata.sensor_id}/{arcname}"
                        elif metadata.experiment_id:
                            arcname = f"{metadata.category.value}/{metadata.experiment_id}/{arcname}"
                        else:
                            arcname = f"{metadata.category.value}/{arcname}"
                        zipf.write(metadata.file_path, arcname)
                        with self._lock:
                            request.processed_files += 1

    def get_download_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        request = self._download_requests.get(request_id)
        if request:
            return request.to_dict()
        return None

    def get_download_file(self, request_id: str) -> Optional[Path]:
        request = self._download_requests.get(request_id)
        if (
            request
            and request.status == "ready"
            and request.download_path
            and request.download_path.exists()
        ):
            return request.download_path
        return None

    # Compression queue APIs
    def mark_for_compression(self, file_paths: List[str]) -> None:
        with self._lock:
            self.compression_mgr.mark_for_compression(file_paths)

    def _process_changed_file(self, file_path: Path, category: DataCategory) -> None:
        """Delegate file change processing to maintenance manager."""
        self.maintenance_mgr._process_changed_file(file_path, category)

    # Shutdown and context management
    def shutdown(self) -> None:
        self._shutdown_event.set()
        self.maintenance_mgr.shutdown()
        info("DataManager shutdown complete")

    def __enter__(self) -> "DataManager":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.shutdown()


_data_manager_instance: Optional[DataManager] = None
_data_manager_lock = threading.Lock()


def get_data_manager(base_output_dir: Optional[Path] = None) -> Optional[DataManager]:
    global _data_manager_instance
    with _data_manager_lock:
        if _data_manager_instance is None:
            try:
                _data_manager_instance = DataManager(base_output_dir)
            except Exception as e:
                error(f"Failed to initialize DataManager: {e}")
                return None
        return _data_manager_instance


def shutdown_data_manager() -> None:
    global _data_manager_instance
    with _data_manager_lock:
        if _data_manager_instance:
            _data_manager_instance.shutdown()
            _data_manager_instance = None
