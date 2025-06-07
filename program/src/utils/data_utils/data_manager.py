"""
Data management service for indexing, querying, and providing access to stored data files.
Complements DataSaver by focusing on data retrieval, organization, and download functionality.
"""

import json
import zipfile
import threading
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from concurrent.futures import Future
from src.utils.concurrency.thread_pool import get_thread_pool_manager, ThreadPoolType, ManagedThreadPool
import uuid
from src.utils.data_utils.compression_service import get_compression_service
from src.utils.data_utils.file_management_service import FileMaintenanceService

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    WATCHDOG_AVAILABLE = False

from src.utils.log_utils.log_service import info, warning, error, debug
from src.utils.config_utils.config_service import get_config_service


class DataCategory(Enum):
    """Categories of data managed by the system"""
    RAW = "raw"
    PROCESSED = "processed"
    EXPERIMENTS = "experiments"
    LOGS = "logs"


class FileStatus(Enum):
    """Status of files in the data management system"""
    ACTIVE = "active"
    COMPRESSED = "compressed"
    ARCHIVED = "archived"
    PENDING_COMPRESSION = "pending_compression"
    ERROR = "error"


@dataclass
class FileMetadata:
    """Metadata information for a data file"""
    file_path: Path
    category: DataCategory
    status: FileStatus
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    sensor_id: Optional[str] = None
    experiment_id: Optional[str] = None
    compressed_path: Optional[Path] = None
    checksum: Optional[str] = None
    tags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert Path objects to strings
        data['file_path'] = str(self.file_path)
        if self.compressed_path:
            data['compressed_path'] = str(self.compressed_path)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['modified_at'] = self.modified_at.isoformat()
        # Convert enums to values
        data['category'] = self.category.value
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileMetadata':
        """Create from dictionary (from JSON deserialization)"""
        data = data.copy()
        # Convert strings back to Path objects
        data['file_path'] = Path(data['file_path'])
        if data.get('compressed_path'):
            data['compressed_path'] = Path(data['compressed_path'])
        # Convert ISO strings back to datetime objects
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['modified_at'] = datetime.fromisoformat(data['modified_at'])
        # Convert strings back to enums
        data['category'] = DataCategory(data['category'])
        data['status'] = FileStatus(data['status'])
        return cls(**data)


@dataclass
class DataIndex:
    """Index of all managed data files"""
    files: Dict[str, FileMetadata]  # file_path -> metadata
    last_updated: datetime
    dir_mtimes: Dict[str, float] = field(default_factory=dict)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'files': {path: metadata.to_dict() for path, metadata in self.files.items()},
            'last_updated': self.last_updated.isoformat(),
            'dir_mtimes': self.dir_mtimes,
            'version': self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataIndex':
        """Create from dictionary (from JSON deserialization)"""
        files = {
            path: FileMetadata.from_dict(metadata_dict)
            for path, metadata_dict in data.get('files', {}).items()
        }
        return cls(
            files=files,
            last_updated=datetime.fromisoformat(data['last_updated']),
            dir_mtimes=data.get('dir_mtimes', {}),
            version=data.get('version', '1.0')
        )


@dataclass
class DownloadRequest:
    """Request for packaging and downloading data files"""
    request_id: str
    requested_files: List[str]  # file paths
    format: str  # 'zip', 'tar.gz', etc.
    status: str  # 'pending', 'processing', 'ready', 'expired', 'error'
    created_at: datetime
    expires_at: datetime
    download_path: Optional[Path] = None
    error_message: Optional[str] = None
    processed_files: int = 0
    total_files: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        if self.download_path:
            data['download_path'] = str(self.download_path)
        return data


if WATCHDOG_AVAILABLE:
    class _DirectoryEventHandler(FileSystemEventHandler):
        """Handle filesystem events to update the index incrementally."""

        def __init__(self, manager: 'DataManager', category: DataCategory) -> None:
            super().__init__()
            self._manager = manager
            self._category = category

        def on_created(self, event):
            if not event.is_directory:
                self._manager._process_changed_file(Path(event.src_path), self._category)

        def on_modified(self, event):
            if not event.is_directory:
                self._manager._process_changed_file(Path(event.src_path), self._category)


class DataManager:
    """
    Comprehensive data management service that provides:
    - Data file indexing and metadata management
    - Query and filtering capabilities
    - Download package creation
    - Background maintenance tasks (compression, cleanup)
    - Integration with existing compression and configuration services
    """

    def __init__(self, base_output_dir: Optional[Path] = None):
        """Initialize the data manager with configuration"""
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        # schedule list for background tasks (worker started after initialization)
        self._background_tasks: List[Tuple[ManagedThreadPool, Future]] = []
        
        # Initialize configuration
        self._config_service = get_config_service()
        self._compression_service = get_compression_service()
        
        # Load storage paths from configuration
        self._load_configuration(base_output_dir)
        
        # Initialize data structures
        self._index: Optional[DataIndex] = None
        self._download_requests: Dict[str, DownloadRequest] = {}
        
        # Create necessary directories
        self._create_directories()
        
        # Load existing index or create new one
        self._load_index()
        
        # Initialize FileMaintenanceService for maintenance operations
        self._maintenance_service = FileMaintenanceService(
            compression_service=self._compression_service,
            compression_threshold_bytes=self.compression_threshold_bytes,
            max_file_age_seconds=self.max_file_age_seconds
        )

        # start background maintenance worker
        mgr = get_thread_pool_manager()
        pool = mgr.get_pool(ThreadPoolType.FILE_IO)
        fut = pool.submit_task(lambda: self._background_maintenance_worker(), task_id="data_maintenance")
        self._background_tasks.append((pool, fut))

        # Start file system watchers if enabled
        self._observer: Optional[Observer] = None
        if WATCHDOG_AVAILABLE and os.getenv('ENABLE_WATCHDOG') == '1':
            try:
                self._start_watchers()
            except Exception as e:  # pragma: no cover - best effort
                warning(f"Failed to start directory watchers: {e}")

        info("DataManager initialized successfully and background maintenance scheduled")

    def _load_configuration(self, base_output_dir: Optional[Path] = None) -> None:
        """Load configuration from config service"""
        if self._config_service:
            storage_cfg = self._config_service.get('data_storage.storage_paths', dict, {}) or {}
            compression_cfg = self._config_service.get('data_storage.compression', dict, {}) or {}
            download_cfg = self._config_service.get('data_storage.downloads', dict, {}) or {}
        else:
            storage_cfg = {}
            compression_cfg = {}
            download_cfg = {}
            warning("Configuration service not available, using defaults")
        
        # Set up directory paths under data_storage.base
        base_dir = base_output_dir or Path(storage_cfg.get('base', 'data'))
        self.raw_dir = Path(storage_cfg.get('raw', str(base_dir / 'raw')))
        self.processed_dir = Path(storage_cfg.get('processed', str(base_dir / 'processed')))
        # Experiments may define a nested dict with base
        exp_cfg = storage_cfg.get('experiments', {}) or {}
        self.experiments_dir = Path(exp_cfg.get('base', str(base_dir / 'experiments')))
        self.logs_dir = Path(storage_cfg.get('logs', str(base_dir / 'logs')))
        self.cache_dir = Path(storage_cfg.get('cache', str(base_dir / 'cache')))
        
        # Set up index and download paths
        self.index_file = Path(storage_cfg.get('index_file', str(base_dir / 'data_index.json')))
        self.downloads_dir = Path(download_cfg.get('downloads_dir', str(base_dir / 'downloads')))
        
        # Configuration settings
        self.auto_compression = compression_cfg.get('enabled', True)
        # File maintenance thresholds
        self.compression_threshold_bytes = compression_cfg.get('threshold_bytes', 10 * 1024 * 1024)
        self.max_file_age_seconds = compression_cfg.get('max_file_age_seconds', 24 * 3600)
        # Download settings
        self.index_scan_interval = max(1, download_cfg.get('scan_interval_minutes', 30))
        self.download_expiry_hours = max(1, download_cfg.get('expiry_hours', 24))
        self.max_download_size_mb = max(1, download_cfg.get('max_size_mb', 500))
        debug(f"DataManager configuration loaded: auto compression enabled: {self.auto_compression}, scan_interval={self.index_scan_interval} min, expiry={self.download_expiry_hours} h , max_size={self.max_download_size_mb} MB")
        # Initialize compression service if enabled
    def _create_directories(self) -> None:
        """Create necessary directories"""
        directories = [
            self.raw_dir, self.processed_dir, self.experiments_dir,
            self.logs_dir, self.cache_dir, self.downloads_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Ensure index file directory exists
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        """Load existing index or create a new one"""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                self._index = DataIndex.from_dict(index_data)
                info(f"Loaded existing data index with {len(self._index.files)} files")
            else:
                self._index = DataIndex(files={}, last_updated=datetime.now())
                info("Created new data index")
        except Exception as e:
            error(f"Failed to load data index: {e}")
            self._index = DataIndex(files={}, last_updated=datetime.now())

    def _save_index(self) -> None:
        """Save current index to disk"""
        try:
            with self._lock:
                if self._index:
                    self._index.last_updated = datetime.now()
                    with open(self.index_file, 'w', encoding='utf-8') as f:
                        json.dump(self._index.to_dict(), f, indent=2)
                    debug("Data index saved successfully")
        except Exception as e:
            error(f"Failed to save data index: {e}")

    def _background_maintenance_worker(self) -> None:
        """Background worker for maintenance tasks"""
        info("Background maintenance worker started")
        
        while not self._shutdown_event.is_set():
            try:
                # Scan for new/changed files
                self.scan_directories()
                
                # Clean up expired downloads
                self._cleanup_expired_downloads()
                
                # Process pending compression tasks
                self._process_compression_queue()
                
                # Perform file rotation and compression via maintenance service
                self._maintenance_service.rotate_old_files([
                    self.raw_dir,
                    self.processed_dir
                ])
                self._maintenance_service.compress_inactive_files([
                    self.raw_dir,
                    self.processed_dir
                ])
                
                # Wait for next iteration
                self._shutdown_event.wait(self.index_scan_interval * 60)
                
            except Exception as e:
                error(f"Error in background maintenance: {e}")
                self._shutdown_event.wait(60)  # Shorter retry interval on error
        
        info("Background maintenance worker stopped")

    def scan_directories(self) -> int:
        """
        Scan all managed directories for new or changed files.
        Returns the number of files processed.
        """
        with self._lock:
            if not self._index:
                return 0
            
            files_processed = 0
            directories_to_scan = [
                (self.raw_dir, DataCategory.RAW),
                (self.processed_dir, DataCategory.PROCESSED),
                (self.experiments_dir, DataCategory.EXPERIMENTS),
                (self.logs_dir, DataCategory.LOGS)
            ]
            
            for directory, category in directories_to_scan:
                if directory.exists():
                    dir_key = str(directory.resolve())
                    current_mtime = directory.stat().st_mtime
                    last_mtime = self._index.dir_mtimes.get(dir_key)
                    if last_mtime is not None and current_mtime <= last_mtime:
                        continue

                    files_processed += self._scan_directory(directory, category)
                    self._index.dir_mtimes[dir_key] = current_mtime
            
            if files_processed > 0:
                self._save_index()
                info(f"Scanned directories and processed {files_processed} files")
            
            return files_processed

    def _scan_directory(self, directory: Path, category: DataCategory) -> int:
        """Scan a specific directory for files using os.scandir for speed"""
        files_processed = 0

        stack = [directory]
        while stack:
            current = stack.pop()
            try:
                for entry in os.scandir(current):
                    if entry.name.startswith('.'):
                        continue
                    path = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(path)
                    elif entry.is_file(follow_symlinks=False):
                        file_key = str(path.resolve())
                        if self._should_update_file_metadata(path, file_key):
                            metadata = self._create_file_metadata(path, category)
                            if metadata and self._index:
                                self._index.files[file_key] = metadata
                                files_processed += 1
            except Exception as e:
                error(f"Error scanning {current}: {e}")

        return files_processed

    def _should_update_file_metadata(self, file_path: Path, file_key: str) -> bool:
        """Check if file metadata needs updating"""
        if not self._index or file_key not in self._index.files:
            return True
        
        try:
            existing_metadata = self._index.files[file_key]
            current_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            return current_mtime > existing_metadata.modified_at
        except (OSError, ValueError):
            return True

    def _create_file_metadata(self, file_path: Path, category: DataCategory) -> Optional[FileMetadata]:
        """Create metadata for a file"""
        try:
            stat = file_path.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime)
            modified_at = datetime.fromtimestamp(stat.st_mtime)
            
            # Extract sensor_id and experiment_id from filename/path
            sensor_id = self._extract_sensor_id(file_path)
            experiment_id = self._extract_experiment_id(file_path)
            
            # Determine file status
            status = FileStatus.ACTIVE
            if file_path.suffix in ['.gz', '.bz2', '.xz', '.zip']:
                status = FileStatus.COMPRESSED
            
            return FileMetadata(
                file_path=file_path,
                category=category,
                status=status,
                size_bytes=stat.st_size,
                created_at=created_at,
                modified_at=modified_at,
                sensor_id=sensor_id,
                experiment_id=experiment_id
            )
            
        except Exception as e:
            error(f"Error creating metadata for {file_path}: {e}")
            return None

    def _extract_sensor_id(self, file_path: Path) -> Optional[str]:
        """Extract sensor ID from file path"""
        # Try to extract from filename (assuming format like "sensor123.csv")
        stem = file_path.stem
        if stem and not stem.startswith('experiment_'):
            # Remove common extensions
            while stem.endswith(('.gz', '.bz2', '.xz', '.zip')):
                stem = Path(stem).stem
            return stem
        return None

    def _extract_experiment_id(self, file_path: Path) -> Optional[str]:
        """Extract experiment ID from file path"""
        # Look for experiment ID in path components or filename
        path_parts = file_path.parts
        for part in path_parts:
            if part.startswith('experiment_'):
                exp_id = part[len('experiment_'):]
                while exp_id.endswith(('.gz', '.bz2', '.xz', '.zip')):
                    exp_id = Path(exp_id).stem
                return exp_id or None
        
        # Check filename
        if file_path.stem.startswith('experiment_'):
            suffix = file_path.stem[len('experiment_'):]
            while suffix.endswith(('.gz', '.bz2', '.xz', '.zip')):
                suffix = Path(suffix).stem
            return suffix or None
        
        return None

    def list_files(self, 
                   category: Optional[DataCategory] = None,
                   sensor_id: Optional[str] = None,
                   experiment_id: Optional[str] = None,
                   status: Optional[FileStatus] = None,
                   tags: Optional[List[str]] = None) -> List[FileMetadata]:
        """
        List files with optional filtering.
        
        Args:
            category: Filter by data category
            sensor_id: Filter by sensor ID
            experiment_id: Filter by experiment ID
            status: Filter by file status
            tags: Filter by tags (files must have all specified tags)
        
        Returns:
            List of matching file metadata
        """
        with self._lock:
            if not self._index:
                return []
            
            results = []
            for metadata in self._index.files.values():
                # Apply filters
                if category and metadata.category != category:
                    continue
                if sensor_id and metadata.sensor_id != sensor_id:
                    continue
                if experiment_id and metadata.experiment_id != experiment_id:
                    continue
                if status and metadata.status != status:
                    continue
                if tags and (not metadata.tags or not all(tag in metadata.tags for tag in tags)):
                    continue
                
                results.append(metadata)
            
            # Sort by modified time (newest first)
            results.sort(key=lambda x: x.modified_at, reverse=True)
            return results

    def get_data_overview(self) -> Dict[str, Any]:
        """
        Get overview statistics of managed data.
        
        Returns:
            Dictionary with statistics and summary information
        """
        with self._lock:
            if not self._index:
                return {}
            
            overview = {
                'total_files': len(self._index.files),
                'last_updated': self._index.last_updated.isoformat(),
                'categories': {},
                'status_summary': {},
                'total_size_bytes': 0,
                'sensors': set(),
                'experiments': set()
            }
            
            for metadata in self._index.files.values():
                # Category breakdown
                cat_name = metadata.category.value
                if cat_name not in overview['categories']:
                    overview['categories'][cat_name] = {'count': 0, 'size_bytes': 0}
                overview['categories'][cat_name]['count'] += 1
                overview['categories'][cat_name]['size_bytes'] += metadata.size_bytes
                
                # Status breakdown
                status_name = metadata.status.value
                overview['status_summary'][status_name] = overview['status_summary'].get(status_name, 0) + 1
                
                # Totals
                overview['total_size_bytes'] += metadata.size_bytes
                
                # Collect unique sensors and experiments
                if metadata.sensor_id:
                    overview['sensors'].add(metadata.sensor_id)
                if metadata.experiment_id:
                    overview['experiments'].add(metadata.experiment_id)
            
            # Convert sets to lists for JSON serialization
            overview['sensors'] = list(overview['sensors'])
            overview['experiments'] = list(overview['experiments'])
            
            return overview

    def create_download_package(self, 
                              file_paths: List[str],
                              format: str = 'zip') -> str:
        """
        Create a download package for the specified files.
        
        Args:
            file_paths: List of file paths to include
            format: Package format ('zip' supported)
        
        Returns:
            Request ID for tracking the download
        """
        if format not in ['zip']:
            raise ValueError(f"Unsupported format: {format}")
        # Validate file paths
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
        
        # Check size limit
        if total_size > self.max_download_size_mb * 1024 * 1024:
            raise ValueError(f"Package size exceeds limit ({self.max_download_size_mb}MB)")
        
        # Create download request
        request_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=self.download_expiry_hours)
        
        download_request = DownloadRequest(
            request_id=request_id,
            requested_files=valid_paths,
            format=format,
            status='pending',
            created_at=datetime.now(),
            expires_at=expires_at,
            processed_files=0,
            total_files=len(valid_paths)
        )
        
        self._download_requests[request_id] = download_request
        
        # Process the request asynchronously via thread pool
        mgr = get_thread_pool_manager()
        pool = mgr.get_pool(ThreadPoolType.GENERAL)
        fut = pool.submit_task(lambda rid=request_id: self._process_download_request(rid), task_id=f"download_{request_id}")
        self._background_tasks.append((pool, fut))
        
        info(f"Created download request {request_id} for {len(valid_paths)} files")
        return request_id

    def _process_download_request(self, request_id: str) -> None:
        """Process a download request in the background"""
        # Ensure thread-safe updates to download_requests
        try:
            with self._lock:
                request = self._download_requests.get(request_id)
                if not request:
                    return
                request.status = 'processing'
                request.processed_files = 0
            # Create download package outside lock
            package_path = self.downloads_dir / f"{request_id}.{request.format}"
            if request.format == 'zip':
                self._create_zip_package(request.requested_files, package_path, request)
            # Update request under lock
            with self._lock:
                request.download_path = package_path
                request.status = 'ready'
            info(f"Download package ready: {request_id}")
        except Exception as e:
            error(f"Error processing download request {request_id}: {e}")
            with self._lock:
                if request_id in self._download_requests:
                    self._download_requests[request_id].status = 'error'
                    self._download_requests[request_id].error_message = str(e)

    def _create_zip_package(self, file_paths: List[str], output_path: Path, request: DownloadRequest) -> None:
        """Create a ZIP package from the specified files and update progress."""
        if not self._index:
            raise ValueError("Data index not available")

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in file_paths:
                if file_path in self._index.files:
                    metadata = self._index.files[file_path]
                    if metadata.file_path.exists():
                        # Use relative path in archive
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
        """Get the status of a download request"""
        request = self._download_requests.get(request_id)
        if request:
            return request.to_dict()
        return None

    def get_download_file(self, request_id: str) -> Optional[Path]:
        """Get the file path for a ready download"""
        request = self._download_requests.get(request_id)
        if request and request.status == 'ready' and request.download_path:
            if request.download_path.exists():
                return request.download_path
        return None

    def _cleanup_expired_downloads(self) -> None:
        """Clean up expired download requests and files"""
        with self._lock:
            now = datetime.now()
            expired_requests = []
            # Collect expired requests
            for request_id, request in list(self._download_requests.items()):
                if request.expires_at < now:
                    expired_requests.append(request_id)
                    # Remove the download file if it exists
                    if request.download_path and request.download_path.exists():
                        try:
                            request.download_path.unlink()
                            debug(f"Removed expired download file: {request.download_path}")
                        except Exception as e:
                            warning(f"Failed to remove expired download file: {e}")
            # Remove expired requests
            for request_id in expired_requests:
                self._download_requests.pop(request_id, None)
            if expired_requests:
                info(f"Cleaned up {len(expired_requests)} expired download requests")

    def _process_compression_queue(self) -> None:
        """Process files pending compression"""
        if not self.auto_compression or not self._compression_service:
            return
        
        with self._lock:
            if not self._index:
                return

            pending_files = [
                metadata for metadata in self._index.files.values()
                if metadata.status == FileStatus.PENDING_COMPRESSION
            ]

        updated = False
        for metadata in pending_files:
            try:
                if self._compression_service and metadata.file_path.exists():
                    # Attempt compression using the compression service
                    # This would depend on the specific compression service API
                    # For now, we'll just update the status
                    metadata.status = FileStatus.COMPRESSED
                    updated = True
                    debug(f"Processed compression for: {metadata.file_path}")

            except Exception as e:
                error(f"Error processing compression for {metadata.file_path}: {e}")
                metadata.status = FileStatus.ERROR
                updated = True

        if updated:
            self._save_index()
    def mark_for_compression(self, file_paths: List[str]) -> None:
        """Mark files for background compression"""
        with self._lock:
            if not self._index:
                return
            
            for file_path in file_paths:
                if file_path in self._index.files:
                    metadata = self._index.files[file_path]
                    if metadata.status == FileStatus.ACTIVE:
                        metadata.status = FileStatus.PENDING_COMPRESSION
            
            self._save_index()

    def _start_watchers(self) -> None:
        """Start watchdog observers for managed directories"""
        if not WATCHDOG_AVAILABLE:
            return

        self._observer = Observer()
        directories = [
            (self.raw_dir, DataCategory.RAW),
            (self.processed_dir, DataCategory.PROCESSED),
            (self.experiments_dir, DataCategory.EXPERIMENTS),
            (self.logs_dir, DataCategory.LOGS),
        ]
        for directory, category in directories:
            if directory.exists():
                handler = _DirectoryEventHandler(self, category)
                self._observer.schedule(handler, str(directory), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def _stop_watchers(self) -> None:
        """Stop watchdog observers"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def _process_changed_file(self, file_path: Path, category: DataCategory) -> None:
        """Update index for a single changed file."""
        with self._lock:
            if not self._index or not file_path.exists():
                return
            file_key = str(file_path.resolve())
            if self._should_update_file_metadata(file_path, file_key):
                metadata = self._create_file_metadata(file_path, category)
                if metadata:
                    self._index.files[file_key] = metadata
                    self._index.dir_mtimes[str(file_path.parent.resolve())] = file_path.parent.stat().st_mtime
                    self._save_index()
    def shutdown(self) -> None:
        """Shutdown DataManager and background tasks"""
        self._shutdown_event.set()
        # cancel background tasks and shutdown only dedicated pools (skip shared GENERAL pool)
        for pool, fut in self._background_tasks:
            if not fut.done():
                fut.cancel()
            # skip shutting down shared GENERAL pool
            try:
                pool_type = getattr(pool, 'pool_type', None)
            except Exception:
                pool_type = None
            if pool_type is not ThreadPoolType.GENERAL:
                pool.shutdown()
        info("DataManager shutdown complete")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown()


# Global instance management
_data_manager_instance: Optional[DataManager] = None
_data_manager_lock = threading.Lock()


def get_data_manager(base_output_dir: Optional[Path] = None) -> Optional[DataManager]:
    """
    Get the global DataManager instance.
    
    Args:
        base_output_dir: Base directory for data storage (used only on first call)
    
    Returns:
        DataManager instance or None if initialization fails
    """
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
    """Shutdown the global DataManager instance"""
    global _data_manager_instance
    
    with _data_manager_lock:
        if _data_manager_instance:
            _data_manager_instance.shutdown()
            _data_manager_instance = None
