from __future__ import annotations

import os
import json
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from utils.log_service import error

if TYPE_CHECKING:
    from .data_manager import DataManager

try:
    from watchdog.events import FileSystemEventHandler, FileSystemEvent

    WATCHDOG_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    FileSystemEventHandler = object  # type: ignore
    FileSystemEvent = object  # type: ignore
    WATCHDOG_AVAILABLE = False

DirectoryEventHandler: Optional[type] = None


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
        data = asdict(self)
        data["file_path"] = str(self.file_path)
        if self.compressed_path:
            data["compressed_path"] = str(self.compressed_path)
        data["created_at"] = self.created_at.isoformat()
        data["modified_at"] = self.modified_at.isoformat()
        data["category"] = self.category.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileMetadata":
        data = data.copy()
        data["file_path"] = Path(data["file_path"])
        if data.get("compressed_path"):
            data["compressed_path"] = Path(data["compressed_path"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["modified_at"] = datetime.fromisoformat(data["modified_at"])
        data["category"] = DataCategory(data["category"])
        data["status"] = FileStatus(data["status"])
        return cls(**data)


@dataclass
class DataIndex:
    """Index of all managed data files"""

    files: Dict[str, FileMetadata]
    last_updated: datetime
    dir_mtimes: Dict[str, float] = field(default_factory=dict)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": {p: m.to_dict() for p, m in self.files.items()},
            "last_updated": self.last_updated.isoformat(),
            "dir_mtimes": self.dir_mtimes,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataIndex":
        files = {
            p: FileMetadata.from_dict(md) for p, md in data.get("files", {}).items()
        }
        return cls(
            files=files,
            last_updated=datetime.fromisoformat(data["last_updated"]),
            dir_mtimes=data.get("dir_mtimes", {}),
            version=data.get("version", "1.0"),
        )


@dataclass
class DownloadRequest:
    """Request for packaging and downloading data files"""

    request_id: str
    requested_files: List[str]
    format: str
    status: str
    created_at: datetime
    expires_at: datetime
    download_path: Optional[Path] = None
    error_message: Optional[str] = None
    processed_files: int = 0
    total_files: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["expires_at"] = self.expires_at.isoformat()
        if self.download_path:
            data["download_path"] = str(self.download_path)
        return data


if WATCHDOG_AVAILABLE:

    class _DirectoryEventHandler(FileSystemEventHandler):
        """Handle filesystem events to update the index incrementally."""

        def __init__(self, manager: "DataManager", category: DataCategory) -> None:
            super().__init__()
            self._manager = manager
            self._category = category

        def on_created(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._manager._process_changed_file(
                    Path(event.src_path), self._category
                )

        def on_modified(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._manager._process_changed_file(
                    Path(event.src_path), self._category
                )

    DirectoryEventHandler = _DirectoryEventHandler


class Indexer:
    """Provides indexing operations for DataManager."""

    def __init__(self, manager: "DataManager") -> None:
        self._manager = manager

    # index loading and saving
    def load_index(self) -> None:
        index_file = self._manager.index_file
        try:
            if index_file.exists():
                with open(index_file, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                self._manager._index = DataIndex.from_dict(index_data)
            else:
                self._manager._index = DataIndex(files={}, last_updated=datetime.now())
        except Exception as e:
            error(f"Failed to load data index: {e}")
            self._manager._index = DataIndex(files={}, last_updated=datetime.now())

    def save_index(self) -> None:
        if not self._manager._index:
            return
        try:
            self._manager._index.last_updated = datetime.now()
            with open(self._manager.index_file, "w", encoding="utf-8") as f:
                json.dump(self._manager._index.to_dict(), f, indent=2)
        except Exception as e:
            error(f"Failed to save data index: {e}")

    def scan_directories(self) -> int:
        mgr = self._manager
        if not mgr._index:
            return 0
        files_processed = 0
        dirs: List[Tuple[Path, DataCategory]] = [
            (mgr.raw_dir, DataCategory.RAW),
            (mgr.processed_dir, DataCategory.PROCESSED),
            (mgr.experiments_dir, DataCategory.EXPERIMENTS),
            (mgr.logs_dir, DataCategory.LOGS),
        ]
        for directory, category in dirs:
            if directory.exists():
                dir_key = str(directory.resolve())
                current_mtime = directory.stat().st_mtime
                last_mtime = mgr._index.dir_mtimes.get(dir_key)
                if last_mtime is not None and current_mtime <= last_mtime:
                    continue
                files_processed += self._scan_directory(directory, category)
                mgr._index.dir_mtimes[dir_key] = current_mtime
        if files_processed > 0:
            self.save_index()
        return files_processed

    def _scan_directory(self, directory: Path, category: DataCategory) -> int:
        files_processed = 0
        stack = [directory]
        mgr = self._manager
        while stack:
            current = stack.pop()
            try:
                for entry in os.scandir(current):
                    if entry.name.startswith("."):
                        continue
                    path = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(path)
                    elif entry.is_file(follow_symlinks=False):
                        file_key = str(path.resolve())
                        if self._should_update_file_metadata(path, file_key):
                            metadata = self._create_file_metadata(path, category)
                            if metadata and mgr._index:
                                mgr._index.files[file_key] = metadata
                                files_processed += 1
            except Exception as e:  # pragma: no cover - best effort
                error(f"Error scanning {current}: {e}")
        return files_processed

    def _should_update_file_metadata(self, file_path: Path, file_key: str) -> bool:
        idx = self._manager._index
        if not idx or file_key not in idx.files:
            return True
        try:
            existing = idx.files[file_key]
            current_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            return current_mtime > existing.modified_at
        except (OSError, ValueError):
            return True

    def _create_file_metadata(
        self, file_path: Path, category: DataCategory
    ) -> Optional[FileMetadata]:
        try:
            stat = file_path.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime)
            modified_at = datetime.fromtimestamp(stat.st_mtime)
            sensor_id = self._extract_sensor_id(file_path)
            experiment_id = self._extract_experiment_id(file_path)
            status = FileStatus.ACTIVE
            if file_path.suffix in [".gz", ".bz2", ".xz", ".zip"]:
                status = FileStatus.COMPRESSED
            return FileMetadata(
                file_path=file_path,
                category=category,
                status=status,
                size_bytes=stat.st_size,
                created_at=created_at,
                modified_at=modified_at,
                sensor_id=sensor_id,
                experiment_id=experiment_id,
            )
        except Exception as e:  # pragma: no cover - best effort
            error(f"Error creating metadata for {file_path}: {e}")
            return None

    def _extract_sensor_id(self, file_path: Path) -> Optional[str]:
        stem = file_path.stem
        if stem and not stem.startswith("experiment_"):
            while stem.endswith((".gz", ".bz2", ".xz", ".zip")):
                stem = Path(stem).stem
            return stem
        return None

    def _extract_experiment_id(self, file_path: Path) -> Optional[str]:
        for part in file_path.parts:
            if part.startswith("experiment_"):
                exp_id = part[len("experiment_") :]
                while exp_id.endswith((".gz", ".bz2", ".xz", ".zip")):
                    exp_id = Path(exp_id).stem
                return exp_id or None
        if file_path.stem.startswith("experiment_"):
            suffix = file_path.stem[len("experiment_") :]
            while suffix.endswith((".gz", ".bz2", ".xz", ".zip")):
                suffix = Path(suffix).stem
            return suffix or None
        return None

    def list_files(
        self,
        category: Optional[DataCategory] = None,
        sensor_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        status: Optional[FileStatus] = None,
        tags: Optional[List[str]] = None,
    ) -> List[FileMetadata]:
        idx = self._manager._index
        if not idx:
            return []
        results = []
        for metadata in idx.files.values():
            if category and metadata.category != category:
                continue
            if sensor_id and metadata.sensor_id != sensor_id:
                continue
            if experiment_id and metadata.experiment_id != experiment_id:
                continue
            if status and metadata.status != status:
                continue
            if tags and (
                not metadata.tags or not all(tag in metadata.tags for tag in tags)
            ):
                continue
            results.append(metadata)
        results.sort(key=lambda x: x.modified_at, reverse=True)
        return results

    def get_data_overview(self) -> Dict[str, Any]:
        idx = self._manager._index
        if not idx:
            return {}
        overview = {
            "total_files": len(idx.files),
            "last_updated": idx.last_updated.isoformat(),
            "categories": {},
            "status_summary": {},
            "total_size_bytes": 0,
            "sensors": set(),
            "experiments": set(),
        }
        for metadata in idx.files.values():
            cat_name = metadata.category.value
            if cat_name not in overview["categories"]:
                overview["categories"][cat_name] = {"count": 0, "size_bytes": 0}
            overview["categories"][cat_name]["count"] += 1
            overview["categories"][cat_name]["size_bytes"] += metadata.size_bytes
            status_name = metadata.status.value
            overview["status_summary"][status_name] = (
                overview["status_summary"].get(status_name, 0) + 1
            )
            overview["total_size_bytes"] += metadata.size_bytes
            if metadata.sensor_id:
                overview["sensors"].add(metadata.sensor_id)
            if metadata.experiment_id:
                overview["experiments"].add(metadata.experiment_id)
        overview["sensors"] = list(overview["sensors"])
        overview["experiments"] = list(overview["experiments"])
        return overview
